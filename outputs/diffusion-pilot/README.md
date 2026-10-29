# Diffusion coprocessor pilot

A bounded first test of the supplied PoC, not the full benchmark or its success gate.

## Result — 28 October 2026

**The calculator and locks worked, but this pilot did not meet the accuracy gate.**

| Condition | Direct final answer | Downstream decision (label-tolerant) | Strict downstream format |
|---|---:|---:|---:|
| Base | 12/18 | 17/18 | 17/18 |
| Inject from 25% (exploratory) | 13/18 | 16/18 | 14/18 |
| Inject from 50% | 13/18 | 16/18 | 14/18 |
| Inject from 75% | 12/18 | 17/18 | 15/18 |
| Post-hoc calculator correction | 18/18 | 17/18 | 17/18 |

The best direct gain was 5.6 percentage points, below the proposed 30-point gate.
These are 36 synthetic prompts, not a general benchmark. Each of 18 operand pairs
appears in both task types, and downstream base accuracy is near ceiling.

The standalone native GPU kernel passed 756 arithmetic cases through 64 input digits,
with zero errors and 0.0643 ms per warmed batch of 756. In the main run, all 54
successful injections used the correct operands and every locked token survived.
Injection coverage was 32/36 at 50% and 22/36 at 75%; occupied slots caused failures.

Sampling-time overhead, summed over the nine paired batches, was 0.94% at 50% and
0.88% at 75%. This is a small observational timing comparison, not a GPU-only
performance validation. Prompt tokenization, model loading, final decoding and
post-run diagnostics are outside that timer; host parsing and all hook transfers
are inside it. The zero-host-transfer target remains untested.

A repeated run reproduced all 72 baseline and 50%-injection output strings exactly.
Earlier injection at 25% did not improve the aggregate scores. In the instrumented
50% run, none of the 29 scorable injected examples had a fully committed final
answer before injection. Thus an already-frozen final answer does not explain
these examples' failure to use a correct intermediate value.

Example: `14927 + 75437 = 90364` was locked correctly, but the model later generated
`Answer: 90434`; its baseline answer was correct. Other strict downstream failures
were only missing `Answer:` labels, hence the separate label-tolerant column.

**Next scientific step:** reserve explicit result slots and compare a schedule
that delays downstream answer commitment, with a matched no-calculator control.
This pilot does not justify proceeding to the learned-trigger/fine-tuning gate.

### Evidence and provenance

- `strict-results/`: original 50%/75% run, all prompts, outputs, events and timings.
- `timing-results/`: exploratory 25% run plus exact replication of base and 50%.
- `kernel-results.json`: standalone GPU correctness and timing measurement.
- `pilot-strict-original.py`: source used for the original run.
- `pilot-instrumented-run.py`: source used for the timing/commit-trace run.
- `pilot.py`: current source, also correcting the post-hoc parser to consume a whole
  comma-containing numeric span. This does not alter the inference hook.
- `evaluated_records.jsonl`: offline post-hoc control regenerated with that parser;
  raw `records.jsonl` files are preserved. Final-answer scores are unchanged.
- Ten harness tests passed on the GPU host. The additional comma-span regression
  check passed locally; the three Torch hook checks require Torch to rerun.

The A100 pod `26i6z57kcsek7x` is retained at the user's explicit request for v2,
at its quoted $1.79/hour rate. It has not been stopped or deleted.

## Reproduce

Python 3.12, PyTorch 2.8.0+cu128, transformers 4.38.2, accelerate, einops,
huggingface_hub; CUDA GPU. `pilot.py` pins the model revision and random seed.

```sh
python -m unittest -v
python gpu_arithmetic.py
python pilot.py --output results --limit 36 --steps 64 --length 192 --batch 4 --fractions 0.5,0.75
```

`--overwrite` is a separate diagnostic intervention that may replace already committed
tokens. It must not be pooled with the masked-slot-only experiment.

## Scientific design

- Frozen LLaDA-8B-Instruct, BF16, deterministic argmax, low-confidence unmasking,
  full-sequence generation, identical 64-forward-pass budget in every condition.
- 36 seeded examples: 5/8/10-digit operands, + / - / *, two operand pairs per cell.
  Each pair has a direct-answer task and a downstream threshold-decision task.
- Base, mid-loop injection, and post-hoc equation correction. The direct post-hoc
  control also corrects the explicit final integer from the last parsed equation;
  it does not read ground truth. It leaves downstream YES/NO decisions unchanged.
- Mid-loop parses the generated draft, never ground-truth operands. Confidence
  applies to the actual draft token. The result must tokenize and round-trip exactly.
- Strict injection writes only to an entirely masked, sufficiently long span after `=`.
  A newline terminates the inserted integer. Occupied/too-short spans are logged.
- Later token selection never revisits committed tokens, preserving successful locks.
- Ground truth is used only for scoring and injection-precision logging.
- Conditions rotate order between batches. Warm-up is excluded. All timings include
  model execution, host parsing, copies, and hook work, but exclude model loading.

## Important limitations

The host-regex pilot uses the GPU calculator by default (`--backend cpu` selects the exact Python reference). It batches eligible operands into one kernel call per barrier, but still transfers drafts and results through the host. It cannot establish zero host round trips or <=10% GPU-only
latency overhead. Its transfer loop also uses host control, as does the reference
sampler. `gpu_arithmetic.py` supplies the integrated one-launch GPU calculator; the tokenizer/parser/locker remain on the host. It supports nonnegative input integers
up to 64 digits, signed subtraction results, and 128-digit multiplication outputs.
Division and signed inputs to that kernel are not implemented.

An argmax draft changing outside the lock is not proof of reasoning or revision of
committed text. The reference sampler freezes committed tokens. Downstream answer
accuracy is the stronger pilot measure, still insufficient to infer an internal
reasoning process. Small sample sizes, explicit formatting instructions and the
narrow task distribution limit generalization. No GSM8K, AR baseline, learned
trigger, fine-tuning, or full timing/confidence sweep is included in this pilot.

## Sources

- https://github.com/ML-GSAI/LLaDA/blob/main/generate.py
- https://huggingface.co/GSAI-ML/LLaDA-8B-Instruct
- Model revision: `08b83a6feb34df1a6011b80c3c00c7563e963b07`

The model card lists MIT licensing. The sampler here is a small independent
implementation of the documented masking schedule, not a copy of the repository.
