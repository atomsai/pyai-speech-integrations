import assert from 'node:assert/strict';
import test from 'node:test';
import { createPyAIAudio } from '../audio.mjs';

test('AI SDK sends PyAI model names, auth and audio through the complete speech/transcription interface', async () => {
  const calls = [];
  const audio = new Uint8Array([82, 73, 70, 70, 36, 0, 0, 0, 87, 65, 86, 69]);
  const client = createPyAIAudio({ apiKey: 'contract-test-only', fetch: async (url, options) => {
    calls.push(url);
    assert.equal(new Headers(options.headers).get('authorization'), 'Bearer contract-test-only');
    if (url.endsWith('/audio/speech')) {
      assert.deepEqual(JSON.parse(options.body), {
        model: 'pyai-speak', input: 'Hello.', voice: 'stock_emma_en_gb', response_format: 'wav',
      });
      return new Response(audio, { headers: { 'content-type': 'audio/wav' } });
    }
    assert.equal(url, 'https://api.pyai.com/v1/audio/transcriptions');
    assert.equal(options.body.get('model'), 'pyai-hear');
    assert.deepEqual(new Uint8Array(await options.body.get('file').arrayBuffer()), audio);
    return Response.json({ text: 'Hello.' });
  }});
  const speech = await client.speak('Hello.');
  assert.deepEqual(speech.audio.uint8Array, audio);
  assert.equal(speech.audio.mediaType, 'audio/wav');
  assert.equal((await client.hear(speech.audio.uint8Array)).text, 'Hello.');
  assert.equal(calls.length, 2);
});

for (const status of [401, 402, 429, 503]) {
  test(`Speak ${status} surfaces without duplicate submission`, async () => {
    let calls = 0;
    const client = createPyAIAudio({ apiKey: 'contract-test-only', fetch: async () => {
      calls += 1;
      return Response.json({ error: { message: 'Request rejected', type: 'test_error' } }, { status });
    }});
    await assert.rejects(client.speak('Hello.'));
    assert.equal(calls, 1);
  });
}

test('missing key fails before networking', () => {
  assert.throws(() => createPyAIAudio({ apiKey: '' }), /PYAI_API_KEY/);
});
