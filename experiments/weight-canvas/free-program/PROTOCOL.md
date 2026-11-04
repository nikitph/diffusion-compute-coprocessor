# Free-program pilot v0.2

Post-v0.1 follow-up, specified before its measured run. The six-slot interface in
v0.1 prevented an observed valid repair strategy: emitting indexed assignments.
The diffusion model succeeded on an explicit edit when free generation was allowed.
Do not pool v0.1 and v0.2 or claim v0.2 was preregistered before v0.1 observations.

Same six faults, models, FP32 MPS, game, practice/held-out seeds as v0.1. Held-out
scores were already seen in v0.1, so v0.2 is exploratory and requires fresh-task
replication for a confirmatory claim. No score-driven prompt search.

Output is unrestricted text, at most 80 tokens, decoded greedily. Allowed executable
programs assign a literal 2x3 E matrix and/or E[i][j] integer values in [0,4]. A
bounded AST interpreter applies these assignments to a copy of the stated damaged
matrix. Actual weights remain E-2. All other code is rejected; no Python exec/eval.
Unlike v0.1, the language model can generate arbitrary tokens and syntax errors.

Diffusion: full bidirectional canvas, low-confidence masking, two highest-confidence
masked tokens unmasked per forward pass, 40 passes per 80-token stage. No CFG.
D-active/D-shuffled/D-none: after at least ten passes, take the first parsable
provisional program with at least one actual masked token before its provisional
EOS (or end of canvas). Proposals fill currently masked tokens only for evaluating
this provisional candidate. Evaluate once, append the immutable report AFTER the
output canvas, reopen the 80 output tokens, and perform 40 additional passes.
Original prompt is unchanged. This is whole-region remasking, not selective repair
or native unmasked-token editing. Log preserved prefix and report hashes every step.
If no eligible pre-completion draft appears, do not invent one or inject retroactively;
record no dispatch and use the completed output. Early stopping is not used.

D-round: finish the initial 40 passes, evaluate completed program (or return parse
error), add candidate/report to a new user prompt, regenerate with 40 passes.
AR-round: two ordinary greedy generations, at most 80 tokens each, with KV cache;
the same candidate/report feedback is delivered between them.

One evaluation opportunity per arm; final evaluation separately. D-shuffled uses
unrelated observations paired with the true candidate's outcome values and retains
the truthful aggregate score. D-none evaluates for audit but withholds the result.
No automatic selection of the best candidate: evaluate the final model output even
when it is worse. Invalid programs have zero deployable catches, with explicit
validity separate from valid controllers' catch scores. Baseline retention is not
counted as model success. Record actual forward calls, positions, wall time, and
validity. AR/diffusion budgets and training histories differ; no architecture-only
or optimized throughput claim.

Same source manifest and full traces are saved separately. This is a small
exploratory mechanism test, not a benchmark of weight-space programming in general.
