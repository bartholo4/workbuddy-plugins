import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PackagingTests(unittest.TestCase):
 def test_install_idempotence_uninstall_preserves_unrelated_hooks(self):
  with tempfile.TemporaryDirectory() as td:
   project=Path(td);folder=project/'.codebuddy';folder.mkdir();settings=folder/'settings.local.json'
   unrelated={'hooks':[{'type':'command','command':'echo unrelated'}]};settings.write_text(json.dumps({'hooks':{'UserPromptSubmit':[unrelated]}}),encoding='utf-8')
   script=ROOT/'plugins/workbuddy-tools/scripts/manage.py'
   for _ in range(2):subprocess.run([sys.executable,str(script),'install','--project',td,'--cli',sys.executable],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(len(json.loads(settings.read_text(encoding='utf-8'))['hooks']['UserPromptSubmit']),2)
   subprocess.run([sys.executable,str(script),'uninstall','--project',td],check=True,stdout=subprocess.DEVNULL)
   self.assertEqual(json.loads(settings.read_text(encoding='utf-8'))['hooks']['UserPromptSubmit'],[unrelated])
 def test_single_plugin_all_commands(self):
  root=ROOT/'plugins/workbuddy-tools'
  self.assertEqual(json.loads((root/'.workbuddy-plugin/plugin.json').read_text(encoding='utf-8'))['name'],'workbuddy-tools')
  self.assertEqual({p.stem for p in (root/'commands').glob('*.md')},{'branch','points','style-new','recover','status'})
  self.assertEqual([p.name for p in (ROOT/'plugins').iterdir() if p.is_dir()],['workbuddy-tools'])
if __name__=='__main__':unittest.main()
