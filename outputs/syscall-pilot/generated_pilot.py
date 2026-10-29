"""Full generated-call hook in a reserved call/result/answer canvas."""
import json,pathlib,time
import torch
from transformers import AutoModel,AutoTokenizer
from async_engine import Engine,signature
from call_parser import parse_tokens
from model_pilot import MODEL,REV,MASK,score,output_tokens,sync

@torch.inference_mode()
def generate(model,tok,rows,mode):
    prompts=[];middles=[];tails=[]
    for row in rows:
        instruction=('Fill the JSON system call between <sys> and </sys>, then use its result to answer. Only one JSON object is allowed in the call span. '
            'Available calls: read_file with args path, offset, length; run with args cmd (argv list), stdin, timeout_ms; write_file with args path,data. '
            'Example: <sys>{"name":"read_file","args":{"path":"example.txt","offset":0,"length":128}}</sys>. '
            'Example: <sys>{"name":"run","args":{"cmd":["python3","-c","print(2+2)"],"stdin":"","timeout_ms":2000}}</sys>. '
            'Return only the requested value after Answer:. If the tool result is unavailable, answer UNKNOWN.\nTask: '+row['question'])
        rendered=tok.apply_chat_template([{'role':'user','content':instruction},{'role':'assistant','content':'<sys>__CALL_SLOT__</sys>'},{'role':'user','content':'System-call result: <res>__RESULT_SLOT__</res>\nUse this result to answer the original question. Return only the requested value.'}],tokenize=False,add_generation_prompt=True)
        prefix,rest=rendered.split('__CALL_SLOT__');middle,tail=rest.split('__RESULT_SLOT__');prompts.append(prefix);middles.append(middle);tails.append(tail+'Answer:')
    encoded=tok(prompts,padding=True,return_tensors='pt').to('cuda');B=len(rows);P=encoded.input_ids.shape[1];C=128;R=128;L=64
    assert len(set(middles))==1 and len(set(tails))==1
    middle=tok.encode(middles[0],add_special_tokens=False);suffix=tok.encode(tails[0],add_special_tokens=False)
    S=P+C+len(middle);A=S+R+len(suffix)
    x=torch.full((B,A+L),MASK,device='cuda',dtype=torch.long);x[:,:P]=encoded.input_ids;x[:,P+C:S]=torch.tensor(middle,device='cuda');x[:,S+R:A]=torch.tensor(suffix,device='cuda')
    attention=torch.ones_like(x);attention[:,:P]=encoded.attention_mask;attention[:,S:S+R]=0
    engine=Engine() if mode=='async' else None;locked={};history=[];parser_seconds=0
    sync();start=time.perf_counter()
    for step in range(64):
        logits=model(x,attention_mask=attention).logits;proposal=logits.argmax(-1);probs=logits.float().softmax(-1)
        conf=probs.gather(-1,proposal.unsqueeze(-1)).squeeze(-1)
        allowed=torch.zeros_like(x,dtype=torch.bool)
        lo,hi,k=(P,P+C,4) if step<32 else (A,A+L,2)
        allowed[:,lo:hi]=True;allowed&=(x==MASK)
        ranks=torch.where(allowed,conf,-torch.inf);positions=ranks.topk(k,dim=1).indices;x.scatter_(1,positions,proposal.gather(1,positions))
        draft=torch.where(x==MASK,proposal,x);actual_conf=probs.gather(-1,draft.unsqueeze(-1)).squeeze(-1)
        hook_start=time.perf_counter();ids=draft[:,P:P+C].tolist();confidence=actual_conf[:,P:P+C].tolist();committed=(x[:,P:P+C]!=MASK).tolist();observations=[]
        for bi,sequence in enumerate(ids):
            parsed=parse_tokens(tok,sequence)
            if parsed is None:continue
            call,indices=parsed;fixed=all(committed[bi][i] for i in indices);minimum=min(confidence[bi][i] for i in indices)
            observations.append({'anchor':str(bi),'call':call,'committed':fixed,'eligible':minimum>=.5 or fixed})
            history.append({'step':step,'id':rows[bi]['id'],'call':call,'committed':fixed,'min_confidence':minimum})
        current={o['anchor']:o for o in observations}
        # Results belong to a particular call revision, never just a slot address.
        for bi,info in list(locked.items()):
            obs=current.get(str(bi))
            if obs is None or signature(obs['call'])!=info['signature']:
                x[bi,S:S+R]=MASK;attention[bi,S:S+R]=0;del locked[bi]
        if engine:
            for delivery in engine.barrier(observations,step):
                bi=int(delivery['anchor']);result=delivery['result'];tokens,truncated=output_tokens(tok,result,R)
                x[bi,S:S+R]=tok.pad_token_id;attention[bi,S:S+R]=0
                if tokens:x[bi,S:S+len(tokens)]=torch.tensor(tokens,device='cuda');attention[bi,S:S+len(tokens)]=1
                locked[bi]={'signature':signature(delivery['call']),'tokens':tokens,'step':step,'result':result,'truncated':truncated}
        parser_seconds+=time.perf_counter()-hook_start;del logits,probs;sync()
    elapsed=time.perf_counter()-start
    answers=tok.batch_decode(x[:,A:],skip_special_tokens=True);calls=tok.batch_decode(x[:,P:P+C],skip_special_tokens=True)
    result=[]
    for bi,row in enumerate(rows):
        parsed=parse_tokens(tok,x[bi,P:P+C].tolist());call=parsed[0] if parsed else None
        info=locked.get(bi)
        result.append({'id':row['id'],'kind':row['kind'],'condition':mode,'text':answers[bi],'expected':row['expected'],**score(answers[bi],row['expected']),
                       'call_text':calls[bi],'parsed_call':call,'result_landed':info is not None,'land_step':info['step'] if info else None,
                       'lock_preserved':x[bi,S:S+len(info['tokens'])].tolist()==info['tokens'] if info else None})
    tail=time.perf_counter()
    if engine:engine.close()
    return result,{'seconds':elapsed,'parser_seconds':parser_seconds,'finalization_seconds':time.perf_counter()-tail,'history':history,'events':engine.events if engine else [],'undelivered_at_end':len(engine.jobs) if engine else 0}

def run(model,tok):
    tasks=json.loads(pathlib.Path('tasks.json').read_text());rows=[tasks[i] for i in (0,1,8,9,16,17)]
    rows += [dict(id=100+i,kind='write',question=f'Use write_file to save the literal text written-{7319+i} to model_writes/item_{i}.txt. After success answer DONE.',expected='DONE') for i in range(2)]
    out=pathlib.Path('generated-results');out.mkdir(exist_ok=True);(out/'tasks.json').write_text(json.dumps(rows,indent=2))
    all_records=[]
    with (out/'records.jsonl').open('w') as rf,(out/'batches.jsonl').open('w') as bf:
        for offset in range(0,len(rows),2):
            for mode in ('base','async'):
                records,metrics=generate(model,tok,rows[offset:offset+2],mode);all_records+=records
                for r in records:rf.write(json.dumps(r)+'\n')
                rf.flush();bf.write(json.dumps({'offset':offset,'condition':mode,**metrics})+'\n');bf.flush()
                print(json.dumps({'offset':offset,'condition':mode,'correct':sum(r['correct'] for r in records),'valid_calls':sum(r['parsed_call'] is not None for r in records),'results_landed':sum(r['result_landed'] for r in records),'seconds':round(metrics['seconds'],2)}),flush=True)
    summary={m:{'n':sum(r['condition']==m for r in all_records),'correct':sum(r['condition']==m and r['correct'] for r in all_records),'valid_calls':sum(r['condition']==m and r['parsed_call'] is not None for r in all_records)} for m in ('base','async')}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
def main():
    tok=AutoTokenizer.from_pretrained(MODEL,revision=REV,trust_remote_code=True);tok.padding_side='left'
    if tok.pad_token_id is None:tok.pad_token=tok.eos_token
    model=AutoModel.from_pretrained(MODEL,revision=REV,trust_remote_code=True,torch_dtype=torch.bfloat16).to('cuda').eval()
    run(model,tok)
if __name__=='__main__':main()
