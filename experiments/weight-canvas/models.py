"""Local, pinned model access. Restrict generation to the declared numeric slots."""
import time
import torch
from transformers import AutoTokenizer,AutoModelForMaskedLM,AutoModelForCausalLM

DIFF=('dllm-hub/Qwen2.5-Coder-0.5B-Instruct-diffusion-mdlm-v0.1','a284e895a6248256baf2f60502e54aba61b24c1a')
AR=('Qwen/Qwen2.5-Coder-0.5B-Instruct','ea3f2471cf1b1f0db85067f1ef93848e38e88c25')
DEVICE='mps' if torch.backends.mps.is_available() else 'cpu'

def sync():
    if DEVICE=='mps':torch.mps.synchronize()

class Backend:
    def __init__(self,kind):
        self.kind=kind;self.repo,self.revision=DIFF if kind=='diffusion' else AR
        self.tok=AutoTokenizer.from_pretrained(self.repo,revision=self.revision,local_files_only=True)
        config_kwargs={}
        if kind=='diffusion':
            from modeling_a2d import A2DQwen2Config,A2DQwen2LMHeadModel
            cls=A2DQwen2LMHeadModel
            config_kwargs['config']=A2DQwen2Config.from_pretrained(self.repo,revision=self.revision,local_files_only=True)
        else:cls=AutoModelForCausalLM
        self.model=cls.from_pretrained(self.repo,revision=self.revision,**config_kwargs,
            local_files_only=True,dtype=torch.float32,attn_implementation='sdpa').eval().to(DEVICE)
        self.tokens=[self.tok.encode(str(i),add_special_tokens=False)[0] for i in range(5)]
        assert all(self.tok.encode(str(i),add_special_tokens=False)==[self.tokens[i]] for i in range(5))
        self.calls=0;self.positions=0;self.seconds=0
    def encode(self,text):return self.tok.encode(text,add_special_tokens=False)
    def prompt(self,text):
        return self.tok.apply_chat_template([{'role':'user','content':text}],tokenize=True,add_generation_prompt=True)
    @torch.inference_mode()
    def predict(self,ids,positions):
        x=torch.tensor([ids],device=DEVICE);sync();start=time.perf_counter()
        # Compute only requested output rows. Attention still spans the entire canvas.
        hidden=self.model.model(input_ids=x,use_cache=False).last_hidden_state[0,positions]
        logits=self.model.lm_head(hidden).float()
        values=logits[:,self.tokens]
        probs=values.softmax(-1)
        choices=values.argmax(-1).tolist()
        confidence=probs.max(-1).values.tolist()
        sync();elapsed=time.perf_counter()-start
        self.calls+=1;self.positions+=len(ids);self.seconds+=elapsed
        return choices,confidence
    def counters(self):return dict(forward_calls=self.calls,processed_positions=self.positions,inference_seconds=self.seconds)
