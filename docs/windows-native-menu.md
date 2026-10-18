# Windows 原生用量菜单核查

核查日期：2026-10-17。目标是在桌面应用头像菜单显示 TokenBots 号池用量。

## 目前结论

不需要搭档提供安装来源或版本才能继续研究。运营者可以直接下载当前官方包。已检查最新 x64 包；未检查 Arm64 实际二进制，也没有在 Windows 中运行修改版客户端。

原生菜单尚未实现。已有网页用量、Plus / Pro / 自动路由不是本目标的验收证据。没有可交付的通用原生菜单补丁。

## 当前发行包证据

- 来源：[官方 Windows 部署文档](https://learn.chatgpt.com/docs/enterprise/windows-deployment)及其链接的 `https://persistent.oaistatic.com/codex-app-prod/ChatGPT-x64.msix`。
- 包身份：`OpenAI.Codex`，架构 x64，MSIX 版本 `26.1013.4894.0`。
- 应用 package.json 版本：`26.1013.40934`。
- MSIX SHA-256：`e2d892e6c22310e4b1a2928b0d3a29a066e0863d3a333754d6585c77cdafbe7f`。
- 菜单资源：`profile-dropdown-items-71a6e604645d.js`，SHA-256 `2e9cd921b030aab1dbd26e12ac1698f4bc9c3129b442e4c65ae690f43d3574c3`。
- 初始界面资源：`app-initial-5851df3f6cb1.js`，SHA-256 `c70d95da34ba7e5962a559dbf68d0102d10b4b47b877f5d9933629bb5a1f3a10`。

官方文档明确下载提供最新 Store 签名包，当前没有独立 MSI 或非 Store EXE 桌面包。官网安装入口可能调用 Store 组件，不应把二者当作必然存在的两套可分别修改的程序。

以上资源只保留在忽略目录 `.runtime/native-research/`，不随仓库分发。签名文件存在不等于已验证 Windows 信任链。ASAR 资源哈希已校验；这不等于证明所有可能的客户端修改方案都不能运行。

## 代码核查发现

1. 当前菜单读取 `authMethod` 和 `sidebarFooter.modelProviderName`，区分 ChatGPT 身份和第三方模型提供方。
2. 用量组件读取 `ambientUsage`；其官方数据分支通过 `authAccountId`、`authUserId`、`currentAccountId` 及用量中的账号和用户身份进行一致性检查。
3. `ambient_usage.default` 是该官方用量对象中的显示数据，不是第三方网关地址配置。
4. [网关文档](https://learn.chatgpt.com/docs/enterprise/connect-to-a-gateway)和[插件文档](https://developers.openai.com/plugins/build/plugins)中已检查的接入方式没有提供头像菜单用量扩展点。

由此可以确认：仅改 TokenBots 网关、provider 名称或新增 `/v1/usage`，不足以实现目标。要交付这个位置的显示，还需要实际客户端集成方案及 Windows 运行验证。不能通过伪造官方登录身份来冒充号池用量，也不能把有代码特征当成补丁可用的证明。

## 我们这边复核，无需搭档回传信息

```sh
mkdir -p .runtime/native-research
curl --fail --location 'https://persistent.oaistatic.com/codex-app-prod/ChatGPT-x64.msix' \
  -o .runtime/native-research/ChatGPT-x64.msix
python scripts/inspect_windows_release.py .runtime/native-research/ChatGPT-x64.msix
```

检测器只读包身份、版本、菜单哈希和特征，检查所读 ASAR 条目完整性，不读取任何已安装客户端凭据。新版本结构发生变化、条目损坏时会报错，需要重新研究，不会自动修改不认识的程序。特征输出不是“原生菜单兼容”认证。

后续验收必须包括：实际 Windows 应用菜单出现真实用量、未知或过期数据显示正确、切换号池后的数据归属正确，以及更新和回退测试。本轮没有满足这些条件。
