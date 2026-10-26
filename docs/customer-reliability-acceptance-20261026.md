# Customer reliability and acceptance — 2026-10-26

The meeting's immediate deliverable is a stable API for customers developing real
projects and later embedding it into their business software. Agent consulting,
reseller terms, corporate receipts and payment collection are separate future
work; this repair does not implement or promise them.

## What can be promised

Do not promise permanent zero faults or unlimited request/context/subscription
capacity. Promise a defined supported environment, measured acceptance results,
bounded recovery, scoped diagnostics, preservation of customer work, and clear
incident ownership. Never claim a server probe proves the customer's Windows
experience or Guangdong direct/proxy networks.

## This repair

- Earlier 2 MiB request cap increased to 16 MiB with bounded buffering, decompression
  and active-request limits. This is a byte limit, not a model context guarantee.
- Found installation templates explicitly disabled remote compaction. The current
  installed Codex binary accepts `unsupported` or `v2`; the setup bundle now sets
  `capabilities.remote_compaction = "v2"`. Both new and repaired legacy provider
  sections use this value. Daily model/effort choices are preserved by setup.
- The deployed native upstream's legacy unary `/responses/compact` returns 502
  (upstream 404). Do not enable that route and advertise it as working. The actual
  supported workflow is streaming `/v1/responses` with a `compaction_trigger`
  input item and a returned opaque compaction item. Public HTTPS live tests verified
  compaction followed by correct recall of a synthetic project codename.
- Forward the client compaction feature header along with the existing session
  metadata. Never decode, fabricate or silently truncate opaque compaction data.
- Record upstream stream transport failures as `upstream_stream_interrupted`,
  with request ID, model and `not_forwarded=false`. Release capacity on exception
  and cancellation. Do not blindly retry an already-started model/tool execution:
  upstream completion/billing may be ambiguous.
- New website-generated packages include `repair-long-session.cmd`. Windows users
  close TokenBots, use the ORIGINAL Key to download/extract a new package, and run
  that command. It targets only the existing `.tokenbots-native-homes/<key hash>`
  directory, backs up configuration, and reuses the original app shortcut. No
  reinstall, account creation, history migration or key rotation is needed. Missing
  or unexpected configuration aborts. Original Codex users retain a separate path:
  configure their original desktop with the normal setup tool and its rollback.

## Verified and pending

| Customer requirement | Evidence/status |
| --- | --- |
| Long project conversations can compact then continue | Real public API returns compaction item, then answers Cedar42 correctly with completion events. Actual installed macOS Codex app-server also compacts then carries opaque state into the next request against a synthetic endpoint. |
| Failure does not leak a capacity slot or silently replay | Regression covers interrupted upstream stream, cancellation, queue timeout and bounded capacity. These are injected tests, not a sustained production load test. |
| Customer work and credentials stay separate | Existing isolation and configuration-backup tests pass; repair derives the existing dedicated home from that package's Key. No customer data or payment records modified. |
| Delivered package contains the repair | Generated directly with the deployed packaging implementation; ZIP valid, repair entry present, v2 configured; deployed file hashes match. |
| Customer Windows execution | Pending. User explicitly deferred powering on Windows this turn. No claim of Windows PowerShell/runtime acceptance. |
| Guangdong with VPN off AND on | Requires customer-side DNS/TLS, login, streaming question/answer, reconnect and long-session tests in both modes. Prior fixed probes are not a current full-device acceptance. |
| Larger enterprise traffic | Pending capacity/load acceptance and upstream capacity planning. Do not equate subscriber count or added accounts with guaranteed concurrent throughput. |
| Native original app projects | Customer chooses original-app configuration vs isolated copy; migration must be explicit, backed up and separately verified. This turn does not move projects. |

Before broader rollout, record client version, OS, network mode, selected model,
request size, completion/answer, latency, error code/request ID and usage; never
record credentials or customer prompts by default. Test network failure and retry
with synthetic requests; investigate ambiguous completion before retry or charging.
Agree on a numerical availability/latency target only after measuring a meaningful
window and defining scheduled maintenance, customer errors and upstream failures.

## Evidence and deployment

- Backend: 129 tests and 17 subtests pass.
- Cross-platform client: 12 tests pass, including actual installed Codex binary,
  compaction/resume, seven-model selection and config rollback (synthetic endpoint).
- Production changes limited to bridge, packaging code and templates/bundle; no
  pricing, billing database, balance, account, pool or website deployment changes.
- Backup: `/opt/tokenbot-pilot/backups/stability-20261026-131843`.
- Sanitized reports: `reports/stability-20261026/`.
- Official API compaction reference (general semantics):
  https://developers.openai.com/api/docs/guides/compaction
  The deployed Codex v2 wire behavior above is established by actual binary/source
  inspection and live tests, not inferred from the standalone API documentation.
