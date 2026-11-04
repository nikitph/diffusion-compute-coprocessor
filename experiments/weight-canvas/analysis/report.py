import collections,hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from controller import REFERENCE,FAULTS,metrics,scenarios
source=root/'results/pilot/records.jsonl'
records=[json.loads(s) for s in source.read_text().splitlines()]
groups=collections.defaultdict(list)
for r in records:groups[r['condition']].append(r)
summary={}
for arm,rows in groups.items():
    total=sum(r['final_metrics']['total'] for r in rows)
    summary[arm]=dict(cases=len(rows),initial_caught=sum(r['initial_metrics']['caught'] for r in rows),
        candidate_caught=sum(r['candidate_metrics']['caught'] for r in rows),
        final_caught=sum(r['final_metrics']['caught'] for r in rows),total=total,
        improved_cases=sum(r['final_metrics']['caught']>r['initial_metrics']['caught'] for r in rows),
        regressed_cases=sum(r['final_metrics']['caught']<r['initial_metrics']['caught'] for r in rows),
        unchanged_programs=sum(r['final']==r['initial'] for r in rows),
        changed_after_feedback=sum(r['final']!=r['candidate'] for r in rows),
        fixes=sum(r['final_metrics']['fixes'] for r in rows),regressions=sum(r['final_metrics']['regressions'] for r in rows),
        forward_calls=sum(r['calls']['forward_calls'] for r in rows),
        processed_positions=sum(r['calls']['processed_positions'] for r in rows),
        inference_seconds=sum(r['calls']['inference_seconds'] for r in rows),
        wall_seconds=sum(r['wall_seconds'] for r in rows))
# Recompute every stored score from saved weights and disjoint held-out seeds.
for r in records:
    expected=metrics(r['final'],r['initial'],scenarios(r['heldout_seed'],512))
    assert expected==r['final_metrics']
    assert r['true_feedback']['candidate']==__import__('controller').version(r['candidate'])
    arrivals=[e for e in r['events'] if e['type']=='feedback_arrival']
    for e in arrivals:
        assert e['remaining_masks_before']==3
    assert r['lock_violations']==0
out=root/'results';(out/'summary.json').write_text(json.dumps(summary,indent=2))
lines=['# Weight canvas — local pilot results','',
       'Measured constrained weight-repair pilot on an Apple M1 Pro (16 GB). No cloud GPU was started.','',
       f'Completed records: {len(records)}/30. Six faults, 512 held-out situations per fault; these are six repair tasks, not 3,072 independent model trials.','',
       '| Condition | Improved tasks | Final catches | Changed after feedback | Regressions on previously caught situations | Forward calls |',
       '|---|---:|---:|---:|---:|---:|']
for arm in ['D-active','D-round','D-shuffled','D-none','AR-round']:
    if arm not in summary:continue
    s=summary[arm];lines.append(f"| {arm} | {s['improved_cases']}/{s['cases']} | {s['final_caught']}/{s['total']} | {s['changed_after_feedback']}/{s['cases']} | {s['regressions']} | {s['forward_calls']} |")
lines+=['','**Conclusion:** all 30 constrained runs reproduced the damaged weights unchanged. This pilot provides no evidence of feedback-driven repair or a diffusion advantage. A post-pilot unrestricted diagnostic succeeded at an explicit two-assignment repair, so the constrained interface is a material limitation; do not infer that the model cannot write weight edits at all.']
lines+=['','## Per-task results','', '| Fault | Initial | D-active | D-round | D-shuffled | D-none | AR-round |','|---|---:|---:|---:|---:|---:|---:|']
lookup={(r['task'],r['condition']):r for r in records}
for i,(fault,initial) in enumerate(FAULTS.items()):
    cells=[str(metrics(initial,initial,scenarios(20262104+i,512))['caught'])]
    for arm in ['D-active','D-round','D-shuffled','D-none','AR-round']:
        r=lookup.get((fault,arm));cells.append(str(r['final_metrics']['caught']) if r else 'not run')
    lines.append('| '+fault+' | '+' | '.join(cells)+' |')
lines+=['','## What this tests','',
        'The runtime evaluates a provisional six-weight controller while three slots are still masked. It writes versioned feedback after the weight program, locks that feedback, reopens the six weights, and continues in the same canvas. All fixed syntax and reports are checked for immutability each denoising step.','',
        'This is numeric inpainting inside a fixed Python weight-assignment scaffold. The decoder is restricted to five digits per weight; the runtime subtracts two to represent signed weights. It is not unrestricted code synthesis, a learned execution trigger, selective invalidation, or self-modification of the generating model.','',
        'No gradient updates, reference-weight substitution, best-of search, or held-out feedback were used. All results are the model-produced final candidate, including regressions.','',
        'D-active/D-shuffled/D-none use 9 forward passes; D-round and AR-round use 12. Early feedback and schedule differ. AR prefixes are recomputed without KV caching, so wall-time comparisons are not optimized architecture benchmarks.','',
        'The diffusion model is an adapted Qwen2.5-Coder-0.5B checkpoint; the AR model is its original instruction-tuned source. Additional diffusion fine-tuning confounds architecture comparisons. D-shuffled scrambles observation/outcome alignment but retains the true aggregate score, so it is not a complete information ablation.','',
        'The evaluator independently recomputed every saved final score. Environment tests include a 10,000-situation reference-controller check and an independently derived action-policy check.','',
        'See `PROTOCOL.md`, `results/pilot/source-manifest.json`, pinned environment files, complete step canvases in `records.jsonl`, and `summary.json`.']
(root/'RESULTS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2))
