import json,pathlib
REQUIRED={'read_file':{'path'},'list_dir':set(),'stat':{'path'},'clock':set(),'run':{'cmd'},'write_file':{'path','data'},'remove':{'path'}}
def validate(call):
    if not isinstance(call,dict) or call.get('name') not in REQUIRED:return False
    name=call['name'];args=call.get('args',{})
    if not isinstance(args,dict) or not REQUIRED[name]<=args.keys():return False
    if 'path' in args:
        if not isinstance(args['path'],str):return False
        p=pathlib.PurePosixPath(args['path'])
        if p.is_absolute() or '..' in p.parts:return False
    if name=='run':
        if not isinstance(args['cmd'],list) or not args['cmd'] or not all(isinstance(v,str) for v in args['cmd']):return False
    if name=='write_file' and (not isinstance(args['data'],str) or len(args['data'].encode())>8192):return False
    return True

def parse_tokens(tokenizer,ids):
    pieces=[tokenizer.decode([i],skip_special_tokens=True,clean_up_tokenization_spaces=False) for i in ids]
    text=''.join(pieces)
    if tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)!=text:return None
    leading=len(text)-len(text.lstrip());clean=text.lstrip()
    try:call,end=json.JSONDecoder().raw_decode(clean)
    except ValueError:return None
    if clean[end:].strip() or not validate(call):return None
    offsets=[0]
    for piece in pieces:offsets.append(offsets[-1]+len(piece))
    indices=[i for i in range(len(ids)) if offsets[i]<leading+end and offsets[i+1]>leading]
    return call,indices
