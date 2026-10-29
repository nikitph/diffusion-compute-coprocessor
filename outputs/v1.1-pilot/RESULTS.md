# v1.1 results

Frozen LLaDA2.2-mini; no fine-tuning. All results and source are saved locally.

**Outcome:** a frozen model can use protected arithmetic results reliably in the supplied-operand setup, especially with protected native editing (A7). This is a positive mechanism result, not a pass of every pre-specified gate.

A7 achieved **114/120 direct** and **115/120 downstream** answers, versus **56/120** and **110/120** in its matched prefill baseline M4 (ordinary A0: 56/120 and 112/120). It fixed 66/74 previously wrong cases and regressed on 3/166 previously right cases (1.8%). No fine-tuning was used.

**No A3–A5 condition passed all gates.** A4 improved direct accuracy but regressed on 10/166 previously right cases (6.0%). Native-call conditions frequently consumed the arithmetic value in an unsupported comparison call instead of producing YES/NO. One A3 stale completion was discarded after a whitespace-only call revision.

Linux multi-call success was **6/20 conventional**, **3/20 async**, and **0/20** with only one async round. The earlier seven tasks scored 4/7 with either tool mode and 0/7 without tools.

All 2,741 main records (2,160 expanded, 480 block-64, 101 Linux), raw traces, controls and source are saved locally. Both experiment pods are stopped. Original repeat checks passed; the optional cross-host repeat was not completed because model reload stalled on storage reads.

## Expanded arithmetic set (240 tasks)

| Condition | Direct /120 | Downstream /120 | Fired /240 | Use (fixed / wrong-base insertions) | Regressions / right base | Direct p vs A0 |
|---|---:|---:|---:|---:|---:|---:|
| A0 | 56 | 112 | 0 | 0/0 | 0/168 | 1 |
| M1 | 56 | 105 | 0 | 0/0 | 7/168 | 1 |
| A1 | 57 | 107 | 15 | 3/7 | 0/161 | 1 |
| A2 | 90 | 14 | 207 | 50/70 | 115/168 | 1.74285e-05 |
| A3 | 86 | 14 | 207 | 46/70 | 115/168 | 0.000100497 |
| M4 | 56 | 110 | 0 | 0/0 | 12/168 | 1 |
| A4 | 102 | 112 | 240 | 58/74 | 10/166 | 1.17029e-10 |
| A7 | 114 | 115 | 240 | 66/74 | 3/166 | 1.05818e-16 |
| A6 | 118 | 112 | 0 | 0/0 | 0/168 | 4.33681e-19 |

### Accuracy by operand size

Each cell is direct / downstream correct, with 24 tasks of each type per size.

| Condition | 5 digits | 8 digits | 10 digits | 12 digits | 15 digits |
|---|---:|---:|---:|---:|---:|
| A0 | 16 / 21 | 12 / 23 | 10 / 21 | 11 / 23 | 7 / 24 |
| M1 | 16 / 20 | 12 / 20 | 10 / 21 | 11 / 21 | 7 / 23 |
| A1 | 16 / 20 | 13 / 20 | 10 / 23 | 11 / 21 | 7 / 23 |
| A2 | 24 / 14 | 16 / 0 | 10 / 0 | 21 / 0 | 19 / 0 |
| A3 | 24 / 14 | 16 / 0 | 6 / 0 | 21 / 0 | 19 / 0 |
| M4 | 16 / 23 | 14 / 22 | 9 / 20 | 11 / 22 | 6 / 23 |
| A4 | 23 / 23 | 23 / 24 | 19 / 22 | 23 / 23 | 14 / 20 |
| A7 | 24 / 24 | 23 / 24 | 21 / 23 | 23 / 23 | 23 / 21 |
| A6 | 24 / 21 | 23 / 23 | 23 / 21 | 24 / 23 | 24 / 24 |

A0: no tools; A1: historical insertion; A2: conventional native calc; A3: async native calc and re-mask; A4: supplied-operand reserved slot and re-mask; A5: references; A7: protected native editing instead of re-mask; A6: post-hoc arithmetic replacement. M1/M4/M5 are sampler/prefill-matched baselines. Use and regression rates use those matched baselines where available. P-values above use A0 as explicitly requested; paired direct n=120, not 240. These exploratory p-values are not corrected for selecting the best condition.

## Gates

**A3:** firing_at_least_70pct: pass, use_at_least_70pct: fail/not established, regressions_at_most_2pct: fail/not established, direct_improvement_p_below_005: pass, midblock_at_least_30pct: pass, late_correct_at_least_50pct: pass, remask_budget_respected: pass, safety_zero_including_stale: fail/not established.

**A4:** firing_at_least_70pct: pass, use_at_least_70pct: pass, regressions_at_most_2pct: fail/not established, direct_improvement_p_below_005: pass, midblock_at_least_30pct: pass, late_correct_at_least_50pct: pass, remask_budget_respected: pass, safety_zero_including_stale: fail/not established.

Safety counters above are evaluated across the accepted run: one discarded A3 completion fails the global zero-stale target; A4 itself had no stale completions, and both had zero lock violations and stray effects. A4 independently fails the regression gate. A7 promotion is exploratory and does not silently replace the pre-specified best-of-A3–A5 gate. A native tool turn can still end before the answer turn starts; a masked result block is not proof that the originating call was still editable.

## Block-64 intervention timing

| Condition | Direct /120 | Downstream /120 | Arrivals | Own block still masked | Masked before EOS |
|---|---:|---:|---:|---:|---:|
| A3 | 62 | 39 | 168 | 168 | 168 |
| A4 | 109 | 108 | 240 | 239 | 239 |

## Native-tool failure diagnosis

| Condition | Downstream tasks ending in unsupported comparison calls | Of those, containing the returned arithmetic integer |
|---|---:|---:|
| A2 | 102/120 | 98/102 |
| A3 | 102/120 | 98/102 |

These outputs fail the requested final YES/NO answer and the supported calc contract. However, reusing the returned integer inside an unsupported comparison call is evidence of result consumption; it must not be described as simply ignoring the result. Arithmetic conditions allow one calc round and reject comparisons rather than executing them or silently adding a recovery turn. No extra prompting, comparison backend, or fine-tuning was added after expansion began.

## Delayed-result controls

| Control | Delay (forward steps) | Re-mask off | Re-mask on |
|---|---:|---:|---:|
| hidden-delay | 0 | 6/6 | 6/6 |
| hidden-delay | 10 | 0/6 | 6/6 |
| hidden-delay | 20 | 0/6 | 6/6 |
| hidden-delay | 40 | 0/6 | 6/6 |
| arithmetic-delay | 0 | 5/6 | 5/6 |
| arithmetic-delay | 10 | 2/6 | 5/6 |
| arithmetic-delay | 20 | 2/6 | 5/6 |
| arithmetic-delay | 40 | 2/6 | 5/6 |
| A4 | 0 | 5/6 | 6/6 |
| A4 | 10 | 6/6 | 6/6 |
| A4 | 20 | 6/6 | 6/6 |
| A4 | 40 | 6/6 | 6/6 |

Dense native-message upstream sampler control: 6/6 exact answers. These controls use supplied calls and are separate from autonomous call-adoption measurements.

## Failed insertion opportunities

| Condition | Absent | Occupied | Too short | Late |
|---|---:|---:|---:|---:|
| A1 | 2 | 223 | 0 | 0 |
| A3 | 33 | 0 | 0 | 0 |
| A4 | 0 | 0 | 0 | 0 |
| A7 | 0 | 0 | 0 | 0 |

## Edit audit (36 smoke tasks)

- A7: 36/36 correct; 133 DELETE and 5 SPLIT proposals consumed.
- A8: 34/36 correct; 0 DELETE and 0 SPLIT proposals consumed.

A8 preserves the provisional draft without structural edits. In the original smoke audit, the two A7 improvements were one formatting repair (Answer:: NO to Answer: NO) and one correction of copied integer digits. This is not two independent arithmetic-computation gains; the kernel supplied the arithmetic result in both cases.

## Linux (7 prior tasks + 20 multi-call tasks)

| Condition | Prior success | Prior strict text | Multi-call success | Multi-call strict text | Total calls |
|---|---:|---:|---:|---:|---:|
| async | 4/7 | 1/7 | 3/20 | 2/20 | 40 |
| async_one_round | 0/0 | 0/0 | 0/20 | 0/20 | 11 |
| conventional | 4/7 | 1/7 | 6/20 | 5/20 | 53 |
| none | 0/7 | 1/7 | 0/20 | 0/20 | 0 |

Multi-call tasks completed with async four-round handling but not the one-round control: 3/20. Strict text is a formatting/exact-text metric; a baseline textual DONE is not counted as a successful write. Write success additionally requires the requested literal call arguments and a successful execution receipt. These Linux outcomes apply to the instrumented sampler and tested prompt/tool contract; they do not establish that the model generally cannot use multiple tools or that fine-tuning is necessary.

## Safety, reproducibility and retained data

```json
{
  "lock_violations": 0,
  "stray_effects": 0,
  "stale_completions": 1,
  "max_remasks_per_task": 2,
  "exhausted_sampler_stages": 0,
  "pending_sampler_stages": 0,
  "residual_mask_tokens": 551,
  "records_with_residual_masks": 25,
  "residual_mask_records_scored_correct": 0,
  "unexpected_workspace_changes": [],
  "literal_write_contents_exact": true,
  "stale_completions_same_arithmetic": 1,
  "kernel_outputs_independently_rechecked": 1317,
  "injected_operand_mismatches": 1,
  "executed_source_files_verified": 12,
  "executed_source_mismatches": []
}
```

Smoke continuation decisions:
```json
{
  "strengthened": [
    "A2",
    "A3"
  ],
  "native_rates": {
    "A2": {
      "default": 0.3055555555555556,
      "strengthened": 0.6388888888888888
    },
    "A3": {
      "default": 0.3055555555555556,
      "strengthened": 0.6388888888888888
    }
  },
  "dropped": [
    "A5"
  ],
  "contract_clarified": true,
  "repro_failed": [],
  "A5_adoption": 0.0,
  "promote_A7": true,
  "F3_delayed_exact_correct": 17
}
```

Reproducibility:
```json
{
  "n": 45,
  "identical": 45,
  "mismatches": []
}
```

Stale completions are discarded by the coordinator, not applied to a revised call. The count remains a failure of the zero-stale target, even when a text revision preserves the same arithmetic; stale-completion-audit.json distinguishes those cases. The residual-mask audit found 25 incomplete outputs (551 mask tokens): 6 A3, 1 A4 and 1 A7 at block 32, and 17 A3 at block 64. All 25 were already scored as failures, so this does not inflate accuracy, but it is an adapter/completion limitation. One historical A1 insertion used a partial wrong operand; new conditions had no injected operand mismatches. The confidence repair and original prompt variants are retained separately; see README.md. Per-token attention diagnostics were unavailable under SDPA. The harness is host-orchestrated and the upstream MoE implementation also touches CPU; these results do not establish GPU-only execution or a speedup. Full raw outputs, kernel results, timings, masks, call/commit events, and control records are in results/. The GPU pod is stopped (EXITED), verified after the complete local backup. The original pod is also EXITED. Persistent disks are preserved and still incur storage charges; see infrastructure.json.

Additional M1 legacy reproducibility: 5/5 exact repeats.

Supplemental cross-host control repeat status (not part of the completed original 45 canonical plus 5 legacy repeats):
```json
{
  "status": "not_completed",
  "n": 0,
  "identical": 0,
  "mismatches": [],
  "reason": "Supplemental cross-host control repeat aborted after model reload stalled on storage page reads; main experiment and original smoke repeats are complete."
}
```
