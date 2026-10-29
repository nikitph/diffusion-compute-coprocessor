"""Flatten saved call/lock events without changing raw model outputs."""
import pathlib,json
ROOT=pathlib.Path(__file__).resolve().parent;R=ROOT/'results-v1.2'
def main():
 records=[]
 for stage in ('delay','linux','full','mid'):
  p=R/(stage+'.jsonl')
  if not p.exists():continue
  for r in map(json.loads,p.read_text().splitlines()):
   ms=[r['metrics']] if 'metrics' in r else [t[k] for t in r.get('rounds',[]) for k in ('first','second') if k in t]
   ev=[e for m in ms for e in m.get('events',[])];pauses=[(i,e) for i,e in enumerate(ev) if e['type']=='pause']
   calls=[]
   for i,e in pauses:
    arrival=next((x for x in ev[i+1:] if x['type']=='arrival' and x['result']==e['result']),None)
    calls.append(dict(result=e['result'],dispatch_step=e['dispatch_step'],dispatch_wall_time=e['dispatch_wall_time'],wait_seconds=e['wait_seconds'],lock_step=e['lock_step'],local_step=e['local_step'],canvas_unchanged=e['state_before']==e['state_after'],result_block_masked=arrival['midblock'] if arrival else None,result_block_masked_before_eos=arrival['midblock_before_eos'] if arrival else None,lock_state=arrival.get('lock_state') if arrival else None))
   if pauses:
    records.append(dict(stage=stage,id=r['id'],condition=r['condition'],kind=r.get('kind'),block=r.get('block',32),delay=r.get('delay',0),correct=r['correct'],strict=r.get('strict'),calls_made=r['calls_count'],rounds_used=r['rounds_used'],per_call=calls,timing=r['timing'],safety=r['safety']))
 (R/'wait-call-metrics.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
 print(json.dumps(dict(wait_records=len(records),wait_calls=sum(len(r['per_call']) for r in records))))
if __name__=='__main__':main()
