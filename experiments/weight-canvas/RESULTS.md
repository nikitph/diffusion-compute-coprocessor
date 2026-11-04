# Weight canvas — local pilot results

Measured constrained weight-repair pilot on an Apple M1 Pro (16 GB). No cloud GPU was started.

Completed records: 30/30. Six faults, 512 held-out situations per fault; these are six repair tasks, not 3,072 independent model trials.

| Condition | Improved tasks | Final catches | Changed after feedback | Regressions on previously caught situations | Forward calls |
|---|---:|---:|---:|---:|---:|
| D-active | 0/6 | 1725/3072 | 0/6 | 0 | 54 |
| D-round | 0/6 | 1725/3072 | 0/6 | 0 | 72 |
| D-shuffled | 0/6 | 1725/3072 | 0/6 | 0 | 54 |
| D-none | 0/6 | 1725/3072 | 0/6 | 0 | 54 |
| AR-round | 0/6 | 1725/3072 | 0/6 | 0 | 72 |

**Conclusion:** all 30 constrained runs reproduced the damaged weights unchanged. This pilot provides no evidence of feedback-driven repair or a diffusion advantage. A post-pilot unrestricted diagnostic succeeded at an explicit two-assignment repair, so the constrained interface is a material limitation; do not infer that the model cannot write weight edits at all.

## Per-task results

| Fault | Initial | D-active | D-round | D-shuffled | D-none | AR-round |
|---|---:|---:|---:|---:|---:|---:|
| velocity_reversed | 239 | 239 | 239 | 239 | 239 | 239 |
| position_reversed | 175 | 175 | 175 | 175 | 175 | 175 |
| paddle_reversed | 181 | 181 | 181 | 181 | 181 | 181 |
| velocity_missing | 321 | 321 | 321 | 321 | 321 | 321 |
| one_hidden_dead | 367 | 367 | 367 | 367 | 367 | 367 |
| gain_doubled | 442 | 442 | 442 | 442 | 442 | 442 |

## What this tests

The runtime evaluates a provisional six-weight controller while three slots are still masked. It writes versioned feedback after the weight program, locks that feedback, reopens the six weights, and continues in the same canvas. All fixed syntax and reports are checked for immutability each denoising step.

This is numeric inpainting inside a fixed Python weight-assignment scaffold. The decoder is restricted to five digits per weight; the runtime subtracts two to represent signed weights. It is not unrestricted code synthesis, a learned execution trigger, selective invalidation, or self-modification of the generating model.

No gradient updates, reference-weight substitution, best-of search, or held-out feedback were used. All results are the model-produced final candidate, including regressions.

D-active/D-shuffled/D-none use 9 forward passes; D-round and AR-round use 12. Early feedback and schedule differ. AR prefixes are recomputed without KV caching, so wall-time comparisons are not optimized architecture benchmarks.

The diffusion model is an adapted Qwen2.5-Coder-0.5B checkpoint; the AR model is its original instruction-tuned source. Additional diffusion fine-tuning confounds architecture comparisons. D-shuffled scrambles observation/outcome alignment but retains the true aggregate score, so it is not a complete information ablation.

The evaluator independently recomputed every saved final score. Environment tests include a 10,000-situation reference-controller check and an independently derived action-policy check.

See `PROTOCOL.md`, `results/pilot/source-manifest.json`, pinned environment files, complete step canvases in `records.jsonl`, and `summary.json`.
