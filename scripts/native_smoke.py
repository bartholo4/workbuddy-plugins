#!/usr/bin/env python3
"""Opt-in actual-host smoke using ONLY a new synthetic HOME/profile/workspace.
No installer download, real credentials, model prompt or existing profile reads.
"""
import argparse,json,os,re,sqlite3,subprocess,sys,uuid,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--node',required=True);p.add_argument('--cli',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 node=Path(a.node).resolve(strict=True);cli=Path(a.cli).resolve(strict=True);out=Path(a.output).absolute()
 out.mkdir(parents=True,exist_ok=False)
 cwd=out/'workspace';home=out/'home';profile=home/'.workbuddy';logs=out/'logs'
 for d in (cwd,profile,logs,out/'tmp'):d.mkdir(parents=True,exist_ok=True)
 env={k:os.environ[k] for k in ('PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT') if k in os.environ}
 env.update(HOME=str(home),USERPROFILE=str(home),APPDATA=str(home/'AppData/Roaming'),LOCALAPPDATA=str(home/'AppData/Local'),TEMP=str(out/'tmp'),TMP=str(out/'tmp'),CODEBUDDY_CONFIG_DIR=str(profile),WORKBUDDY_CONFIG_DIR=str(profile),CODEBUDDY_FORCE_HEADLESS_BUNDLE='1',DISABLE_TELEMETRY='1',DISABLE_GALILEO='1',PYTHONUTF8='1')
 def run(label,args,stdin=None):
  r=subprocess.run([str(node),str(cli),*args],cwd=cwd,env=env,input=stdin,capture_output=True,text=True,encoding='utf-8',timeout=120)
  (logs/(label+'.txt')).write_text(r.stdout+'\nSTDERR\n'+r.stderr,encoding='utf-8')
  if r.returncode:raise RuntimeError(label+' failed; inspect synthetic logs')
  return r.stdout
 for name in ('workbuddy-tools',):run('validate-'+name,['plugin','validate',str(ROOT/'plugins'/name)])
 run('marketplace',['plugin','marketplace','add',str(ROOT)])
 for name in ('workbuddy-tools',):
  run('install-'+name,['plugin','install',name+'@workbuddy-plugins'])
  r=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'plugins'/name/'scripts/manage.py'),'install','--project',str(cwd),'--cli',str(cli),'--node',str(node)],env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
  if r.returncode:raise RuntimeError('Project hook installation failed: '+r.stderr)
 listing=run('list',['plugin','list','--json'])
 assert all(name+'@workbuddy-plugins' in listing for name in ('workbuddy-tools',))
 sid=str(uuid.uuid4());key=re.sub('-+','-',re.sub(r'[/\\:]','-',str(cwd.resolve())).strip('-'));directory=profile/'projects'/key;directory.mkdir(parents=True)
 ids=[str(uuid.uuid4()) for _ in range(4)];rows=[]
 for i,(role,text) in enumerate([('user','Synthetic Q1'),('assistant','Synthetic A1'),('user','EXCLUDED Q2'),('assistant','EXCLUDED A2')]):
  row={'type':'message','id':ids[i],'role':role,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}],'status':'completed','cwd':str(cwd),'sessionId':sid,'timestamp':1793520000000+i}
  if i:row['parentId']=ids[i-1]
  rows.append(row)
 source=directory/(sid+'.jsonl');source.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
 db=sqlite3.connect(profile/'workbuddy.db');db.executescript((ROOT/'src/plugin/tests/linux-sessions-schema.sql').read_text(encoding='utf-8'));db.execute('INSERT INTO sessions(id,cwd,user_id,title,created_at,updated_at) VALUES(?,?,?,?,?,?)',(sid,str(cwd),'synthetic-user','Synthetic source',1793520000000,1793520000000));db.commit();source_row=db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
 calls={}
 def command(namespace,name,args=None):
  text='/'+namespace+':'+name+(' '+json.dumps(args,ensure_ascii=True) if args else '')
  label=namespace+'-'+name;calls[label]=calls.get(label,0)+1
  result=run(label+'-'+str(calls[label]),['--resume',sid,'-p',text])
  assert 'Authentication required' not in result
  line=next((line for line in result.splitlines() if line.startswith('{"conversation_tools"')),None)
  if not line:raise RuntimeError('Native hook did not return operation JSON; inspect '+namespace+'-'+name)
  return json.loads(line)['conversation_tools']
 points=command('workbuddy-tools','points');assert points[0]['message_id']==ids[1]
 command('workbuddy-tools','status')
 op=str(uuid.uuid4());branch=command('workbuddy-tools','branch',{'at':ids[1],'title':'Synthetic branch','operation_id':op});assert 'EXCLUDED' not in (directory/(branch['target']+'.jsonl')).read_text(encoding='utf-8');command('workbuddy-tools','recover',{'operation_id':op})
 seed=cwd/'seed.json';seed.write_text(json.dumps({'schema':1,'messages':[{'role':'user','text':'Synthetic request'},{'role':'assistant','text':'Synthetic answer','reasoning':'We need to verify the facts. Synthetic test only.'}]}),encoding='utf-8')
 style=command('workbuddy-tools','style-new',{'seed':str(seed),'operation_id':str(uuid.uuid4())});styled=directory/(style['target']+'.jsonl');assert 'We need to verify' in styled.read_text(encoding='utf-8')
 fork=str(uuid.uuid4());result=run('style-eof',['--print','--input-format','stream-json','--output-format','stream-json','--resume',style['target'],'--fork-session','--session-id',fork],stdin='');assert '"duration_api_ms":0' in result;assert 'We need to verify' in (directory/(fork+'.jsonl')).read_text(encoding='utf-8')
 assert db.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()==source_row
 assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==3
 for _ in range(5):command('workbuddy-tools','style-new',{'seed':str(seed),'operation_id':str(uuid.uuid4())})
 assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==8
 # Deliberate stream loss and missing interpreter must STILL block in the real host.
 settings=cwd/'.codebuddy/settings.local.json';saved=settings.read_bytes();cfg=json.loads(saved)
 entry=cfg['hooks']['UserPromptSubmit'][0]['hooks'][0];original=entry['command'];shell=entry.get('shell','posix')
 spec=importlib.util.spec_from_file_location('native_smoke_manage',ROOT/'plugins/workbuddy-tools/scripts/manage.py');manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)
 try:
  entry['command']=('& { '+original+' } *> $null') if shell=='powershell' else '('+original+') >/dev/null 2>&1'
  settings.write_text(json.dumps(cfg),encoding='utf-8')
  lost=run('both-hook-streams-discarded',['--resume',sid,'-p','/workbuddy-tools:status'])
  assert 'Authentication required' not in lost and 'blocked' in lost.lower(),lost
  entry['command']=manage.guarded_hook_command([str(out/'missing-python.exe'),str(cwd/'.codebuddy/conversation-tools-router.py')],shell)
  settings.write_text(json.dumps(cfg),encoding='utf-8')
  missing=run('missing-interpreter-failclosed',['--resume',sid,'-p','/workbuddy-tools:status'])
  assert 'Authentication required' not in missing and 'blocked' in missing.lower(),missing
 finally:settings.write_bytes(saved)
 subprocess.run([sys.executable,'-X','utf8',str(ROOT/'plugins/workbuddy-tools/scripts/manage.py'),'uninstall','--project',str(cwd)],env=env,check=True,capture_output=True)
 owners=json.loads((cwd/'.codebuddy/conversation-tools-installed.json').read_text(encoding='utf-8'));assert owners['plugins']=={}
 db.close()
 report={'status':'passed','platform':sys.platform,'native_combined_plugin':True,'source_database_unchanged':True,'reasoning_eof_api_ms':0,'owned_uninstall':True,'repeated_style_creates':5,'both_hook_streams_discarded_blocks':True,'missing_interpreter_blocks':True,'gui':'NOT TESTED','live_model_effect':'NOT TESTED'}
 (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
