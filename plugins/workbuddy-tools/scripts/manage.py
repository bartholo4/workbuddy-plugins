#!/usr/bin/env python3
"""Merge only owned native hook. No trust, permissions, credentials or history edits."""
import argparse,json,os,shlex,sys,shutil
if sys.version_info < (3,10):
    raise SystemExit('conversation-tools requires Python 3.10+; no settings changed')
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbuddy_native.engine import atomic
from workbuddy_native.model import no_links
from workbuddy_native.platform import lock
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=json.loads((ROOT/'.workbuddy-plugin/plugin.json').read_text(encoding='utf-8'))['name']

def hook_command(argv, shell):
    if shell=='posix':return shlex.join(argv)
    if shell=='powershell':
        if any(any(c in a for c in '\r\n\0') for a in argv):raise ValueError('unsupported control characters in hook path')
        return '& '+ ' '.join("'"+a.replace("'","''")+"'" for a in argv)
    raise ValueError('unsupported native hook shell')

def guarded_hook_command(argv,shell):
    command=hook_command(argv,shell)
    if shell=='powershell':
        return "$ErrorActionPreference='Stop'; try { "+command+"; if ($LASTEXITCODE -eq 0) { exit 0 } else { exit 2 } } catch { exit 2 }"
    if shell=='posix':
        return 'if '+command+'; then exit 0; else exit 2; fi'
    raise ValueError('unsupported hook shell')

def configure(a,project,folder,settings,config):
    snapshot=settings.read_bytes() if settings.exists() else None
    current=json.loads(snapshot) if snapshot is not None else {}
    if not isinstance(current,dict):raise ValueError('invalid project settings')
    entries=current.get('hooks',{}).get('UserPromptSubmit',[])
    if not isinstance(entries,list):raise ValueError('invalid hooks array')
    ownership=folder/'conversation-tools-installed.json';router=folder/'conversation-tools-router.py'
    no_links(ownership);no_links(router)
    owners=json.loads(ownership.read_text(encoding='utf-8')) if ownership.exists() else {'schema':2,'plugins':{},'hook':None}
    if not isinstance(owners,dict):raise ValueError('invalid ownership')
    if owners.get('schema')!=2:
        # Uninstall the old exact owned entry, without executing/parsing its shell.
        if a.action!='uninstall':raise ValueError('legacy hook layout: uninstall each old plugin first')
        previous=owners.pop(PLUGIN,None)
        entries=[e for e in entries if e!=previous]
        if entries:current.setdefault('hooks',{})['UserPromptSubmit']=entries
        elif 'hooks' in current:current['hooks'].pop('UserPromptSubmit',None)
        if current.get('hooks')=={}:current.pop('hooks')
        atomic(settings,json.dumps(current,ensure_ascii=False,indent=2).encode())
        if owners:atomic(ownership,json.dumps(owners,ensure_ascii=False,indent=2).encode())
        else:atomic(ownership,b'{"schema":2,"plugins":{},"hook":null}')
        return
    if not {'schema','plugins','hook'}<=set(owners) or set(owners)-{'schema','plugins','hook','stale_hooks'} or not isinstance(owners['plugins'],dict):raise ValueError('invalid ownership schema')
    previous=owners['hook'];plugins=owners['plugins']
    stale=owners.get('stale_hooks',[])
    if not isinstance(stale,list):raise ValueError('invalid ownership recovery list')
    old_hooks=stale+([previous] if previous else [])
    if a.action=='check':
        print(json.dumps({'project':str(project),'plugin':PLUGIN,'hook_installed':PLUGIN in plugins and previous in entries,'router_exists':router.is_file(),'engine_config_present':config.is_file(),'python':sys.version.split()[0],'python_executable':sys.executable,'platform':sys.platform,'hook_shell':a.hook_shell,'hook_shell_available':a.hook_shell!='powershell' or bool(shutil.which('pwsh'))},ensure_ascii=False));return
    if a.action=='install':
        if a.hook_shell=='powershell' and not shutil.which('pwsh'):raise ValueError('PowerShell 7 pwsh not found on PATH; no installation changes')
        if not a.cli or not Path(a.cli).is_absolute() or not Path(a.cli).is_file():raise ValueError('--cli must be the official bundled CLI absolute path')
        argv=[str(Path(a.cli).resolve())]
        if a.node:
            if not Path(a.node).is_absolute() or not Path(a.node).is_file():raise ValueError('invalid --node')
            argv.insert(0,str(Path(a.node).resolve()))
        if os.name=='nt' and Path(argv[0]).suffix.lower() not in {'.exe','.com'}:raise ValueError('Windows needs --node pointing to trusted node.exe, not a batch launcher')
        planned={'schema':1,'cli_argv':argv}
        if config.exists() and json.loads(config.read_text(encoding='utf-8'))!=planned:raise ValueError('existing CLI configuration differs; refusing overwrite')
        atomic(config,json.dumps(planned,ensure_ascii=False,indent=2).encode())
        plugins[PLUGIN]={'python':str(Path(sys.executable).resolve(strict=True)),'handler':str(ROOT/'hooks/dispatch.py'),'shell':a.hook_shell}
        atomic(router,(ROOT/'hooks/router.py').read_bytes())
    else:plugins.pop(PLUGIN,None)
    # One shared project router avoids the actual host's multi-hook result bug.
    entries=[e for e in entries if e not in old_hooks]
    owned=None
    if plugins:
        chosen=plugins[sorted(plugins)[0]]
        command=guarded_hook_command([chosen['python'],'-X','utf8',str(router)],chosen['shell'])
        hook={'type':'command','command':command,'timeout':110}
        if chosen['shell']=='powershell':hook['shell']='powershell'
        owned={'hooks':[hook]};entries.append(owned)
    owners['hook']=owned
    if entries:current.setdefault('hooks',{})['UserPromptSubmit']=entries
    elif 'hooks' in current:current['hooks'].pop('UserPromptSubmit',None)
    if current.get('hooks')=={}:current.pop('hooks')
    if settings.exists():
        backup=settings.with_name('settings.local.json.conversation-tools.backup')
        if not backup.exists():atomic(backup,settings.read_bytes())
    if (settings.read_bytes() if settings.exists() else None)!=snapshot:raise ValueError('settings changed concurrently; refusing overwrite')
    # Durable intent remembers old and new exact hooks until settings commit.
    owners['stale_hooks']=old_hooks+([owned] if owned else [])
    atomic(ownership,json.dumps(owners,ensure_ascii=False,indent=2).encode())
    atomic(settings,json.dumps(current,ensure_ascii=False,indent=2).encode())
    owners['stale_hooks']=[]
    atomic(ownership,json.dumps(owners,ensure_ascii=False,indent=2).encode())
    print(json.dumps({'status':a.action+'ed','plugin':PLUGIN,'project':str(project),'history_deleted':False},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['install','uninstall','check']);p.add_argument('--project',required=True);p.add_argument('--cli');p.add_argument('--node');p.add_argument('--hook-shell',choices=['powershell','posix'],default='powershell' if os.name=='nt' else 'posix');a=p.parse_args()
    project=Path(a.project).resolve(strict=True)
    if not project.is_dir():raise ValueError('project is not directory')
    folder=project/'.codebuddy';settings=folder/'settings.local.json';config=project/'.conversation-tools.json'
    for path in (folder,settings,config):no_links(path)
    if a.action=='check':configure(a,project,folder,settings,config);return
    folder.mkdir(exist_ok=True)
    with lock(folder/'conversation-tools-install.lock'):configure(a,project,folder,settings,config)
if __name__=='__main__':
    try:main()
    except Exception as e:print('Refused: '+str(e),file=sys.stderr);sys.exit(1)
