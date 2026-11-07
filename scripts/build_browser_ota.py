"""Create credential-free runtime archive and cumulative unsigned OTA inputs."""
from pathlib import Path
import hashlib, json, shutil, zipfile
root = Path(__file__).resolve().parents[1]
source = root / 'integrations/windows-codex/browser-tools'
out = root / '.runtime/browser-ota'
out.mkdir(exist_ok=True, parents=True)
archive = out / 'runtime.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for file in sorted(source.rglob('*')):
        if file.is_file() and not file.is_symlink() and '.bin' not in file.parts and 'skills' not in file.relative_to(source).parts:
            # Stable bytes across builds. Only runtime files, no customer readme/data.
            info = zipfile.ZipInfo(file.relative_to(source).as_posix(), (2026,11,6,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, file.read_bytes())
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
asset = dict(name='browser-tools.zip',url=f'https://tokenbots.top/static/ota-{sha}.zip',sha256=sha,size=archive.stat().st_size)
(out / 'assets.json').write_text(json.dumps([asset]))
release = out / 'release'
release.mkdir(exist_ok=True)
(release / 'browser-asset.json').write_text(json.dumps(asset))
for name in ['enable-images.ps1','tokenbots-images.cjs','ota-client.cjs','update-native.ps1','patch-copy.ps1','backend.cjs','component.js']:
    shutil.copyfile(root / 'integrations/windows-codex/native-menu' / name, release / name)
shutil.copyfile(root / 'scripts/windows-ota/apply.ps1',release / 'apply.ps1')
print(json.dumps(asset))
