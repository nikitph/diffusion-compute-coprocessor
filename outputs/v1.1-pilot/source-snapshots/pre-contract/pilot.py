import os
os.environ['HF_HUB_DISABLE_PROGRESS_BARS']='1'
import argparse,json,pathlib,random,re,time,hashlib,torch,collections
from transformers import AutoTokenizer,AutoModelForCausalLM
from transformers.utils import logging as hf_logging
from huggingface_hub.utils import disable_progress_bars
hf_logging.disable_progress_bar();disable_progress_bars()
from event_sampler import decode,MASK
from old_sampler import decode as old_decode
from arithmetic_hook import ArithmeticHook
from arith_reference import dataset,score,posthoc
from gpu_arithmetic import encode,compute,decode as decode_int
import async_engine
from async_engine import Engine,signature,remote_execute
from native_tools import PATTERN,definitions
from call_parser import validate
MODEL='inclusionAI/LLaDA2.2-mini';REV='e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5'
async_engine.READS.add('calc')
EXAMPLES='Examples: 12345 + 67890 = 80235; Answer: 80235. 12345 - 67890 = -55545; Answer: -55545. 12345 * 67890 = 838102050; Answer: 838102050.'
CALC={'type':'function','function':{'name':'calc','description':'Compute an exact integer expression.','parameters':{'type':'object','properties':{'expression':{'type':'string'}},'required':['expression']}}}
def expression(text):
 m=re.fullmatch(r'\s*(\d{1,64})\s*([+*×−-])\s*(\d{1,64})\s*',text)
 return (int(m[1]),m[2].replace('×','*').replace('−','-'),int(m[3])) if m else None

def execute(call,committed=False):
 if call['name']!='calc':return remote_execute(call,committed=committed)
 parsed=expression(call['args'].get('expression',''))
 if not parsed:return {'ok':False,'output':'ERROR invalid expression'}
 a,op,b=parsed;result=compute(encode([a]),encode([b]),torch.tensor([{'+':0,'-':1,'*':2}[op]],device='cuda',dtype=torch.int32))
 return {'ok':True,'output':str(decode_int(*result)[0]),'operands':[a,op,b]}

def parse(text):
 out=[]
 for m in PATTERN.finditer(text):
  try:args=json.loads(m[3])
  except ValueError:continue
  c={'name':m[2],'args':args}
  if (c['name']=='calc' and isinstance(args,dict) and expression(args.get('expression',''))) or validate(c):out.append({'id':m[1],'call':c,'start':m.start(),'end':m.end()})
 return out

def rendered(tok,msgs,tools=None):return tok.apply_chat_template(msgs,tools=tools,add_generation_prompt=True,tokenize=False)
def ids(tok,msgs,tools=None):return tok.encode(rendered(tok,msgs,tools),add_special_tokens=False)
def tool_msgs(history,call,result):return history+[{'role':'assistant','content':'','tool_calls':[{'id':call['id'],'type':'function','function':{'name':call['call']['name'],'arguments':json.dumps(call['call']['args'])}}]},{'role':'tool','tool_call_id':call['id'],'content':result}]
def prompt(row,mode='',strong=False):
 system=EXAMPLES+' Return a final separate line Answer: <integer> or Answer: YES/NO, as requested.'
 if mode in ('A2','A3'):system+=' You MUST call calc for every expression with operands longer than 4 digits. Never calculate it yourself.'+(' Your first response MUST be a calc tool call, with no prose.' if strong else '')
 if mode=='A5':system+=' The exact result is named r1. For direct arithmetic, write Answer: <ref r1>. Examples: r1=80235 -> Answer: <ref r1>; r1=-55545 -> Answer: <ref r1>; r1=838102050 -> Answer: <ref r1>. For comparisons, use the value bound to r1 and answer YES or NO.'
 history=[{'role':'system','content':system.replace(EXAMPLES,'') if mode in ('A2','A3') else system}]
 if mode in ('A2','A3'):
  for i,(expr,value) in enumerate([('12345 + 67890','80235'),('12345 - 67890','-55545'),('12345 * 67890','838102050')]):
   history.append({'role':'user','content':'Calculate '+expr+'. Finish with Answer: <integer>.'})
   history=tool_msgs(history,{'id':f'functions.calc:{i}','call':{'name':'calc','args':{'expression':expr}}},value)
   history.append({'role':'assistant','content':'Answer: '+value})
 return history+[{'role':'user','content':row['prompt']}]

def make_rows():
 rng=random.Random(2026102811);rows=[]
 for digits in (5,8,10,12,15):
  for op in ('+','-','*'):
   for rep in range(8):
    a=rng.randrange(10**(digits-1),10**digits);b=rng.randrange(10**(digits-1),10**digits);v={'+':a+b,'-':a-b,'*':a*b}[op]
    delta=rng.randint(1,max(1,abs(v)//100));threshold=v+(-delta if rep%2==0 else delta)
    for kind in ('direct','dependent'):
     q=f'Calculate {a} {op} {b}. Start with {a} {op} {b} = followed by its result. Use plain decimal integers without commas. '
     q+='Finish with Answer: <integer>.' if kind=='direct' else f'Is that result strictly greater than {threshold}? Finish with Answer: YES or Answer: NO.'
     rows.append(dict(id=len(rows),digits=digits,op=op,a=a,b=b,value=v,threshold=threshold,kind=kind,expected=str(v) if kind=='direct' else ('YES' if v>threshold else 'NO'),prompt=q))
 return rows

class Monitor:
 def __init__(self,tok,allowed):self.tok=tok;self.allowed=allowed;self.engine=Engine(execute=execute);self.deliveries={};self.observed=[]
 def __call__(self,s):
  tokens=s.draft[0,s.prompt_length:].tolist();pieces=[self.tok.decode([i],skip_special_tokens=False,clean_up_tokenization_spaces=False) for i in tokens];text=''.join(pieces)
  if text!=self.tok.decode(tokens,skip_special_tokens=False,clean_up_tokenization_spaces=False):return
  offsets=[0]
  for p in pieces:offsets.append(offsets[-1]+len(p))
  obs=[]
  for c in parse(text):
   if c['call']['name'] not in self.allowed:continue
   ix=[s.prompt_length+i for i in range(len(tokens)) if offsets[i]<c['end'] and offsets[i+1]>c['start']]
   if not ix:continue
   if c['call']['name']=='calc':
    expr=c['call']['args']['expression'];start=text.find(expr,c['start'],c['end'])
    spans=[(start+m.start(),start+m.end()) for m in re.finditer(r'\d+',expr)] if start>=0 else []
    ix=[s.prompt_length+i for i in range(len(tokens)) if any(offsets[i]<end and offsets[i+1]>begin for begin,end in spans)]
    if not ix:continue
   conf=min(s.confidence[0,ix].tolist());committed=all(i<s.block_start or s.block_final for i in ix)
   obs.append({'anchor':c['id'],'call':c['call'],'committed':committed,'eligible':conf>=.9,'confidence':conf})
  self.observed=obs
  for d in self.engine.barrier(obs,s.step):self.deliveries[signature(d['call'])]=d

def answer_stage(model,tok,history,defs,call,ready=None,monitor=None,global_step=0,block=32,delay=0,f3=True,editing=False,compact=False):
 templ=rendered(tok,tool_msgs(history,call,'__RESULT_ANCHOR__'),defs);left,right=templ.split('__RESULT_ANCHOR__');left=tok.encode(left,add_special_tokens=False);right=tok.encode(right,add_special_tokens=False)
 def result_tokens(r):
  val=r.get('output','') if r.get('ok') else 'ERROR: '+r.get('output','')
  z=tok.encode(val,add_special_tokens=False)
  marker=tok.encode(' [truncated]',add_special_tokens=False)
  return z if len(z)<=256 else z[:256-len(marker)]+marker
 if monitor is None and not delay:
  z=left+result_tokens(ready)+right;out,m,s=decode(model,z,block=block,length=192);return tok.decode(out,skip_special_tokens=True),m,ready
 lo=len(left);base=left+right
 if compact:
  # Left padding is explicit and shared with matched controls; it places the native result near the start of a block.
  pad=(8-lo%block)%block;base=[tok.encode('\n',add_special_tokens=False)[0]]*pad+base;lo+=pad
 key=signature(call['call']);stable=[{'anchor':call['id'],'call':call['call'],'committed':True,'eligible':True}];received=False;result=ready
 def hook(s):
  nonlocal received,result
  if received:return
  s.pending=True
  if monitor:
   for d in monitor.engine.barrier(stable,global_step+s.step):monitor.deliveries[signature(d['call'])]=d
   if key in monitor.deliveries:result=monitor.deliveries[key]['result']
  if result is not None and s.step>=delay:
   s.arrival(lo,lo,result_tokens(result),submitted=-1,remask=f3,editing=editing);received=True
 out,m,s=decode(model,base,block=block,length=192,hook=hook);m['received']=received
 return tok.decode(out,skip_special_tokens=True),m,result

def native(model,tok,history,defs,allowed,async_mode,block=32,delay=0,max_rounds=1,compact=False,remask_on_arrival=True):
 start=time.perf_counter();rounds=[];alltext=[];final='';calls=[];events=[];remasks_used=0
 for turn in range(max_rounds):
  mon=Monitor(tok,allowed) if async_mode else None
  out,first,s=decode(model,ids(tok,history,defs),length=384,block=block,hook=mon)
  text=tok.decode(out,skip_special_tokens=False);found=[c for c in parse(text) if c['call']['name'] in allowed];alltext.append(text)
  if not found:
   if mon:mon.engine.close();events+=mon.engine.events
   final=tok.decode(out,skip_special_tokens=True);rounds.append({'first':first,'no_call':True});break
  c=found[0];calls.append(c);ready=None
  if mon:
   accepted=any(signature(o['call'])==signature(c['call']) and o['eligible'] for o in mon.observed) or any(v['signature']==signature(c['call']) and v['submitted'] for v in mon.engine.states.values())
   if not accepted:
    mon.engine.close();events+=mon.engine.events;final=tok.decode(out,skip_special_tokens=True);rounds.append({'first':first,'below_trigger_confidence':True,'observations':mon.observed});break
   stable=[{'anchor':c['id'],'call':c['call'],'committed':True,'eligible':True}]
   for d in mon.engine.barrier(stable,first['forward_calls']):mon.deliveries[signature(d['call'])]=d
  else:ready=execute(c['call'],committed=c['call']['name'] in async_engine.EFFECTS)
  final,second,result=answer_stage(model,tok,history,defs,c,ready,mon,first['forward_calls'],block,delay,f3=remask_on_arrival and remasks_used<2,compact=compact)
  remasks_used+=sum(e['type']=='remask' for e in second.get('events',[]))
  if mon:mon.engine.close();events+=mon.engine.events
  rounds.append({'first':first,'second':second,'result':result})
  value=result.get('output','') if result else 'ERROR no result'
  values=tok.encode(value,add_special_tokens=False);marker=tok.encode(' [truncated]',add_special_tokens=False)
  if len(values)>256:value=tok.decode(values[:256-len(marker)]+marker,skip_special_tokens=False)
  history=tool_msgs(history,c,value)
  # The next round re-generates from this history; the provisional answer is diagnostic only.
  if not parse(final):break
 return {'text':final,'first_texts':alltext,'calls':calls,'rounds':rounds,'events':events,'seconds':time.perf_counter()-start}

def arithmetic(model,tok,row,condition,block=32,delay=0,strong=False,f3=True):
 history=prompt(row,{'M5':'A5','M4':'A4'}.get(condition,condition),strong);baseids=ids(tok,history,[CALC] if condition in ('A2','A3') else None);start=time.perf_counter();events=[];adopted=None
 if condition in ('A2','A3'):
  r=native(model,tok,history,[CALC],{'calc'},condition=='A3',block,delay,compact=block==64,remask_on_arrival=f3)
  text=r['text'];metrics={'events':[e for turn in r['rounds'] for m in ('first','second') for e in turn.get(m,{}).get('events',[])],'lock_violations':sum(turn.get(m,{}).get('lock_violations',0) for turn in r['rounds'] for m in ('first','second'))};events=[{'status':'injected','operand_match':tuple(turn['result'].get('operands',()))==(row['a'],row['op'],row['b'])} for turn in r['rounds'] if (turn.get('result') or {}).get('ok')]
 elif condition in ('A4','A5','A7','M4','M5'):
  prefix=f"{row['a']} {row['op']} {row['b']} = " if condition not in ('A5','M5') else 'r1 = '
  left=baseids+tok.encode(prefix,add_special_tokens=False);lo=len(left)
  if block==64:
   pad=(24-lo%block)%block;left=[tok.encode('\n',add_special_tokens=False)[0]]*pad+left;lo+=pad
  if condition in ('M4','M5'):
   out,metrics,s=decode(model,left,block=block,length=192);text=prefix+tok.decode(out,skip_special_tokens=True)
  else:
   da,db=len(str(row['a'])),len(str(row['b']));width=(da+db if row['op']=='*' else max(da,db)+1)+2
   right=tok.encode('\n',add_special_tokens=False);canvas=left+[MASK]*width+right;done=False;binding=None
   def hook(s):
    nonlocal done,binding
    if done:return
    s.pending=True
    # Operand span is immutable prompt text: confidence 1, known before '=' generation.
    if s.step>=delay:
     result=execute({'name':'calc','args':{'expression':f"{row['a']} {row['op']} {row['b']}"}});vals=tok.encode(result['output'],add_special_tokens=False)
     binding=result['output'];assert len(vals)<=width
     s.arrival(lo,lo+width,vals,submitted=-1,remask=f3 and condition!='A7',editing=condition=='A7');done=True;events.append({'status':'injected','operand_match':True,'slot_occupied':False,'value':binding,'a':row['a'],'b':row['b'],'op':row['op']})
   out,metrics,s=decode(model,canvas,block=block,length=192,hook=hook,holes=[(lo,lo+width)])
   text=prefix+tok.decode(out,skip_special_tokens=True)
   if condition=='A5':
    adopted='<ref r1>' in text;raw=text;text=text.replace('<ref r1>',binding) if binding is not None else text
   else:raw=text
 elif condition in ('A1','M1'):
  h=ArithmeticHook(tok,row) if condition=='A1' else None;out,metrics,s=old_decode(model,torch.tensor([baseids],device='cuda'),gen_length=192,block_length=block,hook=h);text=tok.decode(out,skip_special_tokens=True);events=h.events if h else []
 else:
  out,metrics,s=decode(model,baseids,block=block,length=192);text=tok.decode(out,skip_special_tokens=True)
 r=locals().get('r',{});r.update({'id':row['id'],'kind':row['kind'],'condition':condition,'block':block,'delay':delay,'f3':f3,'text':text,'raw_text':locals().get('raw',text),'expected':row['expected'],**score(text,row),'metrics':metrics,'injection_events':events,'reference_adopted':adopted,'seconds':time.perf_counter()-start})
 return r

def load():
 torch.manual_seed(20261028)
 tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True)
 model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,trust_remote_code=True,dtype=torch.bfloat16,device_map={'':'cuda'},attn_implementation='sdpa').eval()
 execute({'name':'calc','args':{'expression':'12 * 34'}});print('model loaded',flush=True);return model,tok

def append(path,r):
 with path.open('a') as f:f.write(json.dumps(r)+'\n')
 print(json.dumps({k:r.get(k) for k in ('set','id','condition','block','delay','correct','seconds')}),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['smoke','full','mid','linux'],default='smoke');a=p.parse_args();out=pathlib.Path('results');out.mkdir(exist_ok=True)
 model,tok=load();orig=dataset();rows=make_rows();(out/'original-tasks.json').write_text(json.dumps(orig,indent=2));(out/'tasks240.json').write_text(json.dumps(rows,indent=2));(out/'environment.json').write_text(json.dumps({'model':MODEL,'revision':REV,'torch':torch.__version__,'block_lengths':[32,64],'seed':20261028,'fine_tuning':False,'batch':1},indent=2))
 if a.stage=='smoke':
  # Real-model delayed native response control, before all other smoke conditions.
  task={'id':1,'kind':'direct','expected':'6fbed9be80ce'};hist=[{'role':'user','content':'Return exactly the value read from lookup/item_1.txt.'}];call={'id':'functions.read_file:0','call':{'name':'read_file','args':{'path':'lookup/item_1.txt'}}};ready=execute(call['call'])
  delay_existing={(r['delay'],r['f3']) for r in map(json.loads,(out/'delay.jsonl').read_text().splitlines())} if (out/'delay.jsonl').exists() else set()
  for delay in (0,10,20,40):
   for f3 in (False,True):
    if (delay,f3) in delay_existing:continue
    text,m,_=answer_stage(model,tok,hist,definitions(('read_file',)),call,ready=ready,delay=delay,f3=f3)
    append(out/'delay.jsonl',{'id':1,'delay':delay,'f3':f3,'text':text,'used':'6fbed9be80ce' in text,'metrics':m})
  existing={(r['condition'],r['id']) for r in map(json.loads,(out/'smoke.jsonl').read_text().splitlines())} if (out/'smoke.jsonl').exists() else set()
  for c in ('A0','A1','A2','A3','A4','A5','A7','M4','M5'):
   for row in orig:
    if (c,row['id']) not in existing:append(out/'smoke.jsonl',dict(arithmetic(model,tok,row,c),set='original36'))
  for c in ('A0','A1','A2','A3','A4','A5','A7'):
   for row in orig[:5]:append(out/'repeat.jsonl',dict(arithmetic(model,tok,row,c),set='repeat5'))
 elif a.stage in ('full','mid'):
  smoke=[json.loads(x) for x in (out/'smoke.jsonl').read_text().splitlines()];a5=[r for r in smoke if r['condition']=='A5' and r['kind']=='direct'];adopt=sum(r['reference_adopted'] is True for r in a5)/len(a5)
  conditions=['A0','A1','A2','A3','A4','M4']+(['A5','M5'] if adopt>=.5 else []) if a.stage=='full' else ['A3','A4']+(['A5'] if adopt>=.5 else [])
  for row in rows:
   for c in conditions:
    r=arithmetic(model,tok,row,c,block=64 if a.stage=='mid' else 32);append(out/(a.stage+'.jsonl'),dict(r,set='expanded240'))
    if c=='A0':
     text=posthoc(r['text'],row['kind']);append(out/(a.stage+'.jsonl'),dict(id=row['id'],kind=row['kind'],condition='A6',text=text,expected=row['expected'],**score(text,row),set='expanded240'))
 else:
  from linux_runner import run_linux
  run_linux(model,tok,out)
if __name__=='__main__':main()
