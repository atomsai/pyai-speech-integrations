# Public speech pilot

`PUBLIC_DEMO=1` enables a no-login product guide using Hear and Speak. It requires
`SESSION_SECRET` (32+ random characters), `DEMO_BUCKET` (private Cloud Storage),
`PYAI_API_KEY`, and `APP_ORIGIN` (the exact HTTPS deployment origin). Optional
`REFERRAL_CODE` is a server-created PyAI campaign code. Never include keys in browser assets.

Use a dedicated runtime identity, with access only to the two demo secrets and
its private bucket. Set bucket lifecycle deletion to 30 days. Deploy one instance,
minimum zero, with a 60-second request timeout. The server uses atomic Cloud Storage
generation preconditions to persist reservations across restarts and revisions.
Storage failures stop new turns. The default allowance is 100 turns/day globally,
three/day per signed visitor cookie, 300 session starts/day, and one active turn
per process. Clearing cookies bypasses the visitor allowance, but not the global
allowance. Configure a separate Hear/Speak-only key with a $10 monthly budget.
The API's budget is a metered admission gate, not a prepaid invoice or exact spend
reservation; retain the independent demo limits. Provider calls are never retried.

Only anonymous events and bounded counters are stored, for 30 days. No recordings,
transcripts, generated speech, email addresses, or API keys are retained by the
app. PyAI service processing/retention policies apply independently.

The signup link carries a signed campaign attribution through the existing PyAI
referral route. Browser events measure clicks and playback starts, not signups or
payments. The private platform referral report counts server-confirmed signups,
first successful usage, and Stripe-settled prepaid top-ups net of recorded refunds
and disputes. Report cash receipts separately from usage revenue and subscriptions.
