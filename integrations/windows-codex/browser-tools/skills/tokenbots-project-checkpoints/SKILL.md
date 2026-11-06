---
name: tokenbots-project-checkpoints
description: Advance an implementation through explicit acceptance checkpoints without repeated unchanged tests or skipping unfinished dependencies. Use for multi-step project development, stalled verification loops, resuming a task, and SaleSmartly staged acceptance.
---

# 按证据推进项目

优先读取项目已有任务记录、AGENTS.md 和当前改动；没有记录时在项目中建立 `TASK_STATUS.md`。不把新规则覆盖到用户的 AGENTS.md，也不扩大用户授权范围。

记录只需包含：目标、当前阶段、每项状态、依赖、验收条件、最近证据路径/提交/时间、已知阻塞、下一步。状态用 TODO / IN_PROGRESS / VERIFIED / BLOCKED。每条 VERIFIED 必须有对应范围的真实证据，代码存在或检查启动不算完成。

- 先定义本步可观察的验收条件，再实现最小必要改动。测通过后记录证据并进入下一个可执行任务，不反复跑同一测试来“确认一次”。
- 只有新改动、失败或未解决风险才扩大/重跑测试。外部等待有明确超时，网络失败只有限重试；同因重复两次后先调查原因和改变方案，不继续盲试。
- 未完成的前置条件不能标完成后跳过。标明受阻的依赖链，继续与其无关且已授权的工作。不要因缺一个账号就停掉全部开发。
- 重启/上下文恢复时，读取记录和文件改动，复用仍有效证据；仅重验有变化的部分。
- 代码测试、模拟接口、真实 API、Windows UI、客户设备和生产交付分别记录。不能从其中一项推导其他项已通过。
- 不确定外部操作是否成功时先核对已有结果；涉及发消息、下单、扣款、部署等不能盲重放。

SaleSmartly V3 项目额外要求：把 MOCK_PASS / SHADOW_PASS / LIVE_TEST_PASS / PRODUCTION_READY 分开；M0 真实接口能力和供应来源先确认，不能拿假 webhook 数据证明实际平台支持。HUMAN_OWNED/DNC、幂等、租约过期、人工接管和恢复后不得重复联系必须有针对性验收。未获实施授权时只审规格，不擅自启动整套项目。

回复只报告本次完成内容、验证范围、未完成和下一步；不要保证永远无错误。
