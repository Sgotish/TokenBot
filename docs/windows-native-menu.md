# Windows 原生用量菜单核查

核查日期：2026-10-17。目标是在桌面应用头像菜单显示 TokenBots 号池用量。

## 当前实现

已实现 **TokenBots 定制客户端副本** 内的头像菜单用量项。Windows x64 实际应用启动、展开账号菜单、显示“使用情况 / Plus 94%”、展开窗口详情及切换 Pro 后显示 81% 均已通过[运行验收](https://github.com/Sgotish/TokenBot/actions/runs/39085693786)。截图和 UI Automation 文本在该运行的 artifact 中；94% 是隔离测试数据，不是客户真实额度。

这不是修改原有 Store 安装。安装器直接下载已核对的官方包，在用户目录创建独立副本，因此不需要搭档确认原安装来源。两种架构的发行包和 JS 模块均已检查；x64 已实际运行，ARM64 尚未做硬件运行验收。

真实云端用量接口已通过同一 main-process bridge 取得 HTTP 200；Plus / Pro 各一次真实 Responses 请求均完成，已恢复原来的自动路由。真实数据和 UI 测试数据分开验证，避免把接入 Key 放进公开 CI。上游未返回的窗口显示未知，15 分钟前的记录显示待更新。

## 实现与交付

- `integrations/windows-codex/native-menu/component.js`：原生菜单组件，30 秒刷新，展开订阅窗口和重置时间，选择自动 / Plus / Pro。
- `backend.cjs`：主进程读取本机私有配置，转发用量和号池选择；renderer 不接触 Key。限制来源、路径、重定向及池值。
- `patch-copy.ps1`：仅修改带定制副本标记的目录；核对版本和原资源 SHA，更新 ASAR 条目与 Windows `INTEGRITY/ELECTRONASAR` 资源中的 header SHA。完整性校验继续启用，不修改系统保护。
- `install.ps1`：识别 x64 / ARM64，校验固定发行包 SHA，创建独立 UI 数据目录和桌面快捷方式。原应用文件不变，共用用户的 Codex 会话与配置；配置有备份。
- `scripts/build_native_handoff.py`：仅在本机生成包含私有接入配置的 ZIP，保存在 Git 忽略目录 `delivery/`；不可公开上传。

启动文件已修改，**定制副本不再具有有效的官方程序签名，也不是 OpenAI 官方支持版本**。不要关闭 SmartScreen、杀毒或 Windows 保护。升级需重新适配；官方包变化时安装器停止，不能把检测通过视为所有未来版本兼容。回退时退出定制副本、打开原应用；如需恢复线路，使用安装前配置备份。

## 当前发行包证据

- 来源：[官方 Windows 部署文档](https://learn.chatgpt.com/docs/enterprise/windows-deployment)及其链接的 `https://persistent.oaistatic.com/codex-app-prod/ChatGPT-x64.msix`。
- 包身份：`OpenAI.Codex`，架构 x64，MSIX 版本 `26.1013.4894.0`。
- 应用 package.json 版本：`26.1013.40934`。
- MSIX SHA-256：`e2d892e6c22310e4b1a2928b0d3a29a066e0863d3a333754d6585c77cdafbe7f`。
- 菜单资源：`profile-dropdown-items-71a6e604645d.js`，SHA-256 `2e9cd921b030aab1dbd26e12ac1698f4bc9c3129b442e4c65ae690f43d3574c3`。
- 初始界面资源：`app-initial-5851df3f6cb1.js`，SHA-256 `c70d95da34ba7e5962a559dbf68d0102d10b4b47b877f5d9933629bb5a1f3a10`。

官方文档明确下载提供最新 Store 签名包，当前没有独立 MSI 或非 Store EXE 桌面包。官网安装入口可能调用 Store 组件，不应把二者当作必然存在的两套可分别修改的程序。

完整官方资源只保留在忽略目录 `.runtime/native-research/`，不随仓库分发。签名文件存在不等于已验证 Windows 信任链。ASAR 资源哈希已校验；Windows 定制副本实际启动证据见上方运行链接。

## 代码核查发现

1. 当前菜单读取 `authMethod` 和 `sidebarFooter.modelProviderName`，区分 ChatGPT 身份和第三方模型提供方。
2. 用量组件读取 `ambientUsage`；其官方数据分支通过 `authAccountId`、`authUserId`、`currentAccountId` 及用量中的账号和用户身份进行一致性检查。
3. `ambient_usage.default` 是该官方用量对象中的显示数据，不是第三方网关地址配置。
4. [网关文档](https://learn.chatgpt.com/docs/enterprise/connect-to-a-gateway)和[插件文档](https://developers.openai.com/plugins/build/plugins)中已检查的接入方式没有提供头像菜单用量扩展点。

由此可以确认：仅改 TokenBots 网关、provider 名称或新增 `/v1/usage`，不足以实现目标。本实现通过定制副本的客户端组件接入 TokenBots 数据。不能通过伪造官方登录身份来冒充号池用量，也不能把有代码特征当成补丁可用的证明。

## 我们这边复核，无需搭档回传信息

```sh
mkdir -p .runtime/native-research
curl --fail --location 'https://persistent.oaistatic.com/codex-app-prod/ChatGPT-x64.msix' \
  -o .runtime/native-research/ChatGPT-x64.msix
python scripts/inspect_windows_release.py .runtime/native-research/ChatGPT-x64.msix
```

检测器只读包身份、版本、菜单哈希和特征，检查所读 ASAR 条目完整性，不读取任何已安装客户端凭据。新版本结构发生变化、条目损坏时会报错，需要重新研究，不会自动修改不认识的程序。特征输出不是“原生菜单兼容”认证。

验收区分 Windows 界面运行、真实云端接口以及搭档设备端体验；不能将一个层面的成功扩展成所有设备及版本已验证。


## 2026-10-18 精简余量与多模型

使用情况收起时显示当前套餐与剩余百分比；展开只保留套餐切换、已知窗口余量和进度条。账号编号、采集时间、内部刷新错误及长调试说明不再展示。30 秒自动检查仍在运行；过期数据显示待更新，未提供的窗口不伪装为 100%。

菜单识别所有 TokenBots 开头的提供方名称，修复独立客户名称无法显示定制菜单的问题。模型及强度使用原生选择器；服务器现放行七个用户模型，禁止静默替换。新安装默认 Astra / high，已存在的有效选择保留。更新后完全退出旧定制副本，解压新版安装包运行 install-native.cmd，再打开桌面的 TokenBots Codex，新建对话。
