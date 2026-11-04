# Provenance

- Weight-space programming motivation: https://rikiyat.github.io/blog/weight-space-programming/
- Tiny-A2D project: https://github.com/ZHZisZZ/dllm
- Diffusion checkpoint: https://huggingface.co/dllm-hub/Qwen2.5-Coder-0.5B-Instruct-diffusion-mdlm-v0.1/tree/a284e895a6248256baf2f60502e54aba61b24c1a
- Autoregressive checkpoint: https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct/tree/ea3f2471cf1b1f0db85067f1ef93848e38e88c25

`modeling_a2d.py` is the pinned diffusion model's `modeling_qwen2.py`, with the
unused `__main__` conversion example removed. The example imports the complete
`dllm` package; Transformers' remote-code import scanner required it even though
it is not part of inference. Removing only that example allows direct class
loading without unrelated training dependencies. Architecture and forward method
are unchanged. Apache-2.0 license is retained in `LICENSE-A2D`.

The local sampler follows the model card's non-shifted masked-token predictions.
Its active-canvas intervention, evaluator and bounded program interpreter are
experiment code. `models.py` projects only requested hidden-state rows in the
constrained pilot; the diagnostic compares these logits against the model's full
forward method. The free-program pilot projects all 80 output positions.

No pretrained model weights are committed. Both checkpoints reside in the normal
Hugging Face cache on the user's computer. Source manifests preserve the measured
code versions. No training or gradient updates were performed.

The initial Runpod attempts returned capacity errors for A100/A40 and HTTP 402
for A6000. No pod was created. At the user's request, all model comparisons moved
to local MPS inference on the Apple M1 Pro. Existing cloud resources were not changed.
