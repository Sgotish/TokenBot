# 客户试用接入

## 管理员先做

1. 登录独立测试后台，阅读并确认软件的运营承诺。
2. 系统设置中配置 TokenBot 试用品牌，关闭公开注册；不要删除开源署名。
3. 添加已获授权的上游账号。OAuth 由账号持有人在后台完成；API Key 从本地安全配置输入，勿发群聊。不要直接复制旧站生产凭据。
4. 创建试用分组，限制实际可用模型；分组名称和完整模型 ID 分开显示。账本倍率以确认价格表设置，不能沿用不明来源的 0.45 等参数。
5. 创建普通 `user` 客户，设置小额试用额度、有效期、并发及可访问分组；管理员保持独立账户。
6. 创建客户专用 Key，先列模型并做一次小额测试，再交给客户。客户端只收到对外地址与自己的 Key。

## 客户端

当前云端试用入口为 `https://pilot.tokenbots.top/v1`。Mac / Windows / Linux 的 Codex 桌面版与 CLI 配置、用量查询、更新与回退见 [跨平台接入](cross-platform.md)。以下本机地址仅供本机开发测试。

本机测试：`http://127.0.0.1:8180/v1`。此地址只供开发机自己用，不能发送给远程客户。

在现有 Agent 的模型提供商设置中填写：

- Base URL：管理员提供的试用地址（通常含 `/v1`）。
- API Key：该客户自己的 Key。
- Model：经 `/v1/models` 和实际调用确认的完整模型 ID。
- 接口：本期先验证 Responses。CC / Messages 工具需对应平台分组和协议配置后单独验收。

先不要覆盖全局客户端设置，使用一个独立试用项目保存原配置，方便回退。

```bash
# 在本地设置 TOKENBOT_BASE_URL、TOKENBOT_API_KEY；不要把真实 Key 放进代码仓库。
python3 -m tokenbot.cli models
```

## 外贸线索批处理

`examples/leads.jsonl` 是两条虚构公司描述。先替换模型占位符；每条输入自包含，不含客户真实联系人。模板只分类和整理事实，不自动抓取网站、不发送开发信。

```bash
python3 -m tokenbot.cli enqueue examples/leads.jsonl --db .runtime/leads.sqlite
python3 -m tokenbot.cli work --db .runtime/leads.sqlite --limit 2
python3 -m tokenbot.cli metrics --db .runtime/leads.sqlite
python3 -m tokenbot.cli results --db .runtime/leads.sqlite --out .runtime/results.json
```

后台运行可用终端任务管理器启动 `work`；本期 CLI 是单进程串行消费，任务可跨进程重启保留。每次按 `--limit` 最多处理指定数量的已到期任务后退出，429 等待到期后再运行，不在后台无限请求。

重复导入相同 custom_id 和内容不会新增任务；同 ID 改内容会报错。换端点或客户 Key 要使用新数据库。崩溃遗留 `running` 可用 `recover --db ... --older-than 900` 标记待核对，不能自动重放成新扣费。

队列数据库和 results 含业务输入/输出，限定文件权限并放在忽略目录；只导出无正文的 metrics 进行技术排查。人工确定不再需要后按内部数据保留约定清理。

## 上游原生 Batch（可选）

只有供应商明确支持 `/files` + `/batches` 且该模型获授权后才使用：

```bash
python3 -m tokenbot.cli provider-batch-submit examples/leads.jsonl --receipt .runtime/native-receipt.json --enabled
python3 -m tokenbot.cli provider-batch-status batch_REPLACE_WITH_RETURNED_ID
```

原生 Batch 每份文件仅允许同一模型。提交前创建回执，网络失败不自动重试；先用供应商后台检查是否已接受，避免重复计费。完成后用 `provider-batch-results file_RETURNED_ID --out .runtime/native-results.jsonl` 下载结果（失败项的 error_file_id 也要下载核对）。如需取消，用 `provider-batch-cancel batch_RETURNED_ID --confirm`；已完成的工作仍可能计费。

## 演示录屏顺序

展示普通客户登录 → 创建/查看专用 Key（遮挡值）→ 模型 ID → 一条合成线索调用 → 后台 Token、缓存和费用 → 导出结果 → 说明异常反馈方式。正式录屏须在实际账号导入并验收之后进行。
