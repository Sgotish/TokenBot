---
name: tokenbots-browser-check
description: Diagnose unavailable browser or computer operation in TokenBots Codex on Windows, and verify the actual browser tools before a web task. Use when the assistant says it cannot click, log in, see a page, or operate the computer.
---

# 浏览器能力检查

先检查当前会话实际提供的工具。模型能写代码不代表会话拥有电脑控制能力；Skill 也不能授予能力。

1. 有原生 Computer Use 时，按其工具文档选择正确应用或浏览器。没有时检查 `tokenbots_browser` MCP 是否提供 browser_navigate、browser_snapshot、browser_click 等工具。不要凭配置文件存在就声称已启用。
2. 工具缺失时，只做一次启动诊断：设置里的 MCP 状态、错误、当前客户端和 CODEX_HOME。定制版使用 `.tokenbots-native-homes` 独立目录，原版/WSL 的配置不能代替它。不要打印 config.toml 全文、Cookie、Session 或 Key。
3. 若 MCP 配置刚安装，完全退出并重开 TokenBots Codex，在新本地对话验证工具列表。仍失败则记录具体错误，不重复请求模型证明自己是否能控制电脑。
4. 用无账号测试页完成“打开→读取→点击→读取改变后的结果”一次，记录真实结果。工具注册成功与真实点击成功分开报告。
5. TokenBots 浏览器工具启动单独的 Edge 用户目录；它不会继承用户普通浏览器或内嵌浏览器的登录。需要登录时让用户在工具打开的窗口登录，随后读取页面确认。不能声称用户已在另一个窗口登录就等于这里也登录。
6. 每次点击前以当前页面快照为依据，操作后核对结果。Google QR、验证码与身份确认由账号本人完成，不抄取或转移认证信息。提交、支付等沿用本次用户授权边界。
7. 浏览器 MCP 只能操作它的浏览器，不代表鼠标可操作整个桌面。整机能力应核对官方桌面版 Settings → Computer use → Control 和应用授权；Windows 需保持解锁、目标应用可见。不要关闭系统保护或伪造官方登录。
8. 同项目只能由一个任务控制这个浏览器；其他任务继续代码工作。出现 profile in use 时先确认占用任务，不杀用户进程或删登录目录。

官方依据：https://learn.chatgpt.com/docs/computer-use ，浏览器 MCP：https://github.com/microsoft/playwright-mcp 。
