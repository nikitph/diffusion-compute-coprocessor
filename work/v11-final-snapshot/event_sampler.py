"""Auditable block sampler with dense result insertion and event-driven rewinds."""
import math,time,torch
MASK=156895;EOS=156892;DELETE=156930;SPLIT=156931
class State:
 def __init__(self,ids,length,block):
  self.P=len(ids);self.B=block;self.limit=self.P+length;N=math.ceil(self.limit/block)*block
  self.x=torch.full((1,N),MASK,device='cuda',dtype=torch.long);self.x[0,:self.P]=torch.tensor(ids,device='cuda')
  self.fixed=torch.zeros_like(self.x,dtype=torch.bool);self.fixed[:,:self.P]=True
  self.visible=torch.ones_like(self.fixed);self.token_conf=self.fixed.float();self.stamps=torch.full_like(self.x,-1)
  self.locks=[];self.events=[];self.step=0;self.started=self.P;self.rewind=None;self.pending=False;self.remasked=set();self.native_edit=False
  self.prompt_length=self.P;self.block_start=0;self.block_end=0;self.block_final=False;self.draft=None;self.confidence=None
 def assert_locks(self):
  for lo,ids,label in self.locks:assert self.x[0,lo:lo+len(ids)].tolist()==ids,('lock violation',label)
 def lock(self,lo,ids,label='result'):
  self.x[0,lo:lo+len(ids)]=torch.tensor(ids,device='cuda');self.fixed[0,lo:lo+len(ids)]=True;self.visible[0,lo:lo+len(ids)]=True
  self.locks.append((lo,list(ids),label))
 def splice(self,lo,hi,ids,label='result'):
  """Replace only a declared result placeholder; preserve every other prompt token."""
  assert not any(not (p+len(v)<=lo or p>=hi) for p,v,_ in self.locks)
  delta=len(ids)-(hi-lo);oldP=self.P
  for attr,fill in [('x',MASK),('fixed',True),('visible',True),('stamps',-1),('token_conf',1.)]:
   arr=getattr(self,attr);mid=torch.full((1,len(ids)),fill,device='cuda',dtype=arr.dtype)
   if attr=='x':mid[0]=torch.tensor(ids,device='cuda')
   setattr(self,attr,torch.cat([arr[:,:lo],mid,arr[:,hi:]],dim=1))
  self.locks=[(p+delta if p>=hi else p,v,l) for p,v,l in self.locks]
  self.P+=delta;self.prompt_length=self.P;self.limit+=delta;self.started+=delta
  self.block_end+=delta;self.block_start=max(0,self.block_start+delta)
  self.locks.append((lo,list(ids),label))
  N=math.ceil(self.limit/self.B)*self.B
  for attr,fill in [('x',MASK),('fixed',False),('visible',True),('stamps',-1),('token_conf',0.)]:
   arr=getattr(self,attr)
   if arr.shape[1]<N:arr=torch.cat([arr,torch.full((1,N-arr.shape[1]),fill,device='cuda',dtype=arr.dtype)],dim=1)
   setattr(self,attr,arr[:,:N])
  self.rewind=self.block_start//self.B
  self.events.append({'type':'splice','step':self.step,'position':lo,'old_width':hi-lo,'new_width':len(ids),'old_prompt':oldP,'new_prompt':self.P})
 def arrival(self,lo,hi,ids,result_id='r1',submitted=-1,remask=True,editing=False):
  # Measure before the intervention, not after re-masking artificially creates masks.
  ownlo=lo//self.B*self.B;ownhi=min(ownlo+self.B,self.x.shape[1])
  eos_positions=(self.x[0,ownlo:ownhi]==EOS).nonzero().flatten().tolist()
  content_hi=ownlo+eos_positions[0] if eos_positions else ownhi
  before_eos=bool(((self.x[0,ownlo:content_hi]==MASK)&~self.fixed[0,ownlo:content_hi]).any()) and ownlo<self.started
  midblock=bool(((self.x[0,ownlo:ownhi]==MASK)&~self.fixed[0,ownlo:ownhi]).any()) and ownlo<self.started
  self.splice(lo,hi,ids,result_id)
  affected=(torch.arange(self.x.shape[1],device='cuda')>=self.P)&(torch.arange(self.x.shape[1],device='cuda')<self.started)&~self.fixed[0]&(self.stamps[0]>submitted)
  n=int(affected.sum());positions=affected.nonzero().flatten().tolist()
  if (remask or editing) and result_id not in self.remasked and len(self.remasked)<2:
   self.remasked.add(result_id)
   if editing:self.native_edit=True
   else:self.x[0,affected]=MASK;self.stamps[0,affected]=-1
   if positions:self.rewind=min(positions)//self.B
   self.events.append({'type':'native_edit_revisit' if editing else 'remask','result':result_id,'step':self.step,'count':n,'positions':positions,'attention_diagnostic':'unavailable in SDPA path'})
  self.events.append({'type':'arrival','result':result_id,'step':self.step,'midblock':midblock,'midblock_before_eos':before_eos,'remasked_tokens':n if remask else 0})
  self.pending=False;self.assert_locks()

@torch.inference_mode()
def decode(model,ids,length=192,block=32,hook=None,holes=None,max_steps=512):
 s=State(ids,length,block)
 for lo,hi in holes or []:s.visible[0,lo:hi]=False
 b=s.P//block;local=0;resolved=None;calls=0;torch.cuda.synchronize();start=time.perf_counter()
 while b*block<s.limit and calls<max_steps:
  lo=b*block;hi=min(lo+block,s.x.shape[1]);s.block_start=lo;s.block_end=hi;s.started=max(s.started,hi);s.step=calls;s.block_final=False
  active=(s.x[0,lo:hi]==MASK)&~s.fixed[0,lo:hi]
  positions=torch.arange(hi,device='cuda');att=(positions[:,None]//block>=positions[None,:]//block)&s.visible[0,None,:hi]
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
    s.x[0,lo+i:lo+j]=torch.tensor(vals,device='cuda');s.stamps[0,lo+i:lo+j]=calls;i=j
  s.draft=s.x[:,:hi].clone();s.draft[0,lo:hi]=torch.where(s.x[0,lo:hi]==MASK,prop,s.x[0,lo:hi]);s.token_conf[0,lo:hi]=torch.where(s.fixed[0,lo:hi],s.token_conf[0,lo:hi],probs.gather(-1,s.draft[0,lo:hi,None]).squeeze(-1));s.confidence=s.token_conf[:,:hi].clone()
  if hook:hook(s)
  calls+=1;s.assert_locks();del logits,probs
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
   if s.rewind is not None:b=s.rewind;s.rewind=None;local=0;resolved=None;continue
   eos=bool((s.x[0,s.P:hi]==EOS).any())
   if eos and not s.pending:break
   if s.pending and (eos or hi>=s.limit):
    # Keep taking model steps so delayed events can land; no bounded hold expiry.
    local=0;resolved=None;continue
   b+=1;local=0;resolved=None
 torch.cuda.synchronize();output=s.x[0,s.P:s.limit].tolist()
 if EOS in output:output=output[:output.index(EOS)+1]
 return output,{'seconds':time.perf_counter()-start,'forward_calls':calls,'events':s.events,'lock_violations':0,'remask_count':len(s.remasked),'pending_at_end':s.pending,'step_budget_exhausted':calls>=max_steps,'residual_masks':output.count(MASK)},s
