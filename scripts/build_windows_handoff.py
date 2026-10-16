#!/usr/bin/env python3
"""Generate private copy/paste instructions. Never print the generated key."""
import json
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
cfg=json.loads((ROOT/'.runtime/partner-test.json').read_text())
tunnel=json.loads((ROOT/'.runtime/partner-tunnel.json').read_text())
if tunnel.get('stopped_at') or time.time() >= cfg['expires_at']:
    raise SystemExit('Tunnel stopped or test expired; do not issue a stale handoff.')
os.kill(tunnel['runner_pid'],0)
url=tunnel['base_url']
template=(ROOT/'integrations/windows-codex/setup.ps1.template').read_text()
script=template.replace('__BASE_URL__',url).replace('__TEST_KEY__',cfg['key'])
expiry=datetime.fromtimestamp(cfg['expires_at'],ZoneInfo('America/Toronto')).strftime('%Y-%m-%d %H:%M')
intro=f'''Windows Codex 桌面版测试（含专属临时 Key，只发给测试搭档）

1. 保存工作，完全退出 Codex 桌面版。
2. 打开 Windows PowerShell（普通用户即可），复制下面整段代码，粘贴并回车。无需安装 Tailscale。
3. 脚本先检查地址和 Key，失败不会修改配置；成功后备份原 config.toml，再添加测试线路。
4. 重新打开 Codex，选择本机空文件夹，新建本地任务。使用 6.1 Sol / medium，关闭 Fast 模式；不要继续旧任务。
5. 先问“只回复 OK”，再连续追问两次；然后让它创建 hello.py，打印 hello 并运行。
6. 报错时发错误文字和发生时间，截图遮住 Key，不要反复点击重试。

测试地址：{url}
有效期至：{expiry}（多伦多时间）。并发 1，每分钟 6 次，内部测试额度 1 单位；这不是官方 API 充值金额。额度不足时联系我。
这是本机试用服务，服务方 Mac 需要保持运行。本次修复包使用固定主机名的公网入口，替换已失效的 lhr.life 临时地址；无需安装 Tailscale。尚需你在 Windows 桌面版完成实际验证。

恢复原线路：退出 Codex，将脚本打印的 config.toml.before-tokenbots-时间 文件复制回同目录 config.toml，再打开软件。若期间另有配置修改，先另存当前配置。

以下是完整 PowerShell 代码（含临时 Key，请勿发群或提交 Git）：

'''
folder=ROOT/'delivery';folder.mkdir(exist_ok=True,mode=0o700);folder.chmod(0o700)
for name,content in [('Windows-Codex-测试配置.ps1',script),('发给搭档-Windows-Codex.txt',intro+script)]:
    p=folder/name;p.write_text(content,encoding='utf-8-sig');p.chmod(0o600)
readme=f'''这是给 Windows Codex 桌面版使用的测试包，不需要部署服务器，也不需要 Tailscale。

操作步骤：
1. 把 ZIP 下载到自己的电脑，右键选择“全部解压”。不能直接在 ZIP 里面运行。
2. 保存工作，完全退出 Codex 桌面版。
3. 在解压出来的文件夹里，双击 configure.cmd。普通用户运行即可，不需要管理员权限。
4. 看到 Configured 表示配置成功。窗口会显示原配置备份位置。
5. 重新打开 Codex，选择一个本机空文件夹，新建对话，先发送“只回复 OK”。
6. 然后让它创建 hello.py，打印 hello 并运行。将结果或报错发给我们。

若窗口出现红色报错，先截图发给我们，不要反复运行。脚本未在 Windows 实机验证过。
脚本先检查网络和测试 Key，再备份并修改当前用户的 Codex 配置；不会部署号池。
若安全软件阻止运行，把提示发给我们，不要关闭安全软件。

本包已经填写测试地址和临时 Key，不需要你寻找或填写任何账号密码。
只给本次测试搭档使用，不要上传 GitHub 或转发到群里。
有效期至 {expiry}（多伦多时间）。服务器运行在我们的 Mac，需要保持在线。本修复包已替换失效的 lhr.life 地址；旧包不要再用。已配置过旧线路的电脑也可以运行此包更新地址。
并发 1，每分钟 6 次，测试模型 gpt-6.1-sol；使用 medium 并关闭 Fast 模式。

恢复原配置：退出 Codex，把窗口显示的 config.toml.before-tokenbots-时间 文件复制为同目录的 config.toml，然后重新打开。
代码仓库：https://github.com/Sgotish/TokenBot
仓库用于看代码；本次只测试客户端，不需要下载并部署整个仓库。
'''
launcher='''@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
  echo Setup failed. Send the error message to us. Do not retry repeatedly.
) else (
  echo Setup finished. Restart Codex and create a NEW LOCAL chat.
)
pause
'''
package=folder/'TokenBots-Windows-Fix2.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('TokenBots-Windows-Test/README.txt',readme.encode('utf-8-sig'))
    z.writestr('TokenBots-Windows-Test/setup.ps1',script.encode('utf-8-sig'))
    z.writestr('TokenBots-Windows-Test/configure.cmd',launcher.replace('\n','\r\n').encode('ascii'))
package.chmod(0o600)
print('Private Windows handoff generated; key not printed. Expiry: '+expiry+' America/Toronto')
