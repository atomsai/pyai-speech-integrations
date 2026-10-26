# Hear + Speak conversation demos

These examples keep your language model and use PyAI for speech input/output.
They are PyAI-maintained integrations, not marketplace endorsements.

Use Python 3.12 and a dedicated test key with `hear:stream` and `speak:write`.
Your LLM provider bills separately. Both demos close sessions after 60 seconds by
default; `DEMO_SECONDS` controls this developer test bound. Start on localhost,
not an unauthenticated public interface. Never put keys in a browser or Git.

## LiveKit: microphone and speakers, no LiveKit cloud account required

From `demos`:

```sh
python3.12 -m venv .venv-livekit
.venv-livekit/bin/pip install -r requirements-livekit.txt
export PYAI_API_KEY=... OPENAI_API_KEY=...
export PYAI_DEMO_EVENTS=./livekit-events.jsonl
.venv-livekit/bin/python livekit_agent.py download-files
.venv-livekit/bin/python livekit_agent.py console
```

For a room-based app, additionally configure `LIVEKIT_URL`, `LIVEKIT_API_KEY` and
`LIVEKIT_API_SECRET`, then run `livekit_agent.py dev` and connect your LiveKit client.
Use headphones to avoid echo. Console mode exercises local audio devices;
room mode exercises the WebRTC transport. They are different evidence.

## Pipecat: browser WebRTC, transport included

```sh
python3.12 -m venv .venv-pipecat
.venv-pipecat/bin/pip install -r requirements-pipecat.txt
export PYAI_API_KEY=... OPENAI_API_KEY=...
export PYAI_DEMO_EVENTS=./pipecat-events.jsonl
.venv-pipecat/bin/python pipecat_bot.py -t webrtc --host 127.0.0.1
```

Open the local URL printed by the runner, connect and allow microphone access.
The example supplies SmallWebRTCTransport, Silero VAD, the LLM context aggregators,
a greeting and disconnect cleanup. It rejects non-WebRTC transports.

Pinned qualification targets: LiveKit Agents/plugins **1.8.9**, Pipecat **1.14.0**.
The local Pipecat 0.1.4 candidate initializes explicit framework settings.
It is installed from this checkout; PyPI 0.1.3 remains the published release.

## Repeatable 45-second acceptance script

1. Connect; confirm a greeting is audible.
2. Say “My project is a voice guide for a museum. Suggest a short welcome.”
3. Confirm the answer addresses a museum and is audible.
4. While a longer answer is playing, say “Stop. Make it one sentence.”
5. Confirm old audio stops, the new utterance is recognized and the shorter reply
   plays without old audio returning.
6. Disconnect. Confirm no new requests/audio and a session-closed event.

Retain a consented synthetic-input recording and event timestamps. Report physical
speaker playback, transport cancellation and live provider calls separately from
controlled-provider tests. A lifecycle event alone does not prove audible barge-in.

Optional event logs contain only random session IDs, source, time and first
occurrence of each lifecycle event. They do not contain transcripts or audio.
They are activation diagnostics, not billable-usage or payment records.

Run `python demos/pipecat_pipeline_check.py` from the repository root for a
controlled-provider pipeline check. It sends audio through the real framework
and injects an interruption; no paid provider requests or speaker output occur.

## Qualification on October 26, 2026

LiveKit’s actual Hear/Speak adapters recognized the synthetic question and returned
161,760 reply-audio bytes. Pipecat’s real PipelineWorker recognized the exact
question, delivered audio and propagated an injected interruption to its sink.
The first Pipecat harness had bypassed framework startup; the corrected pipeline
passed with an additional explicitly authorized streaming session.

These probes used a deterministic reply, not a paid LLM. The demo entrypoints and
telemetry passed offline startup checks. Physical microphone/speaker playback,
WebRTC room conversations and microphone-driven barge-in remain manual checks
using the acceptance script above; they are not established by these probes.
