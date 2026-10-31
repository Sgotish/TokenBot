# 2026-10-31 官网常驻运行，消除 Render 休眠启动页

## 变更与上线

官网原本经 DigitalOcean 的 Caddy 转发到 Render 免费实例。改 DNS 只能改善入口线路，不能消除 Render 源站休眠。现将相同网站应用常驻运行于已有服务器，Caddy 直接转发到 127.0.0.1:8186，不再请求 Render 网站源站。

- Render Live 页面确认的源代码：sujunming0315/tokenbots-quota，codex/quota-query，771d3c27e331d5c63ae97803670163ca95dc46c2；原部署 dep-dbeg7frncjis73e5c6h0。
- 从该提交 git archive，不部署本地另一个分支或混入未提交文件。原来的 12 项环境变量私密导出并用于同一站点；没有把任何值提交到仓库。
- 原 PostgreSQL、加密密钥、Google 登录、邮件配置和域名保持；没有迁移数据库、改客户余额、充值记录、价格或 Key。原版本启动仅运行既有幂等建表/种子检查。
- 目录 /opt/tokenbot-website/releases/771d3c27e331d5c63ae97803670163ca95dc46c2，current 指向此版本；独立 venv 和无 shell 服务用户 tokenbot-website。环境文件 root:tokenbot-website 0640。
- systemd tokenbot-website.service：开机启动、进程退出自动重启、内存上限 192 MiB、CPU 上限 75%、只读系统目录、仅监听回环。只信任本机 Caddy 的转发头，避免所有访客共用一个限流 IP。
- 现有 API、计费、采集服务路由保持。官网和 www 的 HTTPS 与 DNS 保持，不缓存账户数据。未升级 Render 或购买新实例，不使用定时访问绕过休眠策略。

## 已验证

- 切换前，新进程首页、控制台、文档的 SHA-256 与 Render 一致；价格 JSON 完全一致。
- 既有专用 QA 账户实际密码登录成功。该会话在新进程及 Render 均可读取，确认继续共用原持久会话库。用量、账单和配置 ZIP 下载成功；Google/邮箱登录选项均启用。未重新发送注册邮件或测试 Google 授权全流程。
- 上线后 /、/console、/docs、/healthz、/api/pricing、会话、用量、账单均 HTTP200；用量快照新鲜，价格一致，响应不含 Render 标记；www HTTP301 跳到主站。
- 有限 4 并发、12 次首页请求全部成功，测得约 0.029–0.127 秒。这是本地网络 HTTP 响应，不是全部用户页面渲染时间或容量承诺。
- 广东默认 DNS 三个探针：广州电信 AS4134 1.780秒、广州腾讯云 AS45090 5.079秒、深圳移动 AS56045 2.859秒；/console 全部200、证书验证通过、解析现有服务器IP、无 Render 响应标记。不是所有广东网络或客户 Windows 实机验收。
- 切换前主动结束一次网站主进程，systemd 约20.37秒内自动重启并完成应用初始化，健康接口恢复；不是无中断故障转移。上线后没有额外重启。
- 网站内存当前约78MB、峰值约98MB，服务器约191MiB可用内存；没有重启现有模型服务。systemd 配置验证和 pip check 通过；原后端14项只读健康检查全过。
- 本轮没有模型调用，不消耗客户模型 Token。

证据：网站仓库 reports/website-always-on-20261031/{staging.json,public-cutover.json}；本仓库 reports/website-always-on-20261031/ 与 reports/website-health-20261031.json。私密会话和配置不入报告或开发文档。

## 后续发布（重要）

**官网主站现在由 DigitalOcean 提供。旧 Render Deploy Hook 只更新备用 Render 版本，不会更新主站。** 给搭档的部署交接必须包含这一点。现有授权 SSH 可管理网站服务，无须共享主账号或增加云权限。

1. 在网站仓库确认批准的完整 commit SHA 和目标分支，使用 git archive 导出到新的不可变 releases/<sha> 目录。不要直接覆盖 current 中运行的文件。
2. 新版本 requirements.txt 若与当前不同，先在单独 venv 验证依赖，并准备运行器与依赖一起回退；不要在正在服务的 venv 上直接 pip install。
3. 使用原私密环境配置，在独立回环端口完成新版本的页面、登录、价格、用量、账单和下载预检。不要复制、清空或重建生产数据。
4. 记录旧 current 目标，切换到批准的新版本并重启 tokenbot-website；检查 systemctl ActiveState、/healthz 和公开功能，不能只认构建成功。生产版本切换有短暂服务重启窗口，后续如需无缝发布应使用双进程就绪后切换 Caddy 的流程。
5. 验收失败先将 current 和对应依赖还原，再重启验证。只有站点恢复确认后才宣布上线；每次回填开发计划。

## 回退与边界

本次切换前 Caddy 备份：/etc/caddy/Caddyfile.before-always-on-20261031-143007。回退前先确认 Render 同版本就绪，再恢复这个文件、caddy validate、systemctl reload caddy；这会重新引入 Render 冷启动。不要还原到10/29以前的配置而丢失国内入口修复。

常驻服务不会因为空闲而休眠，正常主域名访问路径已经没有 Render 启动页来源。本轮未进行16分钟无访问的空闲实验，也不把进程重启验证说成永不中断。现有单台1GB服务器仍有容量和单点故障边界；普通网络加载、数据库短暂唤醒或未来发布重启不等同 Render 启动等待页。
