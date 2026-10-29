import csv,hashlib,json,pathlib,random
root=pathlib.Path(__file__).parent;workspace=root/'workspace';workspace.mkdir(exist_ok=True);rng=random.Random(20261028);tasks=[]
for i in range(8):
    secret=hashlib.sha256(f'file-{rng.getrandbits(128)}'.encode()).hexdigest()[:12];path=f'lookup/item_{i}.txt';p=workspace/path;p.parent.mkdir(exist_ok=True);p.write_text(secret+'\n')
    tasks.append(dict(id=len(tasks),kind='file_lookup',question=f'Return the exact 12-character value stored in {path}.',call={'name':'read_file','args':{'path':path,'offset':0,'length':128}},expected=secret))
for i in range(8):
    nonce=str(rng.getrandbits(80));program=f"import hashlib;print(hashlib.sha256(b'{nonce}').hexdigest()[:12])";expected=hashlib.sha256(nonce.encode()).hexdigest()[:12]
    tasks.append(dict(id=len(tasks),kind='code_output',question='Return exactly what this Python program prints: '+program,call={'name':'run','args':{'cmd':['python3','-c',program],'stdin':'','timeout_ms':2000}},expected=expected))
for i in range(8):
    values=[rng.randint(-10000,10000) for _ in range(100)];path=f'tables/table_{i}.csv';p=workspace/path;p.parent.mkdir(exist_ok=True)
    with p.open('w') as f:f.write('amount\n'+'\n'.join(map(str,values))+'\n')
    program=f"import csv;print(sum(int(r['amount']) for r in csv.DictReader(open('{path}'))))"
    tasks.append(dict(id=len(tasks),kind='compute_file',question=f'Return the exact sum of the amount column in {path}.',call={'name':'run','args':{'cmd':['python3','-c',program],'stdin':'','timeout_ms':2000}},expected=str(sum(values))))
(root/'tasks.json').write_text(json.dumps(tasks,indent=2))
print(json.dumps({'tasks':len(tasks),'workspace':str(workspace.resolve())}))
