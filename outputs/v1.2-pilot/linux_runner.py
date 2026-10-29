import json,re,time
from pilot import native,ids,decode,definitions,append

def run_linux(model,tok,out):
 tasks=json.load(open('linux-tasks.json'))
 for task in tasks:
  for mode in (['none','conventional','async'] if task['minimum_calls']==1 else ['none','conventional','async','async_one_round']):
   history=[{'role':'system','content':'Use the declared tools to obtain external information. Follow file links only after reading their names. Return only the requested answer. Persistent writes require the requested literal path and contents.'},{'role':'user','content':task['question']}]
   start=time.perf_counter()
   if mode=='none':
    output,m,_=decode(model,ids(tok,history),length=192);text=tok.decode(output,skip_special_tokens=True);r={'text':text,'calls':[],'rounds':[{'first':m}],'events':[],'seconds':time.perf_counter()-start}
   else:r=native(model,tok,history,definitions(tuple(task['allowed'])),set(task['allowed']),mode.startswith('async'),max_rounds=1 if mode=='async_one_round' else 4)
   text=r['text'];clean=re.sub(r'<\|[^>]+\|>','',text).strip();pred=re.sub(r'^Answer\s*:\s*','',clean,flags=re.I).strip('`"\' .')
   present=bool(re.search(r'(?<![\w])'+re.escape(task['expected'])+r'(?![\w])',clean));executed=any((t.get('result') or {}).get('ok') for t in r['rounds'])
   r.update(id=task['id'],kind=task['kind'],condition=mode,expected=task['expected'],strict=pred==task['expected'],answer_present=present,correct=present and (executed if task['kind']=='write' else True),minimum_calls=task['minimum_calls'],calls_count=len(r['calls']))
   append(out/'linux.jsonl',r)
