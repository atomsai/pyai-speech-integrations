import { writeFile } from 'node:fs/promises';
import { createPyAIAudio } from './audio.mjs';

const pyai = createPyAIAudio();
// One short Speak request and one Hear request. Uses your PyAI quota/credit.
const result = await pyai.speak('Hello. Your voice integration is ready.', {
  abortSignal: AbortSignal.timeout(30_000),
});
await writeFile('reply.wav', result.audio.uint8Array, { flag: 'wx' });
const transcript = await pyai.hear(result.audio.uint8Array, {
  abortSignal: AbortSignal.timeout(30_000),
});
console.log(transcript.text);
