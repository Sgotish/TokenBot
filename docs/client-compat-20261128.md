# Client compatibility and website recovery — 2026-11-28

## Deployed core changes

- Preserve registry pool objects for metadata-only edits so active requests are not incorrectly rejected after a Key/status refresh. Disabled credentials still reject immediately.
- Match the current official visible model list: GPT-6.2 Sol, GPT-6.2 Astra, GPT-6.1 Terra and the seven existing models. Preserve the user's model selection and profile history.
- Add the new models to the upstream native account mapping and price policy without changing existing rates or the live multiplier.
- Add owner-bound Key reveal, private package regeneration and explicit restore of an accidentally disabled Key. Authenticated owner and CSRF checks remain mandatory.
- Raise the affected partner account to 30 active / 100 lifetime Keys. Its four disabled Keys remain disabled until the correct device credential is identified.
- Keep original Show Pet, Scheduled and thread goal management. No replacement cloud Bot service or OAuth entitlement is claimed.

## Validation

- Public Responses API: the three newly enabled models each returned their requested model and a completed response with `42`. Total billed test usage: 13,194 tokens. These finite probes do not establish long-running reliability.
- Windows installer CI 46114126668: PowerShell 5.1 paths/interrupted downloads, native model/reasoning/usage menus, original pet and Scheduled entry, and isolated goal create/read/clear passed. Goal tests issued no inference requests.
- Linux CI 46113936767: x64 and ARM64 native windows, simulated conversation and reinstall with retained conversation passed.
- Website: 11 subscription/cleanup tests and 23 workspace refresh tests passed. Private Key actions bind server-side session identity and require CSRF; responses are no-store.
- Windows upgrade CI 46114480166 passed: signed October-to-November upgrade, original auth and history sentinel, rollback binary, idempotence and old shortcut redirection; native model/effort/usage, Show Pet and Scheduled controls, and plugin entry. The first run checked too early during companion renderer setup; bounded UI-state polling retained the same assertions and passed.

## Outage and unfinished acceptance

Neon paused the website account database at 110.04 CU-hours against its 100 CU-hour allowance. No paid plan was authorized or purchased. The public homepage, documentation, console shell and static downloads are served independently; login and account operations still require the paused database. The public console must not be described as restored login merely because its shell returns HTTP 200.

The once-per-minute credential cleanup SQL was replaced with deadline/event scheduling and failure backoff in website commit 77aec42. The old polling was sufficient to keep a scale-to-zero database awake; it does not by itself quantify every CU-hour. Startup retry is five minutes. No complete current website database backup was available for a safe immediate migration.

Leo's actual Windows 11 Key has not been identified. Do not reactivate all revoked Keys or change the device Key/profile to hide a 401. Match its Key name and restore the original only if it was disabled accidentally.

The pinned desktop base remains 26.1111.21308. Model-menu parity and preservation of native controls are verified; complete parity with every current official cloud plugin or future desktop release is not established.
