TokenBots Codex Linux — 2026111601

这是联网安装包，不用自行区分 x64 和 ARM64。
支持官方 Linux 桌面预览版支持的 Ubuntu 24.04/26.04、Debian 13、Fedora 43/44。
也可识别当前 Arch Linux；安装时由官方安装器提示确认系统升级。
不适用于没有桌面的 VPS，也不承诺覆盖所有 Linux 发行版。

安装
1. 将整个 ZIP 解压到 Linux 电脑。
2. 在解压后的 TokenBots-Linux 文件夹里右键“在终端打开”。
3. 输入：bash install.sh
4. 安装系统软件时输入 Linux 管理员密码；随后输入你自己的 TokenBots API Key。
   终端不显示密码和 Key 的输入内容，这是正常的。不要填写 ChatGPT 密码或 Session。
5. 从系统应用菜单打开“TokenBots Codex”。首次打开按官方引导选择项目。

需要联网，首次下载官方客户端约 550–650 MB，安装占用约 2 GB。
安装包不含任何人的 API Key，也不会读取原有官方账号的凭据。
若缺少 curl / sudo，请先通过系统的软件管理器安装。
系统或处理器不支持时会在修改前停止，保留原来的客户端和对话。

已安装后的入口
- TokenBots Codex：打开桌面客户端。
- TokenBots 登录设置：更换或重新输入自己的 Key。
- TokenBots 检查更新：通过官方签名软件源检查和安装更新，显示检查时间。
- TokenBots 用量查询：查询 TokenBots 用量。

安装器使用官方原始 Linux 客户端，不改官方程序文件。
官方客户端的软件更新由 apt / dnf 管理。安装器自身升级请下载新版 ZIP 并重跑安装。
Linux 预览版功能不等同于 Windows：官方目前未开放 Linux 整机 Computer Use。
第三方插件 OAuth、ChatGPT 云端功能和插件目录仍受官方登录与平台支持范围影响。
不代表已经获得全部官方 Pro 功能或 GitHub OAuth；本包不伪造这些授权。

对话与配置
默认位置：~/.local/share/tokenbots-codex-linux/
profile/ 保存 Codex 配置和对话；desktop/ 保存界面数据；releases/ 保留安装器版本。
如果设置过 XDG_DATA_HOME，则放在该目录的 tokenbots-codex-linux/ 下。
安装、重装、更新都使用同一个 profile，不会另建一个空对话库。
不修改 ~/.codex；已有官方客户端的对话不会自动合并进来。

终端操作（默认数据路径）
bash ~/.local/share/tokenbots-codex-linux/current/tokenbots.sh doctor
bash ~/.local/share/tokenbots-codex-linux/current/tokenbots.sh cli
bash ~/.local/share/tokenbots-codex-linux/current/tokenbots.sh usage

卸载入口但保留对话和登录
bash ~/.local/share/tokenbots-codex-linux/current/tokenbots.sh uninstall
此操作仅移除 TokenBots 应用菜单入口；不会删除数据或卸载官方 ChatGPT。

问题反馈
提供发行版、版本、处理器类型和 doctor 输出即可。不要发送 API Key、auth.json、
tokenbots-access.json、Session 或完整对话数据库。没有在 Leo 的实际设备验收前，
不能把测试机结果理解为他的电脑已经安装完成。

官方 Linux 说明：https://learn.chatgpt.com/docs/linux/linux-app
TokenBots：https://tokenbots.top/
