# Native tool-trained diffusion pilot

## Question

With frozen LLaDA2.2-mini weights, can native computation or Linux tool results
be delivered during denoising, remain protected, and support correct answers?
No fine-tuning is part of this experiment. Existing tool training is an input.

## Model and adapter

Model: inclusionAI/LLaDA2.2-mini, revision
`e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`, BF16, A100 SXM4 80 GB,
PyTorch 2.8.0+cu128, Transformers 5.2.0. Native tool syntax is used.

The experimental sampler is fixed-position block diffusion with block length 32,
8 scheduled unmasking steps and 2 refinement steps. It permits token replacement
but suppresses DELETE/SPLIT/MASK output logits and explicitly protects injected
positions. This differs from the untouched upstream sampler. Setting the editing
threshold to zero does **not** disable editing. The adversarial lock test forces
structural-edit logits high and checks that injected tokens survive.

This adapter runs batch size one. Parsing, queueing, tokenization and the upstream
MoE routing include host work; this is not a GPU-only/no-host implementation.

## Conditions

- Native tools: six synthetic read/compute tasks plus one literal write. Baseline
  has no tool declarations; conventional executes a completed call then starts
  answer generation; async polls draft calls during generation, dispatches eligible
  reads, waits for commitment before writes, and inserts completed results into a
  protected 64-token native tool-role slot. While pending, the active answer block
  can continue refinement (bounded to 32 rounds). No pending future is awaited
  inside the sampler barrier. Thread-pool cleanup outside sampling is timed.
- Dense answer controls reuse successful conventional tool results with ordinary
  native tool messages, comparing the protected sampler and original upstream
  sampler. These isolate result-slot and sampler effects, not call-selection skill.
- Arithmetic: the same 36 prompts as the LLaDA-8B pilot, paired baseline and native
  GPU arithmetic injection, plus post-hoc correction. Insertion requires an eligible
  equation and a still-masked destination; failed opportunities are logged.

The native tool runner handles one call/result turn per task. CSV tasks requiring
more turns can fail this scaffold even when the model can use tools. Exact-answer
and answer-present scores are reported separately. Small exploratory samples and
adaptive forward counts do not establish a general performance improvement.

The Linux gateway uses fresh network-disabled Docker containers; see
`../syscall-pilot/README.md` for isolation and protocol checks. All data is synthetic.
Model writes target only the synthetic workspace.

## Reproduce

Start the gateway and reverse tunnel described in the syscall pilot. Copy its
`tasks.json` alongside these scripts on the CUDA host, set `HF_HOME` to the model
cache, then run `python run_pilot.py` followed by `python dense_control.py`.
Sources are self-contained except for Python/PyTorch/Transformers/Triton dependencies.

## Retained infrastructure

Pod `26i6z57kcsek7x` remains allocated at the user's explicit request. Quoted GPU
compute is $1.79/hour, with an 80 GB workspace volume. Do not release automatically.

## Completed main-run results

| Arithmetic condition | Direct answers | Downstream decisions | Sampling seconds, 36 prompts |
|---|---:|---:|---:|
| Baseline | 7/18 | 14/18 | 124.72 |
| Mid-denoising GPU insertion | 11/18 | 14/18 | 122.65 |
| Post-hoc arithmetic replacement | 16/18 | 14/18 | not measured |

Seven insertions fired (six direct, one dependent), all at the first denoising
step, with correct operands and zero lock violations. Four direct failures became
correct, none regressed. Two fixed erroneous final copies of an already-correct
equation; two fixed multiplication errors. Other opportunities were absent or
occupied. This sparse trigger rate limits conclusions about downstream usefulness.
The 22.2 percentage-point direct gain does not meet the original 30-point gate.
Timing is one sequential exploratory run with adaptive forward counts, not a
statistically established speedup. Post-hoc replacement is a separate control.

For example, baseline task 20 answered `328337777777777` for
`43138899 * 76169003`; insertion produced the correct `3285846927347697`, which
was then copied into the final answer.

Native Linux tools generated five executable calls out of seven requests under
both conventional and async execution. All five async calls completed and their
results were inserted after answer forward steps 0, 0, 2, 0, and 2. There were no
stale completions, stray effects, or lock violations in these traces. One literal
write was submitted only after commitment, and the synthetic output file contains
exactly `native-written-7319` (19 bytes).

Among the six read/compute tasks, both conventional and async answers contained
the correct answer in 2/6 cases, versus 0/6 without tools. Strict answer-only
format scored 0/6 in all modes. The successful write is counted separately: the
baseline said DONE without performing a write, so its textual match is **not**
execution success. Async and conventional both performed the requested write.

Failures: one file answer appended an extra character; one Python call had malformed
JSON; one CSV call ended before its closing call marker; the other CSV answer
requested a second read after the 64-token result budget truncated the file. This
one-turn runner does not execute that second call. These are prototype/model-output
limitations; they do not justify a fine-tuning conclusion.

Mean end-to-end time across the seven tasks, including final thread-pool cleanup,
was 8.77 seconds conventional and 7.41 seconds async. Both include failed tasks;
the conventional CSV answer generated more text, so the difference cannot be
attributed solely to overlap. The no-tool mean was 3.77 seconds with no external
task successes. Model loading and kernel warmup are excluded.

Raw records, timings and events are in `mini-results/`. `analyze.py` regenerates
`summary.json`; raw strict scores are preserved alongside answer-present scores.

## Controls and conclusion

Dense native result messages restored the incorrect file copy under **both** the
protected and upstream samplers. Across five successful tool-result answer controls,
each sampler contained the expected answer in 4/5 outputs (three read/compute
answers plus DONE); only DONE satisfied the strict answer-only format. The CSV
case attempted another call. This implicates the reserved-slot representation in
at least one failure, rather than a lack of tool-result training.

The upstream sampler reproduced the malformed Python-call JSON for task 9, but
completed a valid CSV call for task 17 where the protected adapter ended early.
Thus call failures have mixed causes; these controls do not isolate every cause.

An extra artificial-delay control held delivery for at least 40 global steps.
The result arrived at answer step 37 and its lock survived, but the answer omitted
the value. The bounded 32-round block hold can expire before a very late result,
so late delivery alone does not ensure useful answer revision. This is a scheduling
limitation to address before interpreting delayed-answer failures as model limits.

The narrow pilot demonstrates correct native computation insertion with four
additional direct arithmetic successes, native call dispatch, protected result
arrival, and committed Linux writes using frozen weights. It does **not** establish
reliable general tool use or a speedup. The next engineering targets are native
result placement, late-result scheduling and multi-turn handling. Fine-tuning was
neither performed nor established as necessary.
