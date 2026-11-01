"""Opt-in minimal visible-text seed, never bundled personal history or global style."""
from __future__ import annotations
import json,os,time,uuid
from pathlib import Path
from .engine import Engine,save,encode,atomic
from .platform import lock, fsync_directory
from .model import OperationError,digest,uid,find,no_links

def create_style(engine: Engine, session: str, cwd: Path, args: dict, operation: str) -> dict:
    uid(operation)
    seed_arg=args.get('seed')
    if not isinstance(seed_arg,str) or not Path(seed_arg).is_absolute(): raise OperationError('seed 必须是用户指定的本地绝对路径')
    seed=Path(seed_arg); no_links(seed)
    if seed.is_symlink() or not seed.is_file() or seed.stat().st_size>16384: raise OperationError('seed 必须是小于 16 KiB 的普通 JSON 文件')
    data=seed.read_bytes(); spec=json.loads(data)
    if not isinstance(spec,dict) or set(spec)!={'schema','messages'} or type(spec['schema']) is not int or spec['schema']!=1: raise OperationError('seed 结构应为 schema:1 和 messages')
    messages=spec['messages']
    if not isinstance(messages,list) or len(messages) not in {2,4}: raise OperationError('seed 仅接受 1–2 组最小问答')
    for i,m in enumerate(messages):
        if not isinstance(m,dict) or set(m) not in ({'role','text'},{'role','text','reasoning'}) or m['role']!=('user' if i%2==0 else 'assistant') or not isinstance(m['text'],str) or not 1<=len(m['text'])<=2000 or '\0' in m['text']: raise OperationError('seed 消息格式或长度不支持')
        if 'reasoning' in m and (m['role']!='assistant' or not isinstance(m['reasoning'],str) or not 1<=len(m['reasoning'])<=4000 or '\0' in m['reasoning']): raise OperationError('reasoning 仅允许 assistant 的 1–4000 字纯文本')
    title=args.get('title','')
    if not isinstance(title,str) or len(title)>120 or any(ord(c)<32 for c in title): raise OperationError('标题无效')
    source,source_data,_=engine.source(session,cwd)
    request={'source':session,'boundary':'style-seed','title_sha256':digest(title.encode()),'cwd':str(cwd.resolve()),'seed_sha256':digest(data)}
    journal=engine.state/(operation+'.json')
    no_links(journal); no_links(engine.state/(operation+'.lock'))
    with lock(engine.state/(operation+'.lock')):
        if journal.exists():
            old=json.loads(journal.read_text(encoding='utf-8'))
            if old.get('request')!=request: raise OperationError('操作 ID 已用于另一请求')
            if old.get('status')=='completed' and digest(find(engine.profile,old['target']).read_bytes())==old.get('target_sha256'): return old
            raise OperationError('已有操作需 recover 核查')
        sid=str(uuid.uuid4()); target=source.with_name(sid+'.jsonl'); rows=[]; parent=None
        for i,m in enumerate(messages):
            if m.get('reasoning'):
                rid=str(uuid.uuid4()); reason={'type':'reasoning','id':rid,'parentId':parent,'sessionId':sid,'cwd':str(cwd.resolve()),'timestamp':int(time.time()*1000)+i,'content':[],'rawContent':[{'type':'text','text':m['reasoning']}]}
                rows.append(reason); parent=rid
            mid=str(uuid.uuid4()); row={'id':mid,'timestamp':int(time.time()*1000)+i,'type':'message','role':m['role'],'content':[{'type':'input_text' if i%2==0 else 'output_text','text':m['text']}],'sessionId':sid,'cwd':str(cwd.resolve())}
            if parent: row['parentId']=parent
            if i%2: row['status']='completed'
            rows.append(row); parent=mid
        if title:rows.append({'type':'custom-title','id':str(uuid.uuid4()),'sessionId':sid,'customTitle':title})
        wire=encode(rows)
        receipt={'operation':operation,'request':request,'target':sid,'source_sha256':digest(source_data),'source_size':len(source_data),'target_sha256':digest(wire),'status':'prepared','kind':'style-new','style_default':'off','no_prompt_submitted':True}
        save(journal,receipt)
        if source.read_bytes()!=source_data or seed.read_bytes()!=data: raise OperationError('来源或 seed 已变化')
        # Atomic no-clobber publication, never overwrite an existing UUID.
        temp=target.with_name(target.name+'.'+operation+'.tmp'); atomic(temp,wire)
        try:
            os.link(temp,target)
            fsync_directory(target.parent)
        finally: temp.unlink(missing_ok=True)
        receipt['status']='completed'; save(journal,receipt)
        return receipt
