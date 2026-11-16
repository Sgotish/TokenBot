# TokenBots Linux 桌面安装包 · 2026-11-16

安装器版本 `2026111601`，官方桌面基础版 `26.1111.21308`，官方包内 CLI 为 `0.169.0-alpha.11.1`。

这是无凭据的联网安装器。用户解压后运行 `bash install.sh`，自动识别发行版和处理器，下载并校验官方包，再输入自己的 TokenBots API Key。无需单独安装 Node/npm。包内没有客户 Key、Session、银行卡或官方账号凭据。

## 实现

- 支持识别 Ubuntu 24.04/26.04、Debian 13、Fedora 43/44、当前 Arch，以及 x64/ARM64。未知发行版或架构在修改前停止；不是覆盖所有 Linux 的单一二进制。
- DEB/RPM 使用官方版本固定地址和 SHA-256。Arch 使用官方安装脚本和固定校验值，保留其系统升级确认。
- 不修改官方程序文件。`TokenBots Codex` 菜单入口使用独立的 Codex profile 和 Electron 数据目录。
- 默认数据在 `~/.local/share/tokenbots-codex-linux/`，尊重 `XDG_DATA_HOME`。重装使用同一 profile，原 `~/.codex` 不变；不会自动导入官方账号的历史。
- 另有登录设置、用量查询、检查更新入口。客户端通过官方签名 apt/dnf/pacman 软件源更新；安装器本身下载新版 ZIP 重装。
- 官方内置功能保持原样，第三方授权和云端功能依然要求对应官方授权。没有把 TokenBots Key 伪装成 ChatGPT Pro/OAuth。

## 验证范围

- 5 项安装器回归检查通过：系统/架构选择、重装保留 profile、桌面入口路径转义、密钥拒绝不覆盖已有配置、包内无凭据。
- 通用客户端 7 项本地检查通过；其中 5 项需要真实 CLI 的既有检查在本地运行中跳过，未计为通过。
- Ubuntu 24.04 x64 和 ARM64 均已通过真实安装、原生窗口、界面发送合成消息、正常退出、重装、重新打开对话，以及官方 app-server 读取已保存对话。请求仅发送到隔离的回环测试服务，不是真实模型调用。
- 最终双架构 [Linux desktop installer acceptance](https://github.com/Sgotish/TokenBot/actions/runs/43872211632) 整组通过，验证提交 `084b105`。截图与验收 JSON 在该运行的两个 artifact 中；本机副本为 `reports/linux-final-run/`。
- 测试修正：固定调试端口重用导致重启连接失败；CDP 键盘事件没有触发原生退出；长标题中间位置误点置顶。保留这些失败记录，不能把早期整组运行称为通过。

## 发布

网站静态文件源提交 `07d1502`，分支 `codex/linux-download-20261116`。
安装器源分支 `codex/linux-installer-20261116`；版本化 ZIP 由 `scripts/build_linux_installer.py` 构建。

- ZIP：`https://tokenbots.top/static/TokenBots-Codex-Linux-2026111601.zip`
- SHA-256：`e5bdc4aedf5d7dc20ae33c24da681d08eac4dc43cb2e69119c929fb811f56714`
- 中文说明：`https://tokenbots.top/static/tokenbots-linux-readme-2026111601.txt`
- 版本清单：`https://tokenbots.top/static/tokenbots-linux-release.json`

四个线上文件已发布；实际 GET 均为 HTTP 200，全部字节与源文件一致，ZIP 内容校验通过。
线上验证记录：网站仓库 `reports/linux-release-20261116/verification.json`。

## 未验收

Leo 实机、真实 Key 的模型请求、Debian/Fedora/Arch 整机、Wayland、插件 OAuth、GitHub 仓库操作以及 Windows/Linux 之间的历史迁移均未验收。
官方 Linux 仍是预览版；[官方说明](https://learn.chatgpt.com/docs/linux/linux-app)目前尚未在 Linux 开放整机 Computer Use。安装器提供 Linux 桌面和终端入口，不把无桌面 VPS 当作桌面验收。
