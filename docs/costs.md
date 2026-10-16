# 成本、缓存与报价

## 每次调用的可核对算法

设 U 为未缓存输入，R 为缓存读取，W 为缓存写入，O 为输出。各价格统一为同一种货币/每百万 Token：

`调用成本 = (U×输入价 + R×缓存读取价 + W×缓存写入价 + O×输出价) ÷ 1,000,000`

OpenAI 兼容接口的输入总数通常已包含缓存量，必须先扣除 R、W 再计算 U。Anthropic 的独立缓存字段按对应协议归一化，避免重复计费。缺少缓存明细时标记“未知”，不伪造零命中或免费调用。图片、音频、搜索工具附加费不在本期文本估算器内。

`客户扣费`和`上游成本`各用独立价格表。若成本和售价以同一模型的同一基准价计费，0.4 → 0.45 的加价系数为 1.125。上游已经扣完的金额只乘 1.125，不再乘 0.45；订阅账号的实际成本不能直接按这个例子推导。

内部计算使用 Decimal；只在报告展示处四舍五入。模型版本、长上下文档位、缓存保存时长、币种及供应商价格表要同时记录。

## 号池月度成本

订阅池需按实际购买成本和实际完成的可用任务算账：

`本期经营结果 = 本期已消费确认收入 − API账单 − 订阅成本 − 服务器 − 维护 − 手续费 − 退款成本`

充值到账额是资金流入，不自动等于利润。不要把未用余额或订阅“潜在无限额度”直接计为收益。计算示例：

```bash
python3 -m tokenbot.cli economics examples/economics.example.json
```

示例单位是 EXAMPLE_UNITS，不是对客户的报价。真实成本表放在 `.runtime/` 或 `private/`。

## 缓存与 Batch

缓存命中率 = 返回的缓存读取 Token ÷ 已有缓存明细的输入 Token。报告同时显示明细覆盖率，避免只统计成功命中的调用。

固定指令、工具定义和资料前缀保持稳定，动态公司资料追加在后面；实际缓存命中、写入成本和不同模型的选项以其上游规则为准。相同提示词不保证命中。缓存不等于缓存最终答案，本工具不跨客户复用模型回复。

本地排队不自动享有供应商折扣；原生 Batch 使用供应商确认的价格表，不把同步、Batch、缓存折扣重复相乘。支持批处理也不表示每个模型都支持。

```bash
python3 -m tokenbot.cli metrics --db .runtime/leads.sqlite > .runtime/metrics.json
python3 -m tokenbot.cli cost .runtime/metrics.json --pricing examples/pricing.example.json
```

以上 price 表只用于验证数学逻辑。未成功、交付状态不明、缺失 usage 或没有对应价格的行不算“零成本”，报告明确排除这些行，须另核对真实账单。

依据：[OpenAI Batch](https://developers.openai.com/api/docs/guides/batch)、[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)，以及固定版本 Sub2API 的 usage 解析实现。具体供应商的购买授权与价格以实际合同/账户为准。
