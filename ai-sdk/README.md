# Give your AI SDK app a voice with PyAI

Add voice input and spoken answers while keeping your existing LLM and application.
This server-side example uses AI SDK 7's speech and transcription interfaces with
PyAI's OpenAI-compatible endpoints. It calls PyAI directly with your PyAI key.
AI Gateway provider onboarding is separate; this is not a native Gateway listing.

## Try it live, then build your own

[Open the Hear + Speak voice demo](https://pyai-voice-demo-wfls74alya-uc.a.run.app/?source=ai-sdk).
Record a question about PyAI, read Hear's transcript, and listen to Speak's reply.
You can also type. Answers are scripted; transcription and speech use real PyAI
APIs. Three free questions, no signup required; daily demo limits apply.

The hosted app is a standalone speech reference, not a hosted LiveKit room or
Pipecat pipeline. [Get a free API key](https://console.pyai.com/playground?signup=1&path=api&utm_source=github&utm_medium=readme&utm_campaign=speech-activation)
to use the integrations below, or sign up directly from the demo.

## Run

Use Node.js 22 or newer:

```bash
npm ci
export PYAI_API_KEY=your_server_side_key
npm start
```

The key needs `speak:synthesize` and `hear:transcribe`. The example makes one
short Speak request, saves `reply.wav`, then sends that audio to Hear and prints
the transcript. It uses your PyAI credit or sandbox quota. It refuses to overwrite
an existing `reply.wav`. Keep the key on the server, never in a public environment
variable or browser bundle.

```js
import { createPyAIAudio } from './audio.mjs';

const audio = createPyAIAudio();
const reply = await audio.speak('Your appointment is confirmed.');
const transcript = await audio.hear(reply.audio.uint8Array);
console.log(transcript.text);
```

Choose a Speak voice from `GET https://api.pyai.com/v1/voices`; match the voice to
the language you need. Hear detects the input language automatically. The current
[language table](https://docs.pyai.com/reference/language-support) lists 29 Hear
recognition languages and 17 Speak language groups. The live catalog checked on
October 25, 2026 contained 200 stock Speak voices. Catalog support is not a claim
of equal measured quality for every voice, accent or language.

## Pricing and data

- See the [PyAI pricing page](https://pyai.com/pricing) for current Hear and Speak
  rates and billing details. LLM, framework and hosting costs are separate.
- Customer inputs and outputs are not used for shared/general model training by
  default. No-training is separate from retention; see the
  [privacy policy](https://pyai.com/legal/privacy).

## Verification and limits

`npm test` exercises the actual AI SDK interfaces against controlled HTTP responses:
endpoint, authorization, model, file upload, returned audio/text and no duplicate
submission after errors. It does not call production or establish audio quality.
A bounded live check on October 25, 2026 used this helper for one Speak → Hear
round trip: a 2.48-second WAV (119,084 bytes) was transcribed correctly as
“Hello, your voice integration is ready.” Both requests returned HTTP 200 with
no retries. Complete-response times were 1,954 ms for Speak and 1,464 ms for
Hear. This one English sample is integration evidence, not a first-audio latency,
percentile, multilingual-quality or capacity benchmark.

The example disables automatic retries to avoid an uncertain billed submission
being repeated. Handle errors and retry decisions in your application.

This recipe buffers complete WAV responses and uses synchronous transcription.
It does not expose streaming speech, realtime transcription, cloning, phone calls
or AI Gateway billing. Use the PyAI SDK or the published LiveKit/Pipecat adapters
for streaming voice-agent workflows. No adapter-specific live latency claim is made.
