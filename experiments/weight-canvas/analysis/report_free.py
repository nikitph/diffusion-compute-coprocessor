import collections,hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));sys.path.insert(0,str(root/'free-program'))
from controller import metrics,scenarios,FAULTS,version
from programs import interpret
out=root/'free-program/results';rows=[json.loads(s) for s in (out/'records.jsonl').read_text().splitlines()]
groups=collections.defaultdict(list)
for r in rows:
 groups[r['condition']].append(r)
 if r['valid']:
  e=interpret(r['final_text'],r['initial']);assert e==r['final']
  assert metrics(e,r['initial'],scenarios(r['heldout_seed'],512))==r['final_metrics']
 else:assert r['deployable_caught']==0
 for part in r['parts']:
  a=part['arrival']
  if a:
   assert a['remaining_content_masks']>0
   assert version(a['candidate'])==a['candidate_hash']
   assert a['true_feedback']['candidate']==a['candidate_hash']
  assert part['lock_violations']==0
summary={}
for arm,rs in groups.items():
 summary[arm]=dict(cases=len(rs),valid=sum(r['valid'] for r in rs),improved=sum(r['deployable_caught']>r['initial_metrics']['caught'] for r in rs),
  initial_caught=sum(r['initial_metrics']['caught'] for r in rs),final_caught=sum(r['deployable_caught'] for r in rs),total=512*len(rs),
  changed=sum(r['valid'] and r['final']!=r['initial'] for r in rs),
  arrivals=sum(p['arrival'] is not None for r in rs for p in r['parts']),
  changed_after_feedback=sum(r['valid'] and r['candidate'] is not None and r['final']!=r['candidate'] for r in rs),
  calls=sum(r['forward_calls'] for r in rs),seconds=sum(r['wall_seconds'] for r in rs),
  regressions=sum(r['final_metrics']['regressions'] if r['valid'] else r['initial_metrics']['caught'] for r in rs))
(out/'summary.json').write_text(json.dumps(summary,indent=2))
lines=['# Free-program pilot v0.2 — results','',f'Completed {len(rows)}/30 runs. All inference ran locally on Apple M1 Pro, FP32. No cloud pod was started.','',
 'Exploratory follow-up after the v0.1 interface diagnostic. These six tasks were already examined in v0.1; this is not a fresh confirmatory cohort.','',
 '| Condition | Valid programs | Improved tasks | Final catches | Active arrivals | Changed after feedback |',
 '|---|---:|---:|---:|---:|---:|']
for arm in ['D-active','D-round','D-shuffled','D-none','AR-round']:
 if arm not in summary:continue
 s=summary[arm];lines.append(f"| {arm} | {s['valid']}/{s['cases']} | {s['improved']}/{s['cases']} | {s['final_caught']}/{s['total']} | {s['arrivals']} | {s['changed_after_feedback']} |")
lines+=['','**Conclusion:** no arm improved any of the six controllers. D-active and D-shuffled each retained the damaged controller in the same two tasks and produced invalid programs in the other four. The valid AR outputs all copied the damaged weights. There is no evidence here of feedback-driven repair or a diffusion advantage.']
lines+=['','Invalid programs count as zero deployable catches, not as a controller that physically missed every ball. Validity and game performance are distinct. The baseline totals 1,725/3,072 catches. There are six model repair tasks; the 3,072 situations are nested evaluation observations.','',
 '| Fault | Initial | D-active | D-round | D-shuffled | D-none | AR-round |','|---|---:|---:|---:|---:|---:|---:|']
lookup={(r['task'],r['condition']):r for r in rows}
for i,(name,e) in enumerate(FAULTS.items()):
 cells=[str(metrics(e,e,scenarios(20262104+i,512))['caught'])]
 for arm in ['D-active','D-round','D-shuffled','D-none','AR-round']:
  r=lookup.get((name,arm));cells.append('not run' if r is None else str(r['deployable_caught']) if r['valid'] else 'invalid')
 lines.append('| '+name+' | '+' | '.join(cells)+' |')
lines+=['','## Audit and limitations','',
 'Every valid saved program was independently reinterpreted and its score recomputed. Feedback hashes bind each report to its provisional controller. The decoder asserted prompt/report immutability at every step; arrivals require remaining masks before the provisional EOS.','',
 'Programs are interpreted through a bounded AST whitelist (literal E assignments and indexed integer writes). No generated code is executed through Python exec/eval. For fenced output the first code block is interpreted.','',
 'The generating model remains frozen. The target controller has only six writable weights on a five-value grid. Its architecture, output layer, and game rules are supplied; this is not unconstrained network synthesis.','',
 'Active delivery uses whole-output remasking in the same canvas, not selective semantic revision. Early feedback, total passes, message layout and masks differ from the round-based condition. The autoregressive source and diffusion adaptation have different training. These results do not isolate architecture or establish production latency gains.','',
 'The shuffled control retains truthful aggregate scores and corrupts observation/outcome pairings; it is a partial evidence control. The no-feedback arm tests whether task rules alone suffice. Report improvements only relative to both controls.','',
 'The six deliberately injected faults and one greedy run per condition are descriptive. No fine-tuning occurred. Reference-controller weights were never supplied to measured model runs.']
(root/'free-program/RESULTS.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2))
