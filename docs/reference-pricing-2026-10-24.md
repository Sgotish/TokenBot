# Reference pricing (2026-10-24)

The customer-facing target is **0.5 zhe of the reference CNY price**, not a
native multiplier of 0.5. APINebula's CODEX group publishes a 0.39 native
ratio and a 6.6702 CNY/USD reference exchange rate; its displayed discount is
`0.39 / 6.6702 * 10 = 0.5847 zhe` (rounded to 0.58). TokenBot's target is
`6.6702 * 0.05 = 0.33351` as the single native group multiplier. The existing
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
| gpt-6.1-sol | 0.66702 | 3.3351 | 0.033351 | 0.833775 |
| gpt-6-astra | 3.3351 | 16.6755 | 0.33351 | 4.168875 |
| gpt-6-sol | 0.66702 | 3.3351 | 0.066702 | 0.833775 |
| gpt-6-luna | 0.033351 | 0.166755 | 0.0033351 | 0.04168875 |
| gpt-5.6-sol | 1.66755 | 10.0053 | 0.166755 | 2.0844375 |
| gpt-5.6-terra | 1.33404 | 8.00424 | 0.133404 | 1.66755 |
| gpt-5.6-luna | 0.133404 | 0.800424 | 0.0133404 | 0.166755 |

All amounts are CNY per million tokens, with the multiplier applied once.
For 100,000 ordinary input and 300,000 output tokens on gpt-6.1-sol, the
charge is `0.1 * 0.66702 + 0.3 * 3.3351 = CNY 1.067232`.

## Production activation

1. Deploy the backend price projection and website changes. Existing saved
   `private/pricing-policy.json` is deliberately **not** overwritten on deploy.
2. In the administrator's live price editor, load the current version, enter
   native multiplier `0.33351` and all seven base rate rows from
   `tokenbot/pricing_policy.py`, confirm the change and save once. The save
   operation updates the native channel and each active customer's group rate
   under the pricing lock; do not edit the private JSON directly.
3. Read back the admin projection and `GET /api/pricing`. Check the version
   increment, seven models, `reference_discount_zhe=0.5`, and the table above.
   Check a native channel row and an active customer's group rate before
   describing the rate as live. Historical transactions must retain old rates.

References: https://apinebula.ai/zh/pricing ;
https://developers.openai.com/api/docs/pricing
