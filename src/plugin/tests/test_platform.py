import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from workbuddy_native.platform import lock, LockBusy, fsync_directory, same_path

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.path=self.root/'operation.lock'
    def test_lock_excludes_same_process_and_releases(self):
        with lock(self.path):
            with self.assertRaises(LockBusy):
                with lock(self.path): pass
        with lock(self.path): pass
        self.assertTrue(self.path.exists())
    def test_lock_released_after_exception(self):
        with self.assertRaises(ValueError):
            with lock(self.path): raise ValueError('synthetic')
        with lock(self.path): pass
    def test_reparse_attribute_rejected_without_is_junction_api(self):
        with patch.object(Path,'is_symlink',return_value=False), patch.object(Path,'lstat',return_value=SimpleNamespace(st_file_attributes=0x400)):
            with self.assertRaisesRegex(OSError,'reparse point'):
                with lock(self.path): pass
        self.assertFalse(self.path.exists())
    def test_unc_lock_rejected(self):
        with self.assertRaisesRegex(OSError,'UNC'):
            with lock(Path(r'\\server\share\operation.lock')): pass
    def test_cross_process_lock(self):
        script='''import sys
from pathlib import Path
from workbuddy_native.platform import lock, LockBusy
try:
    with lock(Path(sys.argv[1])): pass
except LockBusy:
    sys.exit(17)
'''
        env=dict(os.environ); env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
        with lock(self.path):
            result=subprocess.run([sys.executable,'-c',script,str(self.path)],env=env,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,17,result.stderr.decode())
        result=subprocess.run([sys.executable,'-c',script,str(self.path)],env=env,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode())
    def test_existing_paths_use_filesystem_identity(self):
        with patch('os.path.samefile',return_value=False) as same:
            self.assertFalse(same_path(self.root,self.root));same.assert_called_once()
    def test_same_path_normalization(self):
        self.assertTrue(same_path(self.root/'a'/'..'/'b',self.root/'b'))
        self.assertFalse(same_path(self.root/'a',self.root/'b'))
    def test_fsync_directory(self): fsync_directory(self.root)
    @unittest.skipUnless(os.name=='nt','Requires actual Windows filesystem')
    def test_windows_case_insensitive_path(self):
        self.assertTrue(same_path(str(self.root).upper(),str(self.root).lower()))
    @unittest.skipUnless(os.name=='nt','Requires actual Windows msvcrt')
    def test_windows_lock_byte_zero(self):
        with lock(self.path) as stream:
            self.assertGreaterEqual(os.fstat(stream.fileno()).st_size,1)
            stream.seek(10)
            # Other participants still lock byte zero, not the caller cursor.
            with self.assertRaises(LockBusy):
                with lock(self.path): pass
        with lock(self.path): pass
    @unittest.skipUnless(os.name=='posix','Requires case-sensitive POSIX semantics')
    def test_posix_case_sensitive_path(self):
        self.assertFalse(same_path(self.root/'A',self.root/'a'))
    @unittest.skipIf(os.name=='nt','Windows symlink creation requires optional privilege')
    def test_symlink_lock_rejected(self):
        target=self.root/'other'; target.write_text('unchanged')
        self.path.symlink_to(target)
        with self.assertRaises(OSError):
            with lock(self.path): pass
        self.assertEqual(target.read_text(),'unchanged')

if __name__=='__main__': unittest.main()
