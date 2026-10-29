# v2 · Linux system calls inside the denoising loop

Oct 28, 2026 · @CREDIT IQ

## Summary

v2 replaces v1's arithmetic kernel with a gateway to a small set of Linux system calls, run asynchronously between denoising steps. The model can read files, run programs and check the clock mid-generation without stalling the batch.

Two rules carry the design:

1. **Submit now, collect later.** A call is queued at step *t*; denoising continues; its result is locked into the canvas at whatever step it completes. This follows the submission/completion-queue pattern of Linux's io\_uring.
2. **Reads on drafts, effects on commit.** Calls with no side effects may run from draft tokens. Calls that change the world wait in a buffer until the tokens requesting them are locked, and are dropped if the draft changes first. This mirrors how CPUs execute reads speculatively but hold stores until commit.

v2 starts from v1's P0 harness (sampler hook, trigger, parser, locker). Security hardening and reproducibility are deferred to v3; v2 runs in a disposable container with no network.

## Goals, non-goals, success criteria

**Goals**

1. Show that asynchronous system calls can run inside the denoising loop without stalling the batch.
2. Show that results arriving mid-generation (file contents, program output) improve answers the model cannot produce alone.
3. Show that the commit rule prevents side effects from drafts the model later revises.
4. Measure how many steps a call takes to land and how the model uses late-arriving results.

**Non-goals for v2**

- Security hardening beyond a disposable container (seccomp profiles, gVisor, capability tokens). Deferred to v3.
- Reproducibility and record/replay of call traces. Deferred to v3.
- Network access, calls to other LLMs, and recursion. Later versions.
- Raw system-call ABI (pointers, structs). v2 exposes typed wrappers only.

**Success criteria** (targets, to revise after the first run)

| Criterion | Target |
| --- | --- |
| Batch stalls caused by a pending call | 0 |
| Accuracy gain on code-output and file-lookup tasks vs base model | ≥ 25 points |
| Side-effecting calls issued from tokens later revised | 0 (by construction) |
| Added wall-clock latency vs base, excluding call run time | ≤ 15% |

## Design

Every call takes one of two paths, chosen by its effect class: draft-safe calls go straight to the queue, side-effecting calls wait in a commit buffer.

&#91;embedded content: call path · draft-safe calls vs side effects\]

**Components**

| Component | Role | v2 form |
| --- | --- | --- |
| Call parser | finds `<sys>…</sys>` spans whose tokens clear confidence τ; validates against the call table | extends v1's parser |
| Submission queue | holds calls from the batch; deduplicates identical calls | in-memory ring buffer, host side |
| Gateway | runs calls in a disposable container; one overlay per `run` | host process + Docker or Podman, no network |
| Completion queue | results waiting to be locked | polled at each step barrier |
| Commit buffer | side-effecting calls waiting for their span to lock | released or dropped at each barrier |
| Locker | writes results into `<res>` slots, marked fixed | v1's locker |

**At each step barrier** the sampler does three things, in order, without waiting on any call: lock every completed result into its slot; release buffered writes whose span is now locked, and drop those whose span changed; submit newly stable call spans. Then it runs the next denoising step.

## Call surface

v2 exposes seven typed calls; each has an effect class that decides whether it may run from draft tokens or only after commit.

| Call | Wraps | Effect class | Runs from |
| --- | --- | --- | --- |
| `read_file(path, offset, len)` | `open`, `read` | read-only | draft |
| `list_dir(path)` | `getdents64` | read-only | draft |
| `stat(path)` | `stat` | read-only | draft |
| `clock()` | `clock_gettime` | read-only | draft |
| `run(cmd, stdin, timeout_ms)` | `fork`, `execve`, `wait4` in a throwaway overlay | isolated: writes land in an overlay deleted afterwards | draft |
| `write_file(path, data)` | `open`, `write` | side effect | commit |
| `remove(path)` | `unlink` | side effect | commit |

`run` is what makes v2 interesting: the model can compile and execute code from a draft, because each run gets a fresh copy-on-write overlay (overlayfs) that is thrown away. Only `write_file` and `remove` touch the persistent workspace.

**Canvas syntax.** A call is a span in the canvas followed by a fixed-width result slot of masked tokens:

```
<sys>run "python3 -c 'print(sum(range(10**6)))'" 2000</sys><res>[MASK × 128]</res>
```

The parser matches `<sys>…</sys>`, validates the call against the table, and fills `<res>` when the result arrives. Output longer than 128 tokens is truncated with a `[truncated]` marker. Errors return as text (`ENOENT`, `timeout`, exit code), never as an exception that halts sampling.

## Tasks, baselines, metrics, experiments

The tasks are chosen so the right answer needs something only the system can provide: real program output, or the contents of a file the model has never seen.

**Tasks**

| Task | Needs | Size |
| --- | --- | --- |
| Code output prediction (CRUXEval-style: what does this program print?) | `run` | 500 |
| File lookup in a synthetic workspace (configs, CSVs, logs) | `read_file`, `list_dir` | 500 |
| Compute over files (e.g. count ERROR lines, sum a CSV column) | `read_file` + `run` | 300 |
| Write tasks ("save the result to out.txt") | `write_file` on commit | 200 |

**Baselines**

1. Base diffusion model, no calls.
2. Conventional tool loop: generate to completion, execute the calls, re-prompt with results. Same model, same calls.
3. Synchronous v2: calls run mid-loop but the batch waits for each result.

**Metrics**

- Accuracy per task.
- Batch stalls: steps where any sequence waited on a call (target 0).
- Steps to land: distribution of steps between submit and result.
- Wasted calls: calls whose requesting span was revised before the result was used.
- Stray effects: side-effecting calls issued from tokens later revised (target 0). Checked by diffing the workspace against expected state.
- Late-result use: share of results arriving after step *T*/2 that still change the answer.

**Experiments**

| ID | Experiment | Varies | Question answered |
| --- | --- | --- | --- |
| E1 | Main result | v2 vs baselines 1 and 2 | Do mid-loop calls beat no calls and a post-generation tool loop? |
| E2 | Async vs sync | v2 vs baseline 3 | What does non-blocking submission save in wall-clock time? |
| E3 | Commit rule off | effects allowed from drafts | How many stray writes does the rule prevent? |
| E4 | Artificial delay | result held back 0, 5, 20, 50 steps | How late can a result land and still help? |
| E5 | Result slot width | 32, 128, 512 tokens | Cost of truncation vs canvas length |
| E6 | Lock vs soft hint | clamp program output vs bias logits | Does the model need hard locks for system results? |

## Risks, open questions, timeline

The main risk is that a frozen model never writes well-formed `<sys>` spans, so v2 likely needs a small fine-tune earlier than v1 did.

**Risks and fallbacks**

| Risk | Effect | Fallback |
| --- | --- | --- |
| Frozen model does not emit call syntax | no calls fire | few-shot prompt template first; then LoRA on \~2,000 synthetic traces with calls and locked results |
| Call spans keep changing while noisy | many wasted calls | submit only when the span's confidence clears τ (v1's trigger), and deduplicate identical calls |
| Results arrive after the answer has settled | result ignored | reserve late steps for re-denoising around new results; E4 measures the window |
| Long program output | truncation hides the answer | E5; let the model request an offset with `read_file` on a saved output file |
| Commit-time effect depends on a value that was itself a draft read | stale write | re-run dependent reads at commit before releasing the write |

**Open questions**

- Should `run` results be hard-locked (exact, like v1) or soft hints? E6 decides.
- Can a call issued from a draft be cancelled when its span changes, or only ignored? Cancelling saves compute but needs process tracking.
- Where does the gateway live: a host process fed by a GPU-side queue, or a sidecar container per batch?

**Timeline** (estimates, single researcher, starting from v1's P0 harness)

- Gateway, call parser, overlay sandbox: about 1 week.
- Async queue and commit buffer: about 1 week.
- Tasks, baselines, E1–E3: about 1 week.
- Fine-tune if needed, E4–E6: about 2 weeks.
