import json,random,pathlib,hashlib
root=pathlib.Path(__file__).parent
workspace=root.parent/'syscall-pilot/workspace';folder=workspace/'v11';folder.mkdir(exist_ok=True);rng=random.Random(2026102812);tasks=[]
for i in range(20):
 count=2+i%3;paths=[f'v11/{hashlib.sha256(f"v11-{i}-{j}-{rng.getrandbits(64)}".encode()).hexdigest()[:16]}.txt' for j in range(count)]
 val=hashlib.sha256(f'value-{i}-{rng.getrandbits(64)}'.encode()).hexdigest()[:12]
 for j,path in enumerate(paths):
  content=json.dumps({'next_file':paths[j+1]}) if j<count-1 else (('event,value\nresult,'+val+'\n') if i%2==0 else ('INFO result='+val+'\n'))
  (workspace/path).write_text(content)
 tasks.append({'id':200+i,'kind':'multi_csv' if i%2==0 else 'multi_log','question':f'Start at {paths[0]}. Follow each next_file link by calling read_file separately. When you reach the final CSV or log record, return its value, exactly. Do not use run for this task.','expected':val,'minimum_calls':count,'allowed':['read_file']})
old=json.loads((root.parent/'llada22-pilot/mini-results/tool-tasks.json').read_text())
for row in old:row['minimum_calls']=1;row['allowed']=['write_file'] if row['kind']=='write' else ['read_file','run']
(root/'linux-tasks.json').write_text(json.dumps(old+tasks,indent=2))
print('27 tasks; chains require 2–4 separately requested reads, fixture paths hidden until prior results')
