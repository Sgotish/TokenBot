# TokenBot · 号池试点与运营工具

为小范围客户试用准备的独立部署包：使用固定版本 **Sub2API v0.2.16** 管理上游账号、客户 Key、分组与使用记录，附带批处理、缓存用量核算、成本估算和人工验收材料。

本仓库不是旧网站的数据库副本，也不是模型服务本身。真实账号授权、模型权限、容量与价格必须在目标环境验证。初始安装没有客户、上游凭据或调用额度。

## 内容

- `deploy/compose.yaml`：独立 PostgreSQL + Redis + Sub2API；仅监听本机回环地址。
- [两账号云端测试](docs/cloud-test.md)：现有 1 GB 服务器上的免平台计费试点、备份与私有 Windows 交付。
- 搭档用量页 `/portal`：选择自动 / Plus / Pro，查看上游剩余窗口、更新时间和实际调用账号；服务器每分钟主动查询额度。
- [Windows 原生菜单](docs/windows-native-menu.md)：保留官方安装，另建定制测试副本，菜单内显示用量并每 30 秒检查；私有安装包由运营者交付。
- `scripts/local_runtime.py`：macOS ARM 本地启动/停止，不注册开机服务。
- `tokenbot/`：持久化异步任务队列、原生 Batch 提交与状态查询、缓存统计和成本计算。
- [选型与范围](docs/architecture.md)、[部署运维](docs/operations.md)、[客户接入](docs/client-guide.md)、[人工验收](docs/acceptance.md)、[成本规则](docs/costs.md)。
- [验收状态](docs/verification.md)：区分实际已测、未测及阻塞项。
- [订阅接入方案](docs/subscription-pilot.md)：Plus/Pro 授权、分组、容量与计费边界。
- [客户 Token 用量与计价研究方案](docs/customer-token-billing-plan.md)：客户用量展示、模拟计价、账本接入与套餐成本研究；尚未启用正式收费。
- [套餐容量与售价研究](docs/capacity-research.md)：被动采集 Token 与额度历史、按模型组合估算容量、只读研究页与部署脚本；部署后积累实测样本。

## Linux / Docker

只想在 Windows Codex 桌面版测试现有号池的搭档，请看[Windows 测试接入](docs/windows-partner.md)。无需在 Windows 部署下面的服务器组件；专属测试包由运营者私发，仓库不含真实测试 Key。

```bash
python3 scripts/init_env.py --admin-email YOUR_ADMIN_EMAIL
# 如已存在 .env，脚本拒绝覆盖；在本地安全编辑。
docker compose --env-file .env -f deploy/compose.yaml up -d
```

打开 `http://127.0.0.1:8180`，管理员凭据只保存在 `.env`。远程服务器使用 SSH 隧道访问后台。公网试用先完成 HTTPS 和访问限制配置，见运维文档。

## macOS ARM 本地试点

需要 Homebrew 的 `postgresql@16` 和 `redis`；不使用机器现有默认数据库。

```bash
brew install postgresql@16 redis
python3 scripts/install_release.py
python3 scripts/local_runtime.py start
# 管理员信息：.runtime/local.json（勿分享/提交）
python3 scripts/healthcheck.py
# 停止并保留数据：
python3 scripts/local_runtime.py stop
```

安装器核验固定 SHA-256，仅提取发行包中的可执行文件。应用使用 8180，独立 PostgreSQL/Redis 使用 55439/56389，均只监听 127.0.0.1。`.runtime` 含数据库及凭据，必须保密。

管理员首次登录会看到 Sub2API 自身的协议确认页，应由实际运营者阅读后确认。工具不代签、不删除该门槛。

试用配置清单见 `deploy/pilot-settings.json`，在管理后台逐项核对后保存：关闭注册和支付，监控使用 V2 被动模式。尚无上游账号的独立本地实例可执行 `python3 scripts/check_local_access.py`，验证客户权限、余额拦截和空池行为。它创建临时测试对象，最后停用并清除测试余额；已有上游账号时拒绝执行。

## 批处理与核算

无需安装 Python 第三方依赖，仓库根目录执行：

```bash
python3 -m tokenbot.cli --help
python3 -m unittest discover -s tests -v
```

本地异步队列调用普通 Responses 接口，**没有自动获得上游 Batch 折扣**。原生 Batch 是独立选项，仅在对应供应商、模型和接口已确认支持时启用。

## 数据与版本

- 真实密钥、客户资料、会议原文、报价、任务输入输出和运行报告均不提交到公开仓库。
- 模型 ID 从目标实例 `/v1/models` 及实际调用确认；不把工具产品名当成已购买的模型权限。
- 独立测试环境不连接旧生产库；自有子域名 `pilot.tokenbots.top` 指向云端试点，原主站及邮件解析保持不变，不导入旧站管理员会话。
- `upstream.lock.json` 固定依赖版本和来源；未修改或复制上游应用源码。上游项目许可证及界面署名保留，见 [THIRD_PARTY.md](THIRD_PARTY.md)。
