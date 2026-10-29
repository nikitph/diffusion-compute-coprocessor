"""P0a scientific pilot: host parser with CPU or GPU calculator; no GPU-only performance claim."""
import argparse, json, random, re, time, math, pathlib, platform

MODEL = 'GSAI-ML/LLaDA-8B-Instruct'
REVISION = '08b83a6feb34df1a6011b80c3c00c7563e963b07'
MASK = 126336
# Intentionally excludes decimals, comma-grouped numbers and multi-operator expressions.
EQ = re.compile(r'(?<![\d.,+*/-])(?P<a>-?\d{1,64})\s*(?P<op>[+*×−-])\s*(?P<b>-?\d{1,64})\s*=')
FULL = re.compile(EQ.pattern + r'\s*(?P<result>-?\d+)')

def calculate(a, op, b):
    return a+b if op=='+' else a-b if op in ('-','−') else a*b

def dataset(seed=20261028):
    rng=random.Random(seed); rows=[]
    for digits in (5,8,10):
        for op in ('+','-','*'):
            for rep in range(2):
                a=rng.randrange(10**(digits-1),10**digits); b=rng.randrange(10**(digits-1),10**digits)
                value=calculate(a,op,b)
                for kind in ('direct','dependent'):
                    threshold=value+(-1 if rep==0 else 1)*rng.randint(1,9)
                    question=(f'Calculate {a} {op} {b}. Start by writing the equation {a} {op} {b} = followed by its result. '
                              'Use plain decimal integers without commas. ')
                    if kind=='direct': question+='Finish with a separate line: Answer: <integer>.'
                    else: question+=f'Then decide whether that result is strictly greater than {threshold}. Finish with Answer: YES or Answer: NO.'
                    rows.append(dict(id=len(rows),digits=digits,op=op,a=a,b=b,value=value,kind=kind,
                                     threshold=threshold,expected=str(value) if kind=='direct' else ('YES' if value>threshold else 'NO'),prompt=question))
    return rows

def score(text,row):
    if row['kind']=='dependent':
        hits=re.findall(r'Answer\s*:\s*(YES|NO)\b',text,re.I)
        prediction=hits[-1].upper() if hits else None
    else:
        hits=re.findall(r'Answer\s*:\s*(-?\d[\d,]*)',text,re.I)
        prediction=str(int(hits[-1].replace(',',''))) if hits else None
    return dict(prediction=prediction,correct=prediction==row['expected'])

def posthoc(text, kind="direct"):
    # Only replace arithmetic results that the model actually emitted.
    # Do not use task operands, ground-truth answers or redo the downstream decision.
    matches=list(FULL.finditer(text))
    corrected=FULL.sub(lambda m:m.group(0)[:m.start('result')-m.start()]+str(calculate(int(m['a']),m['op'],int(m['b']))),text)
    if kind=='direct' and matches:
        m=matches[-1]; value=str(calculate(int(m['a']),m['op'],int(m['b'])))
        corrected=re.sub(r'(Answer\s*:\s*)-?\d[\d,]*',lambda hit:hit[1]+value,corrected,flags=re.I)
    return corrected

def boundaries(tokenizer, ids):
    pieces=[tokenizer.decode([i],skip_special_tokens=False,clean_up_tokenization_spaces=False) for i in ids]
    text=''.join(pieces)
    whole=tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    if text!=whole: return None,None
    offsets=[0]
    for p in pieces: offsets.append(offsets[-1]+len(p))
    return text,offsets

def hook(tokenizer,x,draft,conf,prefix,rows,done,events,step,tau,overwrite=False,backend='gpu'):
    import torch
    ids=draft[:,prefix:].tolist(); confidence=conf[:,prefix:].tolist()
    candidates=[]
    for bi,sequence in enumerate(ids):
        if done[bi]: continue
        text,offsets=boundaries(tokenizer,sequence)
        if text is None: continue
        for match in EQ.finditer(text):
            if match.start() not in offsets or match.end() not in offsets: continue
            begin=offsets.index(match.start());end=offsets.index(match.end())
            if not confidence[bi][begin:end] or min(confidence[bi][begin:end])<tau:continue
            a,b=int(match['a']),int(match['b']);op=match['op'].replace('×','*').replace('−','-')
            if backend=='gpu' and (a<0 or b<0):continue
            candidates.append(dict(bi=bi,begin=begin,end=end,a=a,b=b,op=op))
            break # At most one candidate per sequence per denoising barrier.
    if not candidates:return 0
    if backend=='gpu':
        from gpu_arithmetic import encode,compute,decode
        aa=encode([c['a'] for c in candidates]);bb=encode([c['b'] for c in candidates])
        ops=torch.tensor([{'+':0,'-':1,'*':2}[c['op']] for c in candidates],dtype=torch.int32,device=x.device)
        values=decode(*compute(aa,bb,ops))
    else:values=[calculate(c['a'],c['op'],c['b']) for c in candidates]
    for c,value in zip(candidates,values):
        bi=c['bi'];begin=c['begin'];end=c['end'];sequence=ids[bi]
        result_text=' '+str(value)+'\n';result=tokenizer.encode(result_text,add_special_tokens=False)
        if tokenizer.decode(result,clean_up_tokenization_spaces=False)!=result_text:continue
        start=prefix+end;stop=start+len(result)
        event=dict(step=step,batch_index=bi,id=rows[bi]['id'],a=c['a'],b=c['b'],op=c['op'],value=str(value),start=start,stop=stop,
                   operand_match=(c['a']==rows[bi]['a'] and c['b']==rows[bi]['b'] and c['op']==rows[bi]['op']),
                   min_confidence=min(confidence[bi][begin:end]),backend=backend)
        if stop>x.shape[1]:event['status']='length_failure'
        elif not overwrite and not bool((x[bi,start:stop]==MASK).all()):event['status']='occupied_slot'
        else:
            x[bi,start:stop]=torch.tensor(result,device=x.device)
            event.update(status='injected',result_ids=result,draft_before=tokenizer.decode(sequence,skip_special_tokens=True),
                         before_ids=sequence.copy(),operand_token_ids=sequence[begin:end],operand_start=prefix+begin,operand_end=prefix+end)
            done[bi]=True
        events.append(event)
    return int(backend=='gpu')


def sync():
    import torch
    torch.cuda.synchronize()


def generate(model,tokenizer,rows,steps,length,fraction,tau,overwrite=False,backend="gpu"):
    import torch
    prompts=[tokenizer.apply_chat_template([{'role':'user','content':r['prompt']}],tokenize=False,add_generation_prompt=True) for r in rows]
    tok=tokenizer(prompts,padding=True,return_tensors='pt').to('cuda')
    prefix=tok.input_ids.shape[1]; batch=len(rows)
    x=torch.full((batch,prefix+length),MASK,dtype=torch.long,device='cuda'); x[:,:prefix]=tok.input_ids
    attention=torch.cat((tok.attention_mask,torch.ones((batch,length),device='cuda',dtype=torch.long)),1)
    counts=[length//steps+(i<length%steps) for i in range(steps)]
    events=[]; done=[False]*batch; hook_seconds=0; kernel_calls=0
    sync(); start=time.perf_counter()
    with torch.inference_mode():
        for step in range(steps):
            logits=model(x,attention_mask=attention).logits
            proposal=logits.argmax(-1)
            # Full softmax, matching low-confidence sampling, in float32.
            probs=logits.float().softmax(-1)
            conf=probs.gather(-1,proposal.unsqueeze(-1)).squeeze(-1)
            masked=x==MASK
            draft=torch.where(masked,proposal,x)
            # Confidence refers to the actual token used in the draft, including committed operands.
            actual_conf=probs.gather(-1,draft.unsqueeze(-1)).squeeze(-1)
            del logits,probs
            if fraction is not None and step>=math.floor(steps*fraction):
                sync(); hook_start=time.perf_counter()
                kernel_calls+=hook(tokenizer,x,draft,actual_conf,prefix,rows,done,events,step,tau,overwrite,backend)
                sync(); hook_seconds+=time.perf_counter()-hook_start
            masked=x==MASK
            ranking=torch.where(masked,conf,-torch.inf)
            # Fixed forward count and original transfer schedule; hook can finish a row early.
            # Do not permit the mask token to become a committed result.
            for bi in range(batch):
                k=min(counts[step],int(masked[bi].sum()))
                if k:
                    positions=ranking[bi].topk(k).indices
                    x[bi,positions]=draft[bi,positions]
    sync(); elapsed=time.perf_counter()-start
    final=x[:,prefix:].tolist(); texts=tokenizer.batch_decode(final,skip_special_tokens=True)
    for event in events:
        if event['status']=='injected':
            bi=event['batch_index']; lo=event['start']-prefix; hi=event['stop']-prefix
            event['lock_preserved']=final[bi][lo:hi]==event['result_ids']
            event['operands_preserved']=final[bi][event['operand_start']-prefix:event['operand_end']-prefix]==event['operand_token_ids']
            outside=[i for i in range(length) if not lo<=i<hi]
            event['outside_draft_changes']=sum(final[bi][i]!=event['before_ids'][i] for i in outside)
            del event['before_ids']
    return texts,dict(batch_seconds=elapsed,hook_seconds=hook_seconds,kernel_calls=kernel_calls,events=events,remaining_masks=int((x[:,prefix:]==MASK).sum()))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default='results');parser.add_argument('--limit',type=int,default=36)
    parser.add_argument('--steps',type=int,default=64);parser.add_argument('--length',type=int,default=192);parser.add_argument('--batch',type=int,default=4)
    parser.add_argument('--fractions',default='0.5,0.75');parser.add_argument('--tau',type=float,default=.5);parser.add_argument('--overwrite',action='store_true');parser.add_argument('--backend',choices=['cpu','gpu'],default='gpu')
    args=parser.parse_args(); out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    import torch,transformers
    from transformers import AutoTokenizer,AutoModel
    torch.manual_seed(20261028)
    tokenizer=AutoTokenizer.from_pretrained(MODEL,revision=REVISION,trust_remote_code=True)
    tokenizer.padding_side='left'
    if tokenizer.pad_token_id is None: tokenizer.pad_token=tokenizer.eos_token
    model=AutoModel.from_pretrained(MODEL,revision=REVISION,trust_remote_code=True,torch_dtype=torch.bfloat16).to('cuda').eval()
    if args.backend=="gpu":
        from gpu_arithmetic import encode,compute
        compute(encode([12]),encode([34]),torch.tensor([2],dtype=torch.int32,device="cuda"))
        sync()
    rows=dataset()[:args.limit]
    (out/'dataset.json').write_text(json.dumps(rows,indent=2))
    (out/'environment.json').write_text(json.dumps(dict(model=MODEL,revision=REVISION,torch=torch.__version__,transformers=transformers.__version__,gpu=torch.cuda.get_device_name(),args=vars(args)),indent=2))
    # Warm-up excluded, with full batch/sequence shape where possible.
    generate(model,tokenizer,rows[:args.batch],2,args.length,None,args.tau)
    conditions=[('base',None)]+[(f'mid_{f}',float(f)) for f in args.fractions.split(',') if f]
    records=[]
    with (out/'records.jsonl').open('w') as file:
        for offset in range(0,len(rows),args.batch):
            batch=rows[offset:offset+args.batch]
            # Rotate order to reduce systematic timing bias.
            order=conditions[offset//args.batch%len(conditions):]+conditions[:offset//args.batch%len(conditions)]
            for name,fraction in order:
                texts,metrics=generate(model,tokenizer,batch,args.steps,args.length,fraction,args.tau,args.overwrite,args.backend)
                for row,text in zip(batch,texts):
                    record=dict(id=row['id'],kind=row['kind'],digits=row['digits'],condition=name,text=text,expected=row['expected'],**score(text,row))
                    records.append(record);file.write(json.dumps(record)+'\n')
                    if name=='base':
                        corrected=posthoc(text,row['kind'])
                        record=dict(id=row['id'],kind=row['kind'],digits=row['digits'],condition='posthoc_equations',text=corrected,expected=row['expected'],**score(corrected,row))
                        records.append(record);file.write(json.dumps(record)+'\n')
                file.flush()
                with (out/'batches.jsonl').open('a') as log: log.write(json.dumps(dict(offset=offset,condition=name,**metrics))+'\n')
                print(json.dumps(dict(offset=offset,condition=name,seconds=round(metrics['batch_seconds'],2),correct=sum(score(t,r)['correct'] for t,r in zip(texts,batch)),injections=sum(e['status']=='injected' for e in metrics['events']))),flush=True)
    summary={}
    for kind in ('direct','dependent'):
        for condition in sorted({r['condition'] for r in records}):
            group=[r for r in records if r['kind']==kind and r['condition']==condition]
            summary[f'{kind}/{condition}']=dict(n=len(group),correct=sum(r['correct'] for r in group),accuracy=sum(r['correct'] for r in group)/len(group) if group else None)
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
