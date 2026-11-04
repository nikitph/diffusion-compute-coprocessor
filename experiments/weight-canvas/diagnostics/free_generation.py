"""Post-pilot check: does removing the numeric-slot scaffold restore explicit editing?"""
import sys,pathlib,json,torch,time,ast,re
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from models import Backend,DEVICE,sync
from controller import program,FAULTS,validate
text='Edit this Python program. Set E[0][1] to 3 and E[1][1] to 1. Preserve all other values. Return only the complete E assignment, no explanation.\n'+program(FAULTS['velocity_reversed']).split('\n')[0]
rows=[]
for kind in ['diffusion','ar']:
    b=Backend(kind);prefix=b.prompt(text);start=time.perf_counter()
    with torch.inference_mode():
        if kind=='ar':
            x=torch.tensor([prefix],device=DEVICE)
            y=b.model.generate(x,max_new_tokens=80,do_sample=False,pad_token_id=b.tok.eos_token_id)
            output=y[0,len(prefix):].tolist()
        else:
            ids=prefix+[b.tok.mask_token_id]*80;x=torch.tensor([ids],device=DEVICE)
            for step in range(40):
                hidden=b.model.model(x,use_cache=False).last_hidden_state[:,len(prefix):]
                logits=b.model.lm_head(hidden).float()[0]
                logits[:,b.tok.mask_token_id]=-torch.inf
                v=logits.argmax(-1);p=logits.softmax(-1).gather(-1,v[:,None]).squeeze(-1)
                masked=x[0,len(prefix):]==b.tok.mask_token_id
                p[~masked]=-torch.inf;k=min(2,int(masked.sum()))
                ix=p.topk(k).indices;x[0,len(prefix)+ix]=v[ix]
            output=x[0,len(prefix):].tolist()
    sync();elapsed=time.perf_counter()-start
    decoded=b.tok.decode(output,skip_special_tokens=True)
    rows.append(dict(kind=kind,prompt=text,output=decoded,seconds=elapsed))
    print(kind,repr(decoded),flush=True)
    del b
    if DEVICE=='mps':torch.mps.empty_cache()
(root/'results/free-generation-diagnostic.json').write_text(json.dumps(rows,indent=2))
