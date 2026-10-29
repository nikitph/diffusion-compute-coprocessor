"""Answer-only controls: same successful tool results, no reserved result holes."""
import json,pathlib,time,torch
from run_pilot import MODEL,REV,prompt_ids,answer_score,native_case
from transformers import AutoTokenizer,AutoModelForCausalLM
from native_tools import messages,definitions,parse
from sampler import decode
root=pathlib.Path('mini-results')
rows=[r for r in map(json.loads,(root/'tools.jsonl').read_text().splitlines()) if r['condition']=='conventional' and r.get('tool_result',{}).get('ok')]
tasks={r['id']:r for r in json.loads((root/'tool-tasks.json').read_text())}
tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True)
model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,trust_remote_code=True,dtype=torch.bfloat16,device_map={'':'cuda'},attn_implementation='sdpa').eval()
with (root/'dense-controls.jsonl').open('w') as f:
 for row in rows:
  task=tasks[row['id']];names=('write_file',) if task['kind']=='write' else ('read_file','run')
  ids=prompt_ids(tok,messages(task['question'],row['calls'][0],row['tool_result']['output']),definitions(names))
  for mode in ('protected_dense','upstream_dense'):
   start=time.perf_counter()
   with torch.inference_mode():
    if mode=='protected_dense':output,metrics,_=decode(model,ids,gen_length=128)
    else:
     output=model.generate(inputs=ids,gen_length=128,block_length=32,steps=8,threshold=.5,editing_threshold=0.,max_post_steps=2,max_steps_per_block=48,eos_early_stop=True,temperature=0.)[0]
     metrics={}
   torch.cuda.synchronize();text=tok.decode(output,skip_special_tokens=True)
   record=dict(id=row['id'],kind=row['kind'],condition=mode,text=text,expected=row['expected'],seconds=time.perf_counter()-start,metrics=metrics,**answer_score(text,row['expected']))
   f.write(json.dumps(record)+'\n');f.flush();print(json.dumps(record),flush=True)
with (root/'upstream-call-controls.jsonl').open('w') as f:
 for task in tasks.values():
  if task['id'] not in (9,17):continue
  ids=prompt_ids(tok,messages(task['question']),definitions())
  with torch.inference_mode():
   output=model.generate(inputs=ids,gen_length=256,block_length=32,steps=8,threshold=.5,editing_threshold=0.,max_post_steps=2,max_steps_per_block=48,eos_early_stop=True,temperature=0.)[0]
  text=tok.decode(output,skip_special_tokens=False)
  record=dict(id=task['id'],text=text,calls=parse(text));f.write(json.dumps(record)+'\n');f.flush()
record=native_case(model,tok,tasks[1],'async',delay=40)
(root/'delayed-control.json').write_text(json.dumps(record,indent=2))
print('controls complete',flush=True)
