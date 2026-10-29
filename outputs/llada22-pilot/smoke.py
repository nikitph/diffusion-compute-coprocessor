import json,time,torch
from transformers import AutoTokenizer,AutoModelForCausalLM
MODEL='inclusionAI/LLaDA2.2-mini';REV='e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5'
print('loading',flush=True)
tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True)
model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,trust_remote_code=True,dtype=torch.bfloat16,device_map={'':'cuda'},attn_implementation='sdpa').eval()
print(json.dumps({'loaded':True,'gpu':torch.cuda.get_device_name(),'allocated_gb':torch.cuda.memory_allocated()/1e9}),flush=True)
tools=[{'type':'function','function':{'name':'read_file','description':'Read bytes from a local file.','parameters':{'type':'object','properties':{'path':{'type':'string'},'offset':{'type':'integer'},'length':{'type':'integer'}},'required':['path','offset','length']}}}]
for prompt,defs,length in [('Reply exactly READY.',None,32),('Use read_file to read lookup/item_0.txt with offset 0 and length 128. Do not guess its contents.',tools,128)]:
 inputs=tok.apply_chat_template([{'role':'user','content':prompt}],tools=defs,tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True)['input_ids'].to('cuda')
 t=time.perf_counter()
 with torch.inference_mode():output=model.generate(inputs=inputs,gen_length=length,block_length=32,steps=8,threshold=.5,editing_threshold=0.,max_post_steps=2,max_steps_per_block=48,eos_early_stop=True,temperature=0.)
 torch.cuda.synchronize();print(json.dumps({'prompt':prompt,'seconds':time.perf_counter()-t,'text':tok.decode(output[0],skip_special_tokens=False),'prompt_tokens':inputs.shape[1]}),flush=True)
