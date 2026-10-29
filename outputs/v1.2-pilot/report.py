"""Auditable post-run analysis. No model execution or rescoring from tool results."""
import json,pathlib,collections,math,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parent;R=ROOT/'results-v1.2'
def read(name):
 p=R/(name+'.jsonl');return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def dump(name,value):(R/name).write_text(json.dumps(value,indent=2))
def metrics(r):
 if 'metrics' in r:return [r['metrics']]
 return [t[k] for t in r.get('rounds',[]) for k in ('first','second') if k in t]
def events(r):return [e for m in metrics(r) for e in m.get('events',[])]
def counts(rs):return dict(n=len(rs),correct=sum(bool(r['correct']) for r in rs),strict=sum(bool(r.get('strict')) for r in rs),calls=sum(r.get('calls_count',0) for r in rs),seconds=sum(r.get('seconds',0) for r in rs),wait_seconds=sum(r.get('timing',{}).get('wait_seconds',0) for r in rs))
def pair(a,b):
 aa={r['id']:r for r in a};bb={r['id']:r for r in b};both=set(aa)&set(bb)
 cells=collections.Counter((bool(aa[i]['correct']),bool(bb[i]['correct'])) for i in both)
 wins=cells[False,True];losses=cells[True,False];n=wins+losses
 p=min(1.,2*sum(math.comb(n,k) for k in range(min(wins,losses)+1))/2**n) if n else 1.
 if not both:p=None
 return dict(n=len(both),both_correct=cells[True,True],both_wrong=cells[False,False],b_fixes=wins,b_regresses=losses,exact_two_sided_mcnemar=p)
def failures(r):
 if r['correct']:return 'success'
 text=r['text'];calls=r.get('calls',[]);results=[t.get('result') for t in r.get('rounds',[]) if t.get('result')]
 if r.get('safety',{}).get('residual_masks'):return 'incomplete decoding (residual masks)'
 if any(m.get('step_budget_exhausted') for m in metrics(r)):return 'forward-step ceiling exhausted'
 if any(r['expected'] in str(t.get('output','')) for t in results):return 'final value obtained; continued calls or missing/incorrect final answer'
 from native_tools import PATTERN
 from call_parser import validate
 candidates=[];bad_json=False
 for m in PATTERN.finditer(text):
  try:candidates.append({'name':m[2],'args':json.loads(m[3])})
  except ValueError:bad_json=True
 if any(c['name']=='run' and isinstance(c['args'],dict) and isinstance(c['args'].get('cmd'),str) for c in candidates):return 'invalid run schema: cmd is a string, required array'
 errors=[t.get('output','') for t in results if not t.get('ok')]
 if errors:return 'tool error from chosen arguments: '+str(errors[-1]).replace('\n',' ')[:110]
 if len(calls)>=4:
  lengths=[c['call']['args'].get('length') for c in calls if c['call']['name']=='read_file']
  if lengths and any(isinstance(v,int) and v<=1 for v in lengths):return 'four-call budget exhausted with insufficient/repeated reads'
  return 'four-call budget exhausted before obtaining final value'
 if bad_json or ('<|tool_call_begin|>' in text and not candidates):return 'malformed/incomplete native call or JSON'
 if candidates and not any(validate(c) for c in candidates):return 'invalid tool name or argument schema'
 if any(validate(c) for c in candidates):return 'valid-looking continuation not dispatched; rejected-trigger details not logged'
 if not calls:return 'no tool call generated'
 return 'chain stopped before final value; no valid continuation'
def main():
 data={k:read(k) for k in ('delay','linux','full','mid')};raw_counts={k:len(v) for k,v in data.items()};stopped=(R/'calibration-final.json').exists()
 if stopped:
  cohort=collections.defaultdict(set)
  for row in data['linux']:cohort[row['id']].add(row['condition'])
  included={i for i,cs in cohort.items() if cs=={'L0','L1','L2','L3'}}
  data['linux']=[r for r in data['linux'] if r['id'] in included]
 allrs=sum(data.values(),[])
 complete=(R/'COMPLETE.json').exists() and all(len(data[k])==n for k,n in dict(delay=144,linux=108,full=720,mid=240).items())
 lines=['# v1.2 — wait by default','',('Final calibration from the preserved interrupted run. The user requested stopping here rather than recharging and resuming.' if stopped else ('Completed measured experiment.' if complete else 'INCOMPLETE: measured results are not final.')),'','Frozen LLaDA2.2-mini, BF16, batch 1, no fine-tuning. Exact protocol: `PROTOCOL.md`; raw records and event/timing logs: `results-v1.2/`.','']
 if not complete:
  lines+=['Raw records preserved: '+', '.join(f'{k} {n}' for k,n in raw_counts.items())+'. One unmatched L0 record (task 214) is excluded from Linux comparisons.' if stopped else 'Run still in progress.','']
  lines+=['Analysed counts: '+', '.join(f'{k} {len(v)}' for k,v in data.items())+'.','']
  if (R/'PREREQUISITE_FAILED.json').exists():lines += ['Prerequisite failure: '+(R/'PREREQUISITE_FAILED.json').read_text(),'']
 if stopped:
  lines+=['## Calibrated conclusion','','**Waiting is a working scheduling and insertion mechanism, but these data do not justify making it the default.** The pause removes delay-dependent changes: all 12 delayed-control task groups have identical paused states and outputs across all four delays. It does not reliably produce the requested final answer.','','On the 14 fully matched multi-call Linux tasks, waiting and conventional execution succeed on the same 3 tasks; async succeeds on 1. Waiting fixes two async failures and loses none. The remaining six multi-call tasks and both 240-prompt arithmetic stages were not completed. This is a descriptive partial cohort, not a full H1 result.','','All 24 waiting arithmetic-control outputs contain the returned integer, but the 12 comparison outputs issue unsupported `>` calls instead of YES/NO. Hidden-file waiting outputs contain the exact value in 20/24 cases and meet the strict format in 16/24. Do not conflate these contract failures with an inability to read the injected value.','','The 36-prompt smoke set is encouraging for supplied arithmetic slots: A7W and A7 have identical text on 36/36 prompts, both score 18/18 direct and 18/18 downstream; M4 scores 10/18 and 11/18. This is prerequisite evidence, not a substitute for the 240-task H4 test.','','**Placement limit:** native L3 dispatched 28/29 calls before commitment, but 0/29 recorded native-message insertion boundaries had masks in their block. This L3 counter measures the bridge insertion boundary, not the eventual result-text position, so it does not establish a native result-block claim. The supplied-call D3 controls had 48/48 such masked-block arrivals; A7W smoke had 15/36. These are different placements. Block-64 A7W was not run, so v1.2 does not establish H5.','','Both experiment pods are verified stopped. Retained persistent disks still incur storage charges.','']
 lines += ['## Delayed result controls','','Correct / 6 at each delay; delay-equivalent step time '+str(json.load(open(ROOT/'v11-reference.json'))['delay_calibration']['mean_step_seconds'])+' seconds.','','| Set | Condition | d0 | d10 | d20 | d40 |','|---|---|---:|---:|---:|---:|']
 for kind in ('hidden','arithmetic'):
  for c in ('D1','D2','D3'):
   vals=[counts([r for r in data['delay'] if r['kind']==kind and r['condition']==c and r['delay']==d]) for d in (0,10,20,40)]
   lines.append('| '+kind+' | '+c+' | '+' | '.join(f"{v['correct']}/{v['n']}" for v in vals)+' |')
 delay_states=[]
 for kind in ('hidden','arithmetic'):
  for i in range(6):
   rs=[r for r in data['delay'] if r['condition']=='D3' and r['kind']==kind and r['id']==i]
   hashes=[next(e['state_after'] for e in events(r) if e['type']=='pause') for r in rs]
   delay_states.append(dict(kind=kind,id=i,n=len(rs),identical=len(rs)==4 and len(set(hashes))==1,identical_outputs=len(rs)==4 and len({r['text'] for r in rs})==1))
 dump('delay-state-comparison.json',delay_states)
 hidden_use={c:dict(n=len(rs),exact_value_present=sum(r['expected'] in r['text'] for r in rs),strict_correct=sum(r['correct'] for r in rs)) for c in ('D1','D2','D3') for rs in [[r for r in data['delay'] if r['kind']=='hidden' and r['condition']==c]]}
 dump('hidden-value-use.json',hidden_use)
 arithmetic_use={}
 for c in ('D1','D2','D3'):
  rs=[r for r in data['delay'] if r['kind']=='arithmetic' and r['condition']==c]
  used=sum(bool(re.search(r'(?<![0-9])'+re.escape(str(r['rounds'][0]['result']['output']))+r'(?![0-9])',r['text'])) for r in rs)
  arithmetic_use[c]=dict(n=len(rs),returned_integer_present=used,strict_correct=sum(r['correct'] for r in rs))
 dump('arithmetic-value-use.json',arithmetic_use)
 lines+=['','Arithmetic returned-integer presence (diagnostic, not a replacement for the requested final answer):','','```json',json.dumps(arithmetic_use,indent=2),'```']

 lines+=['','Hidden exact-value presence versus strict `Answer:` compliance (diagnostic only; gates retain strict scoring):','','```json',json.dumps(hidden_use,indent=2),'```']
 unique_failures=[dict(kind=r['kind'],id=r['id'],expected=r['expected'],text=r['text']) for r in data['delay'] if r['condition']=='D3' and r['delay']==0 and not r['correct']]
 dump('wait-delay-failures.json',unique_failures)
 lines+=['','Waiting-control failures at delay 0 (the same prompts also run at longer delays):','','```json',json.dumps(unique_failures,indent=2),'```']
 lines += ['','D3 identical pre-insertion canvas across all four delays: '+str(sum(r['identical'] for r in delay_states))+'/12 task groups.','', '## Linux','','| Condition | Prior tasks | Matched multi-call tasks | Strict / matched total | Actual dispatches |','|---|---:|---:|---:|---:|']
 linuxcounts={}
 for c in ('L0','L1','L2','L3'):
  rs=[r for r in data['linux'] if r['condition']==c];simple=counts([r for r in rs if r['minimum_calls']==1]);multi=counts([r for r in rs if r['minimum_calls']>1]);total=counts(rs);linuxcounts[c]=dict(simple=simple,multi=multi)
  lines.append(f"| {c} | {simple['correct']}/{simple['n']} | {multi['correct']}/{multi['n']} | {total['strict']}/{total['n']} | {total['calls']} |")
 lp={}
 for c in ('L1','L2'):
  for group in ('simple','multi'):
   a=[r for r in data['linux'] if r['condition']==c and (r['minimum_calls']==1)==(group=='simple')];b=[r for r in data['linux'] if r['condition']=='L3' and (r['minimum_calls']==1)==(group=='simple')]
   q=pair(a,b);q.pop('exact_two_sided_mcnemar');lp[c+'→L3 '+group]=q
 dump('linux-paired.json',lp)
 lines+=['','Exact Linux paired counts (B = L3):','','```json',json.dumps(lp,indent=2),'```','','## Arithmetic','','| Block | Condition | Direct / 120 | Downstream / 120 |','|---:|---|---:|---:|']
 groups={}
 for stage,block,cs in [('full',32,('M4','A7','A7W')),('mid',64,('A7W',))]:
  for c in cs:
   rs=[r for r in data[stage] if r['condition']==c];di=counts([r for r in rs if r['kind']=='direct']);de=counts([r for r in rs if r['kind']=='dependent']);groups[block,c]=rs
   lines.append(f"| {block} | {c} | {di['correct']}/{di['n']} | {de['correct']}/{de['n']} |")
 pairs={}
 for a,b in [('M4','A7'),('M4','A7W'),('A7','A7W')]:pairs[a+'→'+b]=pair([r for r in groups[32,a] if r['kind']=='direct'],[r for r in groups[32,b] if r['kind']=='direct'])
 dump('arithmetic-paired.json',pairs)
 baseline={r['id']:r for r in groups[32,'M4']};correct_baseline=[r for r in groups[32,'A7W'] if r['id'] in baseline and baseline[r['id']]['correct']];reg=sum(not r['correct'] for r in correct_baseline);rate=reg/len(correct_baseline) if correct_baseline else None
 lines+=['','The 240-task arithmetic comparisons were not run.' if stopped else '', '','A7W regressions among M4-correct records: '+str(reg)+'/'+str(len(correct_baseline))+(' ('+f'{100*rate:.2f}'+'%).' if rate is not None else '.'),'','Exact two-sided McNemar tests on direct answers:','','```json',json.dumps(pairs,indent=2),'```']
 arrivals=[e for r in data['mid'] for e in events(r) if e['type']=='arrival'];mid=sum(e['midblock'] for e in arrivals);mide=sum(e['midblock_before_eos'] for e in arrivals)
 lines+=['','Block-64 arrivals in a still-masked own block: '+str(mid)+'/'+str(len(arrivals))+'; masked before EOS: '+str(mide)+'/'+str(len(arrivals))+'.','', '## Safety and timings','','| Condition | Records | Lock violations | Stray effects | Stale completions | Residual masks | Wall s | Recorded pause s |','|---|---:|---:|---:|---:|---:|---:|---:|']
 safety={}
 for c in dict.fromkeys(r['condition'] for r in allrs):
  rs=[r for r in allrs if r['condition']==c];ss={k:sum(r.get('safety',{}).get(k,0) for r in rs) for k in ('lock_violations','stray_effect','stale_completion','residual_masks')};safety[c]=ss
  lines.append('| '+c+' | '+str(len(rs))+' | '+' | '.join(str(v) for v in ss.values())+' | '+f"{sum(r.get('seconds',0) for r in rs):.1f} | {sum(r.get('timing',{}).get('wait_seconds',0) for r in rs):.1f} |")
 gates={}
 if complete:
  direct=lambda c:sum(r['correct'] for r in groups[32,c] if r['kind']=='direct')
  gates['H1']=linuxcounts['L3']['multi']['correct']>=linuxcounts['L1']['multi']['correct'] and linuxcounts['L3']['multi']['correct']>linuxcounts['L2']['multi']['correct']
  gates['H2']=linuxcounts['L3']['simple']['correct']>=linuxcounts['L1']['simple']['correct']
  gates['H3']=all(sum(r['correct'] for r in data['delay'] if r['condition']=='D3' and r['kind']==kind and r['delay']==d)>=threshold for kind,threshold in [('hidden',6),('arithmetic',5)] for d in (0,10,20,40))
  gates['H4']=abs(direct('A7W')-direct('A7'))<=2 and rate is not None and rate<=.02
  gates['H5']=len(arrivals)>0 and mid/len(arrivals)>=.3 and sum(r['correct'] for r in data['mid'] if r['kind']=='direct')>=109
  gates['H6']=all(v==0 for c in ('D3','L3','A7W') for v in safety[c].values())
 if stopped:
  observed_gates={'H1':'Not fully evaluated: matched subset 3/14 wait = 3/14 conventional > 1/14 async; six tasks missing','H2':'PASS: wait 4/7 = conventional 4/7','H3':'FAIL: wait hidden 4/6 and arithmetic 3/6 at every delay','H4':'NOT RUN: 240-task comparison absent; smoke only','H5':'NOT RUN: block-64 comparison absent','H6':'Observed counters clean; full planned matrix incomplete'}
  dump('calibrated-gates.json',observed_gates)
 lines+=['','## Pre-registered gates','']+[f'- {k}: **'+('PASS' if v else 'FAIL')+'**' for k,v in gates.items()]
 if not gates:
  lines.extend([f'- {k}: {v}' for k,v in observed_gates.items()] if stopped else ['Pending completion and prerequisite checks.'])
 dump('gates.json',dict(complete=complete,gates=gates,safety=safety))
 lines+=['','## Per-task Linux outcomes','','✓ means task-specific success; failure causes below refer to L3 and are descriptive, not proof of causation.','','| Task | Minimum calls | L0 | L1 | L2 | L3 | L3 cause |','|---:|---:|---|---|---|---|---|']
 traces=[]
 for task in json.load(open(ROOT/'linux-tasks.json')):
  rs={r['condition']:r for r in data['linux'] if r['id']==task['id']};w=rs.get('L3');cause=failures(w) if w else 'not evaluated in matched cohort'
  lines.append(f"| {task['id']} | {task['minimum_calls']} | "+' | '.join('✓' if rs.get(c,{}).get('correct') else ('✗' if c in rs else '—') for c in ('L0','L1','L2','L3'))+' | '+cause.replace('|','/')+' |')
  if w:traces.append(dict(id=task['id'],cause=cause,question=task['question'],expected=task['expected'],text=w['text'],calls=w['calls'],results=[t.get('result') for t in w['rounds']]))
 dump('linux-failure-traces.json',traces)
 chain_evidence=[]
 for r in data['linux']:
  if r['condition']!='L3' or not r['correct'] or r['minimum_calls']<=1:continue
  links=[dict(next_path=r['calls'][i]['call']['args'].get('path'),present_in_previous_result=r['calls'][i]['call']['args'].get('path','__NONE__') in r['rounds'][i-1]['result']['output'],previous_dispatch_step=r['rounds'][i-1]['dispatch_step'],next_dispatch_step=r['rounds'][i]['dispatch_step']) for i in range(1,len(r['calls']))]
  chain_evidence.append(dict(id=r['id'],calls=len(r['calls']),all_calls_before_commit=all(not t['committed'] for t in r['rounds']),links=links,arrival_states=[e for e in events(r) if e['type']=='arrival']))
 dump('successful-chain-evidence.json',chain_evidence)
 lines+=['','Successful waiting chains: '+str(len(chain_evidence))+'. Exact per-call dependency and arrival evidence is in `results-v1.2/successful-chain-evidence.json`.']

 lines+=['','## Interpretation','']
 if complete:
  if all(gates.values()):conclusion='Waiting passes all six pre-registered gates and is the default for this frozen-weight pilot. Async remains an optional latency optimisation that needs a separate benefit demonstration under genuinely slow tools.'
  else:conclusion='Waiting is not established as the default: '+', '.join(k for k,v in gates.items() if not v)+' failed. '+('The delayed-result and mid-block gates passed, so failures elsewhere should not be attributed automatically to result latency. ' if gates['H3'] and gates['H5'] else 'The unmet gates limit the result-consumption or mid-block claim. ')+'Async remains a comparison condition; its tradeoff requires controlled latency measurements. No fine-tuning conclusion follows from this experiment.'
  lines.append(conclusion)
 if stopped:
  lines.append('Waiting should remain an available mechanism, not the established default. The evidence supports exact pause/resume behavior, latency-invariant outputs, successful active-canvas tool chains, and no observed safety violations. It does not support the broader claim that non-waiting caused all prior failures: malformed calls, invalid argument schemas, unnecessary extra calls, and missing final answers persist after results arrive. Async has two additional failures on the completed matched subset, but its speed/quality tradeoff remains unmeasured. The next question is which continuation and tool-contract behavior fails after a correct result is available; these data do not establish that fine-tuning is necessary.')
 lines+=['','L1 accepts parsed final calls without the .9 draft-confidence gate; L2/L3 retain that gate. L3 uses the user-approved active-canvas native-message adapter; L1/L2 retain the old separate call/answer stages. Its different continuation layout and token budget can affect Linux outcomes. A7W preserves schedule position; A7 retains its old local-step reset on result insertion. All comparison arms share the residual-mask completion repair. These are disclosed implementation differences, not evidence that waiting alone caused every change. Sampler denoising time includes host coordination and insertion overhead. Pause timers measure blocked execution/artificial delay up to completion; insertion overhead remains in sampler time. Conventional-arm tool waits are included in total wall time, not in the recorded-pause column. McNemar p-values are unadjusted for the three reported comparisons.','']
 (ROOT/'RESULTS.md').write_text('\n'.join(lines))
 print(json.dumps(dict(complete=complete,counts={k:len(v) for k,v in data.items()},gates=gates)))
if __name__=='__main__':main()
