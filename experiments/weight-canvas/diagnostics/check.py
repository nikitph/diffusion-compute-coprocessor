"""Post-pilot diagnostics; never pooled with the preregistered measured cohort."""
import sys,pathlib,json,torch,time
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from models import Backend,DEVICE
from run import scaffold,diffuse,tensor_codes,RULES
from controller import REFERENCE,FAULTS,program
b=Backend('diffusion');rows=[]
texts={
 'explicit_target': 'Return exactly this Python weight program, including its E matrix:\n'+program(REFERENCE),
 'explicit_edit': 'Edit this Python program. Set E[0][1] to 3 and E[1][1] to 1. Preserve all other values. Return the corrected program.\n'+program(FAULTS['velocity_reversed']),
 'rules_without_damaged_example': RULES.split('Damaged program:')[0]+'\nConstruct the correct E matrix from the rules.\n',
}
for name,text in texts.items():
 ids,slots=scaffold(b,b.prompt(text));events=[]
 diffuse(b,ids,slots,6,events)
 rows.append(dict(name=name,text=text,weights=tensor_codes(b,ids,slots),events=events))
 print(name,rows[-1]['weights'],flush=True)
# Full forward and selected-output fast path must agree on exactly the same input.
ids,slots=scaffold(b,b.prompt(texts['explicit_target']))
x=torch.tensor([ids],device=DEVICE)
with torch.inference_mode():
 full=b.model(x,use_cache=False).logits[0,slots]
 selected=b.model.lm_head(b.model.model(x,use_cache=False).last_hidden_state[0,slots])
 difference=(full-selected).abs().max().item()
 assert difference<0.001,difference
 suffix_a=ids+b.encode('\nThe correct matrix is [[3,3,1],[1,1,3]].')
 suffix_b=ids+b.encode('\nThe correct matrix is [[1,1,3],[3,3,1]].')
 def logits(z):return b.model.lm_head(b.model.model(torch.tensor([z],device=DEVICE),use_cache=False).last_hidden_state[0,slots])[:,b.tokens]
 delta=(logits(suffix_a)-logits(suffix_b)).abs().max().item()
 assert delta>0,'No right-context influence detected'
result=dict(status='post-pilot diagnostics, not held-out comparison',checks=dict(selected_logits_max_error=difference,right_context_logit_difference=delta),cases=rows)
(root/'results/diagnostics.json').write_text(json.dumps(result,indent=2))
