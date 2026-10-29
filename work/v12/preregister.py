import json,pathlib,hashlib
src=pathlib.Path('outputs/v1.1-pilot/results');dst=pathlib.Path('outputs/v1.2-pilot')
rows=[json.loads(x) for x in (src/'full.jsonl').read_text().splitlines()]
selected=[r for r in rows if r['condition']=='A7']
secs=sum(r['metrics']['seconds'] for r in selected);steps=sum(r['metrics']['forward_calls'] for r in selected)
(dst/'v11-reference.json').write_text(json.dumps({'A7_first5_smoke':[r for r in map(json.loads,(src/'smoke.jsonl').read_text().splitlines()) if r['condition']=='A7' and r['id']<5],'delay_calibration':{'cohort':'v1.1 full A7, all 240 records','seconds':secs,'forward_calls':steps,'mean_step_seconds':secs/steps,'definition':'sum sampler seconds / sum forward calls; includes sampler overhead and near-instant arithmetic insertion, no artificial delayed controls','source_sha256':hashlib.sha256((src/'full.jsonl').read_bytes()).hexdigest()}},indent=2))
print(secs/steps)
