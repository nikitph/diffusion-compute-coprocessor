"""Structured-call mechanism control; does NOT claim autonomous call discovery."""
import argparse,concurrent.futures,json,pathlib,re,time
import torch
from transformers import AutoModel,AutoTokenizer
from async_engine import Engine,remote_execute
MODEL='GSAI-ML/LLaDA-8B-Instruct';REV='08b83a6feb34df1a6011b80c3c00c7563e963b07';MASK=126336

def sync():torch.cuda.synchronize()
def score(text,expected):
    lines=[s.strip() for s in text.strip().splitlines() if s.strip()]
    prediction=lines[0] if lines else ''
    prediction=re.sub(r'^Answer\s*:\s*','',prediction,flags=re.I).strip('`"\' ')
    return {'prediction':prediction,'correct':prediction==expected}

def fetch_all(rows):
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(remote_execute,r['call']) for r in rows]
        results=[f.result() for f in futures]
    return results,time.perf_counter()-start

def output_tokens(tokenizer,result,width):
    text=result.get('output','')
    if not result.get('ok',False):text='ERROR: '+text
    ids=tokenizer.encode(text.strip(),add_special_tokens=False)
    truncated=len(ids)>width
    if truncated:
        marker=tokenizer.encode(' [truncated]',add_special_tokens=False)
        ids=ids[:max(0,width-len(marker))]+marker[:width]
    return ids,truncated

@torch.inference_mode()
def sample(model,tok,rows,mode,steps=64,slot=128,answer_length=64,trigger=16,delay=0,preloaded=None):
    texts=[];tails=[]
    for row in rows:
        prompt=('Use the supplied system-call result to answer the question. The call is already supplied; do not write another call. '
                'Return only the requested value, with no explanation. If no result is available, say UNKNOWN.\nQuestion: '+row['question'])
        content=prompt+'\n<sys>'+json.dumps(row['call'],separators=(',',':'))+'</sys><res>__TOOL_SLOT__</res>'
        rendered=tok.apply_chat_template([{'role':'user','content':content}],tokenize=False,add_generation_prompt=True)
        prefix,tail=rendered.split('__TOOL_SLOT__');texts.append(prefix);tails.append(tail+'Answer:')
    encoded=tok(texts,padding=True,return_tensors='pt').to('cuda');B=len(rows);P=encoded.input_ids.shape[1]
    assert len(set(tails))==1
    suffix=tok.encode(tails[0],add_special_tokens=False);A=P+slot+len(suffix);length=A+answer_length
    x=torch.full((B,length),MASK,dtype=torch.long,device='cuda');x[:,:P]=encoded.input_ids;x[:,P+slot:A]=torch.tensor(suffix,device='cuda')
    attention=torch.ones_like(x);attention[:,:P]=encoded.attention_mask;attention[:,P:P+slot]=0
    locked={};truncations=[]
    def lock(index,result,step):
        ids,truncated=output_tokens(tok,result,slot)
        x[index,P:P+slot]=tok.pad_token_id;attention[index,P:P+slot]=0
        if ids:
            x[index,P:P+len(ids)]=torch.tensor(ids,device='cuda');attention[index,P:P+len(ids)]=1
        locked[index]={'ids':ids,'step':step,'result':result};truncations.append(truncated)
    if preloaded is not None:
        for i,result in enumerate(preloaded):lock(i,result,-1)
    engine=Engine(delay_steps=delay) if mode=='async' else None
    observations=[{'anchor':str(i),'call':r['call'],'committed':True} for i,r in enumerate(rows)]
    hook_seconds=0;pending_stalls=0;sync_call_seconds=0;events=[]
    sync();start=time.perf_counter()
    for step in range(steps):
        hook_start=time.perf_counter()
        if mode=='async':
            completions=engine.barrier(observations if step>=trigger else [],step)
            for completion in completions:
                index=int(completion['anchor'])
                if index not in locked:lock(index,completion['result'],step)
        elif mode=='sync' and step==trigger:
            results,seconds=fetch_all(rows);sync_call_seconds+=seconds;pending_stalls+=1
            for i,result in enumerate(results):lock(i,result,step)
        hook_seconds+=time.perf_counter()-hook_start
        logits=model(x,attention_mask=attention).logits
        proposal=logits.argmax(-1);prob=logits.float().softmax(-1);confidence=prob.gather(-1,proposal.unsqueeze(-1)).squeeze(-1)
        masked=x==MASK;masked[:,:A]=False
        ranked=torch.where(masked,confidence,-torch.inf)
        # Exactly one answer token per step when length == steps.
        k=answer_length//steps+int(step<answer_length%steps)
        if k:
            positions=ranked.topk(k,dim=1).indices;x.scatter_(1,positions,proposal.gather(1,positions))
        del logits,prob
        sync() # Real denoising barrier; avoid polling ahead of queued GPU work.
    elapsed=time.perf_counter()-start
    output=tok.batch_decode(x[:,A:],skip_special_tokens=True)
    results=[]
    for i,lock_info in locked.items():
        results.append({'id':rows[i]['id'],'step':lock_info['step'],'lock_preserved':x[i,P:P+len(lock_info['ids'])].tolist()==lock_info['ids'],'ok':lock_info['result'].get('ok',False)})
    drain_start=time.perf_counter()
    if engine:
        engine.close();events=engine.events
    drain_seconds=time.perf_counter()-drain_start
    return output,dict(seconds=elapsed,hook_seconds=hook_seconds,pending_call_stalls=pending_stalls,synchronous_call_seconds=sync_call_seconds,
                       finalization_seconds=drain_seconds,locked=results,truncations=sum(truncations),events=events,
                       undelivered_at_end=len(engine.jobs) if engine else 0,remaining_answer_masks=int((x[:,A:]==MASK).sum()))

@torch.inference_mode()
def syntax_probe(model,tok,rows):
    records=[]
    # A separate free-generation probe, no call injection or supplied call span.
    for row in rows:
        instruction=('Choose a system call to obtain the answer. Return only <sys> followed by a JSON object with name and args, then </sys>. '
            'Available calls: read_file(path, offset, length); run(cmd as an argv list, stdin, timeout_ms). '
            'Example: <sys>{"name":"read_file","args":{"path":"example.txt","offset":0,"length":128}}</sys>. '
            'For Python execution use cmd ["python3","-c","CODE"].\nTask: '+row['question'])
        prompt=tok.apply_chat_template([{'role':'user','content':instruction}],tokenize=True,add_generation_prompt=True)
        P=len(prompt);x=torch.full((1,P+128),MASK,dtype=torch.long,device='cuda');x[0,:P]=torch.tensor(prompt,device='cuda')
        for step in range(64):
            logits=model(x).logits;proposal=logits.argmax(-1);prob=logits.float().softmax(-1)
            confidence=prob.gather(-1,proposal.unsqueeze(-1)).squeeze(-1);confidence=torch.where(x==MASK,confidence,-torch.inf)
            indices=confidence.topk(2,dim=1).indices;x.scatter_(1,indices,proposal.gather(1,indices));del logits,prob
        text=tok.decode(x[0,P:],skip_special_tokens=True);match=re.search(r'<sys>(.*?)</sys>',text,re.S);call=None
        if match:
            try:call=json.loads(match[1])
            except ValueError:pass
        valid=isinstance(call,dict) and call.get('name') in ('read_file','run') and isinstance(call.get('args'),dict)
        execution=remote_execute(call) if valid else None
        records.append({'id':row['id'],'kind':row['kind'],'text':text,'valid_envelope':valid,'expected_call_name':row['call']['name'],
                        'correct_call_name':bool(valid and call['name']==row['call']['name']),
                        'execution':execution,'tool_answer_correct':bool(execution and execution.get('ok') and execution.get('output','').strip()==row['expected'])})
    return records

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tasks',default='tasks.json');parser.add_argument('--output',default='results');parser.add_argument('--limit',type=int,default=24);parser.add_argument('--batch',type=int,default=4);parser.add_argument('--generated',action='store_true');args=parser.parse_args()
    rows=json.loads(pathlib.Path(args.tasks).read_text())[:args.limit];out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True);tok.padding_side='left'
    if tok.pad_token_id is None:tok.pad_token=tok.eos_token
    model=AutoModel.from_pretrained(MODEL,revision=REV,trust_remote_code=True,torch_dtype=torch.bfloat16).to('cuda').eval();torch.manual_seed(20261028)
    (out/'environment.json').write_text(json.dumps({'model':MODEL,'revision':REV,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'steps':64,'result_slot':128,'trigger_step':16,'call_mode':'supplied immutable structured calls; result slot in user turn','gateway':'Linux Docker on Mac via SSH reverse tunnel'},indent=2))
    sample(model,tok,rows[:args.batch],'base',steps=2)
    records=[]
    with (out/'records.jsonl').open('w') as rf,(out/'batches.jsonl').open('w') as bf:
        for offset in range(0,len(rows),args.batch):
            batch=rows[offset:offset+args.batch];base_seconds=None
            modes=[('base','base',0),('async','async',0),('sync','sync',0),('async_delay20','async',20),('post_generation_restart','restart',0)]
            # Keep base first because restart reuses this completed first pass.
            if offset//args.batch%2:modes[1:4]=list(reversed(modes[1:4]))
            for name,mode,delay in modes:
                preloaded=None;tool_seconds=0
                if mode=='restart':preloaded,tool_seconds=fetch_all(batch)
                texts,metrics=sample(model,tok,batch,mode,delay=delay,preloaded=preloaded)
                if name=='base':base_seconds=metrics['seconds']
                if mode=='restart':metrics.update(first_pass_seconds=base_seconds,tool_seconds=tool_seconds,total_two_pass_seconds=base_seconds+tool_seconds+metrics['seconds'])
                for row,text in zip(batch,texts):
                    record={'id':row['id'],'kind':row['kind'],'condition':name,'text':text,'expected':row['expected'],**score(text,row['expected'])};records.append(record);rf.write(json.dumps(record)+'\n')
                rf.flush();bf.write(json.dumps({'offset':offset,'condition':name,**metrics})+'\n');bf.flush()
                print(json.dumps({'offset':offset,'condition':name,'correct':sum(score(t,r['expected'])['correct'] for t,r in zip(texts,batch)),'seconds':round(metrics['seconds'],2),'locked':len(metrics['locked']),'stalls':metrics['pending_call_stalls']}),flush=True)
    probes=syntax_probe(model,tok,[rows[i] for i in (0,1,8,9,16,17) if i<len(rows)])
    (out/'syntax-probe.json').write_text(json.dumps(probes,indent=2));(out/'tasks.json').write_text(json.dumps(rows,indent=2))
    summary={name:{'correct':sum(r['correct'] for r in records if r['condition']==name),'n':sum(r['condition']==name for r in records)} for name in sorted({r['condition'] for r in records})}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2),flush=True)
    if args.generated:
        from generated_pilot import run
        run(model,tok)
if __name__=='__main__':main()
