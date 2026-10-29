# Linux system-call diffusion pilot

A v2 prototype extending the arithmetic pilot. All filesystem data is synthetic.
The GPU is retained at the user's request: pod `26i6z57kcsek7x`, A100 80 GB,
quoted GPU compute rate $1.79/hour.

## Implemented

- Seven typed operations: read_file, list_dir, stat, clock, run, write_file, remove.
- Every operation executes inside a fresh Linux Docker container with network
  disabled. `run` starts from a copy of the fixture workspace and discards its
  writable container layer afterward. Only committed write_file/remove calls get
  a writable mount of the synthetic workspace.
- Bounded worker pool, in-flight read deduplication, completion polling, stale-result
  rejection, and a commit buffer. An unchanged, fully committed call span is
  required before a persistent effect is dispatched.
- Errors and timeouts become result text. Results are token-budgeted and include
  a truncation marker when too long.
- A local loopback gateway and SSH reverse tunnel connect the Linux tool sandbox
  to the A100 sampler. This is a host-side queue experiment, not GPU-only dispatch.
- Generated-call parsing validates JSON inside a reserved call span, measures its
  token confidence, and checks which request tokens have actually committed.

## Experimental layers

1. `test_protocol.py` and `test_parser.py`: controlled protocol/isolation checks.
   The unsafe commit-rule control deliberately writes a disposable test file from
   a draft, demonstrating the stray effect that the guarded version prevents.
2. `model_pilot.py`: 24 structured-call mechanism controls. Calls are supplied and
   immutable; this isolates result delivery from call discovery. Conditions are
   no calls, async, sync, async with a 20-step minimum delay, and a post-generation
   restart. The restart reuses the completed baseline first pass, performs calls,
   and uses another 64 model passes with results; its total timing includes both
   passes and the intervening tool time.
3. `generated_pilot.py`: eight examples where the frozen model generates the JSON
   call inside denoising: two file lookups, two code-output tasks, two CSV sums,
   and two literal writes. It compares no calls with asynchronous execution.
   Calls get the first 32 steps; answers get the next 32. No step waits for a call.
   This schedule is a deliberately structured scaffold, not unrestricted chat.
4. The free-generation syntax probe separately generates six call requests and
   executes valid read/isolated-run requests after generation to check usefulness.

The first structured run puts `<res>` inside an assistant prefill. A second run
puts it in the user/tool-result turn, preserving a fixed result slot. Both are
retained; the layout change is exploratory, not a held-out confirmation. The
second run was interrupted by a pod storage resize and is incomplete. The
generated-call prototype described above was implemented but not run before
the experiment switched to LLaDA2.2-mini native tools.

## Reproduce

On the Mac/CPU gateway host, with Docker available:

```sh
python3 make_tasks.py
docker build -t diffusion-syscall-pilot:local .
python3 -m unittest -v test_parser test_protocol
python3 gateway.py --workspace "$PWD/workspace" --port 18765
```

Forward GPU-host loopback port 18766 to gateway-host loopback port 18765 with SSH.
`async_engine.py` intentionally disables HTTP proxies for this loopback connection.
The actual SSH identity is supplied by the operator; no credentials are packaged.

On the CUDA host, with the pinned LLaDA checkpoint and dependencies from v1:

```sh
python model_pilot.py --tasks tasks.json --output syscall-user-results --generated
```

`model-pilot-assistant-layout.py` reproduces the original assistant-prefill control.
`generated_pilot.py` can also run separately. The result-slot width is 128 tokens;
model and checkpoint revision are pinned in source. Docker's base image digest is
pinned in the Dockerfile. The custom image contains only the container runner.

## Interpretation limits

This is a small implementation pilot, not the full 1,500-task proposed benchmark.
Supplied-call results do not establish autonomous call selection. The generated
call run uses explicit JSON examples, reserved spans and a two-block schedule.
The controlled commit test proves that trace's behavior; real-model workspace
changes must additionally be checked against the requested file contents.

The gateway is split across two hosts, so network/tunnel delay contributes to
submit-to-completion latency. Container programs themselves have no network.
Async wall time overlaps call run time; subtracting a sum of call durations would
be misleading. Report sampling time, sync wait time, barrier overhead, and time
outside generation separately. Polling a completed future is allowed; waiting on
an incomplete future inside an async barrier is not.

Writes in this pilot use literal data and have no speculative read dependencies.
General read-dependent writes and commit-time read revalidation are not implemented.
Likewise, this is not v3 security hardening, a raw syscall ABI, or record/replay.

## Completed LLaDA-8B control results

The assistant-prefill run completed all 24 tasks: baseline 0/24; async, sync,
delayed async, and post-generation restart each 11/24 (0/8 file, 3/8 code,
8/8 CSV). These supplied-call controls establish delivery, not autonomous tool
selection. Six free syntax probes produced five valid calls and two correct
executed results. Raw records are in `assistant-layout-results/`. Partial
user-layout records are in `user-layout-results/`; they are not a full benchmark.
The continuing native-tool experiment is in `../llada22-pilot/`.
