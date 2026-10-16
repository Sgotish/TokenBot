# 搭档异地测试准备

2026-10-16：普通测试用户 Key 经本机 API 入口、双订阅分组和真实模型返回 HTTP 200，文本 `OK`。随后通过公网 HTTPS 地址发送 zstd 压缩的 Responses 流式请求，返回 HTTP 200、文本 `HTTPS_OK` 和 `response.completed`，共 11 个事件。公网模型列表 200、无 Key 请求 401、管理路径 404。尚未验证搭档异地网络、两个账号自动分配或 Windows 客户端连续工具任务。

## 当前状态

- 本机管理服务仍为 `127.0.0.1:8180`。未开放公网或局域网后台。
- 专属测试分组只绑定已导入的两个 OAuth 订阅；普通测试用户并发 1、每分钟 6 次，独立 Key 有 1 天期限及 1 单位内部测试额度。该额度是平台记账限制，不是购买官方 API 余额，也不表示订阅固定可用 Token 数。
- `.runtime/partner-test.json` 保存测试 Key，`.runtime/partner-provision.json` 保存回退所需的原分组及测试对象 ID。文件不进入 Git，不发送管理员登录信息。
- `tokenbot.partner_gateway` 限制为已验证模型和 `/v1/models`、`/v1/responses`、`/v1/chat/completions`；其中 Chat Completions 尚未实测。拒绝管理路径、任意目标地址、后台任务和超大请求；不自动重试。
- 远程入口使用临时 HTTPS SSH 隧道，仅转发 `127.0.0.1:8181` 的受限 API。网站测试入口继续保持关闭。

## 网络选择

本次搭档使用 Windows Codex 桌面版，不安装 Tailscale。曾配置的 Funnel 443 因公共 DNS 未生效而撤回，保留原有无关的私有 Serve 8443。改用 localhost.run 免费 HTTPS 隧道，TLS 在该服务终止，SSH 加密传输到本机 API 桥。只传专属测试 Key 和测试模型请求，不转发订阅凭据或管理接口。免费域名可能变化或提前中断，不作为生产稳定地址。

## 启动与撤销

额外运行依赖见 `integrations/windows-codex/gateway-requirements.txt`。入口支持 Codex 的 zstd 请求压缩并限制解压后体积。先在现有 Python 环境运行：

```sh
python -m uvicorn tokenbot.partner_gateway:app_factory --factory --host 127.0.0.1 --port 8181 --no-proxy-headers --no-access-log
```

若使用私有直连，只绑定指定私有网卡地址，并将搭档具体 IP 加入私有配置；若使用 HTTPS 隧道，目标为 `127.0.0.1:8181`，保留回环限制。禁止通过伪造转发头放行客户端。入口使用测试 Key 鉴权，隧道开通前需确认访问范围和期限。Mac 休眠或进程退出即停止提供服务。

测试结束停止入口，并在本机后台停用测试 Key 和测试用户。若撤销分组绑定，按私有 provision 记录恢复原分组，不删除订阅账号。不要重复执行准备脚本创建额外测试用户。

本次使用 `scripts/run_partner_gateway.py` 和 `scripts/run_partner_tunnel.py` 托管两个进程，到测试 Key 期限停止。隧道不自动重连；若手动重启造成地址变更，重新运行 `scripts/build_windows_handoff.py` 生成文件，不能转发旧地址。临时地址与 PID 存在 `.runtime/partner-tunnel.json`。可向这两个 runner 的 PID 发送 SIGTERM 结束本次测试；不要全局重置 Tailscale 设置。

Windows 配置模板会先验证模型入口，备份既有 `config.toml`，保留其他设置并切换到专属 Responses provider。配置副本在 `delivery/`，包含短期测试密钥，已忽略且仅本机用户可读。模板使用临时明文 bearer token，测试完恢复备份并停用 Key。只验证了当前本机 Codex CLI 对相关 provider 字段的解析，尚未在 Windows 执行 PowerShell 或验证桌面端完整工具调用；由搭档按交付文件执行人工验收。

真实测试结果保存在被忽略的 `reports/partner-key-smoke.json` 和 `reports/partner-public-smoke.json`。额度、调度和客户端表现须由搭档实际测试后再记录，不能据此宣布可商用。
