#!/usr/bin/env python3
"""Generate local secrets once, refusing to replace an existing configuration."""
import argparse
import os
import secrets
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--admin-email', required=True)
p.add_argument('--output', default='.env')
a = p.parse_args()
if '\n' in a.admin_email or '@' not in a.admin_email:
    p.error('Use a valid email address')
values = {'SUB2API_IMAGE':'weishaw/sub2api:0.2.16@sha256:799e9b4ee9e3164f13fe74f4df93022048cb902eda533b98fe5751c883eb1a7c','ADMIN_EMAIL':a.admin_email}
for k in ('POSTGRES_PASSWORD','REDIS_PASSWORD','JWT_SECRET','TOTP_ENCRYPTION_KEY','ADMIN_PASSWORD'):
    values[k] = secrets.token_hex(32)
fd = os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd,'w') as f:
    f.write(''.join(k+'='+v+'\n' for k,v in values.items()))
print('Created private configuration at', Path(a.output).resolve())
