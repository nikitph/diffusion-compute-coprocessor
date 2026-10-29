"""Check retained smoke controls on the replacement A100 after the main run."""
from pilot import *
out=pathlib.Path('results')
def read(name):
 p=out/(name+'.jsonl');return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
gates=json.loads((out/'gates.json').read_text());old={(r['condition'],r['id']):r for name in ('smoke','legacy-baseline') for r in read(name)}
existing={(r['condition'],r['id']) for r in read('cross-host-repeat')}
model,tok=load()
for c in ('A0','A1','M1','A4','M4','A7'):
 if c in gates['dropped'] or (c=='A7' and not gates['promote_A7']):continue
 for row in dataset()[:5]:
  if (c,row['id']) in existing:continue
  r=arithmetic(model,tok,row,c);r['prior_host_text']=old[c,row['id']]['text'];r['matches_prior_host']=r['text']==r['prior_host_text'];append(out/'cross-host-repeat.jsonl',r)
rs=read('cross-host-repeat');report={'n':len(rs),'identical':sum(r['matches_prior_host'] for r in rs),'mismatches':[{'condition':r['condition'],'id':r['id']} for r in rs if not r['matches_prior_host']]}
(out/'cross-host-verification.json').write_text(json.dumps(report,indent=2));print('CROSS HOST COMPLETE '+json.dumps(report),flush=True)
