import os, json, sqlite3, tempfile, unittest, uuid
from workbuddy_native.platform import lock
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from workbuddy_native.engine import encode, save
from workbuddy_native.model import digest
from workbuddy_native.registry import register, RegistryError

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.cwd=self.root/'project'; self.cwd.mkdir()
        self.profile=self.root/'profile'; self.hist=self.profile/'projects'/'project'; self.hist.mkdir(parents=True)
        self.state=self.root/'state'; self.state.mkdir()
        self.engine=SimpleNamespace(profile=self.profile,state=self.state)
        self.source=str(uuid.uuid4()); self.target=str(uuid.uuid4()); self.op=str(uuid.uuid4())
        self.original=encode([{'type':'message','id':str(uuid.uuid4()),'role':'assistant','content':[{'type':'output_text','text':'fixture'}],'cwd':str(self.cwd)}])
        self.target_data=encode([{'type':'message','id':str(uuid.uuid4()),'role':'assistant','content':[{'type':'output_text','text':'fixture'}],'cwd':str(self.cwd)}, {'type':'custom-title','id':str(uuid.uuid4()),'customTitle':'测试 $(touch /tmp/never)','sessionId':self.target}])
        (self.hist/(self.source+'.jsonl')).write_bytes(self.original); (self.hist/(self.target+'.jsonl')).write_bytes(self.target_data)
        self.receipt={'operation':self.op,'target':self.target,'request':{'source':self.source,'cwd':str(self.cwd),'title_sha256':digest('测试 $(touch /tmp/never)'.encode())},'source_sha256':digest(self.original),'target_sha256':digest(self.target_data),'status':'completed'}
        self.journal=self.state/(self.op+'.json'); save(self.journal,self.receipt)
        self.dbpath=self.profile/'workbuddy.db'
        with sqlite3.connect(self.dbpath) as db:
            db.executescript(Path(__file__).with_name('linux-sessions-schema.sql').read_text())
            db.execute('INSERT INTO sessions (id,cwd,user_id,title,status,created_at,updated_at,transport,is_playground,unread,permission_mode,plugin_context_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(self.source,str(self.cwd),'synthetic-user','source','pending',1,1,'local',0,0,'bypass','private-not-copy'))
        self.source_row=self.row(self.source)
    def row(self,id):
        with sqlite3.connect(self.dbpath) as db: return db.execute('SELECT * FROM sessions WHERE id=?',(id,)).fetchone()
    def test_insert_and_idempotent(self):
        self.assertEqual(register(self.engine,self.receipt)['status'],'registered')
        self.assertEqual(register(self.engine,self.receipt)['status'],'already_registered')
        self.assertEqual(self.row(self.source),self.source_row)
        
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute('SELECT permission_mode,plugin_context_json,status FROM sessions WHERE id=?',(self.target,)).fetchone(),(None,None,'Pending'))
        self.assertEqual((self.hist/(self.source+'.jsonl')).read_bytes(),self.original)
    def test_absent_db_does_not_create(self):
        self.dbpath.unlink(); self.assertEqual(register(self.engine,self.receipt)['status'],'cli_only'); self.assertFalse(self.dbpath.exists())
    def test_unknown_schema(self):
        with sqlite3.connect(self.dbpath) as db: db.execute('ALTER TABLE sessions ADD COLUMN unknown_future TEXT')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNone(self.row(self.target))
    def test_unrecognized_default_rejected(self):
        with sqlite3.connect(self.dbpath) as db:
            db.execute('PRAGMA writable_schema=ON')
            db.execute("UPDATE sqlite_master SET sql=replace(sql, ?, ?) WHERE name='sessions'", ("DEFAULT 'Pending'", "DEFAULT 'Other'"))
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNone(self.row(self.target))
    def test_missing_title_uses_fallback(self):
        self.receipt['request']['title_sha256']=digest(b'')
        save(self.journal,self.receipt)
        register(self.engine,self.receipt)
        with sqlite3.connect(self.dbpath) as db:
            self.assertEqual(db.execute('SELECT custom_title FROM sessions WHERE id=?',(self.target,)).fetchone()[0],'分支 '+self.target[:8])
    def test_generated_column_rejected(self):
        with sqlite3.connect(self.dbpath) as db:
            db.execute('ALTER TABLE sessions ADD COLUMN unsafe_generated TEXT GENERATED ALWAYS AS (user_id) VIRTUAL')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNone(self.row(self.target))
    def test_host_append_after_snapshot_allowed(self):
        self.receipt['source_size']=len(self.original); save(self.journal,self.receipt)
        path=self.hist/(self.source+'.jsonl'); path.write_bytes(self.original+b'{}\n')
        self.assertEqual(register(self.engine,self.receipt)['status'],'registered')
        self.assertEqual(path.read_bytes(),self.original+b'{}\n')
    def test_changed_prefix_rejected(self):
        self.receipt['source_size']=len(self.original); save(self.journal,self.receipt)
        path=self.hist/(self.source+'.jsonl'); path.write_bytes(self.original.replace(b'fixture',b'changed')+b'{}\n')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
    def test_shared_operation_lock(self):
        with lock(self.state/(self.op+'.lock')):
            with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNone(self.row(self.target))
    @unittest.skipIf(os.name=='nt','Windows symbolic link creation requires optional privilege')
    def test_symlink_lock_rejected(self):
        target=self.root/'lock-target'; target.write_text('unchanged')
        (self.state/(self.op+'.lock')).symlink_to(target)
        from workbuddy_native.model import OperationError
        with self.assertRaises(OperationError): register(self.engine,self.receipt)
        self.assertEqual(target.read_text(),'unchanged')
    def test_busy(self):
        db=sqlite3.connect(self.dbpath); db.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        finally: db.rollback(); db.close()
        self.assertIsNone(self.row(self.target))
    def test_corrupt(self):
        self.dbpath.write_bytes(b'not sqlite')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
    def test_commit_then_receipt_failure_recovery(self):
        real_save=save; count=0
        def fail(path, data):
            nonlocal count
            count+=1
            if count>=2: raise OSError('synthetic crash after commit')
            real_save(path,data)
        with patch('workbuddy_native.registry.save',side_effect=fail):
            with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNotNone(self.row(self.target))
        self.assertEqual(register(self.engine,self.receipt)['status'],'already_registered')
    def test_foreign_uuid_collision(self):
        with sqlite3.connect(self.dbpath) as db: db.execute('INSERT INTO sessions (id,user_id,cwd,created_at,updated_at) VALUES (?,?,?,1,1)',(self.target,'foreign',str(self.cwd)))
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertEqual(self.row(self.target)[2],'foreign')
    def test_source_history_changed(self):
        (self.hist/(self.source+'.jsonl')).write_bytes(self.original+b'\n')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertIsNone(self.row(self.target))
    def test_trigger_rejected(self):
        with sqlite3.connect(self.dbpath) as db: db.execute('CREATE TRIGGER evil AFTER INSERT ON sessions BEGIN UPDATE sessions SET title="changed"; END')
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertEqual(self.row(self.source),self.source_row)
    @unittest.skipIf(os.name=='nt','Windows symbolic link creation requires optional privilege')
    def test_symlink_database_rejected(self):
        moved=self.dbpath.with_suffix('.saved'); self.dbpath.rename(moved); self.dbpath.symlink_to(moved)
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
    @unittest.skipIf(os.name=='nt','Windows symbolic link creation requires optional privilege')
    def test_symlink_sqlite_sidecar_rejected(self):
        target=self.root/'sidecar-target'; target.write_text('unchanged')
        self.dbpath.with_name(self.dbpath.name+'-wal').symlink_to(target)
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)
        self.assertEqual(target.read_text(),'unchanged')
    def test_target_edited_after_register(self):
        register(self.engine,self.receipt)
        with sqlite3.connect(self.dbpath) as db: db.execute('UPDATE sessions SET status="running" WHERE id=?',(self.target,))
        with self.assertRaises(RegistryError): register(self.engine,self.receipt)

if __name__=='__main__': unittest.main()
