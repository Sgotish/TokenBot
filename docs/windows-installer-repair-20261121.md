# Windows 安装修复 2026112101

本轮修复官网生成的 Windows 专属安装包以及既有包的安装入口。基础客户端保持已适配的 `26.1111.21308`，不更换客户 Key，不修改网关推理逻辑或已安装客户端的会话。

## 已确认的问题

- 截图中的 `-File native-menu\install.ps1 不存在` 与网站发包使用的相对路径入口一致。新入口固定使用自身绝对路径，并在调用 PowerShell 前检查目录完整性。截图无法确定客户是否直接在 ZIP 中运行、只复制了 CMD，或解压缺文件。
- 下载器 `--max-time 900 --retry 2` 不续传；截图两次 15 分钟只收到约 50–60 MB。新版按固定包 SHA 命名缓存，使用持久 `.partial`、Range 续传、连接/停滞超时、最多三次重试、每次最多四小时。重开也可继续，服务器忽略 Range 时单独保留旧片段并干净重试。
- 线上 OTA 清单已是 `2026111501`，但 `/opt/tokenbot-pilot` 的官网发包安装脚本仍引用十月包（x64 SHA 前缀 `ace6a186a30c7b8a`）。已同步全部公开原生安装资源，并把 `desktop-release.json` 纳入两个打包入口，统一使用经审阅版本。
- 安装前检查完整私有配置，支持浏览器下载 MSIX 后放在 CMD 旁边或拖到 CMD 安装。下载完整大小、SHA256 和 Windows Authenticode 验证仍保留；损坏文件隔离，不当作完整包安装。

## 验证证据

- 实现提交 `205f1b68306748ce9b335f801c082ec217e5c404`；测试环境大小写修正提交 `cf9f2e2799cf1dc9c67ff055ebd608201db6fdb4`。
- [Windows 安装验收 44968058100](https://github.com/Sgotish/TokenBot/actions/runs/44968058100) 全部通过：PowerShell 5.1 + 实际 cmd/curl 的 8 项回归、正式固定包下载/签名/解包/适配、真实桌面启动、原生用量/模型/推理强度菜单。测试用量为合成数据，没有调用真实模型。
- 8 项专项覆盖：中文/空格/`&`/`!` 路径且从 System32 启动；缺少同级目录；缺少私有配置；断线后续传；退出后重开续传；完整缓存免网络；服务端忽略 Range；同大小损坏内容拦截。
- [常规 CI 44968058092](https://github.com/Sgotish/TokenBot/actions/runs/44968058092) 全部通过，包含 Python 3.11/3.12/3.13、跨平台客户端及 Windows 配置回归。
- 首次 Windows 运行因测试夹具把 Windows 环境变量转换成区分大小写的字典后访问 `SystemRoot` 而失败；修正夹具后通过。本机系统 Python 3.9 不支持现有服务端 `asyncio.timeout`，本机 API 测试两项失败；CI 的三个受支持版本均通过，未因此修改生产业务逻辑。
- 生产发包服务已备份并更新 18 个文件、重启后 active。用合成 Key 在生产路径调用同一个打包函数：ZIP CRC、6 个关键文件、新版 descriptor 和全部公开原生脚本字节匹配通过；未读取客户 Key。
- 四个公开静态文件实际 GET 200、字节与源文件一致；正式 MSIX 范围请求返回 206，范围 `1024–2047/1057802768`，1024 字节。

## 发布与回退

- [修复 ZIP](https://tokenbots.top/static/TokenBots-Windows-Installer-Repair-2026112101.zip)，33906 字节；SHA256 `e39dc9c1c775a4ebce24af79f20b18bf4236b8dce2c100e6d1f45497287435a3`。
- [说明](https://tokenbots.top/static/tokenbots-windows-installer-readme-2026112101.txt)、[版本清单](https://tokenbots.top/static/tokenbots-windows-installer-release.json)、[校验](https://tokenbots.top/static/TokenBots-Windows-Installer-Repair-2026112101.zip.sha256)。修复 ZIP 没有账号凭据、`setup.ps1` 或 `native-access.json`，需覆盖原专属包；也可用原 Key 从控制台重下载完整包。
- 网站静态发布提交 `528df94`；两个仓库分支均为 `codex/windows-installer-repair-20261121`。
- 生产备份 `/opt/tokenbot-pilot/backups/installer-2026112101-004727`，包含 `restore.json` 和 `receipt.json`。恢复对应原文件并重启 `tokenbot-site-control` 即可回退发包服务；本次没有重启推理网关或迁移数据库。
- OTA 清单仍为 `2026111501`；本次是安装器修复版本，不冒充基础应用或 OTA 升级。

## 官网下载入口补齐

- 用户追问是否每次同步官网下载后，进一步补齐首页导航、页脚和控制台的“客户端下载”，统一进入 [客户端下载与更新](https://tokenbots.top/docs#download)。网站提交 `eaf60d4`。
- 下载页分别提供 Windows 完整专属包、安装修复包、既有客户端更新、Linux 安装包。Windows/Linux 的可见版本和版本化下载 URL 从各自发布清单读取，加载失败时保留已发布的静态链接。
- 线上三个 HTML 和新增 `downloads.js` 已部署；原 HTML 备份位于 `/opt/tokenbot-website/installer-backups/download-entries-20261121`。未重启网站或推理服务。
- 浏览器从实际首页导航点击进入下载页，再点击“下载安装修复包”，成功下载 ZIP，SHA256 与发布清单一致。截图保存在网站仓库 `reports/windows-installer-links-20261121/website-downloads.jpg`。脚本语法、HTML ID/链接目标及 `git diff --check` 通过。
- 以后发布验收需要同时核对 OTA 清单、官网动态专属发包、公开下载清单和客户可见页面；仅更新其中一项不能视为全渠道发布完成。

## 未验收与下一步

Leo 本机 Windows 11、中国实际网络和 ARM64 实机尚未验证；Windows CI 不等于这些场景。请 Leo 完整解压修复包，将其中 TokenBots 文件夹内容覆盖原 TokenBots 安装文件夹，保留原有私有配置，运行 install-native.cmd。安装成功前不删除旧应用或旧对话；使用同一 Key 才能沿用既有专用 home。旧版本下载的残缺包不能与新版本续传拼接。
