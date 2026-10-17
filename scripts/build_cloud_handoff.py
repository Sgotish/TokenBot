#!/usr/bin/env python3
"""Build a private Windows package for the migrated, non-expiring cloud trial."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / '.runtime/cloud-partner.json').read_text())
deployment = json.loads((ROOT / '.runtime/cloud-deployment.json').read_text())
if not deployment.get('public_verified') or cfg['expires_at'] is not None:
    raise SystemExit('Cloud endpoint must be verified and configured without expiry first.')
script = (ROOT / 'integrations/windows-codex/setup.ps1.template').read_text()
script = script.replace('__BASE_URL__', deployment['base_url']).replace('__TEST_KEY__', cfg['key'])
readme = '''TokenBots 云端测试包（替换之前的本机测试包）

1. 下载 ZIP，右键“全部解压”，不要直接在压缩包内运行。
2. 保存工作并完全退出 Codex 桌面版。
3. 双击解压文件夹里的 configure.cmd；普通用户运行即可。
4. 看到 Configured 后重新打开 Codex，在本机空文件夹里新建对话，问“只回复 OK”，再测试创建并运行 hello.py。

地址和专属 Key 已填写。脚本先检查连接，再备份原配置；已配置旧测试线路的电脑会更新同一线路。
配置成功后使用 gpt-6.1-sol / medium，关闭 Fast 模式。
服务已迁到 DigitalOcean，服务方的 Mac 可以关机；你不需要安装 Tailscale 或部署服务器。
本测试 Key 不设平台消费额度、日/周额度或自动到期时间，直到运营者主动撤销。
两个上游订阅本身的用量、模型权限和服务可用性仍然适用；这不是官方无限量套餐。
1 GB 测试服务器最多同时处理 2 个请求，避免把服务器压垮；繁忙时等当前任务结束再试。

若报错，发错误文字和发生时间，遮住 Key。不要关闭安全软件、不要把本包上传 GitHub 或公开转发。
恢复原线路：退出 Codex，将脚本打印的 config.toml.before-tokenbots-时间 备份复制回同目录 config.toml，再重新打开。
'''
launcher = '''@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
  echo Setup failed. Send the error message to us.
) else (
  echo Configured. Restart Codex and start a NEW LOCAL chat.
)
pause
'''
folder = ROOT / 'delivery'
folder.mkdir(mode=0o700, exist_ok=True)
folder.chmod(0o700)
package = folder / 'TokenBots-Windows-Cloud.zip'
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('TokenBots-Windows-Cloud/README.txt', readme.encode('utf-8-sig'))
    archive.writestr('TokenBots-Windows-Cloud/setup.ps1', script.encode('utf-8-sig'))
    archive.writestr('TokenBots-Windows-Cloud/configure.cmd', launcher.replace('\n', '\r\n').encode('ascii'))
package.chmod(0o600)
text = folder / '发给搭档-云端配置.txt'
text.write_text(readme + '\n完整 PowerShell 配置：\n\n' + script, encoding='utf-8-sig')
text.chmod(0o600)
print('Private cloud handoff generated. Credentials were not printed.')
