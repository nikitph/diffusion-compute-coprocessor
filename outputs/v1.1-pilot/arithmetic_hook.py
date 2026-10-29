import torch
from arith_reference import EQ
from gpu_arithmetic import encode,compute,decode as decode_digits
class ArithmeticHook:
    def __init__(self,tokenizer,row,tau=.5):self.tok=tokenizer;self.row=row;self.tau=tau;self.done=False;self.events=[]
    def __call__(self,state):
        if self.done:return
        ids=state.draft[0,state.prompt_length:].tolist();parts=[self.tok.decode([i],skip_special_tokens=False,clean_up_tokenization_spaces=False) for i in ids];text=''.join(parts)
        if self.tok.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)!=text:return
        offsets=[0]
        for p in parts:offsets.append(offsets[-1]+len(p))
        for m in EQ.finditer(text):
            if m.start() not in offsets or m.end() not in offsets:continue
            lo=state.prompt_length+offsets.index(m.start());start=state.prompt_length+offsets.index(m.end())
            if min(state.confidence[0,lo:start].tolist())<self.tau:continue
            a,b=int(m['a']),int(m['b']);op=m['op'].replace('×','*').replace('−','-')
            if a<0 or b<0:continue
            output=compute(encode([a]),encode([b]),torch.tensor([{'+':0,'-':1,'*':2}[op]],dtype=torch.int32,device='cuda'))
            value=decode_digits(*output)[0];string=' '+str(value)+'\n';tokens=self.tok.encode(string,add_special_tokens=False)
            if self.tok.decode(tokens,clean_up_tokenization_spaces=False)!=string:continue
            end=start+len(tokens);event={'step':state.step,'block_step':state.block_step,'a':a,'b':b,'op':op,'value':str(value),'operand_match':a==self.row['a'] and b==self.row['b'] and op==self.row['op']}
            if end>state.x.shape[1]:event['status']='length_failure'
            elif not bool((state.x[0,start:end]==156895).all()):event['status']='occupied_slot'
            else:state.lock(start,tokens,label='gpu_arithmetic');self.done=True;event['status']='injected'
            self.events.append(event)
            if self.done:return
