#!/usr/bin/env python3
"""Installed project router: exactly one host hook, argv-only namespace dispatch."""
import json,subprocess,sys
from pathlib import Path
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
def block(reason):
 message='WorkBuddy conversation tools: '+reason
 print(json.dumps({'decision':'block','reason':message},ensure_ascii=False),flush=True)
 print(message,file=sys.stderr,flush=True)
def main():
 raw=sys.stdin.buffer.read(1024*1024+1)
 if len(raw)>1024*1024:raise ValueError('event too large')
 event=json.loads(raw);prompt=event.get('prompt','')
 if not isinstance(prompt,str) or not prompt.startswith('/'):return
 namespace=prompt.split(':',1)[0][1:]
 if namespace not in {'workbuddy-tools','workbuddy-branch','workbuddy-style','conversation-tools'}:return False
 path=Path(__file__).with_name('conversation-tools-installed.json')
 if path.is_symlink():raise ValueError('ownership is a symlink')
 owners=json.loads(path.read_text(encoding='utf-8'))
 if owners.get('schema')!=2:raise ValueError('unsupported router ownership')
 owner=owners.get('plugins',{}).get(namespace)
 if owner is None:raise ValueError('requested plugin is not installed in this project')
 if not isinstance(owner,dict) or set(owner)!={'python','handler','shell'}:raise ValueError('invalid plugin owner')
 for key in ('python','handler'):
  p=Path(owner[key])
  if not p.is_absolute() or not p.is_file() or p.is_symlink():raise ValueError('missing or linked '+key)
 result=subprocess.run([owner['python'],'-X','utf8',owner['handler']],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=100,check=False)
 if result.returncode not in {0,2}:raise ValueError('operation handler failed')
 output=json.loads(result.stdout)
 if not isinstance(output,dict) or output.get('decision')!='block' or not isinstance(output.get('reason'),str):raise ValueError('handler did not safely stop the prompt')
 print(json.dumps(output,ensure_ascii=False),flush=True)
 print(output['reason'],file=sys.stderr,flush=True)
 return True
if __name__=='__main__':
 try:
  handled=main()
  raise SystemExit(2 if handled else 0)
 except Exception as exc:
  block('refused; '+type(exc).__name__+'; prompt processing stopped')
  raise SystemExit(2)
