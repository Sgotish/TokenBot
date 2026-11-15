# Windows 官方基础客户端升级：2026-11-15

已发布 OTA `2026111501`，基础应用 `26.1111.21308`（官方 MSIX `26.1111.2228.0`）。保留 TokenBots API Key 登录及现有独立 home。客户端基础升级、公共插件目录可用；完整官方账号插件权限尚未对齐。

## 已完成

- 适配新 Rspack 菜单结构，保留官方插件目录、模型菜单和原有授权逻辑。
- OTA 增加经签名清单指定的基础包下载、大小和 SHA256 验证、Windows Authenticode 检查，以及独立新目录迁移。
- 沿用旧客户端的登录配置、会话目录和用户模型选择，保留旧程序；旧快捷方式能转向新程序。
- 菜单同时显示实际基础客户端版本和 TokenBots 更新版本，避免仅更新组件就误报最新版。
- 公共下载入口已增加两个明确的 MSIX 文件路径，未开放其他网关路径。
- 发布源代码：TokenBot 分支 `codex/windows-official-parity-20261115`；网站静态发布源：AI-Token- 分支 `codex/windows-ota-20261115`，提交 `f4fd950`。

## 验证证据

- 13 项 Node 更新器/菜单测试、4 项 Python 发行包检查通过。
- Windows x64 官方包来源、签名、应用启动、用量菜单、七模型及推理强度检查通过；用量是合成 fixture，无真实模型调用。
- [旧版迁移运行](https://github.com/Sgotish/TokenBot/actions/runs/43725864845) 的迁移步骤通过：正式下载地址可用，26.1016.51333 升到 26.1111.21308；auth 和对话文件哨兵未变，旧程序保留、重复迁移幂等、旧快捷方式重定向正确。该运行后续插件测试步骤失败，不能称整次运行通过。
- [最终原生界面运行](https://github.com/Sgotish/TokenBot/actions/runs/43726943812) 全部通过。实际打开 Plugins 公共目录，见 Slack、Figma、Notion、Stripe 等安装入口；截图及 AX 文本在 artifact 的 reports/plugin-directory.*。
- [网站 CI](https://github.com/Sgotish/AI-Token-/actions/runs/43726362501) 通过；另有 4 项本机 i18n 测试通过。
- 发布后实际 GET 清单、更新 ZIP、说明页、翻译文件均为 200，字节与本地一致，清单 Ed25519 验签通过。两个 MSIX 的服务器文件 SHA256 和公共 HEAD 大小匹配。

## 发布与回退

- 稳定清单：https://tokenbots.top/static/windows-ota-v1.json
- 旧版一次性更新包：https://tokenbots.top/static/tokenbots-windows-ota.zip
- 清单 SHA256：`a07ed08d76ebfd7df8fd48283852b99290bddd1b18b772e6f3807567fa1cd00b`
- 更新 ZIP SHA256：`d6d406a1559e80c456e1956841dd68073a726e64d06d679f523defadff4eb280`
- 服务器旧版备份：`/opt/tokenbot-website/ota-backups/20261115-2026111501`；Caddy 原配置：`/etc/caddy/Caddyfile.before-desktop-20261115`。
- 客户端不降级安装旧序号；需要回退时应在更高序号发布修正版，不仅还原旧清单。

## 尚未完成

- 当前测试账号采用合成 TokenBots API Key。公共插件目录已显示，GitHub 未出现在这次目录里；这不是 GitHub OAuth 或仓库读写验收。
- GitHub 官方提供独立 MCP 接入：远程 PAT 或本机官方二进制 OAuth。后者由账号本人在浏览器授权，能保留 TokenBots 模型登录；本次尚未接入或替客户授权。参考 [GitHub 官方 Codex 指南](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-codex.md) 和 [本机 OAuth 文档](https://github.com/github/github-mcp-server/blob/main/docs/oauth-login.md)。不能把公共目录更新写成全部官方云端插件授权一致。
- Leo 本机是否下载安装成功、真实 GitHub 授权和仓库操作、ARM64 硬件运行未验收。当前测试仅证明所列范围，不能证明所有功能/所有账号完全等同。

## 客户更新

左下角账号菜单 → 检查更新 → 更新。基础包约 1 GB，下载完保存任务并完全退出、重开。很老的更新器首次先升级自身，可能需再完全退出重开一次。以客户端 `26.1111.21308` 和定制更新 `2026111501` 同时显示为准。没有按钮时用一次性更新包，完整解压后运行“更新现有客户端.cmd”。
