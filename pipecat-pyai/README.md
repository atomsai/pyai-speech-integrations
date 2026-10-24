# pipecat-pyai

[PyAI](https://pyai.com) **Hear** (speech-to-text) and **Speak** (text-to-speech)
services for [Pipecat](https://pipecat.ai), maintained by PyAI.

Use this package when you want to own the Pipecat transport, frame pipeline,
LLM, tools, and turn policy. Use
[PyAI Omni](https://docs.pyai.com/guides/omni-overview) when you want one
managed speech-to-speech agent instead.

```bash
pip install pipecat-pyai==0.1.3
```

Requires Python 3.11 or newer.

## Usage

```python
from pipecat_pyai import PyAISTTService, PyAITTSService

stt = PyAISTTService()             # PyAI Hear (streaming STT)
tts = PyAITTSService(voice="stock_emma_en_gb")  # PyAI Speak (TTS)
```

Set your key once: `export PYAI_API_KEY=pyai_live_...` (or pass `api_key=`). The
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
