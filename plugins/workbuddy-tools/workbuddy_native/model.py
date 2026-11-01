"""Conservative adapter for WorkBuddy 5.6.2 / bundled CLI 2.147.0 JSONL."""
from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from typing import Any

class OperationError(RuntimeError): pass
UUID = re.compile(r'^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$')
KINDS = {'message','reasoning','function_call','function_call_result','function_call_output','file-history-snapshot','session-meta','ai-title','custom-title','topic'}
def uid(value: Any) -> str:
    if not isinstance(value,str) or not UUID.fullmatch(value): raise OperationError('需要小写 UUID')
    return value

def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def records(data: bytes) -> list[dict[str,Any]]:
    if len(data)>32*1024*1024: raise OperationError('历史大于 32 MiB，拒绝自动处理')
    result=[]; ids=set()
    try:
        for line in data.decode('utf-8-sig').splitlines():
            if not line.strip(): continue
            row=json.loads(line)
            if not isinstance(row,dict) or row.get('type') not in KINDS: raise OperationError('未知历史结构，拒绝猜测适配')
            if row.get('id'):
                uid(row['id'])
                if row['id'] in ids: raise OperationError('重复消息 ID')
                ids.add(row['id'])
            if row.get('sessionId'): uid(row['sessionId'])
            if row.get('subagentInvocations') or (row.get('providerData') or {}).get('toolResult',{}).get('subAgent') is not None: raise OperationError('尚不支持子代理历史图')
            result.append(row)
    except (ValueError,UnicodeError,AttributeError,TypeError) as exc: raise OperationError('无效历史 JSONL') from exc
    if not result: raise OperationError('历史为空')
    return result

def visible(row: dict) -> str:
    c=row.get('content',[])
    if isinstance(c,str): return c.strip()
    if not isinstance(c,list): raise OperationError('未知消息内容结构')
    return '\n'.join(x['text'] for x in c if isinstance(x,dict) and x.get('type') in {'text','input_text','output_text'} and isinstance(x.get('text'),str)).strip()

def boundaries(rows: list[dict]) -> list[tuple[int,dict]]:
    pending=set(); seen=set(); candidates=[]; candidate=None; user_seen=False
    for index,row in enumerate(rows):
        kind=row['type']; content=row.get('content',[])
        if kind=='message' and row.get('role')=='user' and visible(row):
            if candidate is not None and not pending: candidates.append(candidate)
            candidate=None; user_seen=True
        if kind=='reasoning': candidate=None
        calls=[]; results=[]
        if kind=='function_call': calls.append(row.get('callId') or row.get('call_id'))
        if kind in {'function_call_result','function_call_output'}: results.append(row.get('callId') or row.get('call_id'))
        for item in content if isinstance(content,list) else []:
            if not isinstance(item,dict): raise OperationError('未知消息内容项')
            if item.get('type')=='tool_use': calls.append(item.get('id'))
            if item.get('type')=='tool_result': results.append(item.get('tool_use_id'))
        for call in calls:
            if not isinstance(call,str) or not call or call in seen: raise OperationError('工具 ID 缺失或重复')
            seen.add(call); pending.add(call); candidate=None
        for call in results:
            if call not in pending: raise OperationError('未匹配的工具结果')
            pending.remove(call)
        # Hook/auth skipRun output is not a completed model turn.
        if kind=='message' and row.get('role')=='assistant':
            candidate=None
            if user_seen and row.get('status')=='completed' and not pending and visible(row) and not (row.get('providerData') or {}).get('skipRun'):
                uid(row.get('id')); candidate=(index,row)
    if candidate is not None and not pending: candidates.append(candidate)
    return candidates

def no_links(path: Path) -> None:
    if str(path).startswith('\\\\'): raise OperationError('不支持 UNC/网络共享路径，请使用本地磁盘')
    for p in (path,*path.parents):
        if p.is_symlink(): raise OperationError('路径含符号链接，拒绝写入')
        try:
            if getattr(p.lstat(),'st_file_attributes',0)&0x400: raise OperationError('路径含 Windows reparse point/junction，拒绝写入')
        except FileNotFoundError: pass

def inside(path: Path, root: Path) -> Path:
    no_links(path)
    if path.is_symlink() or not path.is_file(): raise OperationError('文件不存在或是符号链接')
    resolved=path.resolve()
    if root.resolve() not in resolved.parents: raise OperationError('路径不在配置目录内')
    return resolved

def find(profile: Path, session: str) -> Path:
    no_links(profile/'projects')
    matches=list((profile/'projects').glob(f'*/{uid(session)}.jsonl'))
    if len(matches)!=1: raise OperationError('会话不存在或重复')
    return inside(matches[0],profile/'projects')
