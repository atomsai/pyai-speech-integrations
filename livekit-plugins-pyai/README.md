# livekit-plugins-pyai

[PyAI](https://pyai.com) **Hear** (speech-to-text) and **Speak** (text-to-speech)
components for [LiveKit Agents](https://docs.livekit.io/agents/), maintained by
PyAI.

Use this package when you want to own the LiveKit room, worker, LLM, tools, and
turn policy. Use [PyAI Omni](https://docs.pyai.com/guides/omni-overview) when
you want one managed speech-to-speech agent instead.

```bash
pip install livekit-plugins-pyai==0.1.2
```

Requires Python 3.10 or newer.

## Replace the speech components

```python
from livekit.agents import AgentSession
from livekit.plugins import pyai

session = AgentSession(
    stt=pyai.STT(),                 # PyAI Hear (streaming STT)
    llm=llm,                                     # keep your existing LLM
    tts=pyai.TTS(voice="stock_emma_en_gb"),      # PyAI Speak (TTS)
    vad=vad,                                     # keep your existing VAD
)
```

Set your key once: `export PYAI_API_KEY=pyai_live_...` (or pass `api_key=`). The
key needs the `hear:stream`, `hear:transcribe`, and `speak:synthesize` scopes.
List voices at `GET https://api.pyai.com/v1/voices`.

See the [integration status and comparison](https://pyai.com/compare/livekit)
for the current public guide link, production notes, and release status. The source
distribution includes `examples/agent.py`; install
`livekit-plugins-pyai[examples]` to run its optional LLM and VAD dependencies.

## STT, `pyai.STT(...)`

| arg | default | notes |
|-----|---------|-------|
| `api_key` | `$PYAI_API_KEY` | opaque PyAI key |
| `base_url` | `https://api.pyai.com` | API base |
| `model` | `pyai-hear` | STT model |
| `language` | omitted (automatic) | Optional supported language code |
| `sample_rate` | `16000` | inbound frames are resampled to this |

Streams audio to the PyAI Hear socket and emits LiveKit `INTERIM_TRANSCRIPT`
(PyAI `partial`/`speech_final`) and `FINAL_TRANSCRIPT` (PyAI corrected `final`).
A batch `recognize()` path uses the sync transcription endpoint.

## TTS, `pyai.TTS(voice=..., ...)`

| arg | default | notes |
|-----|---------|-------|
| `voice` | _(required)_ | a streaming-capable `voice_id` from `GET /v1/voices` |
| `api_key` | `$PYAI_API_KEY` | opaque PyAI key |
| `base_url` | `https://api.pyai.com` | API base |
| `model` | `pyai-speak` | TTS model |
| `sample_rate` | `24000` | output PCM rate |

Requests `response_format: pcm` at the session sample rate and streams the raw
PCM into the agent's audio output as chunks arrive. End-to-end latency also
depends on your network, selected voice, LLM and turn policy.

## Notes

- Billing/limits follow your PyAI key (`hear.minutes`, `speak.minutes`); a
  realtime STT session counts against your key's concurrency.
- Built on the official PyAI Python SDK (`pyai-sdk`).
- Hear supports 29 recognition languages, with automatic detection when
  `language` is omitted. See the [current language table](https://docs.pyai.com/reference/language-support).
- LiveKit Cloud, telephony, your LLM, and worker hosting are separate from PyAI
  Hear and Speak metering.
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
