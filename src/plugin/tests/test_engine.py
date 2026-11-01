import tempfile,unittest,json,uuid,sys,os
from pathlib import Path
from unittest.mock import patch
from workbuddy_native.model import *
from workbuddy_native.engine import Engine,encode
from workbuddy_native.style import create_style
U=lambda:str(uuid.uuid4())
class TestEngine(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cwd=self.root/'project';self.cwd.mkdir();self.profile=self.root/'profile';self.folder=self.profile/'projects'/'project';self.folder.mkdir(parents=True);self.sid=U();self.op=U();self.rows=[];parent=None
  for role in ['user','assistant','user','assistant']:
   row={'type':'message','id':U(),'sessionId':self.sid,'cwd':str(self.cwd),'role':role,'content':[{'type':'text','text':role}],'status':'completed'}
   if parent:row['parentId']=parent
   parent=row['id'];self.rows.append(row)
  self.source=self.folder/(self.sid+'.jsonl');self.source.write_bytes(encode(self.rows));self.engine=Engine(self.profile,['/fake'],self.root/'state')
 def tearDown(self):self.tmp.cleanup()
 def fake(self,args,**kw):
  self.assertIs(kw['stdin'],__import__('subprocess').DEVNULL);self.assertNotIn('shell',kw)
  selected='CODEBUDDY_FORCE_LITE_WB_BUNDLE' if os.name=='nt' else 'CODEBUDDY_FORCE_HEADLESS_BUNDLE'
  other='CODEBUDDY_FORCE_HEADLESS_BUNDLE' if os.name=='nt' else 'CODEBUDDY_FORCE_LITE_WB_BUNDLE'
  self.assertEqual(kw['env'][selected],'1');self.assertNotIn(other,kw['env'])
  target=args[args.index('--session-id')+1];(self.folder/(target+'.jsonl')).write_bytes(self.source.read_bytes());return type('Run',(),{'returncode':0})()
 def test_branch_idempotent_and_immutable(self):
  before=self.source.read_bytes()
  with patch('subprocess.run',self.fake):r=self.engine.branch(self.sid,self.rows[1]['id'],'$(touch BAD)',self.op,self.cwd);r2=self.engine.branch(self.sid,self.rows[1]['id'],'$(touch BAD)',self.op,self.cwd)
  self.assertEqual(r,r2);self.assertEqual(self.source.read_bytes(),before);self.assertEqual(len(records(find(self.profile,r['target']).read_bytes())),3)
 def test_pending_and_incomplete(self):
  rows=self.rows[:2]+[{'type':'function_call','id':U(),'callId':'c'}]
  self.assertEqual(boundaries(rows),[])
  rows=self.rows[:2]+[dict(self.rows[1],id=U(),status='incomplete')];self.assertEqual(boundaries(rows),[])
 def test_unfinished_reasoning_invalidates(self):
  self.assertEqual(boundaries(self.rows[:2]+[{'type':'reasoning','id':U(),'content':[]}]),[])
 def test_embedded_tool_invalidates(self):
  rows=self.rows[:2]+[{'type':'message','role':'assistant','content':[{'type':'tool_use','id':'c'}]}];self.assertEqual(boundaries(rows),[])
 def test_skip_run_not_boundary(self):
  self.rows[3]['providerData']={'skipRun':True};self.assertEqual(len(boundaries(self.rows)),1)
 def test_unknown_uuid_symlink(self):
  with self.assertRaises(OperationError):uid('../escape')
  with self.assertRaises(OperationError):records(b'{"type":"unknown"}\n')
  outside=self.root/(U()+'.jsonl');outside.write_bytes(encode(self.rows));self.source.unlink()
  try:self.source.symlink_to(outside)
  except OSError as exc:
   if os.name=='nt':self.skipTest('Windows symlink privilege unavailable: '+str(exc))
   raise
  with self.assertRaises(OperationError):find(self.profile,self.sid)
 def test_failed_no_retry(self):
  with patch('subprocess.run',side_effect=TimeoutError):
   with self.assertRaises(OperationError):self.engine.branch(self.sid,'latest','',self.op,self.cwd)
  with patch('subprocess.run') as run:
   with self.assertRaises(OperationError):self.engine.branch(self.sid,'latest','',self.op,self.cwd)
   run.assert_not_called()
 def test_recover_prepared(self):
  with patch('subprocess.run',self.fake):r=self.engine.branch(self.sid,'latest','',self.op,self.cwd)
  r['status']='prepared';(self.engine.state/(self.op+'.json')).write_text(json.dumps(r));self.assertEqual(self.engine.recover(self.op)['status'],'completed')
 def test_style_no_model(self):
  seed=self.root/'seed.json';seed.write_text(json.dumps({'schema':1,'messages':[{'role':'user','text':'example'},{'role':'assistant','text':'answer'}]}));before=self.source.read_bytes()
  with patch('subprocess.run') as run:r=create_style(self.engine,self.sid,self.cwd,{'seed':str(seed)},self.op);run.assert_not_called()
  self.assertEqual(self.source.read_bytes(),before);self.assertEqual(len(records(find(self.profile,r['target']).read_bytes())),2)
 def test_reasoning_seed_preserves_plain_text_and_chain(self):
  seed=self.root/'reason.json';seed.write_text(json.dumps({'schema':1,'messages':[{'role':'user','text':'q'},{'role':'assistant','text':'a','reasoning':'synthetic reasoning'}]}))
  r=create_style(self.engine,self.sid,self.cwd,{'seed':str(seed)},self.op);rows=records(find(self.profile,r['target']).read_bytes())
  self.assertEqual(rows[1]['type'],'reasoning');self.assertEqual(rows[1]['rawContent'][0]['text'],'synthetic reasoning');self.assertEqual(rows[2]['parentId'],rows[1]['id']);self.assertNotIn('providerData',rows[1])
 def test_shipped_synthetic_we_need_demo(self):
  seed=Path(__file__).resolve().parents[1]/'examples/we-need-demo.json'
  r=create_style(self.engine,self.sid,self.cwd,{'seed':str(seed)},self.op);rows=records(find(self.profile,r['target']).read_bytes())
  self.assertTrue(rows[1]['rawContent'][0]['text'].startswith('We need'))
 def test_seed_rejects_private_opaque_fields(self):
  seed=self.root/'bad.json';seed.write_text(json.dumps({'schema':1,'messages':[{'role':'user','text':'q'},{'role':'assistant','text':'a','providerData':{'token':'x'}}]}))
  with self.assertRaises(OperationError):create_style(self.engine,self.sid,self.cwd,{'seed':str(seed)},self.op)
if __name__=='__main__':unittest.main()
