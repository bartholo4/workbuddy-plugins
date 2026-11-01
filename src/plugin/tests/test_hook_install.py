import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dispatch',ROOT/'hooks/dispatch.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
mspec=importlib.util.spec_from_file_location('manage',ROOT/'scripts/manage.py');manage=importlib.util.module_from_spec(mspec);mspec.loader.exec_module(manage)
class HookTests(unittest.TestCase):
 def test_powershell_fixed_argv_escaping(self):
  self.assertEqual(manage.hook_command(["C:\\A B\\O'Brien;$x&`test.py"],'powershell'),"& 'C:\\A B\\O''Brien;$x&`test.py'")
  with self.assertRaises(ValueError):manage.hook_command(['bad\npath'],'powershell')
 def test_uninstall_recorded_powershell_hook_without_pwsh(self):
  with tempfile.TemporaryDirectory() as td:
   project=Path(td);folder=project/'.codebuddy';folder.mkdir();old={'hooks':[{'type':'command','shell':'powershell','command':"& 'old-python.exe' 'old-dispatch.py'",'timeout':90}]}
   (folder/'settings.local.json').write_text(json.dumps({'hooks':{'UserPromptSubmit':[old]}}),encoding='utf-8')
   (folder/'conversation-tools-installed.json').write_text(json.dumps({'conversation-tools':old}),encoding='utf-8')
   subprocess.run([sys.executable,str(ROOT/'scripts/manage.py'),'uninstall','--project',td,'--hook-shell','powershell'],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(json.loads((folder/'settings.local.json').read_text(encoding='utf-8')), {})
 def test_normal_prompts_unaffected(self):
  for prompt in ['hello',' /conversation-tools:branch','/other:branch','please /conversation-tools:branch']:self.assertIsNone(d.dispatch({'prompt':prompt}))
 def test_unknown_and_wrong_version_blocked(self):
  for e in [{'prompt':'/conversation-tools:nope','hook_event_name':'UserPromptSubmit','version':'2.147.0'},{'prompt':'/conversation-tools:branch','hook_event_name':'UserPromptSubmit','version':'future'}]:self.assertEqual(d.dispatch(e)['decision'],'block')
 def test_malicious_arguments_not_shell(self):
  out=d.dispatch({'prompt':'/conversation-tools:branch $(touch /tmp/never-create)','hook_event_name':'UserPromptSubmit','version':'2.147.0'})
  self.assertEqual(out['decision'],'block')
 def test_install_uninstall_preserves_other_settings(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'.codebuddy').mkdir();s=p/'.codebuddy/settings.local.json';old={'permissions':{'deny':['x']},'hooks':{'Stop':[{'hooks':[]}],'UserPromptSubmit':[{'hooks':[{'type':'command','command':'echo other'}]}]}};s.write_text(json.dumps(old))
   args=[sys.executable,str(ROOT/'scripts/manage.py')]
   subprocess.run(args+['install','--project',td,'--cli',sys.executable],check=True,stdout=subprocess.DEVNULL)
   subprocess.run(args+['install','--project',td,'--cli',sys.executable],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(len(json.loads(s.read_text())['hooks']['UserPromptSubmit']),2)
   subprocess.run(args+['uninstall','--project',td],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(json.loads(s.read_text()),old)
if __name__=='__main__':unittest.main()

class InstallerRecoveryTests(unittest.TestCase):
 def test_interrupted_change_and_last_uninstall_recover_owned_hooks(self):
  from types import SimpleNamespace
  from unittest.mock import patch
  import contextlib,io
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);folder=root/'.codebuddy';folder.mkdir();settings=folder/'settings.local.json';config=root/'.conversation-tools.json'
   args=SimpleNamespace(action='install',hook_shell='posix',cli=sys.executable,node=None)
   real_atomic=manage.atomic
   with contextlib.redirect_stdout(io.StringIO()):manage.configure(args,root,folder,settings,config)
   def interrupted(path,data):
    if path==settings:raise OSError('synthetic settings publication failure')
    real_atomic(path,data)
   with patch.object(manage.sys,'executable',str(ROOT/'hooks/dispatch.py')):
    with patch.object(manage,'atomic',side_effect=interrupted):
     with self.assertRaises(OSError):manage.configure(args,root,folder,settings,config)
    with contextlib.redirect_stdout(io.StringIO()):manage.configure(args,root,folder,settings,config)
   self.assertEqual(len(json.loads(settings.read_text(encoding='utf-8'))['hooks']['UserPromptSubmit']),1)
   owners=folder/'conversation-tools-installed.json';self.assertEqual(json.loads(owners.read_text(encoding='utf-8'))['stale_hooks'],[])
   args.action='uninstall'
   with patch.object(manage,'atomic',side_effect=interrupted):
    with self.assertRaises(OSError):manage.configure(args,root,folder,settings,config)
   with contextlib.redirect_stdout(io.StringIO()):manage.configure(args,root,folder,settings,config)
   self.assertEqual(json.loads(settings.read_text(encoding='utf-8')), {})
   self.assertEqual(json.loads(owners.read_text(encoding='utf-8'))['plugins'],{})
