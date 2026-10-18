# 实际问答与连续性测试

本工具会真实调用订阅额度，应由已获授权的运营者手动执行。使用合成问题，不发送客户资料。配置只从被忽略的私有文件读取，报告也只保存在本机 `reports/`。

```bash
python scripts/qualify_live_pilot.py --report reports/functional.jsonl
python scripts/qualify_live_pilot.py --report reports/endurance.jsonl --soak-minutes 10
```

功能测试会暂时切换搭档 Key 的 Plus/Pro 号池，结束恢复原选择；测试前应结束正在使用该 Key 的任务。持续测试保留当前选择，先生成 1200 行的较长输出，再每约 30 秒发起一个可自动核对答案的算术问题。失败后停止持续请求并返回非零退出码，不无限重试。

测试内容：
- 两账号各五轮完整历史与随机标记回忆。
- 两账号长回复的结束标记与 Responses `response.completed`。
- 函数调用及 `function_call_output` 回传，校验最终答案。
- 流式中途取消、排队中取消、随后恢复调用。
- 两条运行中的请求加一条排队请求；服务器繁忙与真实上游限流区分。
- 连续调用、首字时间、总时间、文字增量数和文字增量之间的最大间隔。

没有收到 `response.completed` 不能只凭 HTTP 200 算通过。模型暂时不输出文字与网络断流不同，必须同时观察 SSE 结束事件与连接是否异常退出。输出百分比、窗口、调用记录分别核对，不能拿累计 Token 推导订阅剩余量。

国内探针验证采用临时固定问题入口：只允许三次调用，五分钟自动失效；公网探针只获得这个短时、固定用途地址，不获得客户 Key 或管理员凭据。国内节点访问后，云端通过同一认证桥接发起真实 Responses 调用，将文字增量与完成标记返回国内节点。此方法验证真实问答往返，但不等于在国内 Windows Codex 上完成任意任务；后者仍是单独的端到端验收。

参考：[OpenAI 函数调用](https://developers.openai.com/api/docs/guides/function-calling)、[流式响应](https://developers.openai.com/api/docs/guides/streaming-responses)。

Caddy 使用 SSE 自动刷新，不设置负数 `flush_interval`：负数配置会在客户端提前断开时保留后端请求，见 [Caddy Streaming 文档](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#streaming)。应用安全响应头使用纯 ASGI 中间件，避免隐藏队列等待中的断开事件。备份恢复 Caddyfile 时确保 caddy 用户仍有读取权限，再验证 reload 和实际运行配置。
