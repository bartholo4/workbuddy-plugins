"""No model requests, no source writes, argv-only official CLI cloning."""
from __future__ import annotations
import json, os, subprocess, time, uuid
from pathlib import Path
from typing import Any
from .model import OperationError, uid, digest, records, boundaries, find, no_links
from .platform import lock, fsync_directory, same_path

def atomic(path: Path, data: bytes) -> None:
    no_links(path)
    tmp=path.with_name(path.name+'.tmp-'+str(uuid.uuid4()))
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        fsync_directory(path.parent)
    finally:
        if tmp.exists(): tmp.unlink()

def encode(rows: list[dict]) -> bytes: return ''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows).encode()
def save(path: Path, data: dict) -> None: atomic(path,json.dumps(data,ensure_ascii=False,indent=2).encode())

class Engine:
    def __init__(self, profile: Path, cli: list[str], state: Path):
        no_links(profile); no_links(state)
        self.profile=profile.resolve(); self.cli=cli; self.state=state
        if not cli or any(not isinstance(s,str) or '\0' in s for s in cli): raise OperationError('CLI argv 配置无效')
        state.mkdir(parents=True,exist_ok=True,mode=0o700)
        if state.is_symlink(): raise OperationError('状态目录不能是符号链接')

    def points(self, session: str, cwd: Path) -> list[dict]:
        _,_,rows=self.source(session,cwd)
        return [{'message_id':r['id'],'turn':n,'preview':__import__('workbuddy_native.model',fromlist=['visible']).visible(r)[:180]} for n,(_,r) in enumerate(boundaries(rows),1)]

    def source(self, session: str, cwd: Path):
        path=find(self.profile,session); data=path.read_bytes(); rows=records(data)
        dirs=[r['cwd'] for r in rows if r.get('cwd')]
        if not dirs or not all(same_path(d,cwd) for d in dirs) or not cwd.is_dir(): raise OperationError('源会话与当前项目目录不一致')
        return path,data,rows

    def branch(self, session: str, boundary: str, title: str, operation: str, cwd: Path) -> dict:
        uid(session); uid(operation)
        if not isinstance(title,str) or len(title)>120 or any(ord(c)<32 for c in title): raise OperationError('标题应为 0–120 个普通字符')
        source,data,rows=self.source(session,cwd)
        points=boundaries(rows)
        if not points: raise OperationError('没有已完成且工具闭合的回复')
        if boundary=='latest': boundary=points[-1][1]['id']
        uid(boundary)
        ends={r['id']:i for i,r in points}
        if boundary not in ends: raise OperationError('请选择已完成且工具闭合的回复 ID')
        request={'source':session,'boundary':boundary,'title_sha256':digest(title.encode()),'cwd':str(cwd.resolve())}
        lock_path=self.state/(operation+'.lock')
        no_links(lock_path); no_links(self.state/(operation+'.json'))
        with lock(lock_path):
            journal=self.state/(operation+'.json')
            if journal.exists():
                old=json.loads(journal.read_text(encoding='utf-8'))
                if old.get('request')!=request: raise OperationError('操作 ID 已用于不同请求')
                if old.get('status')=='completed':
                    target=find(self.profile,old['target'])
                    if digest(target.read_bytes())!=old['target_sha256']: raise OperationError('目标已变化；禁止重复执行')
                    return old
                raise OperationError('操作未确定；用 recover 命令核查，禁止再次克隆')
            target_id=str(uuid.uuid4()); target=source.with_name(target_id+'.jsonl')
            if target.exists(): raise OperationError('新目标冲突')
            receipt={'operation':operation,'request':request,'target':target_id,'source_sha256':digest(data),'source_size':len(data),'status':'started','started_at':time.time()}
            save(journal,receipt)
            try:
                env=dict(os.environ); env.update(CODEBUDDY_CONFIG_DIR=str(self.profile),WORKBUDDY_CONFIG_DIR=str(self.profile),DISABLE_TELEMETRY='1')
                for k in ('CODEBUDDY_PROJECT_CONFIG_DIR','OTEL_LOG_RAW_API_BODIES'): env.pop(k,None)
                run=subprocess.run(self.cli+['--print','--input-format','stream-json','--output-format','stream-json','--resume',session,'--fork-session','--session-id',target_id,'--resume-session-at',boundary],cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=75,check=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
                receipt['cli_exit_code']=run.returncode
                if run.returncode: raise OperationError('官方 CLI 克隆失败')
                if source.read_bytes()!=data: raise OperationError('宿主更新了源历史；停止新分支提交')
                if find(self.profile,target_id)!=target: raise OperationError('CLI 输出目录不匹配')
                clone_data=target.read_bytes(); clone_rows=records(clone_data); clones={r['id']:r for r in clone_rows if r.get('id')}
                for row in rows:
                    if not row.get('id') or row['type']=='session-meta': continue
                    clone=clones.get(row['id'])
                    if clone is None or any(clone.get(k)!=row.get(k) for k in ('type','role','content','callId','call_id','name','arguments','output','parentId','logicalParentId')): raise OperationError('CLI 克隆契约变化')
                prefix=rows[:ends[boundary]+1]; ids={r.get('id') for r in prefix if r.get('id')}
                final=[r for r in clone_rows if r['type']=='session-meta']
                for row in prefix:
                    if row['type']=='session-meta': continue
                    if any(row.get(k) and row[k] not in ids for k in ('parentId','logicalParentId')): raise OperationError('悬空父消息')
                    r=dict(clones[row['id']]) if row.get('id') else dict(row)
                    if 'sessionId' in r:r['sessionId']=target_id
                    final.append(r)
                if title: final.append({'type':'custom-title','id':str(uuid.uuid4()),'customTitle':title,'sessionId':target_id})
                final_data=encode(final)
                receipt.update(status='prepared',target_sha256=digest(final_data),clone_sha256=digest(clone_data))
                save(journal,receipt)
                if source.read_bytes()!=data or target.read_bytes()!=clone_data: raise OperationError('提交前源或目标发生变化')
                atomic(target,final_data)
                receipt.update(status='completed',finished_at=time.time()); save(journal,receipt)
                return receipt
            except Exception as exc:
                receipt['error_type']=type(exc).__name__; save(journal,receipt)
                raise OperationError(f'操作未完成，保留诊断记录：{operation}；{exc if isinstance(exc,OperationError) else type(exc).__name__}') from exc

    def recover(self, operation: str) -> dict:
        uid(operation); journal=self.state/(operation+'.json')
        no_links(journal); no_links(self.state/(operation+'.lock'))
        with lock(self.state/(operation+'.lock')):
            r=json.loads(journal.read_text(encoding='utf-8')); target=find(self.profile,r['target'])
            # Recovery never rewrites a conversation; final atomic write may have succeeded before receipt save.
            if r.get('status') in {'prepared','completed'} and digest(target.read_bytes())==r.get('target_sha256'):
                r.update(status='completed',recovered_at=time.time()); save(journal,r); return r
            raise OperationError('目标未达到已准备哈希；保留新分支待人工核查，不自动删除或重新克隆')
