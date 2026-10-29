"""Continue after smoke: apply gates, then full/mid/Linux without reloading weights."""
import json,pathlib,time
from pilot import *
from linux_runner import run_linux
out=pathlib.Path('results');smoke=[json.loads(x) for x in (out/'smoke.jsonl').read_text().splitlines()];repeat=[json.loads(x) for x in (out/'repeat.jsonl').read_text().splitlines()]
assert len(smoke)==324 and len(repeat)==35, 'Smoke incomplete: do not expand'
by={(r['condition'],r['id']):r for r in smoke};bad={r['condition'] for r in repeat if by[r['condition'],r['id']]['text']!=r['text']}
model,tok=load();original=dataset();expanded=make_rows();gates={'repro_failed':sorted(bad),'strengthened':[],'dropped':[]}
# Confidence audit repair: keep raw pre-fix traces; replace the accepted A3 cohort.
(out/'smoke-pre-confidence-fix.jsonl').write_text((out/'smoke.jsonl').read_text())
(out/'repeat-pre-confidence-fix.jsonl').write_text((out/'repeat.jsonl').read_text())
repaired=[]
for row in original:
 r=arithmetic(model,tok,row,'A3');append(out/'confidence-repair.jsonl',r);repaired.append(r)
newrepeat=[];bad.discard('A3')
for row in original[:5]:
 r=arithmetic(model,tok,row,'A3');append(out/'confidence-repair-repeat.jsonl',r);newrepeat.append(r)
 if r['text']!=repaired[row['id']]['text']:bad.add('A3')
smoke=[r for r in smoke if r['condition']!='A3']+repaired
repeat=[r for r in repeat if r['condition']!='A3']+newrepeat
(out/'smoke.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in smoke))
(out/'repeat.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in repeat))
by={(r['condition'],r['id']):r for r in smoke}
for c in ('M4','M5'):
 for row in original[:5]:
  r=arithmetic(model,tok,row,c);append(out/'repeat.jsonl',r)
  if r['text']!=by[c,row['id']]['text']:bad.add(c)
# Separate native structural editing from simply preserving the provisional draft.
for row in original:
 for c in ('A7','A8'):
  r=arithmetic(model,tok,row,'A7' if c=='A7' else 'A4',f3=False);r['condition']=c;append(out/'edit-audit.jsonl',r)
legacy=[]
for row in original:
 r=arithmetic(model,tok,row,'M1');append(out/'legacy-baseline.jsonl',r);legacy.append(r)
for row in original[:5]:
 r=arithmetic(model,tok,row,'M1');append(out/'legacy-repeat.jsonl',r)
 if r['text']!=legacy[row['id']]['text']:bad.add('M1')
# Preserve the original smoke before any single allowed prompt strengthening.
for c in ('A2','A3'):
 rs=[r for r in smoke if r['condition']==c];rate=sum(bool(r.get('calls')) for r in rs)/max(1,len(rs))
 if rate<.5:
  gates['strengthened'].append(c)
  retried=[]
  for row in original:
   r=arithmetic(model,tok,row,c,strong=True);append(out/'strengthened.jsonl',r);retried.append(r)
  if sum(bool(r.get('calls')) for r in retried)<len(retried)/2:gates['dropped'].append(c)
  for row in original[:5]:
   r=arithmetic(model,tok,row,c,strong=True);append(out/'strengthened-repeat.jsonl',r)
   if r['text']!=retried[row['id']]['text']:bad.add(c)
a5=[r for r in smoke if r['condition']=='A5' and r['kind']=='direct'];adoption=sum(r.get('reference_adopted') is True for r in a5)/max(1,len(a5));gates['A5_adoption']=adoption
if adoption<.5:gates['dropped'].append('A5')
gates['dropped']+=sorted(bad)
# Hard safety gate: never continue a condition with an observed lock/effect violation.
for r in smoke:
 if r.get('metrics',{}).get('lock_violations',0) or any(e['type'] in ('stray_effect','stale_completion') for e in r.get('events',[])):gates['dropped'].append(r['condition'])
def paired(c):
 rs=[r for r in smoke if r['condition']==c];wrong=[r for r in rs if not by['M4',r['id']]['correct']];right=[r for r in rs if by['M4',r['id']]['correct']]
 return (sum(r['correct'] for r in wrong)/len(wrong) if wrong else 0,sum(not r['correct'] for r in right))
u4,r4=paired('A4');u7,r7=paired('A7');gates['promote_A7']=u7>=u4 and r7<r4 and 'A7' not in bad
# Hidden values distinguish result use from recomputing an easy expression.
for index in range(6):
 call={'id':'functions.read_file:0','call':{'name':'read_file','args':{'path':f'lookup/item_{index}.txt'}}};result=execute(call['call']);expected=result['output'].strip()
 hist=[{'role':'system','content':'After receiving a tool result, return one line: Answer: <exact value>. Do not add explanations.'},{'role':'user','content':f'Read lookup/item_{index}.txt. Return its exact value as Answer: <value>.'}]
 for delay in (0,10,20,40):
  for f3 in (False,True):
   text,m,_=answer_stage(model,tok,hist,definitions(('read_file',)),call,ready=result,delay=delay,f3=f3)
   hits=re.findall(r'(?m)^Answer:\s*([0-9a-f]+)\s*$',text)
   append(out/'hidden-delay.jsonl',dict(id=index,delay=delay,f3=f3,text=text,expected=expected,correct=bool(hits and hits[-1]==expected),answer_present=expected in text,metrics=m))
# Retain upstream dense native messages and a larger delay-control set.
for row in original[:6]:
 hist=prompt(row,'A2');call={'id':'functions.calc:0','call':{'name':'calc','args':{'expression':f"{row['a']} {row['op']} {row['b']}"}}};result=execute(call['call'])
 for delay in (0,10,20,40):
  for f3 in (False,True):
   text,m,_=answer_stage(model,tok,hist,[CALC],call,ready=result,delay=delay,f3=f3)
   append(out/'arithmetic-delay.jsonl',dict(id=row['id'],kind=row['kind'],delay=delay,f3=f3,text=text,expected=row['expected'],**score(text,row),metrics=m))
 z=torch.tensor([ids(tok,tool_msgs(hist,call,result['output']),[CALC])],device='cuda')
 with torch.inference_mode():o=model.generate(inputs=z,gen_length=192,block_length=32,steps=8,threshold=.5,editing_threshold=0.,max_post_steps=2,max_steps_per_block=48,eos_early_stop=True,temperature=0.)[0]
 text=tok.decode(o,skip_special_tokens=True);append(out/'upstream.jsonl',dict(id=row['id'],kind=row['kind'],text=text,**score(text,row)))
for c in ('A4','A5'):
 if c in gates['dropped']:continue
 for row in original[:6]:
  for delay in (0,10,20,40):
   for f3 in (False,True):append(out/'variant-delay.jsonl',arithmetic(model,tok,row,c,delay=delay,f3=f3))
late=[r for r in map(json.loads,(out/'arithmetic-delay.jsonl').read_text().splitlines()) if r['delay']==40 and r['f3']]
if (out/'variant-delay.jsonl').exists():late += [r for r in map(json.loads,(out/'variant-delay.jsonl').read_text().splitlines()) if r['delay']==40 and r['f3']]

late += [r for r in map(json.loads,(out/'hidden-delay.jsonl').read_text().splitlines()) if r['delay']==40 and r['f3']]
gates['F3_delayed_exact_correct']=sum(r['correct'] for r in late)
if not gates['F3_delayed_exact_correct']:gates['dropped']+=['A3','A4','A5','A7']
gates['dropped']=sorted(set(gates['dropped']));(out/'gates.json').write_text(json.dumps(gates,indent=2));print('GATES '+json.dumps(gates),flush=True)
assert 'A0' not in gates['dropped'], 'Baseline failed reproducibility gate'
conditions=[c for c in ('A0','A1','M1','A2','A3','A4','A5','M4','M5') if c not in gates['dropped'] and not(c=='M5' and 'A5' in gates['dropped'])]
if gates['promote_A7'] and 'A7' not in gates['dropped']:conditions.append('A7')
for stage,block,cs in [('full',32,conditions),('mid',64,[c for c in ('A3','A4','A5') if c in conditions])]:
 existing=set()
 if (out/(stage+'.jsonl')).exists():existing={(r['id'],r['condition']) for r in map(json.loads,(out/(stage+'.jsonl')).read_text().splitlines())}
 for row in expanded:
  for c in cs:
   if (row['id'],c) in existing:continue
   r=arithmetic(model,tok,row,c,block=block,strong=c in gates['strengthened']);append(out/(stage+'.jsonl'),dict(r,set='expanded240'))
   if c=='A0':
    text=posthoc(r['text'],row['kind']);append(out/(stage+'.jsonl'),dict(id=row['id'],kind=row['kind'],condition='A6',text=text,expected=row['expected'],**score(text,row),set='expanded240'))
run_linux(model,tok,out)
print('ALL STAGES COMPLETE',flush=True)
