from pathlib import Path
p=Path('outputs/v1.2-pilot/report.py');s=p.read_text()
s=s.replace("data={k:read(k) for k in ('delay','linux','full','mid')};allrs=sum(data.values(),[])","""data={k:read(k) for k in ('delay','linux','full','mid')};raw_counts={k:len(v) for k,v in data.items()};stopped=(R/'calibration-final.json').exists()
 if stopped:
  cohort=collections.defaultdict(set)
  for row in data['linux']:cohort[row['id']].add(row['condition'])
  included={i for i,cs in cohort.items() if cs=={'L0','L1','L2','L3'}}
  data['linux']=[r for r in data['linux'] if r['id'] in included]
 allrs=sum(data.values(),[])""")
s=s.replace("('Completed measured experiment.' if complete else 'INCOMPLETE: measured results are not final.')", "('Final calibration from the preserved interrupted run. The user requested stopping here rather than recharging and resuming.' if stopped else ('Completed measured experiment.' if complete else 'INCOMPLETE: measured results are not final.'))")
needle=" if not complete:\n  lines+=['Current counts: '"
s=s.replace(needle," if not complete:\n  lines+=['Raw records preserved: '+', '.join(f'{k} {n}' for k,n in raw_counts.items())+'. One unmatched L0 record (task 214) is excluded from Linux comparisons.' if stopped else 'Run still in progress.','']\n  lines+=['Analysed counts: '")
# Report actual completed cohort denominators.
s=s.replace("'| Condition | Prior 7 | Multi-call 20 | Strict / 27 | Actual dispatches |'", "'| Condition | Prior tasks | Matched multi-call tasks | Strict / matched total | Actual dispatches |'")
needle=" lines += ['## Delayed result controls'"
idx=s.index(needle)
preamble=""" if stopped:
  lines+=['## Calibrated conclusion','','**Waiting is a working scheduling and insertion mechanism, but these data do not justify making it the default.** The pause removes delay-dependent changes: all 12 delayed-control task groups have identical paused states and outputs across all four delays. It does not reliably produce the requested final answer.','','On the 14 fully matched multi-call Linux tasks, waiting and conventional execution succeed on the same 3 tasks; async succeeds on 1. Waiting fixes two async failures and loses none. The remaining six multi-call tasks and both 240-prompt arithmetic stages were not completed. This is a descriptive partial cohort, not a full H1 result.','','All 24 waiting arithmetic-control outputs contain the returned integer, but the 12 comparison outputs issue unsupported `>` calls instead of YES/NO. Hidden-file waiting outputs contain the exact value in 20/24 cases and meet the strict format in 16/24. Do not conflate these contract failures with an inability to read the injected value.','','The 36-prompt smoke set is encouraging for supplied arithmetic slots: A7W and A7 have identical text on 36/36 prompts, both score 18/18 direct and 18/18 downstream; M4 scores 10/18 and 11/18. This is prerequisite evidence, not a substitute for H4\'s 240-task test.','','**Placement limit:** native L3 dispatched 28/29 calls before commitment, but 0/29 arrivals had masks in the result\'s own block. The supplied-call D3 controls had 48/48 such masked-block arrivals; A7W smoke had 15/36. These are different placements. Block-64 A7W was not run, so v1.2 does not establish H5.','','Both experiment pods are verified stopped. Retained persistent disks still incur storage charges.','']
"""
s=s[:idx]+preamble+s[idx:]
# Replace apostrophes in single-quoted inserted strings safely.
s=s.replace("H4's 240-task", "the 240-task H4").replace("the result's own", "the result’s own")
needle=" lines+=['','## Pre-registered gates','']"
idx=s.index(needle)
insert=""" if stopped:
  observed_gates={'H1':'Not fully evaluated: matched subset 3/14 wait = 3/14 conventional > 1/14 async; six tasks missing','H2':'PASS: wait 4/7 = conventional 4/7','H3':'FAIL: wait hidden 4/6 and arithmetic 3/6 at every delay','H4':'NOT RUN: 240-task comparison absent; smoke only','H5':'NOT RUN: block-64 comparison absent','H6':'Observed counters clean; full planned matrix incomplete'}
  dump('calibrated-gates.json',observed_gates)
"""
s=s[:idx]+insert+s[idx:]
s=s.replace("if not gates:lines.append('Pending completion and prerequisite checks.')", "if not gates:\n  lines.extend([f'- {k}: {v}' for k,v in observed_gates.items()] if stopped else ['Pending completion and prerequisite checks.'])")
s=s.replace("if w else 'pending'", "if w else 'not evaluated in matched cohort'")
needle=" lines+=['','L1 accepts parsed final calls"
idx=s.index(needle)
conclusion=""" if stopped:
  lines.append('Waiting should remain an available mechanism, not the established default. The evidence supports exact pause/resume behavior, latency-invariant outputs, successful active-canvas tool chains, and no observed safety violations. It does not support the broader claim that non-waiting caused all prior failures: malformed calls, invalid argument schemas, unnecessary extra calls, and missing final answers persist after results arrive. Async has two additional failures on the completed matched subset, but its speed/quality tradeoff remains unmeasured. The next question is which continuation and tool-contract behavior fails after a correct result is available; these data do not establish that fine-tuning is necessary.')
"""
s=s[:idx]+conclusion+s[idx:]
p.write_text(s)
