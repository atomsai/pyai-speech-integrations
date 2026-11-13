# pipecat-pyai

[PyAI](https://pyai.com) **Hear** (speech-to-text) and **Speak** (text-to-speech)
services for [Pipecat](https://pipecat.ai), maintained by PyAI.

Use this package when you want to own the Pipecat transport, frame pipeline,
LLM, tools, and turn policy. Use
[PyAI Omni](https://docs.pyai.com/guides/omni-overview) when you want one
managed speech-to-speech agent instead.

```bash
pip install pipecat-pyai==0.1.4
```

Requires Python 3.11 or newer.

## Usage

```python
from pipecat_pyai import PyAISTTService, PyAITTSService

stt = PyAISTTService()             # PyAI Hear (streaming STT)
tts = PyAITTSService(voice="stock_emma_en_gb")  # PyAI Speak (TTS)
```

Set `PYAI_API_KEY` securely in the server environment (or pass `api_key=`). The
key needs the `hear:stream`, `speak:synthesize` scopes. List voices at
`GET https://api.pyai.com/v1/voices`. See the
[integration status and comparison](https://pyai.com/compare/pipecat) for the
current public guide link, production notes, and release status. The source
distribution also includes `examples/bot.py`.

### `PyAISTTService`

WebSocket streaming STT (subclass of Pipecat's `WebsocketSTTService`). Sends
pipeline audio to the PyAI Hear socket and pushes `InterimTranscriptionFrame`
(PyAI `partial`/`speech_final`) and `TranscriptionFrame` (PyAI corrected
`final`). Args: `api_key`, `base_url`, `model` (`pyai-hear`), `language`,
`sample_rate`. The service sends the canonical commit control when Pipecat's
VAD reports the end of speech and marks the corrected transcript finalized.

### `PyAITTSService`

Chunked TTS (subclass of `TTSService`). Requests `response_format: pcm` at the
pipeline's output sample rate and pushes `TTSAudioRawFrame`s as the audio
streams. Args: `voice` (required), `api_key`, `base_url`, `model` (`pyai-speak`),
`sample_rate`, `aiohttp_session`. Use a streaming-capable voice id.

## Notes

- Billing/limits follow your PyAI key (`hear.minutes`, `speak.minutes`); a
  streaming STT session counts against your key's realtime concurrency.
- Built on the official PyAI Python SDK (`pyai-sdk`).
- Hear supports 29 recognition languages, with automatic detection when
  `language` is omitted. See the [current language table](https://docs.pyai.com/reference/language-support).
- Pipecat Cloud, transports, your LLM, and worker hosting are separate from
  PyAI Hear and Speak metering.
- For a fully managed agent, including turn-taking, reasoning, tools, caller
  continuity when enabled on an Agent profile and a caller key is available,
  and optional telephony, use PyAI Omni instead.
- Licensed under Apache-2.0. The source is included in the wheel and source
  distribution.

Language is detected automatically when `language` is omitted. Pass an explicit
supported language only when you intend to pin recognition.

## 0.1.2 release

Includes the `pyai.v1` WebSocket handshake marker alongside the credential
subprotocol for compatibility with the current Hear endpoint. TTS continues
to reuse an aiohttp session and forward PCM audio as it arrives.

## 0.1.3 release

Automatic transcript finals no longer satisfy a later requested speech commit.
When stopping, the adapter waits for the matching commit completion and keeps
all final transcript text, including a late suffix. Older completion messages
remain compatible; the existing five-second drain timeout is unchanged.

## Maintainer and compatibility

Maintained by PyAI, operated by SaaS Labs US, Inc. Source and issues:
https://github.com/atomsai/pyai-speech-integrations

A representative two-turn media → STT → LLM → TTS flow passed with
Pipecat 1.8.1 on Python 3.12 on November 12, 2026. Recorded audio
was independently transcribed and a human confirmed intelligible playback.
This does not establish microphone-driven interruption or compatibility with
every version allowed by the dependency range.

That audio run used the preceding adapter code. Version 0.1.4 initializes STT
model/language settings; its minimum/latest framework checks passed separately.
Provider options are constructor-only: runtime settings updates are unsupported.

Before running an example, verify the key's project, environment, and billing
limits with `GET https://api.pyai.com/v1/me`. Both test and live keys require
checking their actual limits; an environment label is not a cost cap.

Full WebRTC examples and their separately pinned dependencies are in
[the existing demos](../demos/README.md). Those demo pins are distinct from
the versions used in the November 12 acceptance run; do not infer audio
qualification of the newer pins from that run.

## Run the standalone WebRTC example

From this package directory, use Python 3.12 and install the example's pinned
dependencies in an isolated environment:

```bash
python3.12 -m venv .venv
.venv/bin/pip install "pipecat-pyai==0.1.4" "pipecat-ai[webrtc,runner,openai]==1.14.0" "python-dotenv==1.1.1"
.venv/bin/python examples/bot.py -t webrtc --host 127.0.0.1
```

Set `PYAI_API_KEY` and `OPENAI_API_KEY` securely before starting. Open the runner's
local URL and connect with microphone permission. Use headphones to avoid echo.
The example includes the transport, VAD, LLM, speech services, and disconnect
cleanup. `DEMO_SECONDS` defaults to 60; it limits session duration, not spending.
Running a conversation can incur PyAI and LLM charges.

Non-audio qualification on November 13, 2026: the pinned Pipecat 1.14.0 /
pipecat-pyai 0.1.4 environment passed dependency consistency, CLI imports,
constructor-default checks, and pipeline startup/cancellation on Python 3.12.
The check disabled the STT connection hook and blocked outbound connections;
it generated no audio and does not establish live speech or barge-in behavior.
