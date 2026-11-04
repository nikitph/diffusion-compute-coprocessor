# Free-program pilot v0.2 — results

Completed 30/30 runs. All inference ran locally on Apple M1 Pro, FP32. No cloud pod was started.

Exploratory follow-up after the v0.1 interface diagnostic. These six tasks were already examined in v0.1; this is not a fresh confirmatory cohort.

| Condition | Valid programs | Improved tasks | Final catches | Active arrivals | Changed after feedback |
|---|---:|---:|---:|---:|---:|
| D-active | 2/6 | 0/6 | 560/3072 | 6 | 0 |
| D-round | 0/6 | 0/6 | 0/3072 | 0 | 0 |
| D-shuffled | 2/6 | 0/6 | 560/3072 | 6 | 0 |
| D-none | 0/6 | 0/6 | 0/3072 | 6 | 0 |
| AR-round | 6/6 | 0/6 | 1725/3072 | 0 | 0 |

**Conclusion:** no arm improved any of the six controllers. D-active and D-shuffled each retained the damaged controller in the same two tasks and produced invalid programs in the other four. The valid AR outputs all copied the damaged weights. There is no evidence here of feedback-driven repair or a diffusion advantage.

Invalid programs count as zero deployable catches, not as a controller that physically missed every ball. Validity and game performance are distinct. The baseline totals 1,725/3,072 catches. There are six model repair tasks; the 3,072 situations are nested evaluation observations.

| Fault | Initial | D-active | D-round | D-shuffled | D-none | AR-round |
|---|---:|---:|---:|---:|---:|---:|
| velocity_reversed | 239 | 239 | invalid | 239 | invalid | 239 |
| position_reversed | 175 | invalid | invalid | invalid | invalid | 175 |
| paddle_reversed | 181 | invalid | invalid | invalid | invalid | 181 |
| velocity_missing | 321 | 321 | invalid | 321 | invalid | 321 |
| one_hidden_dead | 367 | invalid | invalid | invalid | invalid | 367 |
| gain_doubled | 442 | invalid | invalid | invalid | invalid | 442 |

## Audit and limitations

Every valid saved program was independently reinterpreted and its score recomputed. Feedback hashes bind each report to its provisional controller. The decoder asserted prompt/report immutability at every step; arrivals require remaining masks before the provisional EOS.

Programs are interpreted through a bounded AST whitelist (literal E assignments and indexed integer writes). No generated code is executed through Python exec/eval. For fenced output the first code block is interpreted.

The generating model remains frozen. The target controller has only six writable weights on a five-value grid. Its architecture, output layer, and game rules are supplied; this is not unconstrained network synthesis.

Active delivery uses whole-output remasking in the same canvas, not selective semantic revision. Early feedback, total passes, message layout and masks differ from the round-based condition. The autoregressive source and diffusion adaptation have different training. These results do not isolate architecture or establish production latency gains.

The shuffled control retains truthful aggregate scores and corrupts observation/outcome pairings; it is a partial evidence control. The no-feedback arm tests whether task rules alone suffice. Report improvements only relative to both controls.

The six deliberately injected faults and one greedy run per condition are descriptive. No fine-tuning occurred. Reference-controller weights were never supplied to measured model runs.
