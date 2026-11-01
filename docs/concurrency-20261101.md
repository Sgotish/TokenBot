# Concurrent projects: diagnosis, limits and verification

## Production change, 2026-11-01

The customer's 429s matched the local gateway message `timeout waiting for account
concurrency slot`, each after approximately 30 seconds. The user allowed two
requests while each upstream account allowed only one. This was an operator
capacity mismatch; the evidence did not indicate a Codex client configuration bug.

Both upstream account limits were changed from 1 to 2 through the gateway admin
API. Other account fields were checked unchanged. The bridge remains globally
limited to 2 active requests, with 2 queued requests and a 120-second queue
deadline. The existing customer user limit is 2 (shared across that user's keys).
These are shared server resources, not 2 dedicated upstream slots for every user.

Four bodies at most can remain resident, each with the existing 16 MiB limit.
Startup rejects configurations whose active plus pending counts exceed this
memory budget. Semaphore waiters retain their position across disconnect polls;
cancelled or expired waiters return any concurrently acquired slot. Saturation
still returns a bounded 503 with Retry-After. Upstream quota 429s are not retried
or hidden, and interrupted model streams are never automatically replayed.

Backups were retained in the production private directory before mutation. Roll
back the bridge source/config together from that backup and gracefully restart
the bridge; restore only the saved account concurrency fields through the admin
API if the upstream limit also needs reverting. Never restore balances or
credentials as part of this rollback.

## Codex settings are a different limit

The official subagent documentation exposes
`agents.max_concurrent_threads_per_session`: spawned agent threads per session,
excluding the primary thread. When unset, Codex chooses its default. The examples
use 6 and 8; neither is documented there as a universal account/API request cap.
This setting does not specify how many independent projects a shared upstream
subscription can simultaneously serve. No client settings were changed.

Source checked 2026-11-01:
https://learn.chatgpt.com/docs/agent-configuration/subagents

## Verification

- 43 local tests passed, including 14 billing/pricing subtests. Covered FIFO burst
  handling, queue overflow without model execution, cancellation/disconnect,
  timeout, body limits, broken streams, credential isolation and billing guards.
- Public HTTPS: one operator key, 4 simultaneous submissions, all 4 completed
  with correct synthetic answers. Observed 2 active and 2 pending; queued requests
  waited 3.300 and 3.462 seconds. Same Plus account reached 2 concurrent requests.
- Exact Pro gateway path: 2 simultaneous calls through the operator Pro pool key;
  both completed correctly and the Pro account reached 2 concurrent requests.
  This second check bypassed the public bridge and did not change its selection.
- All 6 calls used gpt-6.1-sol/low. Input: 25,404 tokens including 24,576 cached;
  uncached input: 828; output: 30. Elapsed per call: 1.732–5.595 seconds. No retries.
  Customer keys, projects, balances and pricing were not used or changed.
- Readiness: 15/16 checks passed. Log ingestion retained a cumulative write failure
  count of 1, with queue depth 0, dropped count 0 and empty current error. A second
  read showed no increase. This remains a warning, not a clean health pass.
- Bridge active, zero restarts after deployment; memory peak approximately 49 MiB
  for these small probes. This is not a long-context memory load test.

Sanitized evidence is in ignored local `reports/concurrency-fix-20261101/`.
No Windows desktop or Guangdong end-to-end session was executed in this pass.
Future capacity increases require independent active/queued/body-memory and
upstream-account checks; a larger client agent count alone is not validation.
