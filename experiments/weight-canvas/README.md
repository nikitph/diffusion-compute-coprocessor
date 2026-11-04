# Weight-space programming on an editable diffusion canvas

**Completed locally on 2026-11-04. No feedback-driven controller repair was demonstrated.**
All model inference ran on an Apple M1 Pro with 16 GB memory. No cloud pod was
created and no model was fine-tuned.

The experiment joins weight-space programming with mid-generation external
feedback: a small diffusion model writes a tiny controller's weight program; a
simulator evaluates a provisional draft; a versioned report lands after the
unfinished program; the model's output region reopens for revision. Its own
pretrained weights remain fixed.

## What was run

| Stage | Runs | Result | Evidence |
|---|---:|---|---|
| v0.1 constrained numeric slots | 30 | All arms copied all damaged weights unchanged | [Report](RESULTS.md), [protocol](PROTOCOL.md) |
| v0.2 free weight-assignment programs | 30 | No controller improved; correct and shuffled active feedback had identical task outcomes | [Report](free-program/RESULTS.md), [protocol](free-program/PROTOCOL.md) |
| v0.3 direct signed-weight diagnostic | 5 | No repair on the single already-seen task | [Report](native-weights/RESULTS.md), [protocol](native-weights/PROTOCOL.md) |

Each main stage compares active-canvas diffusion, conventional diffusion revision,
shuffled counterexamples, no feedback, and an autoregressive editor. Six deliberately
damaged controllers are evaluated on 512 held-out situations each. These are six
repair tasks, not 3,072 independent model trials.

The v0.2 active arm produced valid but unchanged controllers in 2/6 tasks, and
invalid programs in 4/6. Shuffled feedback produced the same outcomes. The
conventional diffusion arm produced invalid programs in all six; the AR arm
produced valid but unchanged controllers in all six. Invalid programs count as
zero deployable catches and are distinguished from valid controllers that miss.

## What did work

- The environment/reference controller passed 10,000 generated situations and an
  independent action-policy check.
- The active runtime inserted feedback while output tokens before the provisional
  EOS were still masked. The prompt and inserted report remained fixed during
  revision; every denoising step checks that invariant.
- The diffusion model could perform an explicit two-weight repair when allowed
  to emit free Python assignment statements. Its constrained-slot version copied
  the original values, motivating the separately reported v0.2 follow-up.
- A model-forward diagnostic verified the selected-output implementation against
  full logits (maximum difference about 0.000029), and verified that right-side
  text affects earlier-slot logits. The feedback is visible through bidirectional
  attention; visibility alone did not produce a useful repair.

## Interpretation

This is a working local experimental apparatus and a negative capability pilot.
It does not establish that diffusion cannot support weight-space programming.
Nor does the explicit-edit diagnostic establish autonomous repair: it supplied
which edits to make. The model still needed to infer an edit from behavior in
measured runs, and failed to do so.

The next prerequisite is a model/interface that can solve this repair task with
ordinary feedback. Only then can active-canvas delivery versus round-based
revision meaningfully test an efficiency or reliability advantage. Do not infer
that fine-tuning is necessary from these results.

The local diffusion checkpoint is a Tiny-A2D adaptation of Qwen2.5-Coder-0.5B;
its AR comparison is the source instruction model. This is separate from the
repository's earlier LLaDA experiments. Model lineage, additional training,
message layout, remasking and inference schedules confound broad architecture
claims. v0.2/v0.3 are exploratory follow-ups on already-seen tasks.

## Reproduce and inspect

No arbitrary generated Python is executed. A bounded AST interpreter permits
only literal matrix assignments and indexed weight writes. All controller inputs
are synthetic. The model checkpoint IDs and revisions are pinned in `models.py`;
model weights and local environments are excluded from Git.

From this directory, install the recorded environment and fetch the two checkpoints:

```sh
uv venv .venv --python 3.11
uv pip sync --python .venv/bin/python requirements-lock.txt
.venv/bin/python analysis/download_models.py
```

Run verification without loading models:

```sh
.venv/bin/python -m unittest discover -s . -p 'test_*.py'
.venv/bin/python -m unittest discover -s free-program -p 'test_*.py'
.venv/bin/python analysis/audit.py
```

Generate reports from saved data:

```sh
.venv/bin/python analysis/report.py
.venv/bin/python analysis/report_free.py
```

Run a fresh model experiment in a NEW destination (the helper refuses to overwrite
an existing directory and excludes prior results):

```sh
.venv/bin/python analysis/reproduce.py --variant free --destination /tmp/weight-canvas-reproduction
```

Use `--variant constrained` or `--variant native` for the other stages. The native
variant is the one-task diagnostic. Actual measured source files are preserved;
do not append new runs into their results directories. Trace JSONL includes full
provisional programs, final programs, feedback, conditions, token-step events,
model-call counts and timing. Source manifests and environment files are alongside
records. `diagnostics/` contains post-pilot checks, not additional benchmark tasks.

See [source provenance and licenses](docs/PROVENANCE.md). Upstream architecture
code retains its Apache-2.0 license in `LICENSE-A2D`.
