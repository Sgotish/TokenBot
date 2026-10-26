# Responses request-size repair — 2026-10-26

The customer-visible `413 Test input exceeds 2 MiB` originated in
`tokenbot/partner_gateway.py`, before model execution. The production source
matched the repository before the change. A 3,145,931-byte synthetic request
reproduced this exact error through public HTTPS.

The bridge now accepts up to 16 MiB both on the wire and after zstd decoding.
Bodies use a bounded buffer instead of repeated concatenation; parsed JSON is
released before queueing. Uploads have a 60-second deadline. A pure ASGI guard
allows at most four buffered API requests across upload, queue and complete
stream lifetime; cancellation releases its slot. The bridge memory limit is
256 MiB. Oversize failures receive a request ID and scoped failure metadata,
without storing prompts, credentials or invented token usage. Limits do not
increase a model's context window.

## Validation

- Full backend suite: 126 passed plus 9 subtests.
- Mock upstream: exact 16 MiB accepted intact in plain and zstd form; one byte
  over rejected before forwarding, including a chunked upload; failure metadata
  is scoped; cancellation/capacity recovery verified.
- Public HTTPS after deployment: plain 3,145,931 bytes returned HTTP 200,
  answer 42 and response.completed in 5.965 seconds.
- Public HTTPS zstd: 266 wire bytes / 3,145,931 decoded bytes returned HTTP 200,
  answer 42 and response.completed in 2.330 seconds.
- Two real requests only, both gpt-6.1-sol/low, using an existing operator test
  credential rather than the customer's credential. Combined usage: 8,468 input
  tokens (8,192 cached; 276 uncached), 10 output tokens. JSON whitespace padding
  exercises transport size without large model input.
- 16 MiB + 1 byte still returns HTTP 413 with request_body_too_large and
  not_forwarded=true in the failure record.
- Service active, no unexpected restarts; observed memory peak 86,417,408 bytes.

Only the bridge source and systemd unit were deployed. Pricing, customer
balances, keys and website deployment were not changed. Backup:
`/opt/tokenbot-pilot/backups/request-size-20261026-125955`.
Deployment SHA256: `83462e3b74ab2ceab0eed673700dc086ff1b1bffa25b5bc844728c1cfed3fe23`.
Sanitized local results are in `reports/request-size-20261026/`.

The customer's original conversation has not been replayed. Retry it unchanged;
if it exceeds the new 16 MiB bound, compact the conversation or reduce attachments.
These are request-size regression checks, not a new duration or concurrency soak.
