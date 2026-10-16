# 管理员订阅链路测试

此集成仅测试 `tokenbots.top` 管理员会话 → 临时任务 → 本机订阅账号 → 网站结果。不会修改客户套餐、GMN 路由、余额或客户 Key；不代表生产网关及自动调度已验收。

## 接入旧站

将 `pilot_bridge.py` 放入网站 `app/`，将 `subscription-test.{html,css,js}` 放入 `app/static/`。在 `create_app` 中创建 FastAPI 实例后调用：

```python
from .pilot_bridge import mount_pilot
mount_pilot(app, settings)
```

环境变量为 `PILOT_WORKER_TOKEN`（至少 40 字符的随机凭据）、`PILOT_ADMIN_USER_ID`（指定管理员 ID）、`PILOT_EXPIRES_AT`（Unix 到期时间）。缺项或到期时接口关闭。页面为 `/admin/subscription-test`，使用原网站会话与 CSRF 验证。生产继续保持单实例单进程；任务队列只在内存，重启会丢失未完成任务，不能自动认定未扣额或安全重试。

本机 `.runtime/site-pilot.json` 仅保存 `worker_token` 和 `expires_at`，权限 0600，然后运行 `scripts/site_pilot_worker.py`。固定允许本机账号 1（Pro）和 2（Plus）、模型 `gpt-6.1-sol`、后台固定简短提示，不接收任意提示词、目标网址或账号 ID。正式使用前核对这两个 ID 仍为预期账号。

该程序只向网站发起 HTTPS 请求，不打开公网监听，不把账号 OAuth 凭据或本机管理员密码发给网站。每次请求仍会消耗订阅用量。已领取任务不会因超时自动重发；本机持久收据防止进程重启后重复执行同一任务。

测试完成后停止本机程序并移除三个网站环境变量。独立测试路由可留在代码中保持关闭，或回滚该提交。
