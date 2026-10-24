import { createOpenAI } from '@ai-sdk/openai';
import { generateSpeech, transcribe } from 'ai';

// Server-side only. Direct PyAI billing; this does not route through AI Gateway.
export function createPyAIAudio({ apiKey = process.env.PYAI_API_KEY, fetch: fetcher } = {}) {
  if (!apiKey) throw new Error('Set PYAI_API_KEY on the server.');
  const pyai = createOpenAI({ baseURL: 'https://api.pyai.com/v1', apiKey, fetch: fetcher });
  return {
    speak: (text, { voice = 'stock_emma_en_gb', abortSignal } = {}) => generateSpeech({
      model: pyai.speech('pyai-speak'), text, voice, outputFormat: 'wav',
      maxRetries: 0, abortSignal,
    }),
    hear: (audio, { abortSignal } = {}) => transcribe({
      model: pyai.transcription('pyai-hear'), audio, maxRetries: 0, abortSignal,
    }),
  };
}
