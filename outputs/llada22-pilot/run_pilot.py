import argparse,json,pathlib,re,time,torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from transformers.utils import logging as hf_logging
from huggingface_hub.utils import disable_progress_bars
from sampler import decode,MASK
from native_tools import definitions,messages,parse,Monitor,signature,remote_execute
from arithmetic_hook import ArithmeticHook
from arith_reference import dataset,score as arithmetic_score,posthoc
from lock_check import check
MODEL='inclusionAI/LLaDA2.2-mini';REV='e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5'
hf_logging.disable_progress_bar();disable_progress_bars()

def prompt_ids(tok,conversation,tools=None):
    return tok.apply_chat_template(conversation,tools=tools,add_generation_prompt=True,tokenize=True,return_tensors='pt',return_dict=True)['input_ids'].to('cuda')

def answer_score(text,expected):
    clean=text.strip();clean=re.sub(r'<\|[^>]+\|>','',clean).strip()
    lines=[x.strip() for x in clean.splitlines() if x.strip()]
    prediction=re.sub(r'^Answer\s*:\s*','',lines[-1] if lines else '',flags=re.I).strip('`"\' .')
    return {'prediction':prediction,'correct':prediction==expected,'contains_expected':bool(re.search(r'(?<![\w])'+re.escape(expected)+r'(?![\w])',clean))}

def native_case(model,tok,row,mode,delay=0):
    names=('write_file',) if row['kind']=='write' else ('read_file','run')
    defs=definitions(names)
    conversation=messages(row['question']);ids=prompt_ids(tok,conversation,defs if mode!='base' else None)
    monitor=Monitor(tok,delay_steps=delay,allowed=names) if mode=='async' else None
    total_start=time.perf_counter()
    output,first,_=decode(model,ids,gen_length=256 if mode!='base' else 128,hook=monitor.observe if monitor else None)
    first_text=tok.decode(output,skip_special_tokens=False);calls=[c for c in parse(first_text) if c['call']['name'] in names]
    if mode=='base' or not calls:
        if monitor:monitor.close()
        return dict(id=row['id'],kind=row['kind'],condition=mode,first_text=first_text,text=tok.decode(output,skip_special_tokens=True),expected=row['expected'],**answer_score(tok.decode(output,skip_special_tokens=True),row['expected']),
                    calls=calls,seconds=time.perf_counter()-total_start,first=first,valid_native_call=bool(calls))
    call=calls[0];key=signature(call['call']);stable=[{'anchor':call['id'],'call':call['call'],'committed':True}]
    ready=None;external_wait=0.;injected_step=None;events=[]
    if monitor:
        for d in monitor.engine.barrier(stable,first['forward_calls']):monitor.deliveries[signature(d['call'])]=d
        if key in monitor.deliveries:ready=monitor.deliveries[key]['result']
    else:
        t=time.perf_counter();ready=remote_execute(call['call'],committed=call['call']['name']=='write_file');external_wait=time.perf_counter()-t
    template=tok.apply_chat_template(messages(row['question'],call,'__EXTERNAL_RESULT__'),tools=defs,add_generation_prompt=True,tokenize=False)
    before,after=template.split('__EXTERNAL_RESULT__');left=tok.encode(before,add_special_tokens=False);right=tok.encode(after,add_special_tokens=False)
    width=64;lo=len(left);hi=lo+width;answer_input=torch.tensor([left+[MASK]*width+right],device='cuda')
    def encode_result(result):
        value=result.get('output','') if result.get('ok',False) else 'ERROR: '+result.get('output','unknown error')
        tokens=tok.encode(value.strip(),add_special_tokens=False)
        if len(tokens)>width:
            marker=tok.encode(' [truncated]',add_special_tokens=False);tokens=tokens[:width-len(marker)]+marker
        return tokens
    initial=[(lo,encode_result(ready),'native_tool_result')] if ready is not None else []
    received=ready is not None
    def receive(state):
        nonlocal ready,received,injected_step
        if not received:
            for d in monitor.engine.barrier(stable,first['forward_calls']+state.step):
                if signature(d['call'])==key:
                    ready=d['result'];state.lock(lo,encode_result(ready),label='native_tool_result');received=True;injected_step=state.step
        state.hold_block=not received
    answer,second,state=decode(model,answer_input,gen_length=128,prefix_holes=[(lo,hi)],initial_locks=initial,
                               hook=receive if monitor else None,allow_hold=bool(monitor))
    final_text=tok.decode(answer,skip_special_tokens=True);sampling_total=time.perf_counter()-total_start
    tail=time.perf_counter()
    if monitor:monitor.close();events=monitor.engine.events
    return dict(id=row['id'],kind=row['kind'],condition=mode,first_text=first_text,text=final_text,expected=row['expected'],**answer_score(final_text,row['expected']),
                calls=calls,valid_native_call=True,seconds=sampling_total,first=first,second=second,tool_result=ready,
                external_wait_seconds=external_wait,finalization_seconds=time.perf_counter()-tail,result_received=received,
                result_injected_answer_step=injected_step,events=events)

def main():
    p=argparse.ArgumentParser();p.add_argument('--arithmetic-limit',type=int,default=36);p.add_argument('--tool-limit',type=int,default=6);p.add_argument('--output',default='mini-results');a=p.parse_args()
    out=pathlib.Path(a.output);out.mkdir(exist_ok=True);(out/'lock-test.json').write_text(json.dumps(check(),indent=2));print('lock check passed',flush=True)
    tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True)
    model=AutoModelForCausalLM.from_pretrained(MODEL,revision=REV,trust_remote_code=True,dtype=torch.bfloat16,device_map={'':'cuda'},attn_implementation='sdpa').eval()
    (out/'environment.json').write_text(json.dumps({'model':MODEL,'revision':REV,'torch':torch.__version__,'gpu':torch.cuda.get_device_name(),'sampler':'protected fixed-position block diffusion','block_length':32,'steps':8,'post_steps':2,'structural_edits':False,'token_to_token_edits':True,'batch_size':1},indent=2));print('model loaded',flush=True)
    # Warm the native big-integer kernel before timed measurements.
    from gpu_arithmetic import encode,compute
    compute(encode([12]),encode([34]),torch.tensor([2],dtype=torch.int32,device='cuda'));torch.cuda.synchronize()
    # Run tool capability first, then the complete v1 task set on the new model.
    tasks=json.loads(pathlib.Path('tasks.json').read_text());chosen=[tasks[i] for i in (0,1,8,9,16,17)][:a.tool_limit]
    chosen.append({'id':100,'kind':'write','question':'Use write_file to save the literal text native-written-7319 to model_writes/native.txt. After success return DONE.','expected':'DONE'})
    (out/'tool-tasks.json').write_text(json.dumps(chosen,indent=2))
    with (out/'tools.jsonl').open('w') as f:
        for row in chosen:
            for mode in ('base','conventional','async'):
                record=native_case(model,tok,row,mode);f.write(json.dumps(record)+'\n');f.flush()
                print(json.dumps({'task':'tools','id':row['id'],'kind':row['kind'],'mode':mode,'correct':record['correct'],'contains_expected':record['contains_expected'],'valid_call':record['valid_native_call'],'received':record.get('result_received'),'seconds':round(record['seconds'],2)}),flush=True)
    rows=dataset()[:a.arithmetic_limit];(out/'arithmetic-tasks.json').write_text(json.dumps(rows,indent=2))
    with (out/'arithmetic.jsonl').open('w') as f:
        for row in rows:
            ids=prompt_ids(tok,[{'role':'user','content':row['prompt']}])
            for mode in ('base','mid'):
                hook=ArithmeticHook(tok,row) if mode=='mid' else None
                output,metrics,_=decode(model,ids,gen_length=192,hook=hook)
                text=tok.decode(output,skip_special_tokens=True)
                record={'id':row['id'],'kind':row['kind'],'digits':row['digits'],'condition':mode,'text':text,'expected':row['expected'],**arithmetic_score(text,row),'metrics':metrics,'injection_events':hook.events if hook else []}
                f.write(json.dumps(record)+'\n');f.flush()
                if mode=='base':
                    corrected=posthoc(text,row['kind']);f.write(json.dumps({'id':row['id'],'kind':row['kind'],'digits':row['digits'],'condition':'posthoc','text':corrected,'expected':row['expected'],**arithmetic_score(corrected,row)})+'\n');f.flush()
                print(json.dumps({'task':'arithmetic','id':row['id'],'mode':mode,'correct':record['correct'],'injected':hook.done if hook else False,'seconds':round(metrics['seconds'],2),'forward_calls':metrics['forward_calls']}),flush=True)
if __name__=='__main__':main()
