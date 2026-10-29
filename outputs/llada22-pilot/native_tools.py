import json,re,time
from async_engine import Engine,signature,remote_execute
from call_parser import validate
PATTERN=re.compile(r'<\|tool_call_begin\|>(functions\.([A-Za-z_][A-Za-z_0-9]*):\d+)<\|tool_call_argument_begin\|>(.*?)<\|tool_call_end\|>',re.S)

def parse(text):
    calls=[]
    for m in PATTERN.finditer(text):
        try:args=json.loads(m[3])
        except ValueError:continue
        call={'name':m[2],'args':args}
        if validate(call):calls.append({'id':m[1],'call':call,'start':m.start(),'end':m.end()})
    return calls

def definitions(names=('read_file','run')):
    specs={
      'read_file':('Read bytes from a local file.',{'path':{'type':'string'},'offset':{'type':'integer'},'length':{'type':'integer'}},['path','offset','length']),
      'run':('Execute a program in an isolated Linux workspace and return stdout.',{'cmd':{'type':'array','items':{'type':'string'}},'stdin':{'type':'string'},'timeout_ms':{'type':'integer'}},['cmd','stdin','timeout_ms']),
      'write_file':('Save literal text to a workspace file.',{'path':{'type':'string'},'data':{'type':'string'}},['path','data']),
      'list_dir':('List directory entries.',{'path':{'type':'string'}},['path']),
      'stat':('Inspect file metadata.',{'path':{'type':'string'}},['path']),
      'clock':('Read the Linux system clock.',{},[]),
      'remove':('Remove one file.',{'path':{'type':'string'}},['path'])}
    return [{'type':'function','function':{'name':n,'description':specs[n][0],'parameters':{'type':'object','properties':specs[n][1],'required':specs[n][2]}}} for n in names]

class Monitor:
    def __init__(self,tokenizer,delay_steps=0,allowed=("read_file","run")):
        self.tok=tokenizer;self.allowed=set(allowed);self.engine=Engine(delay_steps=delay_steps);self.deliveries={};self.last=[];self.trace=[]
    def observe(self,state):
        ids=state.draft[0,state.prompt_length:].tolist()
        pieces=[self.tok.decode([i],skip_special_tokens=False,clean_up_tokenization_spaces=False) for i in ids]
        text=''.join(pieces)
        if text!=self.tok.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False):return
        offsets=[0]
        for p in pieces:offsets.append(offsets[-1]+len(p))
        observations=[]
        for parsed in parse(text):
            if parsed['call']['name'] not in self.allowed:continue
            positions=[state.prompt_length+i for i in range(len(ids)) if offsets[i]<parsed['end'] and offsets[i+1]>parsed['start']]
            if not positions:continue
            # Unmasked tokens in the active block remain editable until block close.
            committed=all(p<state.block_start or state.block_final for p in positions)
            confidence=min(state.confidence[0,positions].tolist())
            observations.append({'anchor':parsed['id'],'call':parsed['call'],'committed':committed,'eligible':committed or confidence>=.5})
            self.trace.append({'step':state.step,'id':parsed['id'],'committed':committed,'confidence':confidence,'call':parsed['call']})
        self.last=observations
        for d in self.engine.barrier(observations,state.step):self.deliveries[signature(d['call'])]=d
    def close(self):self.engine.close()

def messages(question,call_info=None,result=None):
    conversation=[{'role':'system','content':'Use the available tool when external data or program execution is needed. Make one tool call at a time. After receiving the result, return only the requested answer.'}, {'role':'user','content':question}]
    if call_info:
        conversation += [{'role':'assistant','content':'','tool_calls':[{'id':call_info['id'],'type':'function','function':{'name':call_info['call']['name'],'arguments':json.dumps(call_info['call']['args'])}}]},
                         {'role':'tool','tool_call_id':call_info['id'],'content':result}]
    return conversation
