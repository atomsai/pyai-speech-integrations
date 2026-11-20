# Hear + Speak conversation demos

These examples keep your language model and use PyAI for speech input/output.
They are PyAI-maintained integrations, not marketplace endorsements.

Use Python 3.12 and a dedicated test key with `hear:stream` and `speak:synthesize`.
Your LLM provider bills separately. Both demos close sessions after 60 seconds by
default; `DEMO_SECONDS` controls this developer test bound. Start on localhost,
not an unauthenticated public interface. Never put keys in a browser or Git.

## Try it live, then build your own

### Add a voice assistant to a website

[Open the managed website widget](https://pyai-voice-demo-wfls74alya-uc.a.run.app/managed-widget). The visitor can open the launcher without a phone number. The test project allows one voice session per UTC day across all visitors. When the visitor starts, microphone audio goes to PyAI.

A coding agent should verify its project with `whoami`, create or reuse a saved agent, and call `draft_website_widget` with the exact HTTPS website origin and both daily session limits. Show the result of `preview_website_widget` to the site owner. After approval, send that revision to `publish_website_widget` and embed the returned snippet. The browser receives a public widget ID. Read the [managed widget guide](https://docs.pyai.com/guides/website-voice-widget) for the full flow.

In the 20 November 2026 test, the public launcher loaded and the service issued a session. The v12 connection closed before speech. This example pins the opt-in v12.1 widget, which includes the browser’s supported connection protocol. The revised connection reached the connected state in a local browser test. A live spoken answer and interruption on this build remain unverified. The [recorded conversation](https://pyai.com/demos/website-enquiry/website-audio.webm) used a separate custom browser implementation.

### Transcribe Hindi-English calls into Latin letters

For a local recording that may be sent privately to PyAI, upload the WAV directly with multipart `POST /v1/transcription/jobs` after verifying the project, budget and retention terms. Set `output_script=latin` for Roman Hinglish. On mono recordings request `diarize=true` for speaker labels when available. For one speaker per stereo channel use `channel=true`. Read `result.words` and `result.segments` for timings. Check names, amounts and speaker turns against the recording. This hosted flow requires cloud processing. [Full Hindi and Hinglish call-transcription recipe and measured results](https://pyai.com/guides/hindi-call-transcription#transcription-results).

### Build with Hear and Speak

[Open the Hear + Speak voice demo](https://pyai-voice-demo-wfls74alya-uc.a.run.app/?source=direct).
Record a question about PyAI, read Hear's transcript, and listen to Speak's reply.
You can also type. Answers are scripted; transcription and speech use real PyAI
APIs. Three free questions, no signup required; daily demo limits apply.

The hosted app is a standalone speech reference, not a hosted LiveKit room or
Pipecat pipeline. [Get a free API key](https://console.pyai.com/playground?signup=1&path=api&utm_source=github&utm_medium=readme&utm_campaign=speech-activation)
to use the integrations below, or sign up directly from the demo.

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
Pipecat adapter 0.1.4 is published on PyPI and initializes explicit framework
settings. These demos install the adapter from this checkout. The pinned demo
framework versions are targets, not a claim of completed live qualification.

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
