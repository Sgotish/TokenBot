"""Build a public, credential-free browser tools add-on for installed native copies."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / 'integrations/windows-codex/browser-tools'
if not (source / 'node_modules/@playwright/mcp/cli.js').is_file():
    raise SystemExit('Run npm ci --ignore-scripts --omit=dev in browser-tools first')
out = root / 'delivery/TokenBots-Windows-Browser-Repair-20261106.zip'
out.parent.mkdir(exist_ok=True)
launcher = '@echo off\r\ncd /d "%~dp0"\r\npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0enable-browser.ps1"\r\nif errorlevel 1 echo Setup stopped. Send the error text without your API Key.\r\npause\r\n'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for file in sorted(source.rglob('*')):
        if file.is_file() and not file.is_symlink() and '.bin' not in file.parts:
            z.write(file, 'TokenBots-Browser-Repair/' + file.relative_to(source).as_posix())
    z.writestr('TokenBots-Browser-Repair/enable-browser.cmd', launcher)
    z.write(root / 'docs/leo-browser-repair-20261106.md', 'TokenBots-Browser-Repair/使用说明.md')
print(str(out))
print('SHA256 ' + hashlib.sha256(out.read_bytes()).hexdigest())
