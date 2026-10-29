"""Auditable block sampler with dense result insertion and event-driven rewinds."""
import math,time,torch,hashlib
DEVICE="cuda" if torch.cuda.is_available() else "cpu"
def sync():
 if DEVICE=="cuda":torch.cuda.synchronize()
MASK=156895;EOS=156892;DELETE=156930;SPLIT=156931
class State:
 def __init__(self,ids,length,block):
  self.P=len(ids);self.B=block;self.limit=self.P+length;N=math.ceil(self.limit/block)*block
  self.x=torch.full((1,N),MASK,device=DEVICE,dtype=torch.long);self.x[0,:self.P]=torch.tensor(ids,device=DEVICE)
  self.fixed=torch.zeros_like(self.x,dtype=torch.bool);self.fixed[:,:self.P]=True
  self.visible=torch.ones_like(self.fixed);self.token_conf=self.fixed.float();self.stamps=torch.full_like(self.x,-1)
  self.locks=[];self.events=[];self.step=0;self.started=self.P;self.rewind=None;self.pending=False;self.remasked=set();self.native_edit=False
  self.wait_seconds=0.;self.local=0;self.resume_cursor=None;self.answer_start=self.P
  self.prompt_length=self.P;self.block_start=0;self.block_end=0;self.block_final=False;self.draft=None;self.confidence=None
 def assert_locks(self):
  for lo,ids,label in self.locks:assert self.x[0,lo:lo+len(ids)].tolist()==ids,('lock violation',label)
 def lock(self,lo,ids,label='result'):
  self.x[0,lo:lo+len(ids)]=torch.tensor(ids,device=DEVICE);self.fixed[0,lo:lo+len(ids)]=True;self.visible[0,lo:lo+len(ids)]=True
  self.locks.append((lo,list(ids),label))
 def splice(self,lo,hi,ids,label='result'):
  """Replace only a declared result placeholder; preserve every other prompt token."""
  assert not any(not (p+len(v)<=lo or p>=hi) for p,v,_ in self.locks)
  delta=len(ids)-(hi-lo);oldP=self.P
  for attr,fill in [('x',MASK),('fixed',True),('visible',True),('stamps',-1),('token_conf',1.)]:
   arr=getattr(self,attr);mid=torch.full((1,len(ids)),fill,device=DEVICE,dtype=arr.dtype)
   if attr=='x':mid[0]=torch.tensor(ids,device=DEVICE)
   setattr(self,attr,torch.cat([arr[:,:lo],mid,arr[:,hi:]],dim=1))
  self.locks=[(p+delta if p>=hi else p,v,l) for p,v,l in self.locks]
  self.P+=delta;self.prompt_length=self.P;self.limit+=delta;self.started+=delta
  if self.answer_start>=hi:self.answer_start+=delta
  self.block_end+=delta;self.block_start=max(0,self.block_start+delta)
  self.locks.append((lo,list(ids),label))
  N=math.ceil(self.limit/self.B)*self.B
  for attr,fill in [('x',MASK),('fixed',False),('visible',True),('stamps',-1),('token_conf',0.)]:
   arr=getattr(self,attr)
   if arr.shape[1]<N:arr=torch.cat([arr,torch.full((1,N-arr.shape[1]),fill,device=DEVICE,dtype=arr.dtype)],dim=1)
   setattr(self,attr,arr[:,:N])
  self.rewind=self.block_start//self.B
  self.events.append({'type':'splice','step':self.step,'position':lo,'old_width':hi-lo,'new_width':len(ids),'old_prompt':oldP,'new_prompt':self.P})
 def snapshot(self):
  h=hashlib.sha256()
  for attr in ('x','fixed','visible','stamps','token_conf'):
   h.update(getattr(self,attr).cpu().contiguous().numpy().tobytes())
  h.update(repr((self.step,self.local,self.P,self.limit,self.block_start,self.block_end,self.started,self.rewind)).encode())
  return h.hexdigest()
 def pause(self,operation,delay_seconds=0.,label='result'):
  sync();before=self.snapshot();t=time.perf_counter();wall=time.time()
  result=operation()
  remaining=delay_seconds-(time.perf_counter()-t)
  if remaining>0:time.sleep(remaining)
  sync();elapsed=time.perf_counter()-t;after=self.snapshot()
  assert before==after,'pause mutated canvas or schedule'
  self.wait_seconds+=elapsed
  self.events.append(dict(type='pause',result=label,dispatch_step=self.step,lock_step=self.step,local_step=self.local,dispatch_wall_time=wall,wait_seconds=elapsed,requested_delay_seconds=delay_seconds,state_before=before,state_after=after,unchanged=True))
  return result
 def wait_arrival(self,lo,hi,ids,label='result',generated=False):
  ownlo=lo//self.B*self.B;ownhi=min(ownlo+self.B,self.x.shape[1])
  ep=(self.x[0,ownlo:ownhi]==EOS).nonzero().flatten()
  end=ownlo+int(ep[0]) if len(ep) else ownhi
  mid=bool(((self.x[0,ownlo:ownhi]==MASK)&~self.fixed[0,ownlo:ownhi]).any()) and ownlo<self.started
  mide=bool(((self.x[0,ownlo:end]==MASK)&~self.fixed[0,ownlo:end]).any()) and ownlo<self.started
  oldP=self.P;oldanswer=self.answer_start;oldstart=self.block_start;oldlocal=self.local;delta=len(ids)-(hi-lo)
  self.splice(lo,hi,ids,label)
  if generated:
   self.P=oldP;self.prompt_length=oldP
   self.answer_start=oldanswer+(delta if hi<=oldanswer else 0)
   mapped=oldstart+(delta if hi<=oldstart else 0)
  else:
   self.answer_start=self.P;mapped=max(0,oldstart+delta)
  self.rewind=None;self.resume_cursor=mapped//self.B;self.native_edit=True;self.pending=False
  self.events.append(dict(type='arrival',result=label,step=self.step,local_step=oldlocal,midblock=mid,midblock_before_eos=mide,remasked_tokens=0,preserved_schedule=True,lock_state=self.snapshot()))
  self.assert_locks()
 def arrival(self,lo,hi,ids,result_id='r1',submitted=-1,remask=True,editing=False):
  # Measure before the intervention, not after re-masking artificially creates masks.
  ownlo=lo//self.B*self.B;ownhi=min(ownlo+self.B,self.x.shape[1])
  eos_positions=(self.x[0,ownlo:ownhi]==EOS).nonzero().flatten().tolist()
  content_hi=ownlo+eos_positions[0] if eos_positions else ownhi
  before_eos=bool(((self.x[0,ownlo:content_hi]==MASK)&~self.fixed[0,ownlo:content_hi]).any()) and ownlo<self.started
  midblock=bool(((self.x[0,ownlo:ownhi]==MASK)&~self.fixed[0,ownlo:ownhi]).any()) and ownlo<self.started
  self.splice(lo,hi,ids,result_id)
  affected=(torch.arange(self.x.shape[1],device=DEVICE)>=self.P)&(torch.arange(self.x.shape[1],device=DEVICE)<self.started)&~self.fixed[0]&(self.stamps[0]>submitted)
  n=int(affected.sum());positions=affected.nonzero().flatten().tolist()
  if (remask or editing) and result_id not in self.remasked and len(self.remasked)<2:
   self.remasked.add(result_id)
   if editing:self.native_edit=True
   else:self.x[0,affected]=MASK;self.stamps[0,affected]=-1
   if positions:self.rewind=min(self.rewind,min(positions)//self.B) if self.rewind is not None else min(positions)//self.B
   self.events.append({'type':'native_edit_revisit' if editing else 'remask','result':result_id,'step':self.step,'count':n,'positions':positions,'attention_diagnostic':'unavailable in SDPA path'})
  self.events.append({'type':'arrival','result':result_id,'step':self.step,'midblock':midblock,'midblock_before_eos':before_eos,'remasked_tokens':n if remask else 0})
  self.pending=False;self.assert_locks()

@torch.inference_mode()
def decode(model,ids,length=192,block=32,hook=None,holes=None,max_steps=512):
 s=State(ids,length,block)
 for lo,hi in holes or []:s.visible[0,lo:hi]=False
 b=s.P//block;local=0;resolved=None;calls=0;sync();start=time.perf_counter()
 while b*block<s.limit and calls<max_steps:
  lo=b*block;hi=min(lo+block,s.x.shape[1]);s.block_start=lo;s.block_end=hi;s.started=max(s.started,hi);s.step=calls;s.local=local;s.block_final=False
  active=(s.x[0,lo:hi]==MASK)&~s.fixed[0,lo:hi]
  positions=torch.arange(hi,device=DEVICE);att=(positions[:,None]//block>=positions[None,:]//block)&s.visible[0,None,:hi]
  logits=model(s.x[:,:hi],attention_mask=torch.where(att[None,None],0.,-torch.inf).to(torch.bfloat16),position_ids=positions[None]).logits[0,lo:hi].float()
  logits[:,MASK]=-torch.inf
  if not s.native_edit or local>=9:logits[:,[DELETE,SPLIT]]=-torch.inf
  probs=logits.softmax(-1);prop=logits.argmax(-1);conf=probs.gather(-1,prop[:,None]).squeeze(-1)
  before=s.x[0,lo:hi].clone();fill=active&(conf>.5);need=max(1,math.ceil(int(active.sum())/max(1,8-local)))
  if int(fill.sum())<need and bool(active.any()):fill[torch.where(active,conf,-torch.inf).topk(min(need,int(active.sum()))).indices]=True
  if local>=7:fill=active
  edits=~active&~s.fixed[0,lo:hi]&(before!=prop)
  change=fill|edits;s.x[0,lo:hi][change]=prop[change];s.stamps[0,lo:hi][change]=calls
  if s.native_edit and bool(((s.x[0,lo:hi]==DELETE)|(s.x[0,lo:hi]==SPLIT)).any()):
   s.events.append({'type':'edit_ops','step':calls,'delete':int((s.x[0,lo:hi]==DELETE).sum()),'split':int((s.x[0,lo:hi]==SPLIT).sum())})
   # Apply upstream edit semantics independently in each unlocked run, never across a lock.
   free=(~s.fixed[0,lo:hi]).tolist();i=0
   while i<len(free):
    if not free[i]:i+=1;continue
    j=i+1
    while j<len(free) and free[j]:j+=1
    vals,_=model._apply_edit_operations_with_tracking(s.x[0,lo+i:lo+j].tolist(),before[i:j].tolist(),[True]*(j-i),MASK,j-i,DELETE,SPLIT)
    s.x[0,lo+i:lo+j]=torch.tensor(vals,device=DEVICE);s.stamps[0,lo+i:lo+j]=calls;i=j
  s.draft=s.x[:,:hi].clone();s.draft[0,lo:hi]=torch.where(s.x[0,lo:hi]==MASK,prop,s.x[0,lo:hi]);s.token_conf[0,lo:hi]=torch.where(s.fixed[0,lo:hi],s.token_conf[0,lo:hi],probs.gather(-1,s.draft[0,lo:hi,None]).squeeze(-1));s.confidence=s.token_conf[:,:hi].clone()
  if hook:hook(s)
  calls+=1;s.assert_locks();del logits,probs
  if s.resume_cursor is not None:
   b=s.resume_cursor;s.resume_cursor=None;local+=1;resolved=None;continue
  if s.rewind is not None:b=s.rewind;s.rewind=None;local=0;resolved=None;continue
  local+=1;active=(s.x[0,lo:hi]==MASK)&~s.fixed[0,lo:hi]
  if not bool(active.any()):
   if resolved is None:resolved=local
  else:resolved=None
  done=(resolved is not None and local-resolved>=2) or local>=10
  if done:
   s.block_final=True;s.draft=s.x[:,:hi].clone()
   if hook:hook(s)
   s.assert_locks()
   if s.resume_cursor is not None:
    b=s.resume_cursor;s.resume_cursor=None;resolved=None;continue
   if s.rewind is not None:b=s.rewind;s.rewind=None;local=0;resolved=None;continue
   eos=bool((s.x[0,s.answer_start:hi]==EOS).any())
   end=s.limit
   ep=(s.x[0,s.answer_start:hi]==EOS).nonzero().flatten()
   if len(ep):end=s.answer_start+int(ep[0])
   holes=((s.x[0,s.P:min(hi,end)]==MASK)&~s.fixed[0,s.P:min(hi,end)]).nonzero().flatten()
   if len(holes):
    target=(s.P+int(holes[0]))//block
    s.events.append({'type':'completion_repair','step':s.step,'block':target})
    b=target;local=0;resolved=None;continue
   if eos and not s.pending:break
   if s.pending and (eos or hi>=s.limit):
    # Keep taking model steps so delayed events can land; no bounded hold expiry.
    local=0;resolved=None;continue
   b+=1;local=0;resolved=None
 sync();output=s.x[0,s.answer_start:s.limit].tolist()
 if EOS in output:output=output[:output.index(EOS)+1]
 return output,{'seconds':time.perf_counter()-start,'wait_seconds':s.wait_seconds,'denoising_seconds':time.perf_counter()-start-s.wait_seconds,'forward_calls':calls,'events':s.events,'lock_violations':0,'remask_count':len(s.remasked),'pending_at_end':s.pending,'step_budget_exhausted':calls>=max_steps,'residual_masks':output.count(MASK)},s
