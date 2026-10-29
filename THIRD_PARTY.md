# Third-party sources

This research uses and retains reference code from:

- [inclusionAI/LLaDA2.2-mini](https://huggingface.co/inclusionAI/LLaDA2.2-mini),
  pinned in the experiment source to revision
  `e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`.
- [GSAI-ML/LLaDA-8B-Instruct](https://huggingface.co/GSAI-ML/LLaDA-8B-Instruct),
  pinned in the initial pilot to revision
  `08b83a6feb34df1a6011b80c3c00c7563e963b07`.

Upstream reference copies include `work/llada22-source/`,
`work/configuration_llada.py`, `work/modeling_llada.py` and
`work/llada_generate.py`. Experiment adapters may build on upstream samplers.
Original source notices are preserved. Consult the pinned upstream sources for
applicable terms. Model weights and installed dependency distributions are not
included in this repository.

## Included notices

- `licenses/llada2-LICENSE` is the Apache 2.0 license text retrieved from
  the inclusionAI/LLaDA2.X upstream repository. The preserved LLaDA2.2 source
  headers also identify Apache 2.0.
- The pinned LLaDA-8B model metadata in `work/model_info.json` declares MIT.
  The pinned Hugging Face snapshot does not contain a standalone license file.
  No copyright holder or replacement license notice has been invented here.
