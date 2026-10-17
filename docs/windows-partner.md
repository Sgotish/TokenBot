# Windows 搭档如何测试

本次服务器和两个订阅账号已迁到 DigitalOcean 云端测试实例。搭档只配置自己的 Windows Codex 桌面版，不需要部署服务器、复制管理员账号或安装 Tailscale。

1. 向运营者获取私发的 `TokenBots-Windows-Cloud.zip` 文件。
2. 保存到 Windows，右键“全部解压”，完全退出 Codex。
3. 双击解压文件夹内的 `configure.cmd`，无需管理员权限。
4. 看到 `Configured` 后，重新打开 Codex，在本机空文件夹里新建对话，先问“只回复 OK”。
5. 再让它创建并运行 `hello.py`。把结果或错误文字、发生时间发给运营者。

如果系统安全软件拦截，不要关闭它，反馈提示即可。脚本会检查测试入口、备份现有配置，再切换专属测试线路；失败时不要反复执行。模板包含不改变持久执行策略的单进程 PowerShell 启动参数。

仓库中只有无密钥模板；真实测试包由 `scripts/build_cloud_handoff.py` 在运营者本机生成，放在被 Git 忽略的 `delivery/` 中。不要把私发包、临时 Key、订阅授权或管理员资料上传到仓库。

本次 Key 不设平台消费额度或自动到期时间，直到运营者主动撤销；仍受上游订阅本身的限制。云端最多同时处理两个请求。运营者的 Mac 可以关机；云服务器或公网入口故障仍会导致不可用。服务端 Responses 与工具调用回传已验证，Windows PowerShell 和桌面端仍需搭档实际验收。

恢复原线路：退出 Codex，将脚本显示的 `config.toml.before-tokenbots-时间` 备份复制回同目录 `config.toml`，然后重新打开。如果测试期间改过配置，先保留当前文件再恢复。

2026-10-17 云端包替换旧本机测试包。重新解压 Cloud 包并运行 configure.cmd；若已有测试 provider，脚本会备份后更新地址和 Key。旧包请勿继续转发。云端运行方式见 [两账号云端测试](cloud-test.md)。
