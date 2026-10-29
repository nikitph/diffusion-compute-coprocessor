# Native compute coprocessor for diffusion language models

Experimental harnesses, synthetic tasks, raw results and analysis for inserting
external computation and Linux tool results into a diffusion model's active
canvas. This repository preserves the research record, including negative results
and interrupted runs. It is not a production tool runtime.

## Start here

| Experiment | Contents | Report |
| --- | --- | --- |
| Initial arithmetic pilot | LLaDA-8B, GPU integer computation and result injection | [Pilot](outputs/diffusion-pilot/README.md) |
| Linux syscall extension | Synthetic file, Python and CSV tasks in isolated containers | [Linux pilot](outputs/syscall-pilot/README.md) |
| Tool-trained model pilot | LLaDA2.2-mini adaptation | [Model pilot](outputs/llada22-pilot/README.md) |
| v1.1 | Expanded arithmetic, protected editing and asynchronous tools | [Results](outputs/v1.1-pilot/RESULTS.md) |
| v1.2 | Pause at dispatch, lock results, resume protected editing | [Calibrated results](outputs/v1.2-pilot/RESULTS.md) |

## Current conclusion

The v1.2 run was interrupted by a funding limit; analysis was deliberately closed
using the locally preserved results. It did **not** complete the planned 240-task
arithmetic comparison or block-64 test.

- All 12 delayed-control task groups produced identical waiting states and outputs
  across four delays. Waiting removes delay-dependent variation in this setup.
- On 14 fully matched multi-call Linux tasks, waiting and conventional execution
  succeeded on the same 3 tasks; asynchronous execution succeeded on 1.
- The 36-prompt supplied-arithmetic smoke set produced identical text for waiting
  and non-waiting protected editing; both scored 36/36. This does not substitute
  for the unrun larger evaluation.
- Invalid calls and missing final answers persist after correct results arrive.
  These data do not establish waiting as a universal default or establish a need
  for fine-tuning.

See the reports for exact gates, scoring rules, placement caveats and per-task
failure evidence. Native message insertion before commitment is distinct from
showing that the result's own block still contains masks.

## Repository layout

- `outputs/`: preserved source, reports, task fixtures, raw JSON/JSONL records,
  event logs, manifests and verified ZIP archives for each experiment.
- `work/`: orchestration, analysis and backup helpers, upstream reference source,
  and intermediate snapshots used during the experiments.
- `specs/`: original supplied experiment briefs.

Historical artifacts are kept in their original locations so recorded paths and
hashes remain meaningful. ZIP archives duplicate some expanded contents and are
retained as independently verified delivery snapshots. Local virtual environments,
Python caches and SSH known-host records are excluded.

## Reproduction

Read each experiment's README and protocol before executing its runner. v1.2 uses
frozen `inclusionAI/LLaDA2.2-mini` revision
`e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`, BF16, batch size 1, on an A100 80 GB.
Its exact GPU package versions are in
[requirements.txt](outputs/v1.2-pilot/requirements.txt). Model weights are not
included. Linux calls use the supplied Docker gateway and synthetic fixtures,
with a fresh network-disabled container per call.

Scripts under `work/` may contain historical absolute paths and pod addresses;
adapt these for a new environment. Nothing in this repository automatically
provisions or starts GPU resources on checkout. Historical lifecycle records
are snapshots, not current cloud status.

For CPU-only sampler invariant tests, install a compatible PyTorch build and run:

```sh
python outputs/v1.2-pilot/test_wait.py
```

The `report.py` and `audit.py` scripts reproduce analyses from saved records;
they do not load the language model. Some audit helpers assume the original
workspace layout, which this checkout preserves.

## Attribution

Reference model and sampler code under `work/` and experiment snapshots may be
third-party code. Their original notices and upstream license terms continue to
apply. This repository does not grant a new license to model weights or replace
upstream licenses. See [third-party sources](THIRD_PARTY.md).
