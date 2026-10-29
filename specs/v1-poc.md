# Native Compute Coprocessor for Diffusion LMs — PoC Spec

Oct 28, 2026 · @CREDIT IQ

## Summary and hypothesis

We pause a masked diffusion language model between denoising steps, run exact arithmetic natively on the GPU, and lock the results into the canvas. If this works, exact-answer accuracy on multi-digit arithmetic rises to near 100% with under 10% added latency, and no retraining is needed for the first result.

**Hypothesis.** Diffusion LMs are weak at exact sequential dependencies (carry chains, long multiplication) because they generate in parallel. Their denoising loop has two properties autoregressive models lack: a natural barrier between steps where every sequence is paused together, and native support for clamping tokens as fixed. Together these let native compute enter the forward loop without breaking batching.

**Why it is cheap to test.** Phase 0 needs no training: a rule-based trigger and parser on the decoded draft, a GPU arithmetic kernel, and the model's existing inpainting path. Training enters only if Phase 0 shows the injection helps.

## Goals, non-goals, success criteria

**Goals**

1. Show that injecting exact results between denoising steps raises exact-match accuracy on arithmetic tasks.
2. Show that the injection keeps the batch synchronous: no host round trip, no per-sequence stall.
3. Find when in the denoising schedule to inject (step index or confidence threshold).
4. Show the model rewrites surrounding reasoning around a locked result, not just copies it.

**Non-goals**

- General program execution (loops, control flow). That is a later phase.
- Beating a Python tool-call baseline on throughput.
- Autoregressive models. They are a baseline only.

**Success criteria** (targets, to be revised after the baseline run)

| Criterion | Target |
| --- | --- |
| Exact-match gain on 5–10 digit arithmetic vs base model | ≥ 30 points |
| Exact-match on word problems (GSM8K-style) vs base | no regression; any gain counted |
| Added wall-clock latency per batch | ≤ 10% |
| Batch synchronisation | zero host round trips during denoising |
| Locked results changed by later steps | 0% (by construction) |

## System design

The coprocessor runs only at the barrier between denoising steps, so every sequence in the batch pauses together and nothing leaves the GPU.

&#91;embedded content: inference loop · one decision, one native call per injection\]

One pass of the loop, per step *t* of *T*:

1. **Denoise.** The model unmasks some positions of the canvas, as normal.
2. **Trigger.** Inject when *t* ≥ *t\** (a fixed late step) and the tokens of an operand span (e.g. `48213 × 9076 =`) all have confidence above τ. Phase 1 replaces this rule with a learned probe.
3. **Parse.** Decode the argmax draft and match operand spans with a regex grammar (`<int> <op> <int> =`). Phase 0 supports + − × ÷ and comparison on integers up to 64 digits.
4. **Compute.** A batched GPU kernel does exact big-integer arithmetic on all matched spans in one launch. Fixed digit budget, so run time is bounded and uniform.
5. **Lock.** Tokenise the result and write it into the masked positions after `=`, marked fixed (the same mechanism as inpainting). Later steps cannot change it but can rewrite text around it.

**Interfaces**

| Component | Input | Output | Phase 0 form |
| --- | --- | --- | --- |
| Trigger | step *t*, per-token confidences | inject mask per sequence | rule: *t* ≥ *t\** and min confidence ≥ τ |
| Parser | argmax draft tokens | list of (span, op, a, b) | regex grammar |
| Kernel | operand tensors, padded to 64 digits | result digits | CUDA or Triton big-int ops |
| Locker | result digits, target positions | updated canvas + fixed mask | tokenizer + model's clamp path |

If the masked slot after `=` is shorter than the result, the locker extends the slot only when the model's generation length allows it; otherwise the case is logged as a slot-length failure.

## Phases

Phase 0 alone answers the core question; each later phase runs only if the gate before it passes.

&#91;embedded content: PoC phases · 3 phases, 2 gates\]

- **P0 · Inference only.** Everything in System design, with the model frozen. Output: accuracy and latency across a grid of *t\** and τ. Gate 1: ≥ 30-point exact-match gain on 5–10 digit arithmetic at ≤ 10% added latency.
- **P1 · Learned trigger.** A linear probe on the model's hidden states predicts, per position and step, whether an operand span is stable. Trained on P0 logs labelled by whether injection at that point gave the correct answer. Gate 2: higher accuracy than the best rule trigger, at equal or fewer kernel calls.
- **P2 · Fine-tune.** LoRA fine-tuning on traces where results arrive locked mid-denoising. Goal: the model learns to write operands in a parseable form early and to reason around locked values. Here the regex parser may be replaced by a learned span decoder.

## Model, tasks, baselines, metrics

Use an open masked-diffusion LM around 7–8B with an accessible sampling loop. Candidates are LLaDA-8B-Instruct and Dream-7B-Instruct; checkpoint availability and licence still need confirming.

**Tasks**

| Task | Why | Size |
| --- | --- | --- |
| Synthetic arithmetic, 2–20 digits, + − × ÷ | controls difficulty by digit count; isolates the carry-chain weakness | 500 per digit bucket |
| Multi-step expressions (3–5 operations) | tests chained injections and rewriting around locked values | 1,000 |
| GSM8K test | real word problems; checks for regressions | 1,319 |
| NUPA and DeepMind Mathematics (arithmetic modules) | lets results sit beside the Qwenputer numbers | subsets |

**Baselines**

1. Base diffusion model, same step count *T*.
2. Base model + post-hoc fix: run the parser on the final output and overwrite the answer. Separates the value of mid-denoising injection from simple answer correction.
3. An autoregressive model of similar size, with and without a Python tool call.

**Metrics**

- Exact-match accuracy, by digit bucket.
- Wall-clock latency per batch and kernel calls per sample.
- Injection precision: share of injections whose parsed operands match the ground-truth operands.
- Rewrite rate: share of samples where text around a locked value changes after injection (evidence the model reasons around it).
- Slot-length failures: results that did not fit the masked slot.

## Experiments and ablations

E1 is the decisive run; the rest explain why it worked or failed.

| ID | Experiment | Varies | Question answered |
| --- | --- | --- | --- |
| E1 | Main result | injection on vs off | Does mid-denoising injection beat the base model? |
| E2 | Timing sweep | *t\** from 50% to 95% of *T*; τ from 0.5 to 0.95 | When are operands stable enough to read? |
| E3 | Post-hoc vs mid-loop | baseline 2 vs E1 | Does the model use the locked value, or is this just answer correction? |
| E4 | Lock vs soft hint | clamp tokens vs bias logits toward them | Is hard clamping necessary? |
| E5 | Single vs repeated injection | inject once vs at every eligible step | Does re-reading operands catch late changes? |
| E6 | Step budget | *T* = 64, 128, 256 | Can injection let us cut steps without losing accuracy? |
| E7 | Noisy kernel | kernel returns a wrong result 10% of the time | Does the model blindly trust locked values? |

E3 is the most important control. If post-hoc correction matches E1, the PoC has shown only that a calculator fixes answers, not that the loop benefits.

## Risks, open questions, budget and timeline

The biggest risk is that operands never settle before the final steps, which would leave no room for the model to use the result.

**Risks and fallbacks**

| Risk | Effect | Fallback |
| --- | --- | --- |
| Operands settle only in the last few steps | injection collapses into post-hoc correction (E3 ties E1) | semi-autoregressive block decoding: inject per block as each block finishes |
| Result longer than the masked slot | truncated or failed lock | reserve a fixed-width answer slot in the prompt template |
| Tokenizer splits digits unevenly | parser misreads operands; locked tokens look unnatural to the model | digit-level re-tokenisation of the result; filter by round-trip check |
| Locking disrupts the model's distribution | worse text around the result | soft hint (E4) or P2 fine-tuning |
| Model trusts a wrong kernel output | silent errors once operands are mis-parsed | E7 measures it; P1 probe adds a confidence gate |

**Open questions**

- Which checkpoint: LLaDA or Dream? Depends on which sampler is easier to hook between steps.
- Can the parser run on the GPU too (token-ID pattern match), or is a host-side regex acceptable for P0?
- Should P2 extend beyond arithmetic to comparisons, dates and counting, as a step toward the web-agent use case?

**Budget and timeline** (estimates, single researcher)

- **Compute:** P0 and P1 are inference plus a linear probe; one 80 GB GPU is enough. P2 LoRA fine-tuning needs roughly 1–4 GPUs for a few days.
- **P0:** about 2 weeks — sampler hook, parser, kernel, E1–E3.
- **P1:** about 2 weeks — probe training on P0 logs, E4–E7.
- **P2:** about 3–4 weeks, only if Gate 2 passes.
