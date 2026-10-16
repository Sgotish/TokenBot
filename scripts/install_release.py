#!/usr/bin/env python3
"""Download only the pinned official macOS ARM release and check its archive hash."""
import hashlib
import json
import os
from pathlib import Path
import platform
import tarfile
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
if platform.system()!='Darwin' or platform.machine()!='arm64':
    raise SystemExit('This local installer requires macOS arm64. Use deploy/compose.yaml on Linux.')
lock=json.loads((ROOT/'upstream.lock.json').read_text())
r=ROOT/'.runtime';r.mkdir(mode=0o700,exist_ok=True)
archive=r/lock['darwin_arm64_asset']
if not archive.exists():
    urllib.request.urlretrieve(lock['repository']+'/releases/download/'+lock['tag']+'/'+archive.name,archive)
if hashlib.sha256(archive.read_bytes()).hexdigest()!=lock['darwin_arm64_sha256']:
    raise SystemExit('Checksum mismatch; refusing to extract or run')
with tarfile.open(archive) as t:
    m=t.getmember('sub2api')
    if not m.isfile(): raise SystemExit('Invalid release executable')
    content=t.extractfile(m).read()
(r/'sub2api').write_bytes(content);(r/'sub2api').chmod(0o700)
(r/'binary.json').write_text(json.dumps({'sha256':hashlib.sha256(content).hexdigest(),'version':lock['tag']}))
print('Verified release installed in .runtime; no credentials downloaded')
