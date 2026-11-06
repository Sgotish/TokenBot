# Leo 浏览器工具与项目推进修复 — 2026-11-06

## 本包用途

适用于桌面快捷方式「TokenBots Codex」的独立 Windows 安装，不适用于 VS Code/WSL/原版。它给当前专属配置接入 Microsoft Playwright MCP（固定版本 0.0.84），附带依赖，无需另外安装 Node、npm 或到国外下载浏览器。使用 Windows 已安装的 Microsoft Edge。

本包不含 API Key，不改变客户的模型、余额或原来的个人 Codex 配置。浏览器可以打开页面、读页面、点击、填写；它不是整台 Windows 的鼠标键盘控制，也不会自动获得普通浏览器中的登录状态。

## 使用

1. 保存工作，完全退出 TokenBots Codex。
2. 完整解压本包，双击 `enable-browser.cmd`。无需管理员权限。失败时保留具体错误，不关闭系统安全保护，不反复重装整个客户端。
3. 看到 Tools registered 后，通过原桌面快捷方式重新启动 TokenBots Codex，新建本地对话。在 MCP 设置中确认 `tokenbots_browser`，或让 Codex 列出当前可用工具。
4. 发给 Codex：`使用 tokenbots-browser-check。先验证浏览器导航、读取和点击能力；不要只看配置文件就报告成功。随后使用 tokenbots-project-checkpoints，读取项目现有记录，列明当前阶段和验收条件，完成一个未完成项。不要重新跑已经通过且没有改动的测试。`
5. 首次需要 GitHub/Cloudflare 等登录时，在工具打开的独立 Edge 窗口中亲自登录，再让 Codex继续。无需把密码、Session 或 Cookie 发给任何人。

两个 Skill 安装在当前 TokenBots 专属 home 的 `skills` 目录，原生桌面工具和浏览器工具的可用性仍由实际客户端决定。若新对话没有工具，提供 MCP 错误文字、客户端名称和版本；注册成功不等于客户设备已经点击成功。

## 回退与边界

完全退出客户端，将本次生成的 `config.toml.before-browser-*` 备份恢复为 config.toml；若之后还有其他配置修改，先保存现文件，再只移除 `[mcp_servers.tokenbots_browser]` 段。不要删除其他 MCP 段。两个 Skill 目录可单独移除。浏览器独立登录资料保存在当前 home 的 browser-profiles 中，不上传它。

旧客户端未必支持官方整机 Computer Use；需要时应核对官方桌面版 Settings → Computer use → Control 及应用授权，Windows保持解锁、目标应用可见。不能靠一个 Skill 宣称拥有未接入的系统工具。

## SaleSmartly 开工前

可以用 Codex 辅助开发，但先完成 M0 的真实接口能力确认和模型供应来源选择，再按 M0–M11 记录阶段。当前文档中的 TokenBots 供应与 Pro OAuth/官方 API 备用路径存在待定关系；先选清楚。人工接管/DNC、重复消息幂等、租约过期和恢复不得重复联系是首批验收重点。模拟、Shadow、真实小范围和生产就绪分别记账，不能用模拟通过代替真实可用。

## Google 二维码

截图是 Google 自己的账号身份确认，不是 TokenBots 卡密或充值码。我们代码中 Google Pay 是后台持卡人的可选付款方式，客户充值不必经过该二维码；网站选择 Google 登录也可能触发 Google 检查。仅凭截图无法确定从哪条入口进入，不能断言是 TokenBots 故障。

需要使用该 Google 账号的人应在自己的设备上完成验证或使用页面的「尝试其他方式」。VPN连通不等于通过账号验证；本补丁不处理、绕过或转发这种二维码。

参考：https://learn.chatgpt.com/docs/computer-use ，https://github.com/microsoft/playwright-mcp ，https://support.google.com/accounts/answer/9283368 。
