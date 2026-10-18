#!/usr/bin/env python3
"""Build a private portable Codex configuration package; no credential output."""
import argparse
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--client-config', type=Path, default=ROOT/'.runtime/cloud-partner.json')
p.add_argument('--output', type=Path)
a = p.parse_args()
config = json.loads(a.client_config.read_text())
origin = config['public_origin']
base = config.get('base_url', origin+'/v1')
u = urlsplit(origin)
if u.scheme != 'https' or not u.netloc or u.username or u.password or u.path or u.query or u.fragment or base != origin+'/v1' or not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', config['key']):
    raise SystemExit('Invalid private access configuration')
ident = config.get('client_id','partner')
if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}',ident):
    raise SystemExit('Invalid client id')
source = ROOT/'integrations/codex-client'
bundle = source/'dist/tokenbots.cjs'
if not bundle.is_file() or bundle.stat().st_mtime < (source/'client.cjs').stat().st_mtime:
    raise SystemExit('Build first: npm ci && npm run build in integrations/codex-client')
output = a.output or ROOT/'delivery'/f'TokenBots-{ident}-Mac-Windows-Linux-CLI.zip'
output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
access = {'public_origin':origin,'base_url':base,'key':config['key'],'label':config.get('label','TokenBots '+ident)}
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    prefix='TokenBots-Cross-Platform/'
    z.write(bundle,prefix+'tokenbots.cjs')
    z.writestr(prefix+'access.json',json.dumps(access,ensure_ascii=False,indent=2))
    z.write(ROOT/'docs/cross-platform.md',prefix+'README.md')
    z.write(source/'node_modules/smol-toml/LICENSE',prefix+'THIRD-PARTY-LICENSE.txt')
    z.writestr(prefix+'tokenbots.sh','#!/bin/sh\nexec node "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/tokenbots.cjs" "$@"\n')
    z.writestr(prefix+'tokenbots.cmd','@echo off\r\nnode "%~dp0tokenbots.cjs" %*\r\n')
    for target in ('cli','desktop'):
        z.writestr(prefix+f'setup-{target}.cmd',f'@echo off\r\nnode "%~dp0tokenbots.cjs" setup --target {target} --access "%~dp0access.json"\r\npause\r\n')
        z.writestr(prefix+f'setup-{target}.command',f'#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nnode ./tokenbots.cjs setup --target {target} --access ./access.json\nread -r unused\n')
    z.writestr(prefix+'start-cli.cmd','@echo off\r\nnode "%~dp0tokenbots.cjs" run\r\npause\r\n')
output.chmod(0o600)
print(f'Private cross-platform package created: {output.name}. No credentials printed.')
