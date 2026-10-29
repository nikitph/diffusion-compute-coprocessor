#!/bin/bash
while kill -0 876 2>/dev/null; do sleep 15; done
cd /workspace/v1.1-pilot || exit 1
if grep -q 'ALL STAGES COMPLETE' finish.log; then
  HF_HOME=/workspace/hf HF_HUB_DISABLE_PROGRESS_BARS=1 /workspace/v11-venv/bin/python -u cross_host_repeat.py > cross-host.log 2>&1
fi
