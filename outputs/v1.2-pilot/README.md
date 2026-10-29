# v1.2 — wait by default

Final calibration from an interrupted run: the user elected to analyse preserved
results after an HTTP 402 funding interruption. See STATUS.md for completed and
unrun cohorts. Both pods are stopped; persistent disks remain billable.

Read `RESULTS.md` for outcomes and `PROTOCOL.md` for the frozen interpretation of
the supplied brief. `results-v1.2/` contains line-delimited raw records, event
logs, timings, prerequisites, source hashes and independent audits. The v1.1
experiment is preserved separately and has not been edited.

## Reproduction

GPU environment: pinned `requirements.txt`, CUDA 12.8 / PyTorch 2.8.0, one A100
SXM4 80GB. `pilot.py` pins the exact Hugging Face model revision. The model cache
was copied to `/dev/shm/v12-hf` to avoid network-filesystem page stalls during
loading; `HF_HOME` points there and hub access is offline for the run.

Start the existing `../syscall-pilot/gateway.py` locally against the unchanged
`../syscall-pilot/workspace` fixtures. The gateway launches a fresh
`diffusion-syscall-pilot:local` Docker container with networking disabled for
every call. Forward remote loopback port 18766 to local loopback port 18765.

From this source directory on the GPU, run `python run_v12.py`. It loads the model
once, performs prerequisites, freezes source hashes, and runs all comparison
arms in that session. Use a fresh results directory for reproduction: the driver
appends raw records and deliberately does not silently resume mixed sessions.

CPU invariant tests: `python test_wait.py` (PyTorch required). Local analysis:
`python report.py` and `python audit.py`. Reporting does not call the model.
The sampler is a protected-edit adapter, not the untouched upstream sampler.
No end-to-end GPU-only execution or pure CUDA latency claim is made.
