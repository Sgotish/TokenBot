# Windows qualification — 2026-10-21

## Verified this session

- Website commit `27b4152` deployed. Billing now says free testing rather than implying an active test. First-snapshot and stale-data states are explicit.
- A fresh QA account's real inference returned 42 with completion. The browser automatically updated requests from 0 to 1 and tokens from 0 to 4240 after the cloud snapshot, without a refresh click.
- Website regression checks: 16 JavaScript and 3 Python tests passed. Cloud health: 13/13.
- Installed the current Windows x64 package in an isolated TokenBots copy and a dedicated QA home. The original personal Codex configuration was preserved. The vendor package signature was valid.
- Added the exact, hash-checked menu adapter for inner app version 26.1016.51333, retaining the earlier adapter. ASAR integrity enforcement remains enabled. ARM64 was not newly tested.
- Deployed the two native installation scripts to the existing cloud service after backing up the originals; a newly downloaded website package matches the updated scripts.
- Windows CLI answered 17+25 with 42 and a completion event. Native desktop with Astra/high also visibly answered 42. Its menu showed Pro 89% / Plus 100%.
- Native component/backend tests: 5 passed. Soak result-validation test: 1 passed. Generated vendor menu passed JavaScript syntax validation.

## Bounded 24-hour observation — running, not yet passed

- Start: 2026-10-21 22:25:35 UTC / 18:25:35 Toronto.
- Planned end: 2026-10-22 22:25:35 UTC / 18:25:35 Toronto.
- Windows scheduled task: `TokenBots-QA-24h-20261021`.
- One short synthetic arithmetic request every 900 seconds, `gpt-6.1-sol` / `low`, at most 97 calls including the endpoint sample.
- Uses the Responses API from Windows to avoid repeatedly sending the CLI system prompt. This is not 24 hours of desktop UI automation. Native and CLI smoke checks are separate evidence.
- First request passed with completion in 1.69 seconds: 4234 input tokens, of which 4096 cached, and 5 output tokens.
- Failure, timeout, sleep/scheduler gap, or a STOP marker ends the run. No automatic retries or parallel test copies. The process temporarily inhibits idle sleep without changing the permanent power plan.
- Reports on Windows: `C:\Users\admin\TokenBots-QA-20261021\reports\soak-24h`. Local evidence: `reports/windows-20261021/` and `reports/workspace-refresh-20261021.png` (ignored artifacts).
- Follow-up checks the final report; no frequent progress messages. Keep Windows powered on and connected.

## Remaining acceptance

At completion, audit duration, every answer/completion, errors, latency and token usage; record the actual outcome in the existing Google Doc and pause the follow-up. This machine's network does not establish Guangdong customer-network acceptance, and a finite test cannot establish permanent fault-free operation.

The existing Google Doc was appended with this session's changes, evidence, unfinished work and next step; export comparison confirmed all prior text was preserved.
