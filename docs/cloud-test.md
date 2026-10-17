# 两账号云端测试实例

2026-10-17 将两个已授权的订阅账号迁到现有 DigitalOcean 1 vCPU / 1 GB 实例。未升级套餐；增加 2 GB 磁盘交换空间。此容量只用于两账号的小范围测试，不能据此承诺生产容量。

## 服务与边界

- PostgreSQL、Redis、固定摘要的 Sub2API 通过 Docker Compose 运行，配置重启恢复。
- 使用 `deploy/cloud-test.override.yaml`：`RUN_MODE=simple`，不检查平台余额和消费配额，仍记录请求和 Token 用量。统计金额是软件计价结果，并非订阅供应商真实账单。
- 迁移前的 Key 在云端全部停用；新搭档普通用户仅授权测试组，新 Key 无消费上限、无 5 小时/日/周额度、无自动到期时间。
- 并发上限为 2，属于小服务器容量保护。上游订阅限制、模型权限和可用性仍然有效，不能承诺无限调用。
- `tokenbot-bridge.service` 以独立非 root 用户运行，仅公开模型列表和 Responses 接口；公网必须带搭档 Key，管理接口不暴露。后台仅通过 SSH 转发访问。
- 公开入口使用 Caddy 自动 HTTPS，直接连接云服务器；测试域名使用 sslip.io 公共 DNS，搭档无需安装 Tailscale。Mac 旧服务停止后，云端继续独立运行。云服务器或 DNS 故障仍会中断访问。

## HTTPS 入口

安装 Ubuntu 的 Caddy 软件包，将 `deploy/Caddyfile.cloud-test` 放在 `/etc/caddy/Caddyfile`。在 Caddy systemd drop-in 中设置 `TOKENBOT_PUBLIC_HOST` 和 `TOKENBOT_PUBLIC_IP`，分别为指向服务器的域名和服务器公网接口地址。此测试使用可解析到公网 IPv4 的 sslip.io 域名；无需购买域名，但它仍是外部 DNS 依赖。开放 80/443，Caddy 自动申请与续签证书，并将请求转发至 127.0.0.1:8181。仅代理 API bridge，不能改为直接公开后台 8180。

已停用此次未完成公网解析的 Funnel 入口；现有 Tailscale 远程管理连接保留。

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
