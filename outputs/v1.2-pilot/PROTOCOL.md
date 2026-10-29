# v1.2 frozen-weight wait experiment

User brief: brief.txt. Same revision, model, seeds, arithmetic prompts, native
few-shots, Linux system message, schemas and synthetic fixtures as v1.1.
No fine-tuning. The user explicitly approved immediate native result insertion
at eligible dispatch in the active canvas, instead of v1.1's answer-stage slot.

Prerequisites run before measured comparisons: invariant tests, exact text
reproduction of the first five v1.1 A7 smoke records, 36 original prompts under
M4/A7/A7W with zero residual masks. A failed prerequisite stops measured runs.
Source and protocol hashes freeze after prerequisites and before measurements;
any subsequent behavioral fix requires a separately identified version.

## Fixed conditions and order

1. 144 delayed controls: hidden six + original arithmetic first six; four delays;
   D1 async/no remask, D2 async/remask, D3 wait/protected editing/no remask.
2. 108 Linux records: same 27 tasks, L0 none/L1 conventional/L2 async4/L3 wait4.
3. 720 block-32 arithmetic records: M4/A7/A7W x 240.
4. 240 block-64 arithmetic records: A7W, as specified by the brief's run order.

Delay wall time is d times the sum of v1.1 A7 full-cohort sampler seconds divided
by sum of its forward calls. This includes sampler overhead and its near-instant
kernel call, because v1.1 did not record pure CUDA-only forward timings. The
calibration and reference file hash are saved in v11-reference.json. D1/D2 keep
their original forward-step delays. D3 pauses at first answer-stage hook (step 0)
for all delay values; no forward passes occur while waiting. Results for these
supplied-call controls are obtained before the sampling segment, as in v1.1.
Artificial latency is imposed inside the pause. The delayed arithmetic contract
uses the accepted v1.1 strengthened native prompt and three examples.

## Sampler changes

A completion guard revisits any unfinished unlocked token before EOS, including
holes shifted into an earlier block by insertion. It does not hide or strip MASK.
It also preserves the earliest needed insertion/revisit cursor. The same repair
applies to rerun comparison arms. Emergency 512-forward ceiling stays unchanged;
residual masks or ceiling exhaustion are reported, never scored as clean output.

Waiting snapshots the canvas, fixed/visible masks, confidence, stamps, dimensions,
global step, local schedule position and cursor. It asserts byte-for-byte identity
after blocking execution/delay and before insertion. Result insertion preserves
local schedule progress. It does not reset the local step to zero as the old A7
revisit path did. A shifted cursor follows the same continuation in its new block;
protected DELETE/SPLIT editing applies only within unlocked spans. No remasking.
This schedule difference is measured by H4, rather than assumed harmless.

For L3, complete draft-call detection/confidence follows v1.1 (tau .9). Writes
still require commitment. At dispatch, execution blocks synchronously; when it
returns, the exact dispatched call span is committed and protected from revision.
The native closing/tool-response/assistant-opening tokens are inserted immediately
after it. Existing adjacent native closing tokens are replaced by the equivalent
bridge; all unfinished continuation tokens are preserved. Result text has the
same 256-token budget. Calls resume in this one canvas, up to four. No speculative
calls or regeneration from rebuilt histories. The original 384-token call canvas
and its remaining schedule are retained; the inserted native messages grow the
canvas, but no additional recovery turns are added. This differs from v1.1's
384-token call + 192-token answer stages and is an adapter-level confound reported
explicitly in interpretation. Generated answers are scored only after the last
inserted assistant header, never against tool-result text or old call arguments.

## Fixed gates

H1: L3 multi >= L1 and > L2. H2: L3 prior7 >= L1.
H3: D3 hidden >=6/6 and arithmetic >=5/6 at EACH delay.
H4: absolute direct count difference A7W vs A7 <=2; A7W regressions among all
M4-correct 240 records <=2%, matching v1.1's regression denominator. Also report
regressions separately on the 120 direct answers.
H5: A7W block64 own-result-block masked share >=30%, direct >=109/120. Also
report masked-before-EOS share so padding after EOS cannot inflate the claim.
H6: waiting arms have zero lock violations, stray effects, stale completions,
residual masks. Report all comparison-arm counters separately as well.

Exact two-sided McNemar on paired 120 direct answers; exact Linux paired counts,
no Linux significance tests. Every L3 failure gets an evidence-based cause.
H1-H6 all pass is the only basis for making waiting the default. Otherwise report
which mechanisms succeeded and which remain unsupported. GPU is stopped after
verified local raw/source backup; persistent disks retained as previously requested.
