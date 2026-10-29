import json,pathlib,collections
root=pathlib.Path('/Users/nikitph/Documents/Codex/2026-10-28/can/outputs/v1.1-pilot/results')
for name in ('contract-smoke','contract-strengthened','contract-repeat','arithmetic-delay','variant-delay','full','mid','linux','cross-host-repeat'):
 p=root/(name+'.jsonl')
 if not p.exists():continue
 rs=[]
 for l in p.read_text().splitlines():
  try:rs.append(json.loads(l))
  except ValueError:pass
 d=collections.defaultdict(list)
 for r in rs:d[r.get('condition','control')].append(r)
 print(name,{k:{'n':len(v),'correct':sum(bool(r.get('correct')) for r in v),'calls':sum(bool(r.get('calls')) for r in v)} for k,v in d.items()})
p=root/'gates.json'
if p.exists():print('gates',p.read_text())
