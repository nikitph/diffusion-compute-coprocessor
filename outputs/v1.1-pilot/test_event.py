import torch,json
from event_sampler import State,decode,MASK,DELETE,SPLIT
class Adversarial:
 def __call__(self,x,**kwargs):
  y=torch.full((*x.shape,157184),-20.,device='cuda');y[:,:,DELETE]=100;y[:,:,SPLIT]=99;y[:,:,MASK]=98;y[:,:,123]=90
  return type('Output',(),{'logits':y})()
def check():
 s=State([10,11,12,13],32,32);s.step=40;s.started=32;s.x[0,4:20]=55;s.stamps[0,4:20]=2;s.lock(8,[77,78],'prior')
 s.arrival(3,3,[91,92],submitted=0)
 assert s.x[0,:6].tolist()==[10,11,12,91,92,13]
 assert s.x[0,10:12].tolist()==[77,78]
 assert int((s.x[0,6:22]==MASK).sum())==14
 s.assert_locks();assert len(s.remasked)==1
 done=False
 def hook(st):
  nonlocal done
  if not done:
   st.pending=True
   if st.step==40:st.arrival(2,2,[777,778],submitted=-1);done=True
 out,m,st=decode(Adversarial(),[10,11,12],length=32,hook=hook,max_steps=100)
 assert done and not m['pending_at_end'] and m['remask_count']==1
 assert not any(x in (MASK,DELETE,SPLIT) for x in out)
 st.assert_locks();return {'passed':True,'delay':40,'prompt_preserved':True,'existing_lock_shifted_intact':True,'structural_edits_suppressed':True,'metrics':m}
if __name__=='__main__':print(json.dumps(check()))
