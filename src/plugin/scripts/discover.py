#!/usr/bin/env python3
"""Read-only local runtime discovery; never executes a candidate or scans profiles."""
import json,os,sys
from pathlib import Path
roots=[]
if os.environ.get('WORKBUDDY_INSTALL_DIR'):roots.append(Path(os.environ['WORKBUDDY_INSTALL_DIR']))
if os.name=='nt':
    for env in ('LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)'):
        if os.environ.get(env):
            root=Path(os.environ[env]);roots.extend([root/'WorkBuddy',root/'Programs'/'WorkBuddy',root/'Tencent'/'WorkBuddy'])
else:roots.extend([Path('/opt/WorkBuddy'),Path('/opt/workbuddy')])
results=[]
for root in dict.fromkeys(roots):
    if not root.is_dir():continue
    resources=root/'resources'
    nodes=[resources/'runtime/node/node.exe',resources/'runtime/node/bin/node.exe',resources/'runtime/node/bin/node']
    clis=[resources/'app.asar.unpacked/cli/bin/codebuddy',resources/'app.asar.unpacked/cli/bin/codebuddy.js']
    vendor=resources/'vendor/node.zip'
    if vendor.is_file():results.append({'install_root':str(root),'bundled_node_archive':str(vendor),'note':'Archive is not executed or extracted; provide a trusted node.exe explicitly.'})
    for node in nodes:
        for cli in clis:
            if node.is_file() and cli.is_file():results.append({'install_root':str(root),'node':str(node.resolve()),'cli':str(cli.resolve())})
print(json.dumps({'python':sys.executable,'python_version':sys.version.split()[0],'python_supported':sys.version_info>=(3,10),'platform':sys.platform,'candidates':results,'next':'Verify the intended official installation; pass --cli and --node explicitly. Set WORKBUDDY_INSTALL_DIR if not found.'},ensure_ascii=True,indent=2))
