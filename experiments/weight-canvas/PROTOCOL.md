# Weight canvas — local pilot v0.1

Frozen before the measured model run. Date: 2026-11-04.

## Scope

Test execution feedback entering a partially denoised weight program. This is a
constrained numeric inpainting pilot, not unrestricted weight-program synthesis.
The language model's weights stay frozen. No training, gradients, fitted optimizer,
or automatic best-candidate selection is used. Model predictions choose the weights.

A 3-input, 2-hidden-ReLU, 3-logit paddle controller has six editable first-layer
weights. Inputs are ball x, one-second horizontal velocity, paddle x. Choose left,
stay, right once; the paddle moves 0.2. Catch within 0.11 of x+velocity. No wall
bounces. All generated scenarios are catchable. Two fixed output neurons implement
opposite actions; the middle logit implements stay. Ties use the first action.

Each scalar uses E in {0,1,2,3,4}; actual weight is E-2. This fixed representation
makes each edit one tokenizer token, allows negative weights and syntax-preserving
inpainting, and exposes a small search space. The scaffold is a Python weight
assignment program. Its evaluator interprets validated data, never executes LLM code.
Both models have identical scaffold and allowed digits; no oracle picks the values.
The model sees the game rules and damaged controller, not the reference controller.
Consequently it could solve this from the rules without using feedback; controls
must establish any feedback benefit.

## Models and numerical precision

Diffusion: dllm-hub/Qwen2.5-Coder-0.5B-Instruct-diffusion-mdlm-v0.1,
a284e895a6248256baf2f60502e54aba61b24c1a.
AR: Qwen/Qwen2.5-Coder-0.5B-Instruct,
ea3f2471cf1b1f0db85067f1ef93848e38e88c25.
Apple M1 Pro, 16 GB unified memory; PyTorch MPS FP32, batch 1, greedy decoding.
These share a model lineage, not identical training. Cross-model results cannot
isolate the causal effect of architecture. Same-model diffusion arms are the
primary mechanism comparison. Pin dependencies in requirements-lock.txt.

## Cohort and controls

Six damage cases are fixed in controller.py. Each gets 64 practice observations
(seed 20261104+case index) and 512 held-out observations (20262104+case index).
Held-out observations never enter prompts or feedback. No prompt selection on these
scores. An independent oracle and 10,000-scenario environment check are prerequisites.
One deterministic run per case/arm; descriptive pilot, no significance claims.

Arms:
- D-active: evaluate a provisional complete candidate after 3/6 numeric slots
  have been unmasked. Remaining slots use the model's argmax proposals. Append a
  versioned immutable evaluator report AFTER the program, then reopen all six
  numeric slots in the SAME canvas. Preserve prompt and scaffold. Six denoising
  passes complete the repaired program; total 9 forward passes.
- D-round: finish all six slots, evaluate completed candidate, then supply the
  candidate and report in a new user prompt and generate a fresh six-slot program;
  total 12 passes.
- D-shuffled: D-active, but counterexample observations are replaced by unrelated
  observations. True evaluation and displayed report are both saved. This is
  deliberately corrupted evidence, not a real evaluator claim. Aggregate score
  remains truthful, so this tests counterexample alignment, not absence of all signal.
- D-none: same mid-canvas reopening schedule as D-active, report withheld. The
  evaluator still runs once for auditing but does not influence generation.
- AR-round: autoregressively fill six numeric slots, evaluate, then issue a new
  prompt containing candidate and feedback and fill a new program; 12 passes.
  Recompute full prefix per step (no KV cache); timing is not an optimized AR baseline.

All arms have one feedback evaluation opportunity, at most 12 model forward passes,
plus final held-out evaluation. D-active gets feedback earlier and uses 9 passes;
this is part of the treatment, not an equal-compute causal isolation. Log actual
forward calls, processed input positions, wall time and inference time. A complete
candidate's syntax is guaranteed by the scaffold; eligibility is not a learned trigger.

Confidence is normalized among five allowed digits; highest confidence remaining
slot is filled each diffusion pass. The provisional candidate retains committed
slots and fills still-masked slots from that pass's predictions. No gradient,
reference weights, or held-out score affects decoding. All numeric slots reopen
on feedback: this pilot does not establish selective dependency-based invalidation.

## Outcomes and gates

Record initial/provisional/final weight arrays and programs; true and displayed
feedback; each canvas transition, masked positions at arrival, report hashes and
immutability assertions. The first three committed values may be changed after
arrival. Positive evidence for use of feedback requires D-active improvements
beyond D-none and D-shuffled, not just a working repaired controller. A single
repair is a demonstration only. Comparison with D-round is descriptive and
schedule-confounded. Report held-out catch rate, recovered failures, regressions
among originally caught cases, and edits. A new environment or larger model is
needed to generalize beyond this small finite weight space.

If all feedback arms fail or controls perform equally, report that result; do not
silently replace the model's proposal with a hand-written repair.
