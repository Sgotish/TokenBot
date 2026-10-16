# 搭档异地测试准备

2026-10-16：普通测试用户 Key 经本机 API 入口、双订阅分组和真实模型返回 HTTP 200，文本 `OK`，收到 `response.completed` 及用量事件。只验证了一次本机 Responses 流式调用，尚未验证搭档异地网络、两个账号自动分配或客户端连续工具任务。

## 当前状态

- 本机管理服务仍为 `127.0.0.1:8180`。未开放公网或局域网后台。
- 专属测试分组只绑定已导入的两个 OAuth 订阅；普通测试用户并发 1、每分钟 6 次，独立 Key 有 1 天期限及 1 单位内部测试额度。该额度是平台记账限制，不是购买官方 API 余额，也不表示订阅固定可用 Token 数。
- `.runtime/partner-test.json` 保存测试 Key，`.runtime/partner-provision.json` 保存回退所需的原分组及测试对象 ID。文件不进入 Git，不发送管理员登录信息。
- `tokenbot.partner_gateway` 限制为已验证模型和 `/v1/models`、`/v1/responses`、`/v1/chat/completions`；其中 Chat Completions 尚未实测。拒绝管理路径、任意目标地址、后台任务和超大请求；不自动重试。
- 远程入口尚未开放，搭档尚未拿到可用地址和 Key。网站测试入口继续保持关闭。

## 网络选择

私有连接可使用 Tailscale；搭档尚未安装。也可选择支持流式响应的 HTTPS 隧道，让搭档只配置 Base URL 和 Key。需要先配置隧道账户/域名及入口权限；不能把 `8180` 管理服务整体发布。Cloudflare 的 Quick Tunnel 不支持 SSE，不用于这次流式验收；命名隧道需另行配置。

## 启动与撤销

额外运行依赖：`fastapi`、`httpx`、`uvicorn`。先在现有 Python 环境运行：

```sh
python -m uvicorn tokenbot.partner_gateway:app_factory --factory --host 127.0.0.1 --port 8181 --no-proxy-headers --no-access-log
```

若使用私有直连，只绑定指定私有网卡地址，并将搭档具体 IP 加入私有配置；若使用 HTTPS 隧道，目标为 `127.0.0.1:8181`，保留回环限制。禁止通过伪造转发头放行客户端。入口使用测试 Key 鉴权，隧道开通前需确认访问范围和期限。Mac 休眠或进程退出即停止提供服务。

测试结束停止入口，并在本机后台停用测试 Key 和测试用户。若撤销分组绑定，按私有 provision 记录恢复原分组，不删除订阅账号。不要重复执行准备脚本创建额外测试用户。

真实测试结果保存在被忽略的 `reports/partner-key-smoke.json`。额度、调度和客户端表现须由搭档实际测试后再记录，不能据此宣布可商用。
