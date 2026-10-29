# v1.2 — final calibration, experiment stopped early

The user requested calibration from preserved results after Runpod stopped the pod
and returned HTTP 402 on restart. No further GPU runs are planned in this task.

- Preserved: 144 delayed-control records, 85 Linux records, 108 smoke records,
  5 exact-reproduction records, raw event/timing logs and frozen runtime source.
- Linux analysis includes 21 fully matched tasks: prior7 + multi-call14. Task214
  has only L0 and is retained raw but excluded from comparisons.
- Waiting/conventional/async multi-call: 3/14, 3/14, 1/14. Waiting and conventional
  have exactly the same successes. H2 passes at 4/7; H3 fails. H4/H5 are unrun.
- All 12 delayed task groups have identical waiting states and outputs across
  delays. Arithmetic integer present24/24, strict12/24; hidden value20/24,
  strict16/24. See RESULTS.md for calibrated interpretation and limitations.
- Both pods hex6gc4ufd8xt6 and 26i6z57kcsek7x are verified EXITED. Retained disks
  remain billable. Local gateway, tunnel, sync and caffeinate are stopped.
- Last successful remote copy and frozen computational source hashes verified
  locally. No post-shutdown remote read was attempted after the user elected
  to stop; a possible uncopied tail on the persistent disk is not analysed.

RESULTS.md is the final analysis of this partial run, not a claim that all planned
v1.2 experiments completed. The report, audits, raw records and exact source are
packaged in diffusion-v1.2-calibrated-results-2026-10-29.zip in the parent folder.
