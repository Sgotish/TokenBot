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


## Final acceptance — 2026-10-22

The bounded API observation passed: **97/97** exact answers and completion events, no recorded failed requests. First-to-last request span was 86400.001 seconds; total process duration 86402.085 seconds. Scheduled task exited with code 0 and the isolated configuration hash was unchanged. No extra inference or rerun was needed for this audit.

Latency: median 2.640 s, nearest-lower-rank P95 7.191 s, maximum 30.254 s (minimum 1.690 s). Call gaps were 899.825–900.003 s.

Token usage: 410698 input (393216 cached, 17482 uncached), 485 output; **411183 total**. Cache hits are included in this total, not subtracted. Monetary cost was not inferred.

The dedicated account's live usage endpoint and website both showed **101 requests / 473148 tokens**, including four earlier validation calls outside the 97-call soak. The website displayed the last recorded call at 18:25:37 Toronto and a fresh snapshot. Cloud readiness checks passed 13/13. Browser polling remained active without manually refreshing data.

Raw final status, per-request results, computed acceptance summary, cloud health, account totals and screenshots are saved under `reports/windows-20261021/`. The Google Doc received an appended final result; previous text was preserved. No Guangdong client-network or long-conversation acceptance is claimed by this result. The follow-up is paused after final reporting.
