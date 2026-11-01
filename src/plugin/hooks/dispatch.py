#!/usr/bin/env python3
"""Native UserPromptSubmit dispatcher: only exact namespaced slash commands."""
from __future__ import annotations
import json, os, sys, uuid
if sys.version_info < (3,10):
    print('{"decision":"block","reason":"conversation-tools requires Python 3.10+; install using a compatible interpreter"}')
    raise SystemExit(2)
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbuddy_native.model import OperationError, uid
from workbuddy_native.engine import Engine
MANIFEST=json.loads((Path(__file__).resolve().parents[1]/'.workbuddy-plugin/plugin.json').read_text(encoding='utf-8'))
PREFIX='/'+MANIFEST['name']+':'
SUPPORTED={'workbuddy-branch':{'branch','points','recover','status'},'workbuddy-style':{'style-new','recover','status'}}.get(MANIFEST['name'],{'branch','points','style-new','recover','status'})

def dispatch(event: dict) -> dict | None:
    prompt=event.get('prompt')
    if not isinstance(prompt,str) or not prompt.startswith(PREFIX): return None
    command,_,raw=prompt.partition(' ')
    try:
        if event.get('hook_event_name')!='UserPromptSubmit': raise OperationError('不支持的事件')
        expected='2.165.0' if sys.platform=='win32' else '2.147.0'
        if event.get('version')!=expected: raise OperationError('CLI 版本不匹配当前平台适配器，停止写入；需要 '+expected)
        if command not in {PREFIX+n for n in SUPPORTED}: raise OperationError('未知命令')
        args=json.loads(raw) if raw.strip() else {}
        if not isinstance(args,dict): raise OperationError('参数必须是 JSON 对象')
        cwd=Path(event['cwd'])
        if not cwd.is_absolute() or not cwd.is_dir(): raise OperationError('当前项目目录无效')
        session=uid(event['session_id'])
        transcript=Path(event['transcript_path'])
        if not transcript.is_absolute() or transcript.name!=session+'.jsonl' or transcript.parent.parent.name!='projects' or transcript.is_symlink(): raise OperationError('宿主历史路径无效')
        profile=transcript.parent.parent.parent.resolve()
        config_path=cwd/'.conversation-tools.json'
        if config_path.is_symlink(): raise OperationError('配置文件不能是符号链接')
        config=json.loads(config_path.read_text(encoding='utf-8'))
        if set(config)!={'schema','cli_argv'} or config['schema']!=1: raise OperationError('配置结构不支持')
        engine=Engine(profile,config['cli_argv'],profile/'conversation-tools-operations')
        name=command[len(PREFIX):]
        allowed={'branch':{'at','title','operation_id'},'points':set(),'style-new':{'seed','title','operation_id'},'recover':{'operation_id'},'status':set()}[name]
        if set(args)-allowed: raise OperationError('存在未知参数')
        if name=='points': result=engine.points(session,cwd)
        elif name=='branch':
            op=args.get('operation_id') or str(uuid.uuid5(uuid.NAMESPACE_URL,session+':'+str(event.get('generation_id',prompt))))
            result=engine.branch(session,args.get('at','latest'),args.get('title',''),op,cwd)
            from workbuddy_native.registry import register
            if (profile/'workbuddy.db').exists(): result=dict(result,desktop_registration=register(engine,result))
        elif name=='recover':
            result=engine.recover(uid(args.get('operation_id')))
            if (profile/'workbuddy.db').exists():
                from workbuddy_native.registry import register
                registration=register(engine,result); result=dict(result,desktop_registration=registration)
        elif name=='style-new':
            from workbuddy_native.style import create_style
            op=args.get('operation_id') or str(uuid.uuid5(uuid.NAMESPACE_URL,session+':'+str(event.get('generation_id',prompt))))
            result=create_style(engine,session,cwd,args,op)
            if (profile/'workbuddy.db').exists():
                from workbuddy_native.registry import register
                result=dict(result,desktop_registration=register(engine,result))
        else: result={'profile':str(profile),'adapter':('Windows WorkBuddy 5.9.3 / CLI 2.165.0' if sys.platform=='win32' else 'Linux WorkBuddy 5.6.2 / CLI 2.147.0'),'style_default':'off','database_present':(profile/'workbuddy.db').exists()}
        if isinstance(result,dict) and result.get('target'):
            result=dict(result,open_uri='workbuddy://chat/'+uid(result['target']),gui_open_verified=False)
        return {'decision':'block','reason':json.dumps({'conversation_tools':result},ensure_ascii=False)}
    except Exception as exc:
        return {'decision':'block','reason':'conversation-tools：'+(str(exc) if isinstance(exc,OperationError) else type(exc).__name__)+'；没有向模型提交此命令。'}

if __name__=='__main__':
    try:
        raw=sys.stdin.buffer.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('hook input too large')
        output=dispatch(json.loads(raw))
        if output is not None:
            print(json.dumps(output,ensure_ascii=False),flush=True)
            print(output['reason'],file=sys.stderr,flush=True)
            raise SystemExit(2)  # Native unconditional stop, even if host loses stdout on exit.
    except Exception:
        output={'decision':'block','reason':'conversation-tools：无效的宿主事件，已拒绝处理。'}
        print(json.dumps(output,ensure_ascii=False),flush=True)
        print(output['reason'],file=sys.stderr,flush=True)
        raise SystemExit(2)
