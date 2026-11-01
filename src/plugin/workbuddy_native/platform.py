"""Small stdlib-only OS boundary; no application or profile mutations."""
from __future__ import annotations
from contextlib import contextmanager
import errno
import os
from pathlib import Path
from typing import Iterator, BinaryIO

class LockBusy(BlockingIOError):
    """The operation is already locked by this or another process."""

@contextmanager
def lock(path: Path) -> Iterator[BinaryIO]:
    """Acquire one nonblocking exclusive lock; callers validate path containment.

    Lock files are persistent, not deleted on unlock (unlinking permits competing
    locks on different inodes). Windows locks exactly byte zero on every path.
    """
    path=Path(path)
    if str(path).startswith('\\\\'): raise OSError('UNC/network lock paths are unsupported')
    for candidate in (path,*path.parents):
        if candidate.is_symlink(): raise OSError('Lock path contains a symbolic link')
        try:
            # FILE_ATTRIBUTE_REPARSE_POINT also covers junctions on Python 3.10/3.11.
            if getattr(candidate.lstat(),'st_file_attributes',0)&0x400:
                raise OSError('Lock path contains a Windows reparse point/junction')
        except FileNotFoundError: pass
    fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'r+b',buffering=0) as stream:
        acquired=False
        try:
            if os.name=='nt':
                import msvcrt
                if os.fstat(stream.fileno()).st_size==0:
                    stream.write(b'\0'); stream.flush()
                stream.seek(0)
                try: msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                except OSError as exc:
                    if exc.errno in {errno.EACCES,errno.EAGAIN,errno.EDEADLK} or getattr(exc,'winerror',None) in {33,36}:
                        raise LockBusy('Operation is already running') from exc
                    raise
            else:
                import fcntl
                try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError as exc: raise LockBusy('Operation is already running') from exc
            acquired=True
            yield stream
        finally:
            if acquired:
                if os.name=='nt':
                    import msvcrt
                    stream.seek(0); msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream,fcntl.LOCK_UN)

def fsync_directory(path: Path) -> None:
    """Flush rename metadata on POSIX; directory handles are not portable on Win."""
    if os.name=='nt': return
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
    try: os.fsync(fd)
    finally: os.close(fd)

def same_path(left: str | Path, right: str | Path) -> bool:
    """Resolved path identity with OS-native case rules, not string casefold."""
    a=str(Path(left).resolve()); b=str(Path(right).resolve())
    if Path(a).exists() and Path(b).exists():
        return os.path.samefile(a,b)
    return os.path.normcase(a)==os.path.normcase(b) if os.name=='nt' else a==b
