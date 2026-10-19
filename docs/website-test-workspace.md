# Website test workspace (2026-10-19)

The public entry is https://tokenbots.top/console. Existing email registration,
Google sign-in and password sessions authorize the test workspace. No prices or
payment deductions are enabled for subscription test keys.

## Customer flow

1. Sign in, create a named API Key, and save its one-time display.
2. Download the personal ZIP. It contains a credential: do not redistribute it.
3. Windows desktop: fully extract, close Codex, run `install-native.cmd`, then use
   the TokenBots Codex shortcut. The original application remains available.
4. Mac desktop: install Node 20+, close Codex, run `setup-desktop.command`.
5. CLI on Windows/Mac/Linux: install Node 20+ and official Codex CLI, run the
   appropriate `setup-cli` script, then `start-cli.cmd` or `sh start-cli.command`.
   The launcher selects the isolated `~/.tokenbots-codex` directory; plain `codex`
   continues to use the original configuration. Configure WSL inside WSL.
6. Select a model and supported effort in Codex. Raw Responses requests specify
   a model. The seven discovered models share the same API credential.

Cross-platform rollback: `node tokenbots.cjs rollback --target cli` (or desktop).
When using a custom directory also supply `--home`. Mac/Linux packages configure
connectivity; they do not install the Windows-only native menu modification.

## Deployment and security

The website is the existing Render service backed by the existing database.
Inference goes directly to `https://pilot.tokenbots.top/v1` on DigitalOcean.
Render free-tier wake-up delays can affect website login and downloads, but are
not on the inference request path. No hosting plan was upgraded.

`tokenbot-site-control.service` runs the FastAPI factory
`tokenbot.site_control:app_factory` on loopback port 8184. Caddy routes only
`/internal/site/*` there; all other pilot requests continue to port 8181.
The control API requires a server-only secret, derived from the existing website
encryption key plus the domain-separation suffix `:subscription-control:v1`
using SHA-256. Store the resulting value in the cloud's private
`site-control.secret`, root-owned mode 0600. Never put it in browser code, URLs,
reports or Git. Changing that encryption key requires coordinated secret rotation.

Allowed operations are fixed: status, create/revoke key, personal package,
admin summary and pause/resume customer. Website sessions and CSRF determine
user identity. Cloud user IDs are strictly validated; subprocess provisioning
has fixed arguments. Existing provisioning and registry locks are shared.
Keys are independent hashed aliases of a per-user pool identity. Revocation
rejects subsequent requests and queued requests when they acquire capacity;
an already streaming response may finish. Website account disable also pauses
cloud access. Existing partner/tester keys are preserved.

The service uses NoNewPrivileges, PrivateTmp, ProtectHome and ProtectSystem=strict,
with writable paths restricted to its private state, bridge state and quota
snapshots. It listens only on loopback. Authentication and body-size limits
apply even though Caddy exposes the authenticated route publicly.

Packaging requires the built `integrations/codex-client/dist/tokenbots.cjs`,
smol-toml license and Windows native-menu scripts. Build with the existing npm
lockfile before deploying these assets. Keep code and assets synchronized.

This small pilot currently permits 20 website customer identities and 10 active
keys per customer (30 historical keys). These are capacity guards, not billing
limits. The pool's existing concurrency limits still apply. Customer Token usage
is isolated; subscription capacity is shared. Unknown quota windows display
unknown, not 100% or unlimited. The UI polls every 30 seconds; collection runs
approximately each minute. Admins can pause website test customers and use the
legacy administration page for existing account management.

## Verification and rollback

2026-10-19: 260 website tests and 62 pool tests passed; CI passed. Two isolated
cloud customers each completed a real gpt-6.1-sol/low streaming answer in about
1.7/2.2 seconds. Each recorded one request and 4,239 tokens. Key creation,
idempotency, personal ZIP scope, cross-user rejection, per-key revocation and
remaining-key validity were checked. The downloaded CLI bundle configured and
rolled back an isolated Mac directory. Existing cloud readiness checks passed.
These tests do not prove every desktop build, mainland network, or indefinite
reliability. Mobile viewport automation did not apply in this browser session;
mobile layout still needs real-device verification.

Cloud pre-change backup: `/root/tokenbot-site-backup-20261019/` (contains secrets,
keep private). Do not restore an old registry over new customers casually:
first stop provisioning and reconcile entries. Website rollback can use the
previous Render deployment or set SUBSCRIPTION_TEST_MODE=false. Keep the cloud
bridge running so existing API customers are not disrupted by a website rollback.
