# v1.2 — wait by default

Final calibration from the preserved interrupted run. The user requested stopping here rather than recharging and resuming.

Frozen LLaDA2.2-mini, BF16, batch 1, no fine-tuning. Exact protocol: `PROTOCOL.md`; raw records and event/timing logs: `results-v1.2/`.

Raw records preserved: delay 144, linux 85, full 0, mid 0. One unmatched L0 record (task 214) is excluded from Linux comparisons.

Analysed counts: delay 144, linux 84, full 0, mid 0.

## Calibrated conclusion

**Waiting is a working scheduling and insertion mechanism, but these data do not justify making it the default.** The pause removes delay-dependent changes: all 12 delayed-control task groups have identical paused states and outputs across all four delays. It does not reliably produce the requested final answer.

On the 14 fully matched multi-call Linux tasks, waiting and conventional execution succeed on the same 3 tasks; async succeeds on 1. Waiting fixes two async failures and loses none. The remaining six multi-call tasks and both 240-prompt arithmetic stages were not completed. This is a descriptive partial cohort, not a full H1 result.

All 24 waiting arithmetic-control outputs contain the returned integer, but the 12 comparison outputs issue unsupported `>` calls instead of YES/NO. Hidden-file waiting outputs contain the exact value in 20/24 cases and meet the strict format in 16/24. Do not conflate these contract failures with an inability to read the injected value.

The 36-prompt smoke set is encouraging for supplied arithmetic slots: A7W and A7 have identical text on 36/36 prompts, both score 18/18 direct and 18/18 downstream; M4 scores 10/18 and 11/18. This is prerequisite evidence, not a substitute for the 240-task H4 test.

**Placement limit:** native L3 dispatched 28/29 calls before commitment, but 0/29 recorded native-message insertion boundaries had masks in their block. This L3 counter measures the bridge insertion boundary, not the eventual result-text position, so it does not establish a native result-block claim. The supplied-call D3 controls had 48/48 such masked-block arrivals; A7W smoke had 15/36. These are different placements. Block-64 A7W was not run, so v1.2 does not establish H5.

Both experiment pods are verified stopped. Retained persistent disks still incur storage charges.

## Delayed result controls

Correct / 6 at each delay; delay-equivalent step time 0.34800585270211065 seconds.

| Set | Condition | d0 | d10 | d20 | d40 |
|---|---|---:|---:|---:|---:|
| hidden | D1 | 6/6 | 0/6 | 0/6 | 0/6 |
| hidden | D2 | 6/6 | 6/6 | 6/6 | 6/6 |
| hidden | D3 | 4/6 | 4/6 | 4/6 | 4/6 |
| arithmetic | D1 | 5/6 | 2/6 | 2/6 | 2/6 |
| arithmetic | D2 | 5/6 | 5/6 | 5/6 | 5/6 |
| arithmetic | D3 | 3/6 | 3/6 | 3/6 | 3/6 |

Arithmetic returned-integer presence (diagnostic, not a replacement for the requested final answer):

```json
{
  "D1": {
    "n": 24,
    "returned_integer_present": 21,
    "strict_correct": 11
  },
  "D2": {
    "n": 24,
    "returned_integer_present": 24,
    "strict_correct": 20
  },
  "D3": {
    "n": 24,
    "returned_integer_present": 24,
    "strict_correct": 12
  }
}
```

Hidden exact-value presence versus strict `Answer:` compliance (diagnostic only; gates retain strict scoring):

```json
{
  "D1": {
    "n": 24,
    "exact_value_present": 7,
    "strict_correct": 6
  },
  "D2": {
    "n": 24,
    "exact_value_present": 24,
    "strict_correct": 24
  },
  "D3": {
    "n": 24,
    "exact_value_present": 20,
    "strict_correct": 16
  }
}
```

Waiting-control failures at delay 0 (the same prompts also run at longer delays):

```json
[
  {
    "kind": "hidden",
    "id": 2,
    "expected": "90f8790c8b0c",
    "text": "The file contains the value \"90f8790c8b0c\"."
  },
  {
    "kind": "hidden",
    "id": 4,
    "expected": "9f9a4a2995d5",
    "text": "Answer: "
  },
  {
    "kind": "arithmetic",
    "id": 1,
    "expected": "YES",
    "text": "<|tool_calls_section_begin|><|tool_call_begin|>functions.calc:4<|tool_call_argument_begin|>{\"expression\": \"174209 > 174205\"}<|tool_call_end|><|tool_calls_section_end|>"
  },
  {
    "kind": "arithmetic",
    "id": 3,
    "expected": "NO",
    "text": "<|tool_calls_section_begin|><|tool_call_begin|>functions.calc:4<|tool_call_argument_begin|>{\"expression\": \"90364 > 90367\"}<|tool_call_end|><|tool_calls_section_end|>"
  },
  {
    "kind": "arithmetic",
    "id": 5,
    "expected": "YES",
    "text": "<|tool_calls_section_begin|><|tool_call_begin|>functions.calc:4<|tool_call_argument_begin|>{\"expression\": \"33505 > 33501\"}<|tool_call_end|><|tool_calls_section_end|>"
  }
]
```

D3 identical pre-insertion canvas across all four delays: 12/12 task groups.

## Linux

| Condition | Prior tasks | Matched multi-call tasks | Strict / matched total | Actual dispatches |
|---|---:|---:|---:|---:|
| L0 | 0/7 | 0/14 | 1/21 | 0 |
| L1 | 4/7 | 3/14 | 3/21 | 39 |
| L2 | 4/7 | 1/14 | 2/21 | 29 |
| L3 | 4/7 | 3/14 | 1/21 | 29 |

Exact Linux paired counts (B = L3):

```json
{
  "L1\u2192L3 simple": {
    "n": 7,
    "both_correct": 4,
    "both_wrong": 3,
    "b_fixes": 0,
    "b_regresses": 0
  },
  "L1\u2192L3 multi": {
    "n": 14,
    "both_correct": 3,
    "both_wrong": 11,
    "b_fixes": 0,
    "b_regresses": 0
  },
  "L2\u2192L3 simple": {
    "n": 7,
    "both_correct": 4,
    "both_wrong": 3,
    "b_fixes": 0,
    "b_regresses": 0
  },
  "L2\u2192L3 multi": {
    "n": 14,
    "both_correct": 1,
    "both_wrong": 11,
    "b_fixes": 2,
    "b_regresses": 0
  }
}
```

## Arithmetic

| Block | Condition | Direct / 120 | Downstream / 120 |
|---:|---|---:|---:|
| 32 | M4 | 0/0 | 0/0 |
| 32 | A7 | 0/0 | 0/0 |
| 32 | A7W | 0/0 | 0/0 |
| 64 | A7W | 0/0 | 0/0 |

The 240-task arithmetic comparisons were not run.

A7W regressions among M4-correct records: 0/0.

Exact two-sided McNemar tests on direct answers:

```json
{
  "M4\u2192A7": {
    "n": 0,
    "both_correct": 0,
    "both_wrong": 0,
    "b_fixes": 0,
    "b_regresses": 0,
    "exact_two_sided_mcnemar": null
  },
  "M4\u2192A7W": {
    "n": 0,
    "both_correct": 0,
    "both_wrong": 0,
    "b_fixes": 0,
    "b_regresses": 0,
    "exact_two_sided_mcnemar": null
  },
  "A7\u2192A7W": {
    "n": 0,
    "both_correct": 0,
    "both_wrong": 0,
    "b_fixes": 0,
    "b_regresses": 0,
    "exact_two_sided_mcnemar": null
  }
}
```

Block-64 arrivals in a still-masked own block: 0/0; masked before EOS: 0/0.

## Safety and timings

| Condition | Records | Lock violations | Stray effects | Stale completions | Residual masks | Wall s | Recorded pause s |
|---|---:|---:|---:|---:|---:|---:|---:|
| D1 | 48 | 0 | 0 | 0 | 0 | 407.4 | 0.0 |
| D2 | 48 | 0 | 0 | 0 | 0 | 454.2 | 0.0 |
| D3 | 48 | 0 | 0 | 0 | 0 | 442.2 | 292.3 |
| L0 | 21 | 0 | 0 | 0 | 0 | 66.5 | 0.0 |
| L1 | 21 | 0 | 0 | 0 | 0 | 362.7 | 0.0 |
| L2 | 21 | 0 | 0 | 0 | 0 | 292.1 | 0.0 |
| L3 | 21 | 0 | 0 | 0 | 0 | 303.5 | 34.9 |

## Pre-registered gates

- H1: Not fully evaluated: matched subset 3/14 wait = 3/14 conventional > 1/14 async; six tasks missing
- H2: PASS: wait 4/7 = conventional 4/7
- H3: FAIL: wait hidden 4/6 and arithmetic 3/6 at every delay
- H4: NOT RUN: 240-task comparison absent; smoke only
- H5: NOT RUN: block-64 comparison absent
- H6: Observed counters clean; full planned matrix incomplete

## Per-task Linux outcomes

✓ means task-specific success; failure causes below refer to L3 and are descriptive, not proof of causation.

| Task | Minimum calls | L0 | L1 | L2 | L3 | L3 cause |
|---:|---:|---|---|---|---|---|
| 0 | 1 | ✗ | ✓ | ✓ | ✓ | success |
| 1 | 1 | ✗ | ✓ | ✓ | ✓ | success |
| 8 | 1 | ✗ | ✓ | ✓ | ✓ | success |
| 9 | 1 | ✗ | ✗ | ✗ | ✗ | invalid run schema: cmd is a string, required array |
| 16 | 1 | ✗ | ✗ | ✗ | ✗ | invalid run schema: cmd is a string, required array |
| 17 | 1 | ✗ | ✗ | ✗ | ✗ | tool error from chosen arguments: FileNotFoundError: [Errno 2] No such file or directory: 'python3 -c "\nimport csv\nwith open(\'tables/table_1. |
| 100 | 1 | ✗ | ✓ | ✓ | ✓ | success |
| 200 | 2 | ✗ | ✗ | ✗ | ✗ | final value obtained; continued calls or missing/incorrect final answer |
| 201 | 3 | ✗ | ✗ | ✗ | ✗ | malformed/incomplete native call or JSON |
| 202 | 4 | ✗ | ✗ | ✗ | ✗ | malformed/incomplete native call or JSON |
| 203 | 2 | ✗ | ✗ | ✗ | ✗ | valid-looking continuation not dispatched; rejected-trigger details not logged |
| 204 | 3 | ✗ | ✗ | ✗ | ✗ | valid-looking continuation not dispatched; rejected-trigger details not logged |
| 205 | 4 | ✗ | ✓ | ✗ | ✓ | success |
| 206 | 2 | ✗ | ✗ | ✗ | ✗ | valid-looking continuation not dispatched; rejected-trigger details not logged |
| 207 | 3 | ✗ | ✗ | ✗ | ✗ | malformed/incomplete native call or JSON |
| 208 | 4 | ✗ | ✗ | ✗ | ✗ | malformed/incomplete native call or JSON |
| 209 | 2 | ✗ | ✗ | ✗ | ✗ | final value obtained; continued calls or missing/incorrect final answer |
| 210 | 3 | ✗ | ✓ | ✗ | ✓ | success |
| 211 | 4 | ✗ | ✗ | ✗ | ✗ | tool error from chosen arguments: FileNotFoundError: [Errno 2] No such file or directory: '/fixture/vv1/15dd5cb741b6b1ac.txt' |
| 212 | 2 | ✗ | ✗ | ✗ | ✗ | chain stopped before final value; no valid continuation |
| 213 | 3 | ✗ | ✓ | ✓ | ✓ | success |
| 214 | 4 | — | — | — | — | not evaluated in matched cohort |
| 215 | 2 | — | — | — | — | not evaluated in matched cohort |
| 216 | 3 | — | — | — | — | not evaluated in matched cohort |
| 217 | 4 | — | — | — | — | not evaluated in matched cohort |
| 218 | 2 | — | — | — | — | not evaluated in matched cohort |
| 219 | 3 | — | — | — | — | not evaluated in matched cohort |

Successful waiting chains: 3. Exact per-call dependency and arrival evidence is in `results-v1.2/successful-chain-evidence.json`.

## Interpretation

Waiting should remain an available mechanism, not the established default. The evidence supports exact pause/resume behavior, latency-invariant outputs, successful active-canvas tool chains, and no observed safety violations. It does not support the broader claim that non-waiting caused all prior failures: malformed calls, invalid argument schemas, unnecessary extra calls, and missing final answers persist after results arrive. Async has two additional failures on the completed matched subset, but its speed/quality tradeoff remains unmeasured. The next question is which continuation and tool-contract behavior fails after a correct result is available; these data do not establish that fine-tuning is necessary.

L1 accepts parsed final calls without the .9 draft-confidence gate; L2/L3 retain that gate. L3 uses the user-approved active-canvas native-message adapter; L1/L2 retain the old separate call/answer stages. Its different continuation layout and token budget can affect Linux outcomes. A7W preserves schedule position; A7 retains its old local-step reset on result insertion. All comparison arms share the residual-mask completion repair. These are disclosed implementation differences, not evidence that waiting alone caused every change. Sampler denoising time includes host coordination and insertion overhead. Pause timers measure blocked execution/artificial delay up to completion; insertion overhead remains in sampler time. Conventional-arm tool waits are included in total wall time, not in the recorded-pause column. McNemar p-values are unadjusted for the three reported comparisons.
