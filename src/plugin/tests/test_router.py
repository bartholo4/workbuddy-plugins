import json,os,shutil,subprocess,sys,tempfile,unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('router_manage',ROOT/'scripts/manage.py');manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)
class RouterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.router=self.root/'conversation-tools-router.py';shutil.copy2(ROOT/'hooks/router.py',self.router)
  self.handler=self.root/'handler.py';self.handler.write_text("import json,sys\nprint(json.dumps({'decision':'block','reason':'SYNTHETIC RECEIPT'}),flush=True)\nsys.exit(2)\n",encoding='utf-8')
  self.owners=self.root/'conversation-tools-installed.json';self.owners.write_text(json.dumps({'schema':2,'hook':None,'plugins':{'workbuddy-style':{'python':str(Path(sys.executable).resolve()),'handler':str(self.handler),'shell':'powershell' if os.name=='nt' else 'posix'}}}),encoding='utf-8')
 def invoke(self,prompt,stdout=subprocess.PIPE):return subprocess.run([sys.executable,str(self.router)],input=json.dumps({'prompt':prompt}).encode(),stdout=stdout,stderr=subprocess.PIPE)
 def test_handled_exit2_even_when_stdout_discarded(self):
  self.assertEqual(self.invoke('/workbuddy-style:style-new').returncode,2)
  self.assertEqual(self.invoke('/workbuddy-style:style-new',subprocess.DEVNULL).returncode,2)
 def test_handler_crash_or_missing_still_exit2(self):
  self.handler.write_text('raise RuntimeError("synthetic")',encoding='utf-8');self.assertEqual(self.invoke('/workbuddy-style:style-new').returncode,2)
  self.handler.unlink();self.assertEqual(self.invoke('/workbuddy-style:style-new').returncode,2)
 def test_handler_allow_is_rejected(self):
  self.handler.write_text('print("{}")',encoding='utf-8');self.assertEqual(self.invoke('/workbuddy-style:style-new').returncode,2)
 def test_reserved_missing_owner_still_blocks(self):
  self.assertEqual(self.invoke('/workbuddy-branch:points').returncode,2)
 def test_normal_and_other_prompts_noop(self):
  for text in ['ordinary hello','/unrelated:command']:
   r=self.invoke(text);self.assertEqual((r.returncode,r.stdout,r.stderr),(0,b'',b''))
 @unittest.skipUnless(os.name=='posix','POSIX shell integration')
 def test_posix_guard_maps_missing_interpreter_to2(self):
  command=manage.guarded_hook_command([str(self.root/'missing-python'),str(self.router)],'posix')
  r=subprocess.run(['/bin/sh','-c',command],capture_output=True);self.assertEqual(r.returncode,2)
  r=subprocess.run(['/bin/sh','-e','-c',command],capture_output=True);self.assertEqual(r.returncode,2)
 @unittest.skipUnless(os.name=='nt' or shutil.which('pwsh'),'Requires actual PowerShell 7 parser')
 def test_powershell_real_parser_and_error_guard(self):
  self.assertIsNotNone(shutil.which('pwsh'),'Windows validation requires PowerShell 7; do not silently skip')
  script=self.root/"space ' & ; $ ` (中文).py";script.write_text('import json,sys;print(json.dumps(sys.argv[1:]))',encoding='utf-8')
  argv=[sys.executable,'-X','utf8',str(script),"quote ' space & ; $ ` (中文)"]
  command=manage.guarded_hook_command(argv,'powershell')
  r=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,encoding='utf-8');self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout),argv[4:])
  r=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',manage.guarded_hook_command([str(self.root/'missing.exe')],'powershell')],capture_output=True);self.assertEqual(r.returncode,2)
  for code in (1,2):
   command=manage.guarded_hook_command([sys.executable,'-c','import sys;sys.exit('+str(code)+')'],'powershell')
   r=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',command],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   self.assertEqual(r.returncode,2)
if __name__=='__main__':unittest.main()
