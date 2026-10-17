# 两账号云端测试实例

2026-10-17 将两个已授权的订阅账号迁到现有 DigitalOcean 1 vCPU / 1 GB 实例。未升级套餐；增加 2 GB 磁盘交换空间。此容量只用于两账号的小范围测试，不能据此承诺生产容量。

## 服务与边界

- PostgreSQL、Redis、固定摘要的 Sub2API 通过 Docker Compose 运行，配置重启恢复。
- 使用 `deploy/cloud-test.override.yaml`：`RUN_MODE=standard` 保持分组隔离。三个专属测试组的计费倍率为零，搭档用户保留 1 单位的内部准入标记余额；真实调用扣费为零，余额不消耗。它不是给搭档设置的消费限额。统计原价不是订阅供应商真实账单。
- 迁移前的 Key 在云端全部停用；新搭档普通用户仅授权测试组，新 Key 无消费上限、无 5 小时/日/周额度、无自动到期时间。
- 并发上限为 2，属于小服务器容量保护。上游订阅限制、模型权限和可用性仍然有效，不能承诺无限调用。
- `tokenbot-bridge.service` 以独立非 root 用户运行，公开模型接口和受保护的搭档用量页；API 必须带搭档 Key，用量页使用同一 Key 换取安全会话，管理接口不暴露。后台仅通过 SSH 转发访问。
- 公开入口使用 Caddy 自动 HTTPS，直接连接云服务器；测试域名使用 sslip.io 公共 DNS，搭档无需安装 Tailscale。Mac 旧服务停止后，云端继续独立运行。云服务器或 DNS 故障仍会中断访问。

## HTTPS 入口

安装 Ubuntu 的 Caddy 软件包，将 `deploy/Caddyfile.cloud-test` 放在 `/etc/caddy/Caddyfile`。在 Caddy systemd drop-in 中设置 `TOKENBOT_PUBLIC_HOST` 和 `TOKENBOT_PUBLIC_IP`，分别为指向服务器的域名和服务器公网接口地址。此测试使用可解析到公网 IPv4 的 sslip.io 域名；无需购买域名，但它仍是外部 DNS 依赖。开放 80/443，Caddy 自动申请与续签证书，并将请求转发至 127.0.0.1:8181。仅代理 API bridge，不能改为直接公开后台 8180。

已停用此次未完成公网解析的 Funnel 入口；现有 Tailscale 远程管理连接保留。

## Plus / Pro 选择与用量

访问 HTTPS 入口的 `/portal`，或使用私有 Windows 包中的 `open-usage.cmd`。Key 不写进网址，不保存到浏览器本地存储。登录后查看订阅窗口剩余百分比、重置时间、快照时间、累计 Token 和实际调用账号。

- 自动组只关联两个测试账号；Plus 专属只关联 Plus，Pro 专属只关联 Pro，专属组不设置回退。每个组使用独立内部 Key，外部搭档 Key 保持不变。
- 选择作用于该搭档 Key 的全部后续请求，保存在 `/var/lib/tokenbot-bridge/selection.json`。正在调用时拒绝切换；切换后在 Codex 新建对话，避免跨账号沿用上游会话。
- `tokenbot-usage.timer` 每分钟调用本机后台读取已有响应头和日志，导出脱敏快照；不定时发送收费模型探测。网页每 30 秒刷新。缺失或已结束窗口显示未知，超过 15 分钟的上游快照标为历史数据。
- 当前 Pro 上游仅返回周窗口，不能据此编造 5 小时额度。百分比由上游返回的已用比例计算，可能经过上游取整。
- 这是配套网页，未改动 Codex 官方原生头像菜单；当前检查的客户端没有供此第三方提供商接入该菜单的接口。Windows 提供独立快捷入口。

固定版本的重要兼容事项：`simple` 模式的调度会忽略分组，不能用于专属号池。本版管理员 API 拒绝零倍率，但结算支持零倍率。因此在备份后运行 `deploy/free-test-pools.sql`（传入三个已核对的组 ID），再重启 gateway 使配置缓存重新加载。保持准入余额为正、禁用 Key 消费额度和到期时间。**不要通过后台把倍率改回正数**；升级 Sub2API 前必须重新验证路由隔离、扣费为零和余额不变。

```bash
docker exec -i tokenbot-pilot-postgres-1 psql -U tokenbot -d tokenbot \
  -v plus_group_id=4 -v pro_group_id=5 -v auto_group_id=6 < deploy/free-test-pools.sql
docker restart tokenbot-pilot-gateway-1
```

快照采集器私有配置 `private/collector.json` 包含 `admin`、`partner` 登录对象、`accounts`/`groups` 的 ID 到标签映射，以及 `snapshot_path`。此文件 root:root 0600；桥接私有配置增加 `public_origin`、`selection_path`、`snapshot_path` 和 `pools`（auto/plus/pro 的内部 Key、标签及组 ID），root:tokenbot-bridge 0640。内部 Key 仅允许本机桥接来源 IP。

安装 `deploy/tokenbot-usage.service` 和 `.timer` 到 systemd，建立 root:tokenbot-bridge 0750 的 `/var/lib/tokenbot-status`，然后 `systemctl enable --now tokenbot-usage.timer`。快照只含展示字段，root:tokenbot-bridge 0640；Web 进程无法读取采集器管理员密码。备份时连同选择状态和私有配置一起保存。

## 启停与备份

部署根目录 `/opt/tokenbot-pilot`。私有 `cloud.env` 与 `private/partner.json` 不进入 Git。

```bash
cd /opt/tokenbot-pilot
docker compose --env-file cloud.env -f compose.yaml -f cloud-test.override.yaml up -d
docker compose --env-file cloud.env -f compose.yaml -f cloud-test.override.yaml ps
systemctl status tokenbot-bridge --no-pager
systemctl status caddy --no-pager
```

数据库备份包含订阅授权，必须按密钥管理，切勿公开上传：

```bash
cd /opt/tokenbot-pilot
umask 077
mkdir -p backups
docker compose --env-file cloud.env -f compose.yaml -f cloud-test.override.yaml exec -T postgres pg_dump -U tokenbot -d tokenbot -Fc > "backups/tokenbot-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

首次迁移前已保留停写后的本地数据库快照。不要同时启动本机和云端的同一份 OAuth 账号副本；云端运行后可能更新授权，回迁应先停写并重新导出云端数据库，不能直接用旧快照覆盖新授权。

停止云端入口：停止本实例专用的 `caddy`，再停止 `tokenbot-bridge` 和对应 Compose 项目。数据卷保留；不要执行 `down -v`。

## 搭档交付与验证

运营者核实公网 DNS、TLS、鉴权和真实调用后，将实际地址及验证状态写入被忽略的 `.runtime/cloud-deployment.json`，执行 `scripts/build_cloud_handoff.py`。私发生成的 ZIP；公开仓库只有无密钥模板。

已分别测试两个上游账号，并用搭档 Key 验证流式工具调用及工具结果回传。自动化测试覆盖鉴权、过期检查和公网管理接口隔离。Windows 桌面端仍需搭档按 [接入说明](windows-partner.md) 完成实际验收；服务端成功不等于 Windows 界面已验收。

2026-10-17 专属路由验收：Plus → 账号 2，Pro → 账号 1；两次流式请求均完成，实际平台扣费均为 0，准入余额保持 1。重启桥接后 Pro 选择仍保留，验收后恢复自动。保留早期简易模式的错误路由记录供审计；它不代表修复后的行为。新增页面的登录、切换、真实用量和调用记录已在 Chrome 验证；Windows 快捷脚本仍需搭档在 Windows 执行确认。
