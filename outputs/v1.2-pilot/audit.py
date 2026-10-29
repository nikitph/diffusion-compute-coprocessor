"""Independent local integrity and invariant audit of recorded evidence."""
import pathlib,json,hashlib,collections
ROOT=pathlib.Path(__file__).resolve().parent;R=ROOT/'results-v1.2'
def read(k):
 p=R/(k+'.jsonl');return list(map(json.loads,p.read_text().splitlines())) if p.exists() else []
def ms(r):return [r['metrics']] if 'metrics' in r else [t[k] for t in r.get('rounds',[]) for k in ('first','second') if k in t]
def events(r):return [e for m in ms(r) for e in m.get('events',[])]
def main():
 counts={};duplicates=[];safety=[];pauses=[];calcs=[];missing=[];write_checks=[]
 for stage,n in {'delay':144,'linux':108,'full':720,'mid':240,'prerequisite-smoke':108,'prerequisite-reproduction':5}.items():
  rows=read(stage);counts[stage]=dict(actual=len(rows),expected=n);seen=set()
  for r in rows:
   key=(r.get('kind') if stage=='delay' else '',r['id'],r['condition'],r.get('delay',0),r.get('block',32))
   if key in seen:duplicates.append([stage,key])
   seen.add(key)
   ident=dict(stage=stage,id=r['id'],condition=r['condition'],delay=r.get('delay',0))
   ev=events(r)
   for m in ms(r):
    for k in ('lock_violations','residual_masks','pending_at_end','step_budget_exhausted'):
     if m.get(k):safety.append(dict(**ident,issue=k,value=m[k]))
   for e in ev:
    if e['type']=='pause':pauses.append(dict(**ident,exact=e['state_before']==e['state_after'],same_step=e['dispatch_step']==e['lock_step'],wait_seconds=e['wait_seconds']))
    if e['type']=='remask' and r['condition'] in ('D3','L3','A7W'):safety.append(dict(**ident,issue='wait_remasked'))
   for e in r.get('injection_events',[]):
    if all(k in e for k in ('a','b','op','value')):
     a,b,op=e['a'],e['b'],e['op'];expected={'+':a+b,'-':a-b,'*':a*b}[op]
     calcs.append(dict(**ident,exact=str(expected)==e['value']))
   if stage=='linux' and r.get('kind')=='write':
    receipts=[(c,t) for c,t in zip(r['calls'],r['rounds']) if c['call']['name']=='write_file' and c['call']['args']=={'path':'model_writes/native.txt','data':'native-written-7319'} and (t.get('result') or {}).get('ok')]
    write_checks.append(dict(**ident,scored_correct=r['correct'],matching_receipt=bool(receipts),strict=r.get('strict')))
 freeze=R/'frozen-source-manifest.json';source={}
 if freeze.exists():
  for name,digest in json.loads(freeze.read_text())['files'].items():
   p=ROOT/name;source[name]=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==digest if name!='local-processes.json' else 'local process IDs are mutable orchestration metadata, not runtime source'
 else:missing.append('frozen-source-manifest')
 ws=ROOT.parent/'syscall-pilot/workspace';before=json.load(open(ROOT/'workspace-before.json'));after={str(p.relative_to(ws)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ws.rglob('*') if p.is_file()};changed=[p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]
 result=dict(counts=counts,duplicates=duplicates,safety_findings=safety,pause_count=len(pauses),pause_checks_all_pass=all(x['exact'] and x['same_step'] for x in pauses),kernel_values_checked=len(calcs),kernel_all_exact=all(x['exact'] for x in calcs),source_hashes_match=source,missing=missing,write_checks=write_checks,workspace_changes=changed,unexpected_workspace_changes=[x for x in changed if x!='model_writes/native.txt'])
 (R/'independent-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
