#!/usr/bin/env python3
"""Build public installation repair files; never include any access configuration."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='2026112101'

def build(output):
    source=ROOT/'integrations/windows-codex'
    readme='''TokenBots Windows 安装修复 2026112101

此包不含账号、密码或 API Key。用于修复原专属安装包，不能单独完成账号配置。
1. 先关闭报错的安装窗口，不删除已安装的应用或对话。
2. 完整解压本 ZIP，把其中 TokenBots 文件夹里的内容复制到原来的 TokenBots 安装文件夹，选择替换同名文件。
   完成后 install-native.cmd、setup.ps1、native-menu 文件夹须在同一级；保留原来的 setup.ps1 和 native-menu/native-access.json。
3. 双击 install-native.cmd。不要在 ZIP 预览里运行，也不要只把 CMD 文件复制到桌面。不需以管理员身份运行。

原包找不到时：登录 https://tokenbots.top/console，用原来的 Key 重新下载专属配置包，完整解压后运行。
不要创建新 Key 来替代旧 Key；安装器用原来的 Key 识别已有配置和对话目录。

本次修复绝对路径、缺文件提示、旧版官网发包和慢速下载。基础应用仍为已适配的 26.1111.21308。
下载约 1 GB；显示进度，连接中断会续传，再次运行也继续已保存的进度。
旧安装器的不同版本残缺文件不能拼接到新版包，首次使用新版需要下载匹配的基础包。
网速慢也可用浏览器或下载管理器下载控制台显示的 MSIX 地址，把文件放到 install-native.cmd 旁边再运行，或拖到 install-native.cmd 上。
安装前仍检查完整大小、SHA256 和 Windows 签名；不会关闭 Windows 安全保护。
如果安全软件拦截，请保留提示；不要关闭杀毒或 SmartScreen。
'''
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('TokenBots/安装说明.txt',readme.encode('utf-8-sig'))
        z.writestr('TokenBots/install-native.cmd',(source/'install-native.cmd').read_text().replace('\n','\r\n').encode('ascii'))
        for p in sorted((source/'native-menu').iterdir()):
            if p.suffix in ('.ps1','.js','.cjs') or p.name=='desktop-release.json':
                z.write(p,'TokenBots/native-menu/'+p.name)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    print(f'{output.name} {output.stat().st_size} bytes SHA256 {digest}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'delivery'/f'TokenBots-Windows-Installer-Repair-{VERSION}.zip')
    build(parser.parse_args().output)
