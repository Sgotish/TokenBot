#!/usr/bin/env python3
"""Build the PRIVATE custom-client installer after Windows UI validation."""
import argparse
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--validated-run', required=True, help='Successful Windows UI acceptance run URL')
args = parser.parse_args()
if not args.validated_run.startswith('https://github.com/Sgotish/TokenBot/actions/runs/'):
    raise SystemExit('Expected this repository runtime validation URL')
config = json.loads((root / '.runtime/cloud-partner.json').read_text())
deployment = json.loads((root / '.runtime/cloud-deployment.json').read_text())
setup = (root / 'integrations/windows-codex/setup.ps1.template').read_text()
setup = setup.replace('__BASE_URL__', deployment['base_url']).replace('__TEST_KEY__', config['key'])
readme = '''TokenBots Codex 原生用量菜单 — 定制测试副本

这是 TokenBots 维护的定制客户端副本，不是 OpenAI 官方发布或支持的版本。
不会替换原来的官网 / Microsoft Store 安装，不需要提供安装来源或版本。

1. 把 ZIP 完整解压到一个文件夹，先完全退出原 Codex / ChatGPT 桌面应用。
2. 双击 install-native.cmd。它会配置云端线路、下载官方包并在本机创建定制副本。
   首次下载约 1 GB；请等待完成。自动识别 x64 / ARM64。
3. 打开桌面上的 TokenBots Codex 快捷方式，点击左下角账号菜单的“使用情况”。
   首次使用若出现欢迎页，选择工作类型后继续，再点击 Skip 跳过示例任务。
   可查看订阅窗口、展开详情，并切换自动 / Plus / Pro。先结束任务再切换，新建对话。

使用 TokenBots Codex 快捷方式才能看到新菜单；原应用的快捷方式仍打开原版。
菜单每 30 秒检查；服务器约每分钟主动查询上游额度，不需发送模型请求来更新。
显示本次检查和上游更新时间；无变化不代表未刷新，上游百分比可能取整。
Pro 若仅返回周窗口，5 小时栏会明确显示上游未提供，不把缺失数据当作 100%。
云端平台额度不设上限，上游订阅限制仍适用。
这是本机生成的定制程序，已修改启动器的归档元数据，因此不再具有有效的官方程序签名。
没有关闭归档校验、杀毒、SmartScreen 或 Windows 系统保护；遇到拦截请停止，不要关闭安全软件。
当前适配应用 26.1013.40934；下载内容更新后会停下而不是盲改新版本。
应用更新适配由我们维护，本定制副本不会自动跟随官方包升级。

回退：退出 TokenBots Codex，打开原来的官方应用。原应用和会话目录未被替换。
恢复配置则使用 configure 输出的 config.toml.before-tokenbots 备份；先保存你后续新增的配置。
本包包含你的接入 Key，只私发给指定搭档，不上传仓库、群聊或公开网盘。
'''
launcher = '''@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 goto failed
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0native-menu\install.ps1"
if errorlevel 1 goto failed
echo Ready. Open the TokenBots Codex desktop shortcut.
pause
exit /b 0
:failed
echo Installation stopped. Your original app is unchanged. Send us the error text without your Key.
pause
exit /b 1
'''
folder = root / 'delivery'
folder.mkdir(mode=0o700, exist_ok=True)
package = folder / 'TokenBots-Codex-Native-Usage.zip'
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
    prefix = 'TokenBots-Codex-Native-Usage/'
    archive.writestr(prefix + 'README.txt', readme.encode('utf-8-sig'))
    archive.writestr(prefix + 'install-native.cmd', launcher.replace('\n', '\r\n').encode('ascii'))
    archive.writestr(prefix + 'setup.ps1', setup.encode('utf-8-sig'))
    for file in (root / 'integrations/windows-codex/native-menu').iterdir():
        if file.suffix in ('.ps1', '.js', '.cjs'):
            archive.write(file, prefix + 'native-menu/' + file.name)
    archive.writestr(prefix + 'native-menu/native-access.json', json.dumps({'origin': config['public_origin'], 'key': config['key']}))
    archive.writestr(prefix + 'validation.txt', args.validated_run + '\nWindows UI fixture validation; live cloud bridge tested separately.\n')
package.chmod(0o600)
print('Private native menu package created. No credentials printed.')
