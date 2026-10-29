# Complete

The main frozen-weight experiment is complete and saved locally: 2,160 expanded arithmetic records, 480 block-64 records, and 101 Linux records, plus smoke tests, repeat checks and controls. See RESULTS.md for findings and limitations.

All 52 transferred remote files were verified against remote SHA-256 hashes, and the cumulative archive was independently verified. Both experiment pods are EXITED; GPU compute has stopped. Persistent disks are retained and remain billable. See infrastructure.json and final-archive-verification.json.

The original 45 canonical and 5 legacy repeats matched exactly. The optional 30-case cross-host repeat did not run: its model reload stalled on storage reads, so it was aborted to avoid more idle compute charges. This limitation is recorded explicitly.

The prior funding interruption remains in checkpoint-status.json as historical context.
