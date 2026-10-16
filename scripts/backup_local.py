#!/usr/bin/env python3
"""Private local backup, without printing passwords or stopping the database."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tarfile
ROOT=Path(__file__).resolve().parents[1];r=ROOT/'.runtime'
cfg=json.loads((r/'local.json').read_text())
out=r/'backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True,mode=0o700)
file=out/'postgres.dump'
subprocess.run(['/opt/homebrew/opt/postgresql@16/bin/pg_dump','-h','127.0.0.1','-p','55439','-U','tokenbot','-d','tokenbot','-Fc','-f',str(file)],env={**os.environ,'PGPASSWORD':cfg['db_password']},check=True)
file.chmod(0o600)
config=out/'config.tar.gz'
with tarfile.open(config,'w:gz') as t:
    for name in ('local.json','data/config.yaml','binary.json'):
        p=r/name
        if p.exists():t.add(p,arcname=name,recursive=False)
config.chmod(0o600)
print('Private backup created:',out)
