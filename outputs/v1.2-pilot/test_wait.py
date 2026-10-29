"""CPU/GPU invariant tests; no trained model or prompt tuning."""
import json,time,torch
from event_sampler import State,decode,MASK,DELETE,SPLIT,EOS,DEVICE
class Constant:
 def __call__(self,x,**kw):
  logits=torch.full((*x.shape,157184),-20.,device=DEVICE)
  logits[:,:,123]=20
  return type('Output',(),{'logits':logits})()
 def _apply_edit_operations_with_tracking(self,x,*args):return x,None

def check():
 s=State([10,11,12],64,32);s.step=4;s.local=3;s.started=32;s.block_end=32
 s.x[0,5]=77;s.stamps[0,5]=3
 before=s.snapshot();r=s.pause(lambda:99,.01)
 assert r==99 and s.snapshot()==before and s.step==4 and s.local==3
 assert s.wait_seconds>=.01
 s.wait_arrival(2,2,[91,92]);assert s.local==3 and s.rewind is None
 assert s.x[0,:5].tolist()==[10,11,91,92,12];s.assert_locks()
 s=State([1,2,3],64,32);s.started=32;s.block_end=32;s.step=1;s.local=2
 s.x[0,3:32]=123;s.x[0,7]=MASK;s.x[0,20]=EOS
 old=s.x[0,12:32].tolist();s.wait_arrival(12,12,[77,78,79],generated=True)
 assert s.P==3 and s.x[0,15:35].tolist()==old and s.local==2 and s.resume_cursor==0
 s.assert_locks()
 # Old decoder accepted EOS in block 1 while a previous block retained a hole.
 once=False
 def hole(st):
  nonlocal once
  if st.block_start==32 and not once:
   st.x[0,4]=MASK;st.x[0,40]=EOS;once=True
 out,m,st=decode(Constant(),[1,2,3],length=64,hook=hole)
 assert once and m['residual_masks']==0 and any(e['type']=='completion_repair' for e in m['events'])
 # Waiting does not turn wall-clock delay into denoising steps or canvas changes.
 digests=[];outputs=[]
 for delay in (0,.01,.02):
  done=False
  def hook(st):
   nonlocal done
   if done:return
   st.pause(lambda:None,delay)
   digests.append(st.events[-1]['state_after'])
   st.wait_arrival(2,2,[91,92]);done=True
  out,m,st=decode(Constant(),[1,2,3],length=32,hook=hook)
  assert m['residual_masks']==0 and m['remask_count']==0
  assert m['events'][0]['dispatch_step']==m['events'][0]['lock_step']==0
  outputs.append(out)
 assert len(set(digests))==1 and outputs[0]==outputs[1]==outputs[2]
 return dict(passed=True,pause_state_exact=True,schedule_preserved=True,continuation_preserved=True,earlier_hole_repaired=True,delay_states_identical=True)
if __name__=='__main__':print(json.dumps(check()))
