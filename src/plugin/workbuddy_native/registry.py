"""Insert-only desktop discovery adapter. No schema migrations or source updates."""
from __future__ import annotations
import json, sqlite3, time
from contextlib import contextmanager
from .platform import lock, LockBusy, same_path
from pathlib import Path
from typing import TYPE_CHECKING
from .model import OperationError, uid, digest, find, records, no_links
from .engine import save
if TYPE_CHECKING:
    from .engine import Engine

_REQUIRED = {"id", "cwd", "user_id", "title", "custom_title", "status", "created_at",
             "updated_at", "deleted_at", "transport", "is_playground", "unread"}
_COPY = ("mode", "model", "project_id", "source_mode")
_NEVER_COPY = {"permission_mode", "use_sandbox_cli", "plugin_context_json", "buddy_snapshot_id", "buddy_binding_json",
               "expert_id", "expert_locale", "expert_runtime_identity", "expert_marketplace"}
_KNOWN_COLUMNS = _REQUIRED | set(_COPY) | {"last_activity_at", "is_background_automation", "expert_id",
    "expert_locale", "expert_runtime_identity", "expert_marketplace", "permission_mode", "use_sandbox_cli",
    "plugin_context_json", "last_user_prompt_expert_selection", "context_window", "addon_selection",
    "session_settings", "thought_level", "buddy_snapshot_id", "buddy_binding_json", "conversation_origin",
    "visibility", "group_id", "group_title", "agent_dirty", "agent_dirty_at", "agent_last_synced", "verified_at"}


class RegistryError(OperationError): pass

def safe_path(path: Path) -> None:
    try: no_links(path)
    except OperationError as exc: raise RegistryError(str(exc)) from exc

@contextmanager
def registry_lock(path: Path):
    try:
        with lock(path) as handle: yield handle
    except LockBusy as exc: raise RegistryError('桌面登记正在执行') from exc

def rowhash(row) -> str:
    return digest(json.dumps(dict(row),ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode())

def schema(db: sqlite3.Connection, fields: set[str]) -> set[str]:
    extended=db.execute("PRAGMA table_xinfo(sessions)").fetchall()
    if any(r[6] for r in extended): raise RegistryError("未知隐藏或生成字段；拒绝写入")
    columns=[tuple(r[:6]) for r in extended]
    names={r[1] for r in columns}
    expected=json.loads(Path(__file__).with_name('linux-sessions-columns.json').read_text(encoding='utf-8'))
    actual=[dict(zip(('cid','name','type','notnull','dflt_value','pk'),r)) for r in columns]
    if actual!=expected: raise RegistryError('桌面 schema 不匹配已核对的 40 列适配器；拒绝写入')
    if not _REQUIRED <= names or not names <= _KNOWN_COLUMNS:
        raise RegistryError("未知桌面数据库结构；拒绝写入")
    if [r[1] for r in columns if r[5]] != ['id']:
        raise RegistryError("sessions.id 主键不匹配")
    for r in columns:
        if r[1] in _NEVER_COPY and r[4] is not None and str(r[4]).strip().upper()!='NULL':
            raise RegistryError("安全字段具有未核对默认值")
        if r[3] and r[4] is None and r[1] not in fields:
            raise RegistryError("未处理的必填字段")
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name='sessions'").fetchone() or db.execute("PRAGMA foreign_key_list(sessions)").fetchall():
        raise RegistryError("sessions 存在触发器或外键；拒绝写入")
    return names

def source_ok(row, cwd: str) -> None:
    if row is None or not row['user_id'] or row['deleted_at'] is not None or row['transport']!='local' or row['is_playground']!=0:
        raise RegistryError("源桌面会话不是有效本地普通会话")
    if not row['cwd'] or not same_path(row['cwd'],cwd):
        raise RegistryError("桌面源会话工作目录不一致")

def register(engine: Engine, receipt: dict) -> dict:
    """Insert metadata for one verified branch; absent DB is an explicit CLI-only result.

    Crash after COMMIT is recovered by matching the precommitted insertion digest.
    An uncertain absent row is not reinserted automatically.
    """
    operation=uid(receipt.get('operation')); target_id=uid(receipt.get('target'))
    request=receipt.get('request',{}); source_id=uid(request.get('source'))
    if source_id==target_id: raise RegistryError("源和目标不能相同")
    journal=engine.state/(operation+'.json')
    safe_path(journal)
    if journal.is_symlink() or not journal.is_file(): raise RegistryError("缺少操作记录")
    stored=json.loads(journal.read_text(encoding='utf-8'))
    for key in ('operation','request','target','source_sha256','source_size','target_sha256','status'):
        if stored.get(key)!=receipt.get(key): raise RegistryError("操作记录与结果不一致")
    if stored.get('status')!='completed': raise RegistryError("分支尚未完成")
    database=engine.profile/'workbuddy.db'
    if not database.exists(): return {'status':'cli_only','reason':'desktop_database_absent','target':target_id}
    safe_path(database)
    for suffix in ('-wal','-shm','-journal'): safe_path(database.with_name(database.name+suffix))
    if database.is_symlink() or not database.is_file(): raise RegistryError("数据库不是普通本地文件")
    source=find(engine.profile,source_id); target=find(engine.profile,target_id)
    if not same_path(source.parent,target.parent): raise RegistryError("新分支目录不一致")
    source_data=source.read_bytes(); source_hash=digest(source_data); target_hash=digest(target.read_bytes())
    size=stored.get('source_size',len(source_data))
    if type(size) is not int or not 0<size<=len(source_data) or digest(source_data[:size])!=stored['source_sha256'] or target_hash!=stored['target_sha256']: raise RegistryError("源快照或目标文件已变化；拒绝登记")
    rows=records(target.read_bytes())
    cwd=request.get('cwd')
    if not isinstance(cwd,str) or not Path(cwd).is_absolute() or not same_path(Path(cwd).resolve(),cwd): raise RegistryError("无效项目目录")
    title='' if request.get('title_sha256')==digest(b'') else next((r['customTitle'] for r in reversed(rows) if r['type']=='custom-title' and isinstance(r.get('customTitle'),str)), '')
    if digest(title.encode())!=request.get('title_sha256'): raise RegistryError("标题摘要不匹配")
    title=title or '分支 '+target_id[:8]
    lock_path=engine.state/(operation+'.lock'); safe_path(lock_path)
    with registry_lock(lock_path):
        # Re-read under lock. Do not lose concurrent registration state.
        stored=json.loads(journal.read_text(encoding='utf-8'))
        for key in ('operation','request','target','source_sha256','source_size','target_sha256','status'):
            if stored.get(key)!=receipt.get(key): raise RegistryError('操作记录在等待锁时发生变化')
        previous=stored.get('desktop_registration',{})
        registration=dict(previous)
        db=None; commit_started=False
        try:
            db=sqlite3.connect(database.as_uri()+'?mode=rw',uri=True,timeout=0.5,isolation_level=None)
            db.row_factory=sqlite3.Row
            names=schema(db,_REQUIRED|set(_COPY))
            db.execute('BEGIN IMMEDIATE')
            schema(db,_REQUIRED|set(_COPY))
            source_row=db.execute('SELECT * FROM sessions WHERE id=?',(source_id,)).fetchone()
            source_ok(source_row,cwd); source_row_hash=rowhash(source_row)
            if previous.get('source_row_sha256') and previous['source_row_sha256']!=source_row_hash:
                raise RegistryError("源桌面行已变化；禁止恢复登记")
            now=int(time.time()*1000)
            values=dict(id=target_id,cwd=source_row['cwd'],user_id=source_row['user_id'],title=title,custom_title=title,status='Pending',created_at=now,updated_at=now,deleted_at=None,transport='local',is_playground=0,unread=0)
            for key in _COPY:
                if key in names: values[key]=source_row[key]
            columns=list(values)
            existing=db.execute('SELECT * FROM sessions WHERE id=?',(target_id,)).fetchone()
            if existing is not None:
                if previous.get('insert_columns')!=columns or not previous.get('expected_insert_sha256') or rowhash({k:existing[k] for k in columns})!=previous['expected_insert_sha256']:
                    raise RegistryError("目标 UUID 已存在且不属于此操作")
                if any(existing[k] is not None for k in _NEVER_COPY if k in names): raise RegistryError("目标安全字段已变化")
                if previous.get('target_row_sha256') and rowhash(existing)!=previous['target_row_sha256']: raise RegistryError("已登记目标已被修改")
                status='already_registered'
            else:
                if previous.get('status') in {'prepared','unknown','registered','already_registered'}:
                    raise RegistryError("上次登记结果不确定且目标不存在；禁止自动重插")
                registration.update(status='prepared',insert_columns=columns,expected_insert_sha256=rowhash(values),source_row_sha256=source_row_hash)
                stored['desktop_registration']=registration; save(journal,stored)
                db.execute('INSERT INTO sessions ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(values[k] for k in columns))
                status='registered'
            after=db.execute('SELECT * FROM sessions WHERE id=?',(source_id,)).fetchone()
            target_row=db.execute('SELECT * FROM sessions WHERE id=?',(target_id,)).fetchone()
            if rowhash(after)!=source_row_hash or digest(source.read_bytes())!=source_hash or digest(target.read_bytes())!=target_hash:
                raise RegistryError("提交前源记录或历史文件变化")
            registration.update(status=status,target=target_id,target_row_sha256=rowhash(target_row),source_row_sha256=source_row_hash,finished_at=time.time())
            commit_started=True; db.execute('COMMIT')
            stored['desktop_registration']=registration; save(journal,stored)
            return registration
        except Exception as exc:
            if db is not None and db.in_transaction:
                try: db.execute('ROLLBACK')
                except sqlite3.Error: commit_started=True
            # Preserve prepared intent if receipt persistence itself fails.
            registration.update(status='unknown' if commit_started or previous.get('status') in {'prepared','unknown'} else 'failed',error_type=type(exc).__name__)
            stored['desktop_registration']=registration
            try: save(journal,stored)
            except OSError: pass
            if isinstance(exc,RegistryError): raise
            raise RegistryError('桌面登记失败：'+type(exc).__name__+'；分支文件已保留') from exc
        finally:
            if db is not None: db.close()
