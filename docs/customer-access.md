# 独立客户接入与交付

2026-10-18：同一个 HTTPS 入口支持独立客户。每个客户有独立外部 Key、三个上游分组 Key、非管理员用户、号池选择文件和用量快照。原搭档 Key 保留。上游账号与订阅窗口仍共享，客户调用记录与选择独立；多发 Key 不会增加上游容量。

## 运营者流程

在已授权服务器上执行，凭据不打印；客户标识使用英文小写与连字符。先核对网关实际看到的桥接来源 IP，本次 Docker 环境为 `172.18.0.1`，其他部署不可照抄。

```bash
cd /opt/tokenbot-pilot
venv/bin/python scripts/provision_cloud_client.py customer-id --label "Customer label" --upstream-cidr 172.18.0.1/32
```

注册表路径在 private/partner.json 的 clients_path。启停无需重启桥接：

```bash
venv/bin/python scripts/set_cloud_client_enabled.py customer-id --disable
venv/bin/python scripts/set_cloud_client_enabled.py customer-id --enable
```

停用拒绝新请求和仍在排队的请求；已执行的请求可完成。Key 更换会使旧浏览器会话失效。配置文件错误时客户访问失败关闭，不回退到其他客户。注册表不可手工合并相同选择文件、快照或上游 Key。

通过现有 SSH 将 private/customers/customer-id.handoff 复制到本地 `.runtime/customers/customer-id.json`（权限 600），再生成私有安装包：

```bash
python scripts/build_native_handoff.py --client-config .runtime/customers/customer-id.json --validated-run https://github.com/Sgotish/TokenBot/actions/runs/39133370992
```

包位于 delivery/，只交给对应客户。包内含 Key，禁止上传公开 GitHub 或共享群。客户之间不要复制已配置好的整个 .codex 目录。无需客户安装服务器；不同电脑各用自己的包。相同电脑重装新客户包会切换本机的接入身份，不支持同时复用同一用户配置作为不同身份。

客户端先检查网络与模型，再备份配置；重装更新 Key 和显示名称，备份名包含毫秒及随机后缀。原生菜单使用同一客户 Key 查询用量、切换号池。

## 验证

- 合成测试：Cookie 与 Bearer 隔离、无效 Bearer 不回退 Cookie、Key 轮换、单客户停用、过期、重复路径/上游 Key 失败关闭。
- 真实云端：tester-a（Plus）和 tester-b（Pro）各正确回答 42，各自仅有自己的 1 条调用记录；A 停用后 401，B 仍 200。测试结束恢复 A，原搭档仍 Pro。
- 首次真实调用因 Key 白名单仅含回环地址而 403；已修正为实际 Docker 来源并复测通过，报告保留失败证据。
- Windows CI 对两个隔离的 CODEX_HOME 跑真实安装脚本与 Key 更新分支，网络响应使用夹具，不宣称是在客户电脑实测。

仍需国内不同设备与运营商的真实桌面任务验收。新增客户沿用两订阅的总容量，不能宣称无限并发或永久不限流。
