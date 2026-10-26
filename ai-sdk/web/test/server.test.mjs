import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { once } from "node:events";
import { createVoiceServer } from "../server.mjs";
function wav() {
  const b = Buffer.alloc(44 + 3200);
  b.write("RIFF");
  b.writeUInt32LE(b.length - 8, 4);
  b.write("WAVEfmt ", 8);
  b.writeUInt32LE(16, 16);
  b.writeUInt16LE(1, 20);
  b.writeUInt16LE(1, 22);
  b.writeUInt32LE(16000, 24);
  b.writeUInt32LE(32000, 28);
  b.writeUInt16LE(2, 32);
  b.writeUInt16LE(16, 34);
  b.write("data", 36);
  b.writeUInt32LE(b.length - 44, 40);
  return b;
}
async function fixture(t, options = {}) {
  const dir = await mkdtemp(join(tmpdir(), "pyai-web-"));
  const calls = [];
  const audio = {
    hear: async () => {
      calls.push("hear");
      return { text: "What is pricing?" };
    },
    speak: async () => {
      calls.push("speak");
      return { audio: { uint8Array: wav(), mediaType: "audio/wav" } };
    },
  };
  const server = createVoiceServer({
    audio,
    accessCode: "test-only-code-123456",
    origin: "http://localhost:3000",
    dataDir: dir,
    ...options,
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = `http://127.0.0.1:${server.address().port}`;
  t.after(async () => {
    server.closeAllConnections();
    await new Promise((r) => server.close(r));
    await rm(dir, { recursive: true, force: true });
  });
  let cookie = "";
  const post = (path, data, headers = {}) =>
    fetch(base + path, {
      method: "POST",
      headers: {
        origin: "http://localhost:3000",
        cookie,
        "content-type": "application/json",
        ...headers,
      },
      body: JSON.stringify(data),
    });
  const login = async () => {
    const r = await post("/api/session", {
      code: "test-only-code-123456",
      source: "ai-sdk",
    });
    cookie = r.headers.get("set-cookie").split(";")[0];
    return r;
  };
  return { dir, calls, post, login, base, server };
}
test("real HTTP audio path records activation without text/audio/credentials", async (t) => {
  const f = await fixture(t);
  await f.login();
  const r = await f.post("/api/turn", { audio: wav().toString("base64") });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.match(d.reply, /pricing link below/);
  assert.match(d.reply, /pyai dot com slash pricing/);
  assert.deepEqual(f.calls, ["hear", "speak"]);
  assert.equal(
    (await f.post("/api/event", { event: "playback_started", turn: d.turn }))
      .status,
    200,
  );
  assert.equal(
    (
      await f.post("/api/event", {
        event: "signup_clicked",
        email: "not-recorded@example.com",
      })
    ).status,
    200,
  );
  const log = await readFile(join(f.dir, "events.jsonl"), "utf8");
  for (const value of [
    "What is pricing",
    "0.001",
    "test-only",
    "not-recorded",
    "RIFF",
  ])
    assert.ok(!log.includes(value));
  const rows = log.trim().split("\n").map(JSON.parse);
  assert.deepEqual(
    rows.map((r) => r.event),
    [
      "session_started",
      "turn_started",
      "transcription_succeeded",
      "answer_succeeded",
      "speech_succeeded",
      "playback_started",
      "signup_clicked",
    ],
  );
  assert.ok(rows.every((r) => r.source === "ai-sdk"));
});
test("auth, origin, bad recordings and invented conversion events cannot call providers", async (t) => {
  const f = await fixture(t);
  assert.equal((await f.post("/api/turn", { text: "hi" })).status, 401);
  await f.login();
  assert.equal(
    (
      await f.post(
        "/api/turn",
        { text: "hi" },
        { origin: "https://evil.example" },
      )
    ).status,
    403,
  );
  assert.equal(
    (await f.post("/api/turn", { audio: "not-a-wave" })).status,
    400,
  );
  assert.equal(
    (await f.post("/api/event", { event: "payment_completed" })).status,
    400,
  );
  assert.equal(
    (
      await f.post("/api/event", {
        event: "playback_started",
        turn: "invented",
      })
    ).status,
    400,
  );
  assert.deepEqual(f.calls, []);
});
test("session and daily limits reserve before usage; opening a new session cannot bypass daily cap", async (t) => {
  const f = await fixture(t, { maxDailyTurns: 1 });
  await f.login();
  assert.equal((await f.post("/api/turn", { text: "pricing" })).status, 200);
  await f.login();
  assert.equal((await f.post("/api/turn", { text: "pricing" })).status, 429);
  assert.deepEqual(f.calls, ["speak"]);
});
test("provider failure is redacted and never retried", async (t) => {
  let n = 0;
  const f = await fixture(t, {
    audio: {
      speak: async () => {
        n++;
        throw Object.assign(new Error("secret-key-and-transcript"), {
          statusCode: 402,
        });
      },
    },
  });
  await f.login();
  const r = await f.post("/api/turn", { text: "pricing" });
  assert.equal(r.status, 502);
  assert.ok(!(await r.text()).includes("secret"));
  assert.equal(n, 1);
  const log = await readFile(join(f.dir, "events.jsonl"), "utf8");
  assert.ok(!log.includes("secret"));
  assert.match(log, /402/);
});
test("timeout aborts provider request and records failure", async (t) => {
  let aborted = false;
  const f = await fixture(t, {
    timeoutMs: 20,
    audio: {
      speak: (_, { abortSignal }) =>
        new Promise((resolve, reject) =>
          abortSignal.addEventListener(
            "abort",
            () => {
              aborted = true;
              reject(new Error("aborted"));
            },
            { once: true },
          ),
        ),
    },
  });
  await f.login();
  const r = await f.post("/api/turn", { text: "hello" });
  assert.equal(r.status, 502);
  assert.equal(aborted, true);
  assert.match(await r.text(), /timed out/);
});
test("concurrent turn rejected while first is running", async (t) => {
  let release;
  const f = await fixture(t, {
    answer: () =>
      new Promise((r) => {
        release = r;
      }),
  });
  await f.login();
  const first = f.post("/api/turn", { text: "hello" });
  while (!release) await new Promise((r) => setTimeout(r, 5));
  assert.equal((await f.post("/api/turn", { text: "again" })).status, 429);
  release("Hello");
  assert.equal((await first).status, 200);
});
test("app serves strict browser headers and never serves data files", async (t) => {
  const f = await fixture(t);
  const r = await fetch(f.base);
  assert.equal(r.status, 200);
  assert.match(
    r.headers.get("content-security-policy"),
    /frame-ancestors 'none'/,
  );
  assert.match(await r.text(), /Your app/);
  assert.equal((await fetch(f.base + "/.voice-data/events.jsonl")).status, 404);
});

test("daily usage reservations survive a server restart", async (t) => {
  const first = await fixture(t, { maxDailyTurns: 1 });
  await first.login();
  assert.equal(
    (await first.post("/api/turn", { text: "pricing" })).status,
    200,
  );
  first.server.closeAllConnections();
  await new Promise((resolve) => first.server.close(resolve));
  const second = await fixture(t, { maxDailyTurns: 1, dataDir: first.dir });
  await second.login();
  assert.equal(
    (await second.post("/api/turn", { text: "pricing" })).status,
    429,
  );
  assert.deepEqual(second.calls, []);
});

test('public pilot issues secure visitor identity and fails closed on exhausted shared cap',async(t)=>{
 const events=[];let reservations=0;
 const f=await fixture(t,{publicDemo:true,sessionSecret:'x'.repeat(32),referralCode:'cp_'+'a'.repeat(26),storage:{start:async()=>true,event:async e=>events.push(e),reserve:async()=>++reservations<=1}});
 const config=await (await fetch(f.base+'/api/config?source=livekit')).json();
 assert.equal(config.publicDemo,true);assert.match(config.signupUrl,/pyai.com\/r\/cp_/);assert.match(config.signupUrl,/utm_source=livekit/);
 const login=await f.login();assert.match(login.headers.get('set-cookie'),/voice_visitor=/);
 assert.equal((await f.post('/api/turn',{text:'pricing'})).status,200);
 await f.login();assert.equal((await f.post('/api/turn',{text:'pricing'})).status,429);
 assert.deepEqual(f.calls,['speak']);
 await f.post('/api/event',{event:'signup_clicked'});await f.post('/api/event',{event:'signup_clicked'});
 assert.equal(events.filter(e=>e.event==='signup_clicked').length,1);
});
