import types,torch
from sampler import decode,DELETE,SPLIT,MASK
class Adversarial:
    device=torch.device('cuda')
    def __call__(self,x,**kw):
        logits=torch.full((*x.shape,157184),-10.,device=x.device)
        logits[:,:,DELETE]=100.;logits[:,:,SPLIT]=90.;logits[:,:,MASK]=80.;logits[:,:,123]=70.
        return types.SimpleNamespace(logits=logits)
def check():
    def hook(s):
        if not s.locks:s.lock(8,[777,778,779],label='adversarial_lock')
    out,metrics,state=decode(Adversarial(),torch.tensor([[42]],device='cuda'),gen_length=32,steps=2,post_steps=1,hook=hook,fixed_budget=True)
    assert state.x[0,8:11].tolist()==[777,778,779]
    assert not any(v in (DELETE,SPLIT,MASK) for v in out)
    return {'passed':True,'injected_tokens_unchanged':True,'delete_split_mask_suppressed':True,'forward_calls':metrics['forward_calls']}
