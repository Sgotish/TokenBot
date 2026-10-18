# Windows 搭档如何测试

本次服务器和两个订阅账号已迁到 DigitalOcean 云端测试实例。搭档只配置自己的 Windows Codex 桌面版，不需要部署服务器、复制管理员账号或安装 Tailscale。

1. 向运营者获取私发的 `TokenBots-Windows-Pools.zip` 文件。
2. 保存到 Windows，右键“全部解压”，完全退出 Codex。
3. 双击解压文件夹内的 `configure.cmd`，无需管理员权限。
4. 看到 `Configured` 后，重新打开 Codex，在本机空文件夹里新建对话，先问“只回复 OK”。
5. 再让它创建并运行 `hello.py`。把结果或错误文字、发生时间发给运营者。

如果系统安全软件拦截，不要关闭它，反馈提示即可。脚本会检查测试入口、备份现有配置，再切换专属测试线路；失败时不要反复执行。模板包含不改变持久执行策略的单进程 PowerShell 启动参数。

已经配置好云端线路的电脑无需重新运行 configure.cmd。双击新包的 **open-usage.cmd**，它将本包 Key 复制到剪贴板并打开用量页；粘贴登录即可选择自动、Plus 或 Pro，查看剩余窗口和实际调用账号。先结束当前任务再切换，然后在 Codex 新建对话。选择影响这个 Key 的所有后续请求。

这是独立的用量页面，未向 Codex 官方头像菜单添加按钮。网页中的旧快照会标记，缺失窗口显示未知；订阅剩余量与平台不设消费限额是两回事。

## 原生菜单适配状态：尚未完成

2026-10-17 重新检查 macOS 客户端 26.1013.40934（20770）：配置中的第三方 provider 名称和官方 ChatGPT 用量分支是分开的；原生菜单的 ambient usage 来源也依赖官方账户用量查询。仅修改我们的 `/v1/usage` 或网关配置不能证明该菜单已接入。检查文件为 `profile-dropdown-items-fd62d4277e96.js`，SHA-256 `0509c4b20ba069880812317669073ce2d66bd1b6449060caed6677fe2c6bd3e5`。厂商代码未修改或提交。

[官方网关接入文档](https://learn.chatgpt.com/docs/enterprise/connect-to-a-gateway)描述 provider 配置；[插件清单文档](https://developers.openai.com/plugins/build/plugins)描述 skills、MCP、界面资源及生命周期 hook。目前这些已检查资料没有提供第三方头像菜单用量挂载点，这并不证明所有未来版本均不支持。

不再要求搭档提供版本或安装来源。运营者直接从[官方 Windows 部署文档](https://learn.chatgpt.com/docs/enterprise/windows-deployment)下载最新包检查。该文档明确：官网入口和离线下载使用 Store 签名包，当前没有独立 MSI 或非 Store EXE 桌面包。因此“官网安装还是 Store 安装”不是这项开发的必要前置问题。

2026-10-17 已下载并检查官方最新 x64 MSIX（包版本 `26.1013.4894.0`，应用版本 `26.1013.40934`）。Windows 菜单同样将 provider 显示与官方账号用量分开，并校验用量对应的账号及用户；添加网关端点或调整 provider 名称不会将我们的号池数据接到官方菜单。包包含签名文件，菜单资源有 SHA-256 完整性元数据；本次只读检查验证了所读取资源的哈希，没有在 Windows 上验证签名信任或启动修改版程序。详细证据与复核命令见 [Windows 最新包核查](windows-native-menu.md)。

`inspect-native-menu.cmd` 仅保留为可选的本机诊断工具，不再要求搭档运行或回传报告。原生头像菜单需求仍未完成：目前没有已验证的客户端扩展或补丁，也没有把独立用量网页当成菜单完成品。在真实 Windows 客户端验证前，不应交付声称能添加该菜单的一键补丁。

仓库中只有无密钥模板；真实测试包由 `scripts/build_cloud_handoff.py` 在运营者本机生成，放在被 Git 忽略的 `delivery/` 中。不要把私发包、临时 Key、订阅授权或管理员资料上传到仓库。

本次 Key 不设平台消费额度或自动到期时间，直到运营者主动撤销；仍受上游订阅本身的限制。云端最多同时处理两个请求。运营者的 Mac 可以关机；云服务器或公网入口故障仍会导致不可用。服务端 Responses 与工具调用回传已验证，Windows PowerShell 和桌面端仍需搭档实际验收。

恢复原线路：退出 Codex，将脚本显示的 `config.toml.before-tokenbots-时间` 备份复制回同目录 `config.toml`，然后重新打开。如果测试期间改过配置，先保留当前文件再恢复。

2026-10-17 Pools 包增加用量入口，保留已验证的云端地址和 Key。若仍使用旧本机线路，运行 configure.cmd 会备份后更新配置。旧本机包请勿继续转发。云端运行方式见 [两账号云端测试](cloud-test.md)。
