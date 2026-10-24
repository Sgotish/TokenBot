# Reference pricing (2026-10-24)

The customer-facing target is **0.5 zhe of the reference CNY price**, not a
native multiplier of 0.5. APINebula's CODEX group publishes a 0.39 native
ratio and a 6.6702 CNY/USD reference exchange rate; its displayed discount is
`0.39 / 6.6702 * 10 = 0.5847 zhe` (rounded to 0.58). TokenBot's target is
`6.6702 * 0.05 = 0.33351`, but Sub2API persists group rates to four decimals.
The effective native multiplier is `0.3335`, corresponding to about `0.499985`
zhe (shown as 0.5 zhe). The existing
1 CNY = 1 internal credit top-up rule is unchanged.

GPT-6.1 Sol, GPT-6 Astra, GPT-6 Sol and GPT-5.6 Sol use APINebula's
short-context CODEX model rates. The three models not listed there use the
OpenAI Fast reference rates, as
requested. Fast is a **price reference only**; TokenBot currently serves
Standard speed and keeps one rate across context lengths. Cache-write uses the
30-minute/1.25x input reference rate. If the provider's price or FX reference
changes, review these values explicitly rather than silently recalculating
historical bills.

| Model | Input | Output | Cache read | Cache write |
| --- | ---: | ---: | ---: | ---: |
| gpt-6.1-sol | 0.667 | 3.335 | 0.03335 | 0.83375 |
| gpt-6-astra | 3.335 | 16.675 | 0.3335 | 4.16875 |
| gpt-6-sol | 0.667 | 3.335 | 0.0667 | 0.83375 |
| gpt-6-luna | 0.03335 | 0.16675 | 0.003335 | 0.0416875 |
| gpt-5.6-sol | 1.6675 | 10.005 | 0.16675 | 2.084375 |
| gpt-5.6-terra | 1.334 | 8.004 | 0.1334 | 1.6675 |
| gpt-5.6-luna | 0.1334 | 0.8004 | 0.01334 | 0.16675 |

All amounts are CNY per million tokens, with the multiplier applied once.
For 100,000 ordinary input and 300,000 output tokens on gpt-6.1-sol, the
charge is `0.1 * 0.667 + 0.3 * 3.335 = CNY 1.0672`.

## Production activation

On 2026-10-24 production price version 2 completed. An initial `0.33351`
attempt stopped under the pending-price lock when Sub2API read back `0.3335`.
The pending transaction was resumed with the representable `0.3335` rate;
`pricing_pending` is now false. All three active accounts read back `0.3335`
on each assigned group, and `GET /api/pricing` returns version 2 and seven
models. Historical transactions retain old rates. Future edits must use at
most four meaningful decimal places for the native multiplier.

References: https://apinebula.ai/zh/pricing ;
https://developers.openai.com/api/docs/pricing
