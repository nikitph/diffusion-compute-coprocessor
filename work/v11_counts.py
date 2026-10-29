import json,pathlib,collections
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can/outputs/v1.1-pilot/results')
for name in ('full','mid','linux','cross-host-repeat'):
 p=root/(name+'.jsonl')
 if not p.exists():continue
 rs=[]
 for l in p.read_text().splitlines():
  try:rs.append(json.loads(l))
  except ValueError:pass
 if name=='mid' and len(rs)==480:
  print('mid COMPLETE: 480 records');continue
 if name=='full' and len(rs)==2160:
  print('full COMPLETE: 2160 records');continue
 print(name,len(rs),dict(collections.Counter(x['condition'] for x in rs)))
 if rs:print('last', {k:rs[-1].get(k) for k in ('id','condition','seconds')})
 if name in ('full','mid'):
  print('safety',{'locks':sum(r.get('metrics',{}).get('lock_violations',0) for r in rs),'stray':sum(e['type']=='stray_effect' for r in rs for e in r.get('events',[])),'stale':sum(e['type']=='stale_completion' for r in rs for e in r.get('events',[]))})

  ms=[m for r in rs for m in ([r.get('metrics',{})]+[t.get(k,{}) for t in r.get('rounds',[]) for k in ('first','second')])]
  print('sampler ceilings',sum(bool(m.get('step_budget_exhausted')) for m in ms),'pending',sum(bool(m.get('pending_at_end')) for m in ms))
