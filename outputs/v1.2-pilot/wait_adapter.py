"""v1.2 synchronous dispatch inside the live native-call canvas."""
import re,time
import torch
from pilot import parse,ids,execute,rendered,tool_msgs,definitions,signature
from event_sampler import decode,MASK,EOS,DEVICE
import async_engine

def result_tokens(tok,result):
 value=result.get('output','') if result.get('ok') else 'ERROR: '+result.get('output','')
 z=tok.encode(value,add_special_tokens=False);marker=tok.encode(' [truncated]',add_special_tokens=False)
 return z if len(z)<=256 else z[:256-len(marker)]+marker

def delayed_answer(model,tok,history,defs,call,ready,wait_seconds,block=32):
 template=rendered(tok,tool_msgs(history,call,'__RESULT_ANCHOR__'),defs)
 left,right=template.split('__RESULT_ANCHOR__');left=tok.encode(left,add_special_tokens=False);right=tok.encode(right,add_special_tokens=False)
 done=False
 def hook(s):
  nonlocal done
  if done:return
  result=s.pause(lambda:ready,wait_seconds,call['id'])
  s.wait_arrival(len(left),len(left),result_tokens(tok,result),call['id']);done=True
 out,m,s=decode(model,left+right,length=192,block=block,hook=hook)
 m['received']=done
 return tok.decode(out,skip_special_tokens=True),m,ready

def native_wait(model,tok,history,defs,allowed,block=32,max_rounds=4):
 start=time.perf_counter();calls=[];rounds=[];events=[];seen=set()
 # These are only the native call-turn closing tokens, not generated content.
 closer_ids=set(tok.encode('<|tool_calls_section_end|><|role_end|>',add_special_tokens=False)+[EOS])
 def hook(s):
  if len(calls)>=max_rounds:return
  startpos=s.answer_start
  tokens=s.draft[0,startpos:].tolist()
  pieces=[tok.decode([v],skip_special_tokens=False,clean_up_tokenization_spaces=False) for v in tokens]
  text=''.join(pieces)
  if text!=tok.decode(tokens,skip_special_tokens=False,clean_up_tokenization_spaces=False):return
  offsets=[0]
  for p in pieces:offsets.append(offsets[-1]+len(p))
  for call in parse(text):
   if call['call']['name'] not in allowed:continue
   pos=[startpos+i for i in range(len(tokens)) if offsets[i]<call['end'] and offsets[i+1]>call['start']]
   if not pos:continue
   key=(pos[0],call['id'])
   if key in seen:continue
   confidence_pos=pos
   if call['call']['name']=='calc':
    expr=call['call']['args']['expression'];begin=text.find(expr,call['start'],call['end'])
    spans=[(begin+m.start(),begin+m.end()) for m in re.finditer(r'\d+',expr)] if begin>=0 else []
    confidence_pos=[startpos+i for i in range(len(tokens)) if any(offsets[i]<b and offsets[i+1]>a for a,b in spans)]
   if not confidence_pos:continue
   confidence=min(s.confidence[0,confidence_pos].tolist())
   committed=all(i<s.block_start or s.block_final for i in confidence_pos)
   if confidence<.9 or (call['call']['name'] in async_engine.EFFECTS and not committed):continue
   # Confidence eligibility is identical to v1.1. Commit exactly the dispatched
   # draft span when accepting it; subsequent edits cannot revise executed args.
   call_ids=s.draft[0,pos[0]:pos[-1]+1].tolist()
   result=s.pause(lambda:execute(call['call'],committed=call['call']['name'] in async_engine.EFFECTS),label=call['id'])
   s.lock(pos[0],call_ids,'accepted_call_'+str(len(calls)))
   end=pos[-1]+1;replace_end=end
   while replace_end<s.x.shape[1] and int(s.x[0,replace_end]) in closer_ids:replace_end+=1
   value=tok.decode(result_tokens(tok,result),skip_special_tokens=False)
   bridge='<|tool_calls_section_end|><|role_end|><role>tool</role>## Return of '+call['id']+'\n'+value+'\n<|role_end|><role>assistant</role>'
   bridge_ids=tok.encode(bridge,add_special_tokens=False)
   s.wait_arrival(end,replace_end,bridge_ids,call['id'],generated=True)
   s.answer_start=end+len(bridge_ids)
   seen.add(key);calls.append(call);rounds.append({'result':result,'dispatch_step':s.step,'confidence':confidence,'committed':committed})
   events.extend([dict(type='submit',step=s.step,call=call['call'],committed=committed,effect=call['call']['name'] in async_engine.EFFECTS),dict(type='completion',step=s.step,submit_step=s.step,steps_to_land=0,result=result)])
   return
 out,m,s=decode(model,ids(tok,history,defs),length=384,block=block,hook=hook)
 return dict(text=tok.decode(out,skip_special_tokens=True),raw_canvas=tok.decode(s.x[0,s.P:s.limit].tolist(),skip_special_tokens=False),calls=calls,rounds=rounds,events=events,metrics=m,seconds=time.perf_counter()-start)
