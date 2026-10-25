# Give your agents a voice. Keep your stack.

Use PyAI Hear for speech input and Speak for spoken answers in the applications
and voice agents you already build. Keep your LLM, tools, transport and turn policy.

| Your stack | Start here | Available today |
|---|---|---|
| LiveKit Agents, Python | [LiveKit plugin](livekit-plugins-pyai/) | `pip install livekit-plugins-pyai==0.1.2` |
| Pipecat, Python | [Pipecat services](pipecat-pyai/) | `pip install pipecat-pyai==0.1.3` |
| AI SDK 7, Node.js | [Speech and transcription example](ai-sdk/) | Direct PyAI API integration; offline contracts and live Speak → Hear round trip passed |

## Reach people in their language

Hear supports 29 recognition languages with automatic detection. Speak's live
catalog contains 200 stock voices across 17 language groups (checked October 25,
2026). Choose the voice that fits your audience and test your accents, audio
conditions and terminology. See the [language table](https://docs.pyai.com/reference/language-support)
and query `GET /v1/voices` for the current catalog.

## Predictable speech pricing

Hear is $0.001 per audio minute. Synchronous nonempty requests round up to a
started minute per request; empty transcripts are free. Speak is $0.04 per
generated audio minute, metered by output duration. Your LLM, framework,
telephony and hosting costs are separate. [Current pricing](https://pyai.com/pricing).

Customer inputs and outputs are not used for shared/general model training by
default. This is separate from retention; [read the privacy policy](https://pyai.com/legal/privacy).

## Start building

Get a key at [PyAI Console](https://console.pyai.com), select a voice, and follow
the example for your framework. Keep API keys on the server. For complete
managed speech-to-speech conversations, see [PyAI Omni](https://docs.pyai.com/guides/omni-overview).

Maintained by PyAI, a product of SaaS Labs US, Inc. Contact: gaurav@pyai.com.
These are PyAI-maintained integrations; no upstream endorsement or native
Vercel AI Gateway/Hugging Face provider approval is implied.

## Source and verification

The Python directories mirror the already public Apache-2.0 PyPI source releases.
Their archive URLs and verified SHA-256 hashes are in [SOURCE-PROVENANCE.json](SOURCE-PROVENANCE.json).
README language notes have been corrected; Python runtime code is unchanged.
Each package retains its license and release history. The AI SDK example is
Apache-2.0 under the adjacent LICENSE file.

Six AI SDK tests cover the actual SDK interface, request/response contracts and
failure handling using controlled HTTP responses. These are not live acoustic
tests. Existing Python release checks are distinct from a fresh end-to-end
conversation test on a new framework version. We do not claim a latency SLA,
language-wide accuracy score or production capacity from a short smoke test.

On October 25, 2026, the AI SDK helper completed a live round trip with exactly
two requests and no retries: a 2.48-second WAV was transcribed correctly as
“Hello, your voice integration is ready.” Full-response times were 1,954 ms for
Speak and 1,464 ms for Hear. This single English sample verifies integration;
it does not establish first-audio latency, percentiles or capacity.
