#!/usr/bin/env python3
"""Deterministic source-copy build; no network, dependencies or vendor binaries."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/plugin'
sys.path.insert(0,str(SOURCE))
from workbuddy_native.model import no_links
PLUGINS={'workbuddy-tools':{'branch','points','style-new','recover','status'}}
def build():
    for old_name in ('workbuddy-branch','workbuddy-style'):
        old=ROOT/'plugins'/old_name
        if old.exists():
            no_links(old)
            manifest=old/'.workbuddy-plugin/plugin.json'
            if not manifest.is_file() or json.loads(manifest.read_text(encoding='utf-8')).get('name')!=old_name:raise RuntimeError('Unowned old plugin directory')
            shutil.rmtree(old)
    for name,commands in PLUGINS.items():
        target=ROOT/'plugins'/name
        no_links(target)
        if target.exists():
            manifest_path=target/'.workbuddy-plugin/plugin.json'
            if target.is_symlink() or not manifest_path.is_file() or json.loads(manifest_path.read_text(encoding='utf-8')).get('name')!=name:
                raise RuntimeError('Refuse to replace a directory not owned by this plugin build: '+str(target))
            shutil.rmtree(target)
        target.mkdir(parents=True,exist_ok=True)
        shutil.copytree(SOURCE,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','tests','README.zh-CN.md'))
        manifest=json.loads((target/'.workbuddy-plugin/plugin.json').read_text(encoding='utf-8'));manifest.update(name=name,version='0.2.0-rc.3',description='Windows-first native conversation branching and opt-in reasoning seed tools')
        (target/'.workbuddy-plugin/plugin.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        for command in (target/'commands').glob('*.md'):
            if command.stem not in commands:command.unlink()
        skill=target/'skills/conversation-tools/SKILL.md'
        text=skill.read_text(encoding='utf-8').replace('/conversation-tools:',f'/{name}:')
        lines=[line for line in text.splitlines() if not any(f'/{name}:{command}' in line for command in {'branch','points','style-new','recover','status'}-commands)]
        skill.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    marketplace={'name':'workbuddy-plugins','owner':{'name':'WorkBuddy Conversation Tools'},'plugins':[{'name':name,'source':'./plugins/'+name,'version':'0.2.0-rc.3'} for name in PLUGINS]}
    (ROOT/'.workbuddy-plugin/marketplace.json').write_text(json.dumps(marketplace,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':build()
