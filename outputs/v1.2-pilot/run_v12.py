"""One model load: gated prerequisites, then immutable v1.2 experiment."""
import faulthandler,hashlib,json,pathlib,re,time,os,sys
faulthandler.enable();faulthandler.dump_traceback_later(300,repeat=True)
from pilot import *
from wait_adapter import delayed_answer,native_wait
from test_wait import check
OUT=pathlib.Path('results-v1.2');OUT.mkdir(exist_ok=True)
REF=json.load(open('v11-reference.json'));STEP_SECONDS=REF['delay_calibration']['mean_step_seconds']
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2))
def metrics(r):
 if 'metrics' in r:return [r['metrics']]
 return [t[k] for t in r.get('rounds',[]) for k in ('first','second') if k in t]
def normalize(r):
 ms=metrics(r);events=[e for m in ms for e in m.get('events',[])];engine=r.get('events',[])
 r['safety']={k:sum(m.get(k,0) for m in ms) for k in ('lock_violations','residual_masks')}
 r['safety'].update({k:sum(e['type']==k for e in engine) for k in ('stray_effect','stale_completion')})
 r['timing']={'wait_seconds':sum(m.get('wait_seconds',0) for m in ms),'denoising_seconds':sum(m.get('denoising_seconds',m.get('seconds',0)) for m in ms),'wall_seconds':r.get('seconds',sum(m.get('seconds',0) for m in ms))}
 r['forward_calls']=sum(m.get('forward_calls',0) for m in ms)
 r['calls_count']=sum(e['type']=='submit' for e in engine) if engine else len(r.get('calls',r.get('injection_events',[])))
 r['rounds_used']=len(r.get('rounds',[])) if 'rounds' in r else int(r['calls_count']>0)
 r['call_metrics']=[dict(dispatch_step=e['dispatch_step'],lock_step=e['lock_step'],wait_seconds=e['wait_seconds'],dispatch_wall_time=e['dispatch_wall_time']) for e in events if e['type']=='pause']
 r.setdefault('strict',bool(r.get('correct',False)))
 return r

def emit(name,r):append(OUT/(name+'.jsonl'),normalize(r))
def linux(model,tok,task,c):
 history=[{'role':'system','content':'Use the declared tools to obtain external information. Follow file links only after reading their names. Return only the requested answer. Persistent writes require the requested literal path and contents.'},{'role':'user','content':task['question']}]
 if c=='L0':
  st=time.perf_counter();output,m,_=decode(model,ids(tok,history),length=192);r=dict(text=tok.decode(output,skip_special_tokens=True),calls=[],rounds=[{'first':m}],events=[],seconds=time.perf_counter()-st)
 elif c=='L3':r=native_wait(model,tok,history,definitions(tuple(task['allowed'])),set(task['allowed']),max_rounds=4)
 else:r=native(model,tok,history,definitions(tuple(task['allowed'])),set(task['allowed']),c=='L2',max_rounds=4)
 clean=re.sub(r'<\|[^>]+\|>','',r['text']).strip();pred=re.sub(r'^Answer\s*:\s*','',clean,flags=re.I).strip('`"\' .')
 present=bool(re.search(r'(?<![\w])'+re.escape(task['expected'])+r'(?![\w])',clean));executed=any((t.get('result') or {}).get('ok') for t in r['rounds'])
 r.update(id=task['id'],kind=task['kind'],condition=c,expected=task['expected'],strict=pred==task['expected'],answer_present=present,correct=present and (executed if task['kind']=='write' else True),minimum_calls=task['minimum_calls'])
 return r

def main():
 save('unit-tests-gpu.json',check())
 model,tok=load();faulthandler.cancel_dump_traceback_later()
 orig=dataset();rows=make_rows();save('tasks240.json',rows);save('smoke-tasks.json',orig)
 save('environment.json',dict(model=MODEL,revision=REV,torch=torch.__version__,device=torch.cuda.get_device_name(),seed=20261028,batch=1,dtype='BF16',fine_tuning=False,delay_calibration=REF['delay_calibration']))
 expected={r['id']:r for r in REF['A7_first5_smoke']};repro=[]
 for row in orig[:5]:
  r=arithmetic(model,tok,row,'A7');r['exact_reproduction']=r['text']==expected[row['id']]['text'];emit('prerequisite-reproduction',r);repro.append(r['exact_reproduction'])
 if not all(repro):
  save('PREREQUISITE_FAILED.json',dict(reason='A7 exact reproduction failed',matches=repro));return
 smoke=[]
 for row in orig:
  for c in ('M4','A7','A7W'):
   r=arithmetic(model,tok,row,c);emit('prerequisite-smoke',r);smoke.append(r)
 if any(r['metrics']['residual_masks'] for r in smoke):
  save('PREREQUISITE_FAILED.json',dict(reason='residual masks on smoke'));return
 save('prerequisites.json',dict(passed=True,reproduced=5,smoke_prompts=36,smoke_conditions=['M4','A7','A7W'],smoke_records=108,residual_masks=0))
 # Freeze exact code and protocol before the first measured comparison.
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('.').iterdir() if p.is_file() and p.suffix in ('.py','.json','.txt','.md')}
 save('frozen-source-manifest.json',dict(timestamp=time.time(),files=files))
 print('PREREQUISITES PASSED; MEASURED RUN START',flush=True)
 for kind in ('hidden','arithmetic'):
  for index in range(6):
   if kind=='hidden':
    call={'id':'functions.read_file:0','call':{'name':'read_file','args':{'path':f'lookup/item_{index}.txt'}}};ready=execute(call['call']);expected=ready['output'].strip();assert ready['ok']
    history=[{'role':'system','content':'After receiving a tool result, return one line: Answer: <exact value>. Do not add explanations.'},{'role':'user','content':f'Read lookup/item_{index}.txt. Return its exact value as Answer: <value>.'}];defs=definitions(('read_file',))
   else:
    row=orig[index];history=prompt(row,'A2',True);call={'id':'functions.calc:3','call':{'name':'calc','args':{'expression':f"{row['a']} {row['op']} {row['b']}"}}};ready=execute(call['call']);expected=row['expected'];defs=[CALC]
   for delay in (0,10,20,40):
    for c in ('D1','D2','D3'):
     if c=='D3':text,m,_=delayed_answer(model,tok,history,defs,call,ready,delay*STEP_SECONDS)
     else:text,m,_=answer_stage(model,tok,history,defs,call,ready=ready,delay=delay,f3=c=='D2')
     hits=re.findall(r'(?m)^Answer:\s*([0-9a-f]+)\s*$',text)
     correct=bool(hits and hits[-1]==expected) if kind=='hidden' else score(text,row)['correct']
     emit('delay',dict(id=index,kind=kind,condition=c,delay=delay,text=text,expected=expected,correct=correct,metrics=m,calls=[call],rounds=[{'result':ready}],seconds=m['seconds']))
 for task in json.load(open('linux-tasks.json')):
  for c in ('L0','L1','L2','L3'):emit('linux',linux(model,tok,task,c))
 for row in rows:
  for c in ('M4','A7','A7W'):emit('full',arithmetic(model,tok,row,c,block=32))
 for row in rows:emit('mid',arithmetic(model,tok,row,'A7W',block=64))
 save('COMPLETE.json',dict(completed=True,timestamp=time.time(),expected_counts=dict(delay=144,linux=108,full=720,mid=240)))
 print('ALL V1.2 STAGES COMPLETE',flush=True)
if __name__=='__main__':main()
