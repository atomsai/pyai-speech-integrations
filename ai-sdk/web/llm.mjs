import { createOpenAI } from "@ai-sdk/openai";
import { generateText } from "ai";
// Optional server-only adapter. PYAI remains the speech layer; bring your LLM.
export function createAnswer({
  apiKey = process.env.OPENAI_API_KEY,
  model = process.env.LLM_MODEL,
  fetch: fetcher,
} = {}) {
  if (!apiKey || !model)
    throw new Error("Set OPENAI_API_KEY and LLM_MODEL for LLM mode.");
  const provider = createOpenAI({ apiKey, fetch: fetcher });
  return async (text, { abortSignal }) => {
    const result = await generateText({
      model: provider.chat(model),
      system:
        "You are a concise voice assistant. Answer in at most three short sentences and fewer than 100 words. Do not use markdown. Do not claim to make calls, purchases or take actions.",
      prompt: text,
      maxOutputTokens: 200,
      maxRetries: 0,
      abortSignal,
    });
    return result.text;
  };
}
