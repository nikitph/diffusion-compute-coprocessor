"""Fixed-position LLaDA2.2 block sampler with explicit external locks.
Same block-causal attention and threshold/floor unmasking family as upstream.
DELETE/SPLIT/MASK output logits are suppressed; text-to-text refinement is bounded.
This is a protected experimental sampler, not an untouched upstream benchmark.
"""
import math,time
import torch
MASK=156895;EOS=156892;DELETE=156930;SPLIT=156931

class State:
    def __init__(self,x,fixed,visible,prompt_length):
        self.x=x;self.fixed=fixed;self.visible=visible;self.prompt_length=prompt_length
        self.locks=[];self.events=[];self.step=0;self.block_step=0;self.block_start=0;self.block_end=0;self.block_final=False
        self.draft=None;self.confidence=None;self.hold_block=False
    def lock(self,start,ids,visible=True,label='external'):
        end=start+len(ids)
        if end>self.x.shape[1]:raise ValueError('lock exceeds canvas')
        values=torch.tensor(ids,dtype=torch.long,device=self.x.device)
        self.x[0,start:end]=values;self.fixed[0,start:end]=True;self.visible[0,start:end]=visible
        self.locks.append((start,end,values.clone(),label))
        self.events.append({'type':'lock','label':label,'step':self.step,'start':start,'end':end})
    def assert_locks(self):
        for start,end,values,label in self.locks:
            if not torch.equal(self.x[0,start:end],values):raise AssertionError('external lock changed: '+label)

@torch.inference_mode()
def decode(model,input_ids,gen_length=192,block_length=32,steps=8,threshold=.5,editing_threshold=0.,post_steps=2,
           hook=None,prefix_holes=None,initial_locks=None,fixed_budget=False,allow_hold=False):
    if input_ids.shape[0]!=1:raise ValueError('This pilot adapter is batch size 1; no multi-sequence batching claim.')
    device=model.device;P=input_ids.shape[1];nblocks=math.ceil((P+gen_length)/block_length);N=nblocks*block_length
    x=torch.full((1,N),MASK,dtype=torch.long,device=device);x[:,:P]=input_ids
    fixed=torch.zeros_like(x,dtype=torch.bool);fixed[:,:P]=True
    visible=torch.ones_like(x,dtype=torch.bool)
    for lo,hi in prefix_holes or []:visible[:,lo:hi]=False
    state=State(x,fixed,visible,P)
    for lo,ids,label in initial_locks or []:state.lock(lo,ids,label=label)
    base_mask=(torch.arange(N,device=device)[:,None]//block_length>=torch.arange(N,device=device)[None,:]//block_length)
    positions=torch.arange(N,device=device)[None,:]
    forward_count=0;hook_seconds=0;block_steps=[]
    torch.cuda.synchronize();started=time.perf_counter()
    for block in range(P//block_length,nblocks):
        lo=block*block_length;hi=(block+1)*block_length;state.block_start=lo;state.block_end=hi
        initial_count=int(((x[0,lo:hi]==MASK)&~fixed[0,lo:hi]).sum())
        floors=[initial_count//steps+int(i<initial_count%steps) for i in range(steps)]
        rounds=max(steps+post_steps,32) if allow_hold else steps+post_steps;ran=0;resolved_round=None
        for local_step in range(rounds):
            state.step=forward_count;state.block_step=local_step
            active=(x[0,lo:hi]==MASK)&~fixed[0,lo:hi]
            if state.hold_block:resolved_round=None
            if not fixed_budget and not state.hold_block and not bool(active.any()):
                if resolved_round is None:resolved_round=local_step
                if local_step-resolved_round>=post_steps:break
            attention=(base_mask[:hi,:hi]&visible[0,None,:hi])[None,None,:,:]
            bias=torch.where(attention,0.,-torch.inf).to(torch.bfloat16)
            logits=model(x[:,:hi],attention_mask=bias,position_ids=positions[:,:hi]).logits[0,lo:hi].float()
            logits[:,[MASK,DELETE,SPLIT]]=-torch.inf
            probability=logits.softmax(-1);proposed=logits.argmax(-1);confidence=probability.gather(-1,proposed[:,None]).squeeze(-1)
            before=x[0,lo:hi].clone();fill=active&(confidence>threshold)
            need=floors[local_step] if local_step<steps else int(active.sum())
            if int(fill.sum())<need:
                ranked=torch.where(active,confidence,-torch.inf);count=min(need,int(active.sum()))
                if count:fill[ranked.topk(count).indices]=True
            if local_step==steps-1:fill=active # bounded resolution of all masks
            editable=~active&~fixed[0,lo:hi]
            edits=editable&(confidence>editing_threshold)&(before!=proposed)
            x[0,lo:hi][fill|edits]=proposed[fill|edits]
            state.draft=x[:,:hi].clone();remaining=x[0,lo:hi]==MASK
            state.draft[0,lo:hi]=torch.where(remaining,proposed,x[0,lo:hi])
            state.confidence=torch.ones((1,hi),device=device)
            actual=probability.gather(-1,state.draft[0,lo:hi,None]).squeeze(-1)
            state.confidence[0,lo:hi]=actual
            state.block_final=local_step==rounds-1
            if not fixed_budget and not bool((x[0,lo:hi]==MASK).any()):
                if resolved_round is None:resolved_round=local_step+1
                state.block_final=((local_step+1-resolved_round)>=post_steps and not state.hold_block) or state.block_final
            if hook:
                h=time.perf_counter();hook(state);torch.cuda.synchronize();hook_seconds+=time.perf_counter()-h
            state.assert_locks();forward_count+=1;ran+=1
            del logits,probability
        # This notification marks the actual irreversible block boundary.
        state.block_final=True;state.draft=x[:,:hi].clone();state.confidence=torch.ones((1,hi),device=device)
        if hook:
            h=time.perf_counter();hook(state);torch.cuda.synchronize();hook_seconds+=time.perf_counter()-h
        state.assert_locks();block_steps.append(ran)
        if not fixed_budget and bool((x[0,P:hi]==EOS).any()):break
    torch.cuda.synchronize();elapsed=time.perf_counter()-started
    output=x[0,P:P+gen_length].tolist()
    if EOS in output:output=output[:output.index(EOS)+1]
    metrics={'seconds':elapsed,'forward_calls':forward_count,'hook_seconds':hook_seconds,'block_steps':block_steps,
             'locks':len(state.locks),'lock_violations':0,'events':state.events,'residual_masks':output.count(MASK),'structural_edits_disabled':True}
    return output,metrics,state
