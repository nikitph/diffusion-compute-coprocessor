import json,pathlib,collections,subprocess,sys,math,hashlib,re
root=pathlib.Path(__file__).parent;data=root/'results'
def rows(name):
 p=data/(name+'.jsonl');return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
subprocess.run([sys.executable,str(root/'analyze.py')],stdout=subprocess.DEVNULL,check=True)
a=json.loads((data/'analysis.json').read_text());g=json.loads((data/'gates.json').read_text())
full=rows('full');mid=rows('mid');linux=rows('evaluated-linux');assert full and len(linux)==101,'Experiment incomplete'
assert len({(r['condition'],r['id']) for r in linux})==101,'Duplicate Linux records'
expected={c for c in ('A0','A1','M1','A2','A3','A4','A5','M4','M5') if c not in g['dropped'] and not(c=='M5' and 'A5' in g['dropped'])}|{'A6'}
if g['promote_A7'] and 'A7' not in g['dropped']:expected.add('A7')
assert {r['condition'] for r in full}==expected,'Missing full conditions'
assert {r['condition'] for r in mid}==expected.intersection({'A3','A4','A5'}),'Missing mid-block conditions'
for stage in (full,mid):
 for c in {r['condition'] for r in stage}:
  ids=[r['id'] for r in stage if r['condition']==c];assert len(ids)==240 and len(set(ids))==240,(c,len(ids))
def events(r):
 if 'metrics' in r:return r['metrics'].get('events',[])
 return [e for turn in r.get('rounds',[]) for key in ('first','second') for e in turn.get(key,{}).get('events',[])]
def violations(r):
 if 'metrics' in r:return r['metrics'].get('lock_violations',0)
 return sum(turn.get(key,{}).get('lock_violations',0) for turn in r.get('rounds',[]) for key in ('first','second'))
canonical=full+mid+linux+rows('arithmetic-delay')+rows('variant-delay')+rows('hidden-delay')
safety={'lock_violations':sum(violations(r) for r in canonical),'stray_effects':sum(e['type']=='stray_effect' for r in canonical for e in r.get('events',[])),'stale_completions':sum(e['type']=='stale_completion' for r in canonical for e in r.get('events',[])),'max_remasks_per_task':max(sum(e['type']=='remask' for e in events(r)) for r in canonical)}
workspace=root.parent/'syscall-pilot/workspace';before=json.loads((root/'workspace-before-linux.json').read_text());after={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in workspace.rglob('*') if p.is_file()}
sampler_metrics=[m for r in canonical for m in ([r.get('metrics',{})]+[t.get(k,{}) for t in r.get('rounds',[]) for k in ('first','second')])]
safety['exhausted_sampler_stages']=sum(bool(m.get('step_budget_exhausted')) for m in sampler_metrics)
safety['pending_sampler_stages']=sum(bool(m.get('pending_at_end')) for m in sampler_metrics)
safety['residual_mask_tokens']=sum(m.get('residual_masks',0) for m in sampler_metrics)
residual_audit=[]
for stage in ('full','mid'):
 for r in rows(stage):
  ms=[r.get('metrics',{})]+[t.get(k,{}) for t in r.get('rounds',[]) for k in ('first','second')]
  n=sum(m.get('residual_masks',0) for m in ms)
  if n:residual_audit.append({'stage':stage,'id':r['id'],'condition':r['condition'],'residual_masks':n,'scored_correct':r['correct']})
safety['records_with_residual_masks']=len(residual_audit)
safety['residual_mask_records_scored_correct']=sum(r['scored_correct'] for r in residual_audit)
(data/'residual-mask-audit.json').write_text(json.dumps(residual_audit,indent=2))
safety['unexpected_workspace_changes']=[n for n in sorted(set(before)|set(after)) if n!='model_writes/native.txt' and before.get(n)!=after.get(n)]
safety['literal_write_contents_exact']=(workspace/'model_writes/native.txt').read_bytes()==b'native-written-7319'
checks=0
for r in full+mid:
 for e in r.get('injection_events',[]):
  if e.get('status')=='injected' and 'value' in e:
   truth={'+':e['a']+e['b'],'-':e['a']-e['b'],'*':e['a']*e['b']}[e['op']];assert int(e['value'])==truth;checks+=1
 for t in r.get('rounds',[]):
  q=t.get('result') or {}
  if q.get('ok') and 'operands' in q:
   x,op,y=q['operands'];assert int(q['output'])=={'+':x+y,'-':x-y,'*':x*y}[op];checks+=1
stale_audit=[]
for r in canonical:
 ev=r.get('events',[])
 for i,e in enumerate(ev):
  if e['type']!='stale_completion':continue
  nxt=next((q for q in ev[i+1:] if q['type']=='submit' and q.get('anchor')==e.get('anchor') and q.get('step')==e.get('step')),None)
  m=re.fullmatch(r'\s*(\d+)\s*([+*×−-])\s*(\d+)\s*',(nxt or {}).get('call',{}).get('args',{}).get('expression',''))
  same=bool(m and [int(m[1]),m[2].replace('×','*').replace('−','-'),int(m[3])]==(e.get('result') or {}).get('operands'))
  stale_audit.append({'id':r['id'],'condition':r.get('condition'),'step':e['step'],'same_arithmetic_after_text_revision':same})
safety['stale_completions_same_arithmetic']=sum(x['same_arithmetic_after_text_revision'] for x in stale_audit)
(data/'stale-completion-audit.json').write_text(json.dumps(stale_audit,indent=2))
safety['kernel_outputs_independently_rechecked']=checks
safety['injected_operand_mismatches']=sum(e.get('status')=='injected' and not e.get('operand_match',True) for r in full+mid for e in r.get('injection_events',[]))
source_manifest=json.loads((data/'executed-source-manifest.json').read_text())
safety['executed_source_files_verified']=len(source_manifest)
safety['executed_source_mismatches']=[n for n,h in source_manifest.items() if hashlib.sha256((root/n).read_bytes()).hexdigest()!=h]
assert not safety['executed_source_mismatches'],'Local source differs from executed source'
(data/'final-verification.json').write_text(json.dumps(safety,indent=2))
lines=['# v1.1 results','', 'Frozen LLaDA2.2-mini; no fine-tuning. All results and source are saved locally.','', '## Expanded arithmetic set (240 tasks)','', '| Condition | Direct /120 | Downstream /120 | Fired /240 | Use (fixed / wrong-base insertions) | Regressions / right base | Direct p vs A0 |','|---|---:|---:|---:|---:|---:|---:|']
summary_text=['**Outcome:** a frozen model can use protected arithmetic results reliably in the supplied-operand setup, especially with protected native editing (A7). This is a positive mechanism result, not a pass of every pre-specified gate.', '', 'A7 achieved **114/120 direct** and **115/120 downstream** answers, versus **56/120** and **110/120** in its matched prefill baseline M4 (ordinary A0: 56/120 and 112/120). It fixed 66/74 previously wrong cases and regressed on 3/166 previously right cases (1.8%). No fine-tuning was used.', '', '**No A3–A5 condition passed all gates.** A4 improved direct accuracy but regressed on 10/166 previously right cases (6.0%). Native-call conditions frequently consumed the arithmetic value in an unsupported comparison call instead of producing YES/NO. One A3 stale completion was discarded after a whitespace-only call revision.', '', 'Linux multi-call success was **6/20 conventional**, **3/20 async**, and **0/20** with only one async round. The earlier seven tasks scored 4/7 with either tool mode and 0/7 without tools.', '', 'All 2,741 main records (2,160 expanded, 480 block-64, 101 Linux), raw traces, controls and source are saved locally. Both experiment pods are stopped. Original repeat checks passed; the optional cross-host repeat was not completed because model reload stalled on storage reads.', '']
lines[4:4]=summary_text
for c in ('A0','M1','A1','A2','A3','M4','A4','M5','A5','A7','A6'):
 if c not in a['full']:continue
 d=a['full'][c];p=d['direct_vs_A0']['exact_mcnemar_p'];lines.append(f"| {c} | {d['direct']['correct']} | {d['dependent']['correct']} | {d['fired']} | {d['use_numerator']}/{d['use_denominator']} | {d['regressions']}/{d['right_base']} | {p:.6g} |")
task_map={r['id']:r for r in json.loads((data/'tasks240.json').read_text())}
lines += ['', '### Accuracy by operand size', '', 'Each cell is direct / downstream correct, with 24 tasks of each type per size.', '', '| Condition | 5 digits | 8 digits | 10 digits | 12 digits | 15 digits |', '|---|---:|---:|---:|---:|---:|']
for c in ('A0','M1','A1','A2','A3','M4','A4','A7','A6'):
 if c not in a['full']:continue
 cells=[]
 for digits in (5,8,10,12,15):
  ss=[r for r in full if r['condition']==c and task_map[r['id']]['digits']==digits]
  cells.append(' / '.join(str(sum(r['correct'] for r in ss if r['kind']==k)) for k in ('direct','dependent')))
 lines.append('| '+c+' | '+' | '.join(cells)+' |')
lines += ['', 'A0: no tools; A1: historical insertion; A2: conventional native calc; A3: async native calc and re-mask; A4: supplied-operand reserved slot and re-mask; A5: references; A7: protected native editing instead of re-mask; A6: post-hoc arithmetic replacement. M1/M4/M5 are sampler/prefill-matched baselines. Use and regression rates use those matched baselines where available. P-values above use A0 as explicitly requested; paired direct n=120, not 240. These exploratory p-values are not corrected for selecting the best condition.', '', '## Gates', '']
gate_records={}
for c in ('A3','A4','A5'):
 if c not in a['full']:continue
 d=a['full'][c];m=a['mid'].get(c,{});late=[r for r in rows('arithmetic-delay' if c=='A3' else 'variant-delay') if r['delay']==40 and r.get('f3',False) and (c=='A3' or r['condition']==c)]
 rate=sum(r['correct'] for r in late)/len(late) if late else None
 tests={'firing_at_least_70pct':d['firing_rate']>=.7,'use_at_least_70pct':d['use_rate'] is not None and d['use_rate']>=.7,'regressions_at_most_2pct':d['regression_rate'] is not None and d['regression_rate']<=.02,'direct_improvement_p_below_005':d['direct_vs_A0']['exact_mcnemar_p']<.05 and d['direct_vs_A0']['wrong_to_right']>d['direct_vs_A0']['right_to_wrong'],'midblock_at_least_30pct':m.get('arrivals',0)>0 and m.get('midblock',0)/m['arrivals']>=.3,'late_correct_at_least_50pct':rate is not None and rate>=.5,'remask_budget_respected':safety['max_remasks_per_task']<=2,'safety_zero_including_stale':safety['lock_violations']==0 and safety['stray_effects']==0 and safety['stale_completions']==0 and not safety['unexpected_workspace_changes']}
 gate_records[c]={'tests':tests,'all_pass':all(tests.values()),'late_correct_rate':rate,'late_n':len(late)}
 lines += [f"**{c}:** "+', '.join(k+': '+('pass' if v else 'fail/not established') for k,v in tests.items())+'.','']
(data/'final-gates.json').write_text(json.dumps(gate_records,indent=2))
lines += ['Safety counters above are evaluated across the accepted run: one discarded A3 completion fails the global zero-stale target; A4 itself had no stale completions, and both had zero lock violations and stray effects. A4 independently fails the regression gate. A7 promotion is exploratory and does not silently replace the pre-specified best-of-A3–A5 gate. A native tool turn can still end before the answer turn starts; a masked result block is not proof that the originating call was still editable.', '', '## Block-64 intervention timing', '', '| Condition | Direct /120 | Downstream /120 | Arrivals | Own block still masked | Masked before EOS |','|---|---:|---:|---:|---:|---:|']
for c,d in a['mid'].items():lines.append(f"| {c} | {d['direct']['correct']} | {d['dependent']['correct']} | {d['arrivals']} | {d['midblock']} | {d['midblock_before_eos']} |")
lines += ['', '## Native-tool failure diagnosis', '', '| Condition | Downstream tasks ending in unsupported comparison calls | Of those, containing the returned arithmetic integer |', '|---|---:|---:|']
for c in ('A2','A3'):
 ss=[r for r in full if r['condition']==c and r['kind']=='dependent']
 failures=[r for r in ss if '<|tool_call_begin|>' in r['text'] and any(re.search('[<>]',v) for v in re.findall(r'"expression"\s*:\s*"([^"]*)"',r['text']))]
 uses=sum(any(str((t.get('result') or {}).get('output','NOT_A_RESULT')) in r['text'] for t in r.get('rounds',[]) if (t.get('result') or {}).get('ok')) for r in failures)
 lines.append(f'| {c} | {len(failures)}/{len(ss)} | {uses}/{len(failures)} |')
lines += ['', 'These outputs fail the requested final YES/NO answer and the supported calc contract. However, reusing the returned integer inside an unsupported comparison call is evidence of result consumption; it must not be described as simply ignoring the result. Arithmetic conditions allow one calc round and reject comparisons rather than executing them or silently adding a recovery turn. No extra prompting, comparison backend, or fine-tuning was added after expansion began.']
lines += ['', '## Delayed-result controls', '', '| Control | Delay (forward steps) | Re-mask off | Re-mask on |', '|---|---:|---:|---:|']
for name in ('hidden-delay','arithmetic-delay','variant-delay'):
 rs=rows(name)
 for c in sorted({r.get('condition',name) for r in rs}):
  for delay in (0,10,20,40):
   cells=[]
   for f3 in (False,True):
    subset=[r for r in rs if r.get('condition',name)==c and r['delay']==delay and r['f3']==f3]
    cells.append(str(sum(r['correct'] for r in subset))+'/'+str(len(subset)))
   lines.append(f'| {c} | {delay} | '+ ' | '.join(cells)+' |')
u=rows('upstream');lines += ['',f'Dense native-message upstream sampler control: {sum(r["correct"] for r in u)}/{len(u)} exact answers. These controls use supplied calls and are separate from autonomous call-adoption measurements.', '', '## Failed insertion opportunities', '', '| Condition | Absent | Occupied | Too short | Late |', '|---|---:|---:|---:|---:|']
for c in ('A1','A3','A4','A5','A7'):
 if c in a['full']:
  f=a['full'][c]['failed_opportunities'];lines.append('| '+c+' | '+' | '.join(str(f.get(k,0)) for k in ('absent','occupied','too_short','late'))+' |')
lines += ['', '## Edit audit (36 smoke tasks)', '']
for c in ('A7','A8'):
 rs=[r for r in rows('edit-audit') if r['condition']==c];ops=[e for r in rs for e in events(r) if e['type']=='edit_ops'];lines.append(f"- {c}: {sum(r['correct'] for r in rs)}/{len(rs)} correct; {sum(e['delete'] for e in ops)} DELETE and {sum(e['split'] for e in ops)} SPLIT proposals consumed.")
lines += ['', 'A8 preserves the provisional draft without structural edits. In the original smoke audit, the two A7 improvements were one formatting repair (Answer:: NO to Answer: NO) and one correction of copied integer digits. This is not two independent arithmetic-computation gains; the kernel supplied the arithmetic result in both cases.', '', '## Linux (7 prior tasks + 20 multi-call tasks)', '', '| Condition | Prior success | Prior strict text | Multi-call success | Multi-call strict text | Total calls |','|---|---:|---:|---:|---:|---:|']
for c,d in a['linux'].items():lines.append(f"| {c} | {d['one']['correct']}/{d['one']['n']} | {d['one']['strict']}/{d['one']['n']} | {d['multi']['correct']}/{d['multi']['n']} | {d['multi']['strict']}/{d['multi']['n']} | {d['one']['calls']+d['multi']['calls']} |")
by={(r['condition'],r['id']):r for r in linux};onlymulti=[r['id'] for r in linux if r['condition']=='async' and r['minimum_calls']>1 and r['correct'] and not by['async_one_round',r['id']]['correct']]
lines += ['',f"Multi-call tasks completed with async four-round handling but not the one-round control: {len(onlymulti)}/20. Strict text is a formatting/exact-text metric; a baseline textual DONE is not counted as a successful write. Write success additionally requires the requested literal call arguments and a successful execution receipt. These Linux outcomes apply to the instrumented sampler and tested prompt/tool contract; they do not establish that the model generally cannot use multiple tools or that fine-tuning is necessary.",'', '## Safety, reproducibility and retained data','', '```json',json.dumps(safety,indent=2),'```','', 'Smoke continuation decisions:','```json',json.dumps(g,indent=2),'```','', 'Reproducibility:','```json',json.dumps(a['reproducibility'],indent=2),'```','', 'Stale completions are discarded by the coordinator, not applied to a revised call. The count remains a failure of the zero-stale target, even when a text revision preserves the same arithmetic; stale-completion-audit.json distinguishes those cases. The residual-mask audit found 25 incomplete outputs (551 mask tokens): 6 A3, 1 A4 and 1 A7 at block 32, and 17 A3 at block 64. All 25 were already scored as failures, so this does not inflate accuracy, but it is an adapter/completion limitation. One historical A1 insertion used a partial wrong operand; new conditions had no injected operand mismatches. The confidence repair and original prompt variants are retained separately; see README.md. Per-token attention diagnostics were unavailable under SDPA. The harness is host-orchestrated and the upstream MoE implementation also touches CPU; these results do not establish GPU-only execution or a speedup. Full raw outputs, kernel results, timings, masks, call/commit events, and control records are in results/. The GPU pod is stopped (EXITED), verified after the complete local backup. The original pod is also EXITED. Persistent disks are preserved and still incur storage charges; see infrastructure.json.']
legacy={r['id']:r for r in rows('legacy-baseline')};legacy_rep=rows('legacy-repeat')
lines += ['', f'Additional M1 legacy reproducibility: {sum(legacy[r["id"]]["text"]==r["text"] for r in legacy_rep)}/{len(legacy_rep)} exact repeats.']
cross=data/'cross-host-verification.json'
if cross.exists():lines += ['', 'Supplemental cross-host control repeat status (not part of the completed original 45 canonical plus 5 legacy repeats):', '```json',cross.read_text(),'```']
(root/'RESULTS.md').write_text('\n'.join(lines)+'\n');print(json.dumps({'report':str(root/'RESULTS.md'),'full_records':len(full),'mid_records':len(mid),'linux_records':len(linux),'safety':safety,'gates':gate_records},indent=2))
