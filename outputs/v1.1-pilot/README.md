# v1.1 frozen-weight experiment

Requested brief: `brief.txt`. Model remains inclusionAI/LLaDA2.2-mini revision
`e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`, BF16, batch 1, temperature 0.
No fine-tuning. A100 SXM4 80GB, $1.79/hour GPU compute. The original pod
`26i6z57kcsek7x` stopped after the account ran out of funds. After recharge, its
host had no available GPU; continuation uses replacement `hex6gc4ufd8xt6` with
the same image and pinned packages. Both pods are now stopped after verified local backup. Retained disks still incur
storage charges; see `infrastructure.json` for final lifecycle state.

## Implementation and interpretation

- F1: real model-generated native `calc(expression)` calls; GPU integer kernel;
  native tokenizer-rendered tool responses. Async response insertion splices the
  actual result tokens into an empty native response, shifting the continuation.
  It does not leave padded masked result positions in the prompt.
- F2a: supplied operands in a fixed equation prefill and a protected result slot.
  Width follows operand lengths. Only the kernel can fill it; unused padding is
  removed on arrival. This is a supplied-operand mechanism control, not autonomous
  discovery. The matched M4 baseline uses the same equation prefill without a slot.
- F2b: an explicit r1 binding and requested `<ref r1>` output; adopted references
  are resolved by the runtime using the computed kernel result. Numeric direct
  success is therefore partly mechanical, not evidence of model copying. M5 has
  the same reference instructions without a runtime binding result.
- F3: an arrival event re-masks unlocked written tokens after submission from the
  result through every started dependent block, at most once/result and twice/
  sequence. The block cursor rewinds to regenerate those tokens. Pending events
  continue receiving barriers after EOS; there is a 512-forward emergency ceiling
  (recorded as a failure, never silently treated as completion). No future is
  waited on inside a sampling barrier. Native T2T refinement remains enabled.
- A7 smoke: upstream DELETE/SPLIT semantics applied separately to unlocked runs of
  a dependent block; fixed positions are boundaries that edits cannot cross.
  This is an instrumented protected variant, not untouched upstream decoding.
- F4: up to four native call/result rounds, 256-token result budget. All Linux
  calls execute in the existing fresh, network-disabled container gateway.
  Read-only draft requests may execute speculatively; persistent writes require
  commitment. Errors remain text. New tasks contain synthetic hidden file chains
  ending in CSV/log values, with 2–4 explicitly requested separate reads.

Native async calls still end a tool-call turn before the provisional answer turn
starts. Mid-block metrics measure whether the *result's block* has unlocked masks
at arrival, before re-masking. They must not be described as proof that the native
call itself remained editable at arrival. F2a/F2b are separate canvas mechanisms.
Block-64 cases explicitly left-pad with newline tokens to place result slots near
an early position of a block; padding and exact prompts are reproducible in source.

The SDPA path does not provide the requested per-token attention diagnostic.
Events explicitly mark that diagnostic unavailable; attention values are not
invented. It is diagnostic only and does not affect the re-mask rule.

## Measurement plan

Original 36 prompts are the smoke set. Expanded 240 prompts comprise five operand
sizes × three operations × eight pairs × two task types. Threshold offsets are
uniform seeded nonzero integers within 1% of the exact result (at least one).
Whether that avoids ceiling effects is measured, not assumed.

A0/A6 share the question and three arithmetic examples. M4/M5 are additional
prefill/reference-matched baselines for A4/A5. Tool conditions add declarations
and an explicit call requirement. Report these prompt changes as interventions.
A1 retains the earlier sampler and 0.5 trigger as a historical control; new native
calls use the requested 0.9 threshold. Immutable supplied operands have confidence 1.

Exact McNemar tests use actual paired direct samples: **120**, not 240, for the
expanded set. Per-condition p-values and selection of the best condition are
exploratory; no uncorrected best-of-many result will be presented as confirmatory.
Firing, paired use, regressions, answer accuracy, native/reference adoption,
pre-intervention mid-block masks, re-mask events, locks, and side effects are
recorded separately. Native result-arrival timing is host/queue dependent.

`results/*.jsonl` are append-only raw records. `analyze.py` produces aggregates.
`test_event.py` checks delayed arrival, prompt preservation, pre-existing locks,
and structural-edit suppression using adversarial logits before the real model.

## Smoke-stage audit trail

The initial native prompt variant had arithmetic examples but no native tool
exchanges. Its outputs are retained as excluded diagnostic data in
`smoke-before-native-examples.jsonl`. The corrected F1 prompt uses the same three
arithmetic examples as native call/result exchanges.

A confidence audit found that the first adapter reset completed-block confidence
to 1. The accepted A3 cohort is rerun with persistent measured confidence and a
0.9 operand-token threshold. A completed call that never passed the threshold is
not force-dispatched by the async fallback. Pre-fix records and repeated outputs
are retained separately; corrected records are in `confidence-repair*.jsonl`.
Conventional A2 still executes completed calls normally, without speculative
confidence gating.

M1 is an additional no-insertion baseline using A1's older sampler. M4 and M5
match the equation and reference prefills respectively. These avoid attributing
sampler or prefill changes to insertion itself. The A7 edit audit compares all
36 cases against A8: preserve the provisional draft with structural edits disabled.
Actual DELETE/SPLIT events are counted when present; enabling them is not proof
that they caused an improvement.

Hidden-value, arithmetic and variant controls compare re-mask on/off at delays
0, 10, 20 and 40. Exact final answers are reported separately from merely mentioning
the expected value. Expansion requires at least one exact delayed success with
F3, in addition to the adoption, safety and reproducibility checks. The historical pre-contract
source is hashed in `source-manifest.json`; it is not the final source manifest.
The final archive manifest covers the accepted current source and all retained data.

### Arrival timing caveat

In the async answer-stage adapter, even a result already collected during call
sampling is applied at the first answer sampling barrier, after one provisional
forward pass. Artificial-delay controls defer it further. Thus these are controlled
insertion experiments; they do not establish that a production scheduler naturally
needs to wait that long, nor that holding a ready result improves latency. The
call queue timestamps and answer insertion steps are retained separately. A3's
native call itself can be fully committed before this controlled answer-block
insertion. Interpret the mid-block gate with that distinction, and inspect the
separate before-EOS diagnostic rather than counting only trailing masks.

## Calc contract correction and recovery

Pre-contract native prompts sometimes induced unsupported comparison calls.
`finish_run.py` clarifies that calc accepts only two integers with +, -, or *,
and that the model must decide comparisons itself. Both native conditions are
rerun on the original smoke set, with five repeat cases each; native arithmetic
delay and upstream controls are also replaced. Pre-contract results remain
separately named and must not be mixed into the accepted cohorts. The contract
change affects neither supplied-operand controls nor the hidden-file controls.

Continuation resumes full and mid-block arithmetic by (condition, task ID).
The original interrupted run had not reached expanded arithmetic or Linux tests.
`checkpoint-status.json`, `checkpoint-manifest.json`, and `STATUS.md` retain
historical recovery context; the final `RESULTS.md` and `final-verification.json`
are the completion evidence.

## Reproduction notes

Use a separate working copy so the archived evidence remains unchanged. Install
`requirements.txt` on the pinned PyTorch/CUDA image, keep the model revision above,
and run scripts from this directory. The accepted run uses `finish_run.py`, followed
by `cross_host_repeat.py`; `report.py` is run locally after the final transfer.
`finish_run.py` expects the retained 324-record smoke and 45-record repeat checkpoint.
For exact checkpoint replay, restore `results/smoke-pre-contract.jsonl` and
`results/repeat-pre-contract.jsonl` to `smoke.jsonl` and `repeat.jsonl` in the working
copy, and move generated continuation cohorts aside. Full and mid-stage loops
resume by `(condition, id)`; native contract controls and Linux are not resumable
without explicitly filtering completed records.

The archive includes the sibling `syscall-pilot` gateway, container build files,
and synthetic workspace. Start that gateway against its workspace on local port
18765 and expose it only on the GPU host's loopback port 18766 through an SSH reverse
tunnel. `async_engine.py` deliberately bypasses HTTP proxies for that loopback
endpoint. The gateway requires the local `diffusion-syscall-pilot:local` Docker
image, fresh containers, and disabled networking. Model weights are not bundled;
the pinned public Hugging Face revision is the download reference.

`results/executed-source-manifest.json` records SHA-256 hashes of the actual
computation scripts on the replacement GPU host. The final verifier checks them
against the local source. The outer archive manifest independently verifies every
bundled file, including raw result records and the exact synthetic fixtures.

The supplemental cross-host control repeat was aborted before sampling because
model reload stalled on storage page reads. It is not presented as a successful
repeat. The original 45 canonical plus 5 legacy repeated outputs matched exactly.

`remote-snapshot/` preserves the verbatim final remote files and their hash
manifest. Derived analyses were regenerated locally, so compare remote transfer
hashes against that snapshot and final deliverables against the archive manifest.
