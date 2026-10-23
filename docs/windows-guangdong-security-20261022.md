# 2026-10-22 安装、广东回测与 PHP 安全核对

## 改动与部署
- 网站配置包的 Windows x64 安装器改用已审核、原始签名有效的固定 MSIX；保留 SHA256 和 Authenticode 校验。官方 latest 链接在 10/22 已变化，不再将变化的下载内容与旧固定哈希混用。
- 每把 Key 使用独立 CODEX_HOME 和 Electron user-data-dir。原个人配置不变；网站 wrapper 不再先改默认 .codex。配置目录先设置继承 ACL，再写文件，避免递归目录授权导致文件不可读。
- 动态打包服务、安装脚本和固定下载文件已部署。重新从网站生成的包已核实包含新脚本。
- 同一账户的 Key 在不同电脑上的调用汇总到同一账户；不同账户不合并。只有经 TokenBots 入口的调用会入账，原版快捷方式或旧对话仍可能使用原线路。

## Windows 真实验证
- 在 DESKTOP-QKF9CE4 创建空缓存环境、移除 Node PATH，并设置冲突 CODEX_HOME：约 1 GB 下载、签名/hash、解包与补丁成功，原个人配置哈希未变。
- 后续实际 CLI 验收发现文件 ACL 不可读，已修复并从新配置目录重装；此轮复用刚核验的缓存，未重复下载。
- 新安装内置 CLI + 新专属配置，gpt-6.1-sol/low，返回准确 42，turn.completed，exit 0。input 15173（cached 4096），output 5。
- 网站账户统计由此前101次，加本轮广东6次和 Windows CLI1次，达到108次 / 514102 Token，最新调用 2026-10-23 00:15:14 UTC。
- 4 项 bundle/backend 测试、5 项 native bridge/menu 测试通过。不是另一台物理电脑验收，也未验证 Windows ARM64 新包。

## 广东主动发起的回测
探针在广东发起 HTTPS，收到真实模型答案和完成事件，验证请求出境及响应返回。
| 节点 | 短问答往返 | 结果 |
|---|---:|---|
| 广州电信 AS4134 | 3.566秒 | 正确42、完成事件、TLS通过 |
| 东莞电信 AS4134 | 3.453秒 | 同上 |
| 深圳天威 AS17962 | 3.226秒 | 同上 |
| 广州移动 AS9808 | 3.007秒 | 同上 |
广州电信和移动额外各测一次 SSE，正确输出1至80及END-GD、完成事件，连接保持20秒，均通过。6次模型调用共25776 Token。模型实际生成约3.75/4.02秒，剩余时间是保活，不能称20秒持续生成。公共探针以固定一次性 GET 测试入口触发服务端 Responses POST；没有让探针持有客户 Key，也不等同客户 Windows 任意提问验收。未覆盖广东联通/所有用户网络。

网站首页首轮：广州电信30秒无首字节超时；东莞12.509秒；深圳0.867秒；广州移动2.028秒。广州电信后续两次为0.818/0.820秒、HTTP200。Render 配置为free，症状与冷启动一致，但没有平台日志证明根因；不能承诺首页所有时段畅通。若正式上线要求无休眠，需要选择常驻托管并重新验收。未擅自购买套餐。
临时测试路由已撤回，探针服务已停止。后台13项只读健康检查全部通过。
原理：客户端用普通HTTPS访问公开TokenBots网关，网关调用上游并把流式结果返回同一连接。客户端不需要自行连接上游或建立VPN，但仍取决于当地运营商到我们域名的实际连通性。
证据：reports/guangdong-20261022/（测量ID、原始响应、summary.json、health.json）。

## PHP 安全
- DigitalOcean 公告和 PHP 官方通告确认 CVE-2026-109618 / CVE-2026-109619。PHP 8.3 分支上游修复版为8.3.36。
- TokenBot DO宿主及运行中的gateway/Postgres/Redis容器未发现PHP运行时/进程，网站为Python；未发现这两项PHP漏洞适用的运行组件，不需要安装PHP补丁。
- Solus WordPress站点健康实际显示 PHP8.3.35 / LiteSpeed，低于上游修复版；主机商是否回移补丁未证实。需要Hostinger确认并升级。
- Hostinger未登录；已打开登录页并请求用户登录具备Solus主机权限的账户。现有WordPress权限无法更新服务器PHP，本项尚未修补，不标完成。

- 原生桌面：新快捷方式打开独立的首次引导窗口，完成引导后 Astra/high 对17+25返回42；旧客户端仍单独存在，未复用旧会话。截图见 reports/guangdong-20261022/windows-native-answer.jpg。

下一步：Hostinger登录后更新PHP并验证网站；选择网站常驻托管后再测广东首访。
来源：https://www.digitalocean.com/blog/critical-php-rce-vulnerabilities-patch-now
https://www.php.net/releases/8_3_36.php
https://render.com/docs/free
https://learn.chatgpt.com/docs/enterprise/windows-deployment
