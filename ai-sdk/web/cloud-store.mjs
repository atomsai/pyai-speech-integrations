// Private Cloud Storage ledger. Generation preconditions keep caps atomic across
// process restarts, revisions and overlapping instances. No speech is retried.
import { randomUUID } from 'node:crypto';

export function createCloudStore({ bucket, fetch: request = fetch, token } = {}) {
  if (!/^[a-z0-9][a-z0-9._-]{2,220}$/.test(bucket || '')) throw new Error('Invalid demo bucket');
  let credential, expires = 0;
  async function accessToken() {
    if (token) return token();
    if (Date.now() < expires) return credential;
    const r = await request('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', {
      headers: { 'Metadata-Flavor': 'Google' }, signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) throw new Error('Storage identity unavailable');
    const d = await r.json(); credential = d.access_token;
    expires = Date.now() + Math.max(0, d.expires_in - 60) * 1000;
    return credential;
  }
  async function call(url, options = {}) {
    return request(url, { ...options, headers: { ...options.headers, Authorization: `Bearer ${await accessToken()}` }, signal: AbortSignal.timeout(5000) });
  }
  async function read(name) {
    const r = await call(`https://storage.googleapis.com/storage/v1/b/${bucket}/o/${encodeURIComponent(name)}?alt=media`);
    if (r.status === 404) return { generation: '0', data: { starts: 0, turns: [], visitors: {} } };
    if (!r.ok) throw new Error('Demo ledger unavailable');
    const generation = r.headers.get('x-goog-generation');
    if (!generation) throw new Error('Missing ledger generation');
    return { generation, data: await r.json() };
  }
  async function write(name, data, generation = '0') {
    return call(`https://storage.googleapis.com/upload/storage/v1/b/${bucket}/o?uploadType=media&name=${encodeURIComponent(name)}&ifGenerationMatch=${encodeURIComponent(generation)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    });
  }
  async function change(day, update) {
    for (let attempt = 0; attempt < 5; attempt++) {
      const { data, generation } = await read(`limits/${day}.json`);
      const result = update(data);
      if (!result) return false;
      const r = await write(`limits/${day}.json`, data, generation);
      if (r.ok) return true;
      if (r.status !== 412) throw new Error('Demo ledger unavailable');
    }
    throw new Error('Demo ledger busy');
  }
  return {
    start: (day) => change(day, d => { if (d.starts >= 300) return false; d.starts++; return true; }),
    reserve: (day, visitor, turn, limit) => change(day, d => {
      if (d.turns.includes(turn)) return true;
      if (d.turns.length >= limit || (d.visitors[visitor] || 0) >= 3) return false;
      d.turns.push(turn); d.visitors[visitor] = (d.visitors[visitor] || 0) + 1; return true;
    }),
    async event(row) {
      const r = await write(`events/${row.at.slice(0, 10)}/${randomUUID()}.json`, row);
      if (!r.ok) throw new Error('Event storage unavailable');
    },
  };
}
