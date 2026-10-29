"""Resume the audited smoke run after clarifying calc's supported operations."""
from pilot import *
from linux_runner import run_linux
out=pathlib.Path('results');original=dataset();expanded=make_rows()
def read(name):
 p=out/(name+'.jsonl');return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def save(name,rs):(out/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rs))
smoke=read('smoke');repeat=read('repeat');assert len(smoke)==324 and len(repeat)==45
save('smoke-pre-contract',smoke);save('repeat-pre-contract',repeat)
model,tok=load();gates={'strengthened':[],'native_rates':{},'dropped':[],'contract_clarified':True};accepted=[];newrepeat=[]
for c in ('A2','A3'):
 rs=[]
 for row in original:
  r=arithmetic(model,tok,row,c);append(out/'contract-smoke.jsonl',r);rs.append(r)
 rate=sum(bool(r.get('calls')) for r in rs)/36;gates['native_rates'][c]={'default':rate}
 strong=rate<.5
 if strong:
  gates['strengthened'].append(c);rs=[]
  for row in original:
   r=arithmetic(model,tok,row,c,strong=True);append(out/'contract-strengthened.jsonl',r);rs.append(r)
  rate=sum(bool(r.get('calls')) for r in rs)/36;gates['native_rates'][c]['strengthened']=rate
 if rate<.5:gates['dropped'].append(c)
 accepted+=rs
 for row in original[:5]:
  r=arithmetic(model,tok,row,c,strong=strong);append(out/'contract-repeat.jsonl',r);newrepeat.append(r)
smoke=[r for r in smoke if r['condition'] not in ('A2','A3')]+accepted
repeat=[r for r in repeat if r['condition'] not in ('A2','A3')]+newrepeat
save('smoke',smoke);save('repeat',repeat);by={(r['condition'],r['id']):r for r in smoke}
bad={r['condition'] for r in repeat if by[r['condition'],r['id']]['text']!=r['text']}
legacy={r['id']:r for r in read('legacy-baseline')}
for r in read('legacy-repeat'):
 if legacy[r['id']]['text']!=r['text']:bad.add('M1')
gates['repro_failed']=sorted(bad);gates['dropped']+=sorted(bad)
a5=[r for r in smoke if r['condition']=='A5' and r['kind']=='direct'];gates['A5_adoption']=sum(r.get('reference_adopted') is True for r in a5)/len(a5)
if gates['A5_adoption']<.5:gates['dropped'].append('A5')
for r in smoke:
 if r.get('metrics',{}).get('lock_violations',0) or any(e['type'] in ('stray_effect','stale_completion') for e in r.get('events',[])):gates['dropped'].append(r['condition'])
def paired(c):
 rs=[r for r in smoke if r['condition']==c];wrong=[r for r in rs if not by['M4',r['id']]['correct']];right=[r for r in rs if by['M4',r['id']]['correct']]
 return sum(r['correct'] for r in wrong)/len(wrong),sum(not r['correct'] for r in right)
u4,r4=paired('A4');u7,r7=paired('A7');gates['promote_A7']=u7>=u4 and r7<r4 and 'A7' not in bad
# Supersede only the affected native arithmetic controls. Hidden files and slots remain valid.
for name in ('arithmetic-delay','upstream'):
 old=read(name)
 if old:save(name+'-pre-contract',old);save(name,[])
for row in original[:6]:
 hist=prompt(row,'A2','A2' in gates['strengthened']);call={'id':'functions.calc:3','call':{'name':'calc','args':{'expression':f"{row['a']} {row['op']} {row['b']}"}}};result=execute(call['call'])
 for delay in (0,10,20,40):
  for f3 in (False,True):
   text,m,_=answer_stage(model,tok,hist,[CALC],call,ready=result,delay=delay,f3=f3)
   append(out/'arithmetic-delay.jsonl',dict(id=row['id'],kind=row['kind'],delay=delay,f3=f3,text=text,expected=row['expected'],**score(text,row),metrics=m))
 z=torch.tensor([ids(tok,tool_msgs(hist,call,result['output']),[CALC])],device='cuda')
 with torch.inference_mode():o=model.generate(inputs=z,gen_length=192,block_length=32,steps=8,threshold=.5,editing_threshold=0.,max_post_steps=2,max_steps_per_block=48,eos_early_stop=True,temperature=0.)[0]
 text=tok.decode(o,skip_special_tokens=True);append(out/'upstream.jsonl',dict(id=row['id'],kind=row['kind'],text=text,**score(text,row)))
existing={(r['condition'],r['id'],r['delay'],r['f3']) for r in read('variant-delay')}
for c in ('A4','A5'):
 if c in gates['dropped']:continue
 for row in original[:6]:
  for delay in (0,10,20,40):
   for f3 in (False,True):
    if (c,row['id'],delay,f3) not in existing:append(out/'variant-delay.jsonl',arithmetic(model,tok,row,c,delay=delay,f3=f3))
late=[r for name in ('hidden-delay','arithmetic-delay','variant-delay') for r in read(name) if r['delay']==40 and r['f3']]
gates['F3_delayed_exact_correct']=sum(r['correct'] for r in late)
if not gates['F3_delayed_exact_correct']:gates['dropped']+=['A3','A4','A5','A7']
gates['dropped']=sorted(set(gates['dropped']));(out/'gates.json').write_text(json.dumps(gates,indent=2));print('GATES '+json.dumps(gates),flush=True)
assert 'A0' not in gates['dropped'],'Baseline failed repeat check'
conditions=[c for c in ('A0','A1','M1','A2','A3','A4','A5','M4','M5') if c not in gates['dropped'] and not(c=='M5' and 'A5' in gates['dropped'])]
if gates['promote_A7'] and 'A7' not in gates['dropped']:conditions.append('A7')
for stage,block,cs in [('full',32,conditions),('mid',64,[c for c in ('A3','A4','A5') if c in conditions])]:
 existing={(r['id'],r['condition']) for r in read(stage)}
 for row in expanded:
  for c in cs:
   if (row['id'],c) in existing:continue
   r=arithmetic(model,tok,row,c,block=block,strong=c in gates['strengthened']);append(out/(stage+'.jsonl'),dict(r,set='expanded240'))
   if c=='A0':
    text=posthoc(r['text'],row['kind']);append(out/(stage+'.jsonl'),dict(id=row['id'],kind=row['kind'],condition='A6',text=text,expected=row['expected'],**score(text,row),set='expanded240'))
run_linux(model,tok,out)
print('ALL STAGES COMPLETE',flush=True)
