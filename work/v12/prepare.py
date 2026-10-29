from pathlib import Path
p=Path('outputs/v1.2-pilot/event_sampler.py');s=p.read_text()
s=s.replace('import math,time,torch','import math,time,torch,hashlib\nDEVICE="cuda" if torch.cuda.is_available() else "cpu"\ndef sync():\n if DEVICE=="cuda":torch.cuda.synchronize()')
s=s.replace("device='cuda'","device=DEVICE").replace('torch.cuda.synchronize();','sync();')
s=s.replace('self.prompt_length=self.P;self.block_start', 'self.wait_seconds=0.;self.local=0;self.resume_cursor=None;self.answer_start=self.P\n  self.prompt_length=self.P;self.block_start')
s=s.replace("if positions:self.rewind=min(positions)//self.B", "if positions:self.rewind=min(self.rewind,min(positions)//self.B) if self.rewind is not None else min(positions)//self.B")
# Completion guard handles holes shifted to blocks before the current cursor.
s=s.replace('eos=bool((s.x[0,s.P:hi]==EOS).any())', '''eos=bool((s.x[0,s.answer_start:hi]==EOS).any())
   end=s.limit
   ep=(s.x[0,s.answer_start:hi]==EOS).nonzero().flatten()
   if len(ep):end=s.answer_start+int(ep[0])
   holes=((s.x[0,s.P:min(hi,end)]==MASK)&~s.fixed[0,s.P:min(hi,end)]).nonzero().flatten()
   if len(holes):
    target=(s.P+int(holes[0]))//block
    s.events.append({'type':'completion_repair','step':s.step,'block':target})
    b=target;local=0;resolved=None;continue''')
s=s.replace('s.step=calls;s.block_final=False','s.step=calls;s.local=local;s.block_final=False')
s=s.replace("if s.rewind is not None:b=s.rewind", "if s.resume_cursor is not None:\n   b=s.resume_cursor;s.resume_cursor=None;local+=1;resolved=None;continue\n  if s.rewind is not None:b=s.rewind",1)
s=s.replace("output=s.x[0,s.P:s.limit].tolist()", "output=s.x[0,s.answer_start:s.limit].tolist()")
s=s.replace("'seconds':time.perf_counter()-start,", "'seconds':time.perf_counter()-start,'wait_seconds':s.wait_seconds,'denoising_seconds':time.perf_counter()-start-s.wait_seconds,")
# Add pause with exact state/schedule evidence and wait-specific insertion.
needle=' def arrival(self,lo,hi,ids,'
idx=s.index(needle)
s=s[:idx]+''' def snapshot(self):
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
''' +s[idx:]
p.write_text(s)
