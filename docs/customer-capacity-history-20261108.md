# 2026-11-08 capacity, image listing and history recovery

## Live server and website

The exact reported `Request capacity is busy; retry later` message came from a
bridge-wide guard retaining four requests through upload, queue wait and the
entire response stream. Production had two execution slots and two waiters.
This rejected the fifth request across all customers before model execution.

Execution remains two; the disk-spooled admission budget is twelve, with ten
queue positions and the existing 120-second queue timeout. Execution and retained
body limits are separate. This is burst tolerance, not unlimited upstream capacity
or a promise that every 503 is eliminated. Maximum retained compressed+decoded
bodies remain bounded at 6 GiB on the current 9.3 GiB-free disk.

The workspace now renders the actual image_generation capability beside the seven
text models. The shipped client uses gpt-6.1-sol with the image_generation tool;
unverified standalone image model aliases are not advertised as callable models.

Deployed at 2026-11-08 18:25 UTC. Backup:
`/opt/tokenbot-pilot/backups/capacity-images-20261108-182529`.
Initial restart encountered a configuration-file permission error; restored
root:tokenbot-bridge 0640, restarted and verified authenticated/public behavior.
No customer key, billing ledger, balance or everyday model setting was changed.

Validation: 21 gateway/control tests passed; six simultaneous synthetic requests
queue while only two execute, cancellation is not forwarded and slots recover.
Authenticated public model discovery returned 200 with seven models; image
capability control response returned 200. One bounded real gpt-6.1-sol/low
request returned HTTP 200, correct answer 5, response.completed, 22 uncached input
and 5 output tokens. Website public JS and signed-in console show the image card.

## Native history recovery

The latest previously published OTA was 2026110701. Reviewed desktop code requests
thread lists with useStateDbOnly=true. The native API schema documents that false
scans JSONL rollouts to repair thread metadata. An isolated four-project fixture
reproduced the mechanism: removing one synthetic index row yielded three visible
histories; native scan-and-repair restored four, with all original rollout hashes
unchanged. The new helper uses that API, never direct SQL, in customer profiles.
Direct SQL fault injection exists only in the explicitly synthetic CI fixture.

The startup helper validates the existing per-key profile, is bounded to 20 seconds,
uses no model requests and writes only time/status/counts to a local diagnostic.
It preserves archived status, keys, model/provider settings and rollout files.
A failed scan does not prevent the app from opening. The cumulative installer
backs up and rolls back launcher/helper changes, and covers the first cold launch.

Local native protocol verification passed for four-project recovery and another
fresh process/repeated recovery. Eleven updater/native menu unit tests passed.
Windows acceptance and publication results are recorded below after completion.

## Remaining acceptance boundary

The customer's actual Windows data has not been inspected. Existing test-device
SSH refused the connection. This fixture proves repair of missing index metadata,
not recovery of deleted rollout files, a wrong profile/path, or every cause of an
empty project. Customer restart confirmation is still required; no customer
conversation was deleted, moved, archived or re-created.

## Windows acceptance and publication

Windows run https://github.com/Sgotish/TokenBot/actions/runs/42510745064 passed
at commit 7fcc195. The actual bundled Windows app-server reproduced 4 -> 3 -> 4,
then a fresh process and repeated repair preserved all four histories. The native
menu showed latest, available, staged and offline states; cumulative signed update
was idempotent and preserved a synthetic project sentinel. No inference occurred.

OTA **2026110801** is published. Public feed was cryptographically verified and
matched the tested candidate bytes. Public update ZIP SHA256:
`9fbd99e8cf39f1b5bb2c12c6df0f7a11d39c5af5921932b0182c06c6f27a2411`.
Use the existing native menu: check updates, update, save tasks, fully exit, reopen
via the original shortcut. Verify current version 2026110801 and installation time.
Customer-device receipt and the reported project's actual recovery remain unverified.

During signed-in website QA another capacity issue was observed: three parallel
normal dashboard reads competed for two immediately rejecting control slots.
Control requests now have a bounded 10-second wait (12 waiting requests maximum),
with two executing workers unchanged. Six parallel read regression requests passed;
six live read-only control requests also returned 200. Gateway/control regression
total is now 22 (the additional control test passed along with the five existing
control tests). The API gateway and control-plane fixes are separate.
