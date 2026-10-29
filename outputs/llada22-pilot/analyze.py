import json,pathlib,statistics,collections
root=pathlib.Path(__file__).parent/'mini-results'
def read(name):
 p=root/name
 return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
tools=read('tools.jsonl');arith=read('arithmetic.jsonl');dense=read('dense-controls.jsonl')
summary={}
for label,rows in [('tools',tools),('dense_controls',dense)]:
 summary[label]={}
 for condition in sorted({r['condition'] for r in rows}):
  rs=[r for r in rows if r['condition']==condition]
  summary[label][condition]={'n':len(rs),'exact':sum(r['correct'] for r in rs),'answer_present':sum(r['contains_expected'] for r in rs),'valid_calls':sum(r.get('valid_native_call',False) for r in rs),'received':sum(r.get('result_received',False) for r in rs),'mean_seconds':statistics.mean(r['seconds']+r.get('finalization_seconds',0) for r in rs)}
summary['arithmetic']={}
summary['read_compute_tasks']={}
for condition in ('base','conventional','async'):
 rs=[r for r in tools if r['condition']==condition and r['kind']!='write']
 summary['read_compute_tasks'][condition]={'n':len(rs),'exact':sum(r['correct'] for r in rs),'answer_present':sum(r['contains_expected'] for r in rs)}
summary['write_task']={r['condition']:{'answer_correct':r['correct'],'executed_successfully':bool(r.get('tool_result',{}).get('ok',False))} for r in tools if r['kind']=='write'}
for condition in sorted({r['condition'] for r in arith}):
 rs=[r for r in arith if r['condition']==condition]
 summary['arithmetic'][condition]={k:{'correct':sum(r['correct'] for r in rs if r['kind']==k),'n':sum(r['kind']==k for r in rs)} for k in ('direct','dependent')}
 if condition!='posthoc':summary['arithmetic'][condition]['sampling_seconds']=sum(r['metrics']['seconds'] for r in rs)
 if condition=='mid':
  events=[e for r in rs for e in r['injection_events'] if e['status']=='injected']
  summary['arithmetic'][condition]['injections']=len(events)
  summary['arithmetic'][condition]['matching_operands']=sum(e['operand_match'] for e in events)
summary['async']={'injected_answer_steps':[r['result_injected_answer_step'] for r in tools if r['condition']=='async' and r.get('result_injected_answer_step') is not None],
 'event_counts':dict(collections.Counter(e['type'] for r in tools if r['condition']=='async' for e in r.get('events',[]))),
 'effect_submissions':[e for r in tools for e in r.get('events',[]) if e['type']=='submit' and e['effect']],
 'lock_violations':sum(r.get('second',{}).get('lock_violations',0)+r.get('first',{}).get('lock_violations',0) for r in tools)}
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
