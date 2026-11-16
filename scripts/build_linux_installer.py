#!/usr/bin/env python3
"""Build the credential-free Linux online installer; never read private access files."""
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'integrations/linux-codex'
client = ROOT / 'integrations/codex-client'
bundle = client / 'dist/tokenbots.cjs'
if not bundle.is_file() or bundle.stat().st_mtime < (client / 'client.cjs').stat().st_mtime:
    raise SystemExit('Run npm ci && npm run build in integrations/codex-client first.')
output = ROOT / 'delivery/linux-2026111601'
folder = output / 'TokenBots-Linux'
folder.mkdir(parents=True, exist_ok=True)
files = {name: source / name for name in ('install.sh', 'platform.sh', 'tokenbots.sh', 'linux.cjs', 'packages.tsv', 'README.txt')}
files.update({
    'tokenbots.cjs': bundle,
    'native-menu/tokenbots-images.cjs': ROOT / 'integrations/windows-codex/native-menu/tokenbots-images.cjs',
    'THIRD-PARTY-LICENSE.txt': client / 'node_modules/smol-toml/LICENSE',
})
for name, original in files.items():
    target = folder / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, target)
    target.chmod(0o755 if name.endswith('.sh') else 0o644)
sums = ''.join(f'{hashlib.sha256((folder/name).read_bytes()).hexdigest()}  {name}\n' for name in sorted(files))
(folder / 'SHA256SUMS').write_text(sums)
archive = output / 'TokenBots-Codex-Linux-2026111601.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in sorted([*files, 'SHA256SUMS']):
        z.write(folder / name, 'TokenBots-Linux/' + name)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n')
print(archive)
print('SHA256 ' + checksum)
