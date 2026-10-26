# Voice chatbot reference app

A browser app that records up to 15 seconds, sends audio to Hear, produces an answer,
and plays Speak audio. It also accepts typed questions. The default answer engine is
an explicitly labelled scripted product guide; optional AI SDK LLM mode is available.
No API keys, customer audio or transcripts are written to the event log.

## Run

Requires Node 22+. From `ai-sdk`:

```sh
npm ci --ignore-scripts
cp web/.env.example web/.env
# Edit web/.env: PYAI_API_KEY and a random DEMO_ACCESS_CODE of at least 16 characters.
# Generate your access code with: openssl rand -hex 24
npm run web
```

Open http://localhost:3000 and enter the demo access code. For attribution, use
`/?source=livekit`, `pipecat`, `openclaw`, or `ai-sdk`. The source is an untrusted
campaign label, never an identity or authorization signal.

To use a language model, set `OPENAI_API_KEY` and `LLM_MODEL` on the server. The
adapter in `llm.mjs` can be replaced with another provider. LLM requests have no
automatic retries and share the turn deadline. Conversations are single-turn;
this starter does not retain chat history server-side.

`node web/preview.mjs` runs an **offline UI preview** with a tone and a labelled
canned answer. It is not speech recognition or synthesis evidence.

## Activation tracking

Private `DATA_DIR/events.jsonl` records opaque 30-minute session IDs, source, event,
time and safe numeric/error metadata. It never stores access codes, API keys,
IP addresses, audio or question/reply text. Browser playback and link-click events
are explicitly client-reported. Treat them as diagnostics, not billing evidence.

```sh
npm run activation-report -- /persistent/voice/events.jsonl
```

The report counts unique sessions for session start, recognized speech, generated
answer, speech returned, browser playback, signup intent and errors. Repeated
playback events are deduplicated by session in the report. A new session is not
necessarily a new person. **Signup clicked is not signup completed or payment.**
To measure account activation/revenue, join first successful server-side PyAI usage
and settled billing events to the Console's campaign attribution. That requires a
separate Console/billing integration; this app does not invent those conversions.
Set a log-retention policy on your persistent volume (e.g. 30 days).

## Hosted deployment

Use the included Dockerfile with a persistent volume at `/data`, `DATA_DIR=/data`,
`HOST=0.0.0.0`, and `PUBLIC_ORIGIN=https://your-demo-domain.example` (exact origin).
Terminate TLS before the app; microphone capture requires HTTPS outside localhost.
Set a **dedicated, capped PyAI key** and a separately distributed demo access code
through your host's secret manager. Never deploy with an internal qualification key.
The host must preserve the original browser `Origin` header.

This pilot is intentionally **one process, one replica**. It serializes turns,
limits each session to 10 attempts, and reserves at most 100 attempts per UTC day
before calling any provider. Failed attempts count. Daily reservations survive
restart on persistent storage; session cookies expire on restart. If reservation
storage is unavailable, requests fail before provider usage.
These are attempt limits, not an exact dollar cap. Set provider-side spending limits.
Do not autoscale without replacing the local reservation ledger with a shared atomic
limiter. Add host-level request/login rate limiting before opening registration.

The UI's Stop playback button stops browser audio. This request/response starter
does not claim real-time conversational barge-in; use the framework demos for that.

## Verification

`npm test` exercises the full local HTTP boundary with controlled providers,
auth/origin checks, malformed audio, session/global caps, failure redaction,
timeout cancellation, concurrency and privacy of activation events.
Live qualification results are recorded separately; offline tests do not prove
acoustic quality, microphone permissions, speaker output or provider availability.

On October 26, 2026, the app’s actual HTTP login → synthetic WAV → Hear →
scripted answer → Speak path passed against live PyAI. Hear returned the exact
fixture question and Speak returned 1,071,404 audio bytes; the complete turn
took 4,317 ms in this one sample. No retries were made. This verifies the server
integration, not browser microphone capture, physical playback or LLM quality.
