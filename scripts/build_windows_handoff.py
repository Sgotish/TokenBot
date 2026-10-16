#!/usr/bin/env python3
"""Generate private copy/paste instructions. Never print the generated key."""
import json
import os
import time
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
这是本机试用服务，服务方 Mac 需要保持运行。免费隧道地址可能变更或提前断开；连接失败请联系我获取新配置。尚需你在 Windows 桌面版完成实际验证。

恢复原线路：退出 Codex，将脚本打印的 config.toml.before-tokenbots-时间 文件复制回同目录 config.toml，再打开软件。若期间另有配置修改，先另存当前配置。

以下是完整 PowerShell 代码（含临时 Key，请勿发群或提交 Git）：

'''
folder=ROOT/'delivery';folder.mkdir(exist_ok=True,mode=0o700);folder.chmod(0o700)
for name,content in [('Windows-Codex-测试配置.ps1',script),('发给搭档-Windows-Codex.txt',intro+script)]:
    p=folder/name;p.write_text(content,encoding='utf-8-sig');p.chmod(0o600)
print('Private Windows handoff generated; key not printed. Expiry: '+expiry+' America/Toronto')
