"""Paired analysis. Direct n=120 in the 240-task set; no fabricated n=240 test."""
import json,pathlib,math,collections
root=pathlib.Path(__file__).parent/'results'
def read(name):
 p=root/(name+'.jsonl');rs=[json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
 if name=='linux':
  for r in rs:
   r['accepted_calls']=r['calls_count'];r['calls_count']=sum(e['type']=='submit' for e in r.get('events',[])) if r['condition'].startswith('async') else r['calls_count']
   if r['kind']=='write':
    calls=[c['call'] for c in r.get('calls',[])];valid=bool(calls) and all(c['name']=='write_file' and c['args'].get('path')=='model_writes/native.txt' and c['args'].get('data')=='native-written-7319' for c in calls)
    executed=any((t.get('result') or {}).get('ok') for t in r.get('rounds',[]))
    r['raw_correct']=r['correct'];r['correct']=r['answer_present'] and valid and executed
  if rs:(root/'evaluated-linux.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rs))
 return rs
def exact_mcnemar(b,c):
 n=b+c
 return min(1.,2*sum(math.comb(n,k) for k in range(min(b,c)+1))/2**n) if n else 1.
def analyze(rows):
 by=collections.defaultdict(dict)
 for r in rows:by[r['condition']][r['id']]=r
 result={}
 for c,group in by.items():
  baseline=by.get('M1' if c=='A1' else 'M5' if c=='A5' else 'M4' if c in ('A4','A7') else 'A0',by.get('A0',{}));rs=list(group.values());eligible=len(rs)
  fired=[r for r in rs if any(e.get('status')=='injected' for e in r.get('injection_events',[]))]
  wrongfires=[r for r in fired if r['id'] in baseline and not baseline[r['id']]['correct']]
  fixed=[r for r in wrongfires if r['correct']];rightbase=[r for r in rs if r['id'] in baseline and baseline[r['id']]['correct']];regress=[r for r in rightbase if not r['correct']]
  arrivals=[e for r in rs for e in r.get('metrics',{}).get('events',[]) if e['type']=='arrival']
  failures=collections.Counter()
  for r in rs:
   ev=r.get('injection_events',[])
   if not any(e.get('status')=='injected' for e in ev):
    causes={e.get('status') for e in ev}
    failures['occupied' if 'occupied_slot' in causes else 'too_short' if 'length_failure' in causes else 'late' if r.get('metrics',{}).get('pending_at_end') else 'absent']+=1
  d={'n':eligible,'fired':len(fired),'firing_rate':len(fired)/eligible,'use_numerator':len(fixed),'use_denominator':len(wrongfires),'use_rate':len(fixed)/len(wrongfires) if wrongfires else None,'regressions':len(regress),'right_base':len(rightbase),'regression_rate':len(regress)/len(rightbase) if rightbase else None,'failed_opportunities':dict(failures),'midblock':sum(e['midblock'] for e in arrivals),'arrivals':len(arrivals),'remasks':sum(e['type']=='remask' for r in rs for e in r.get('metrics',{}).get('events',[])),'lock_violations':sum(r.get('metrics',{}).get('lock_violations',0) for r in rs),'seconds':sum(r.get('seconds',0) for r in rs)}
  for kind in ('direct','dependent'):
   subset=[r for r in rs if r['kind']==kind];pairs=[r for r in subset if r['id'] in baseline];better=sum(r['correct'] and not baseline[r['id']]['correct'] for r in pairs);worse=sum(not r['correct'] and baseline[r['id']]['correct'] for r in pairs)
   d[kind]={'correct':sum(r['correct'] for r in subset),'n':len(subset),'paired_n':len(pairs),'wrong_to_right':better,'right_to_wrong':worse,'exact_mcnemar_p':exact_mcnemar(better,worse)}
  d['injected_operand_errors']=sum(e.get('status')=='injected' and not e.get('operand_match',True) for r in rs for e in r.get('injection_events',[]))
  d['stale_completions']=sum(e['type']=='stale_completion' for r in rs for e in r.get('events',[]))
  d['stray_effects']=sum(e['type']=='stray_effect' for r in rs for e in r.get('events',[]))
  d['midblock_before_eos']=sum(e.get('midblock_before_eos',False) for e in arrivals)
  if c=='A5':d['reference_adoption']=sum(r.get('reference_adopted') is True for r in rs if r['kind']=='direct')/max(1,sum(r['kind']=='direct' for r in rs))
  a0=by.get('A0',{});pairs=[r for r in rs if r['kind']=='direct' and r['id'] in a0];b=sum(r['correct'] and not a0[r['id']]['correct'] for r in pairs);w=sum(not r['correct'] and a0[r['id']]['correct'] for r in pairs)
  d['direct_vs_A0']={'paired_n':len(pairs),'wrong_to_right':b,'right_to_wrong':w,'exact_mcnemar_p':exact_mcnemar(b,w)}
  result[c]=d
 return result
summary={s:analyze(read(s)+(read('legacy-baseline') if s=='smoke' else [])) for s in ('smoke','full','mid')}
smoke={(r['condition'],r['id']):r for r in read('smoke')};rep=read('repeat');summary['reproducibility']={'n':len(rep),'identical':sum(smoke.get((r['condition'],r['id']),{}).get('text')==r['text'] for r in rep),'mismatches':[{'condition':r['condition'],'id':r['id']} for r in rep if smoke.get((r['condition'],r['id']),{}).get('text')!=r['text']]}
summary['delay']=[{'delay':r['delay'],'f3':r['f3'],'used':r['used'],'remasks':r['metrics'].get('remask_count'),'lock_violations':r['metrics'].get('lock_violations')} for r in read('delay')]
summary['linux']={}
for c in sorted({r['condition'] for r in read('linux')}):
 rs=[r for r in read('linux') if r['condition']==c];summary['linux'][c]={}
 for group in ('one','multi'):
  ss=[r for r in rs if (r['minimum_calls']==1)==(group=='one')];summary['linux'][c][group]={'n':len(ss),'correct':sum(r['correct'] for r in ss),'strict':sum(r['strict'] for r in ss),'calls':sum(r['calls_count'] for r in ss),'seconds':sum(r['seconds'] for r in ss)}
(root/'analysis.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
