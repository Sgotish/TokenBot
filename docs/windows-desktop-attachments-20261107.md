# 2026-11-07 Windows desktop, attachment transport and OTA acceptance

Released TokenBots Windows OTA **2026110701**. Public signed feed and update ZIP were fetched after atomic publication and matched local bytes. Website commit: `1af9cb7`. Client implementation: `4d1c670`; final desktop acceptance fixture: `6e03bb9`.

## Changes

- Added local Windows foreground desktop MCP: screenshots/window enumeration, focus, click, Unicode text, keyboard chords and scroll. This operates existing apps/browser windows through Windows UI rather than copying cookies into the independent Playwright profile. Requires an unlocked interactive Windows session and normal OS permissions. This custom adapter is not the official Computer Use plugin and does not establish complete official feature parity.
- Removed the two TokenBots-owned trial workflow skills and zero-retry overrides; customer-owned skills, model/reasoning choice, keys and projects are preserved. Enabled the provider's remote compaction v2 capability on existing profiles.
- Removed the extra bridge rejection of background/service_tier parameters. Upstream capabilities, account entitlements and resource limits still apply.
- Gateway request cap now matches the deployed upstream default of 256 MiB rather than our old 16 MiB. Anonymous disk spooling, incremental zstd decoding and streaming JSON metadata inspection avoid retaining duplicate complete request bodies in memory. Customer content is forwarded intact. This is not an unlimited request guarantee.

## Verification

- [Windows desktop MCP acceptance](https://github.com/Sgotish/TokenBot/actions/runs/42392113920): actual window focus/click, Chinese input, shortcuts, screenshots and native multi-file picker passed. Five synthetic filename fixtures were selected (one DOCX extension, four PNG extensions); this tests file selection, not document parsing or Codex's original attachment error.
- [Native cumulative OTA acceptance](https://github.com/Sgotish/TokenBot/actions/runs/42392039873): 11 updater tests passed. A real reviewed Windows client upgraded, desktop MCP registered, owned trial overrides/skills removed, project sentinel preserved, repeated upgrade idempotent. Actual menu showed latest/version/time, available/download state and offline failure. No model requests were made by these Windows tests.
- [Regression checks](https://github.com/Sgotish/TokenBot/actions/runs/42392113953): passed.
- Two bounded production Responses probes used synthetic images and `gpt-6.1-sol` / low: 20,102,572 bytes plain -> HTTP 200, response.completed, correct answer 4, 11.120 s; same image history with follow-up, 20,102,731 decoded bytes / 15,081,097 zstd wire bytes -> HTTP 200, completed, correct answer 42, 8.369 s. Total 10,967 tokens: 8,192 cached input, 2,765 noncached input, 10 output. No customer request/key was used; no balances or client everyday model settings changed.
- Production gateway hash: `b9b4e9e9eb04369fac8343b7b9a9c0645cb55a9a5d3bb6e73abce0a9e68e2b5b`; service active, NRestarts 0 after update.

## Customer update

Profile menu -> 检查更新 -> 更新. Save work, fully exit, reopen via the original TokenBots shortcut, then start a new local chat to load new tools. Completion is the device showing **current version 2026110701**, latest status and installation time. Publication alone does not prove Leo installed it. Only old clients without that menu need [the one-time repair ZIP](https://tokenbots.top/static/tokenbots-windows-ota.zip).

## Open items

The original “无法开启档案” toast is not reproduced/root-caused. The tested native picker and gateway transport do not prove that toast fixed. Customer device access, a reproducible file/path and client error logs are still needed. The original customer's conversation and Windows installation have not been verified. Finite synthetic tests do not establish permanent zero failures.
