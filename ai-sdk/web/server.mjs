import { createServer } from "node:http";
import { readFile, appendFile, mkdir } from "node:fs/promises";
import { randomBytes, timingSafeEqual, createHmac } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { createPyAIAudio } from "../audio.mjs";

const assets = new Map([
  ["/", ["index.html", "text/html"]],
  ["/app.js", ["app.js", "text/javascript"]],
  ["/style.css", ["style.css", "text/css"]],
]);
const sourceNames = new Set([
  "direct",
  "livekit",
  "pipecat",
  "openclaw",
  "ai-sdk",
]);
const publicEvents = new Set([
  "playback_started",
  "signup_clicked",
  "pricing_clicked",
]);
const equal = (a, b) => {
  const x = Buffer.from(a),
    y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
};
export function guideReply(text) {
  if (/price|pricing|cost|charge/i.test(text))
    return "Hear costs $0.001 per input audio minute, rounded up to a started minute per nonempty synchronous request. Speak costs $0.04 per generated audio minute. Hosting and your language model cost extra.";
  if (/language|voice|accent/i.test(text))
    return "Hear supports 29 recognition languages. Speak offers 200 stock voices across 17 language groups in the October 25 catalog. Test your own accents and terminology before going live.";
  if (/train|privacy|retain/i.test(text))
    return "PyAI does not use customer inputs and outputs for shared model training by default. That is separate from retention. Please review the privacy policy for details.";
  if (/integrat|start|build|livekit|pipecat|sdk/i.test(text))
    return "Start with the PyAI speech integrations repository. Choose the AI SDK, LiveKit, or Pipecat example, create a PyAI key, and keep it on your server. Your existing language model can stay the same.";
  return "I am the PyAI product guide. Ask me about pricing, supported languages, privacy, or adding Hear and Speak to your app.";
}
export function createVoiceServer({
  audio,
  answer = async (text) => guideReply(text),
  mode = "product-guide",
  accessCode,
  publicDemo = false,
  sessionSecret,
  storage,
  referralCode,
  origin = "http://localhost:3000",
  dataDir = "./.voice-data",
  maxDailyTurns = 100,
  maxSessionTurns = 10,
  timeoutMs = 45000,
  now = () => Date.now(),
} = {}) {
  if (publicDemo && (!storage || !sessionSecret || sessionSecret.length < 32))
    throw new Error("Public demo requires durable storage and a signing secret.");
  if (!publicDemo && (!accessCode || accessCode.length < 16))
    throw new Error("Set DEMO_ACCESS_CODE to at least 16 characters.");
  if (!Number.isInteger(maxDailyTurns) || maxDailyTurns < 1)
    throw new Error("Invalid daily turn limit.");
  const expectedOrigin = new URL(origin).origin;
  const sessions = new Map();
  let busy = false,
    reservations = [];
  const ready = storage ? Promise.resolve() : mkdir(dataDir, { recursive: true }).then(async () => {
    try {
      reservations = (
        await readFile(resolve(dataDir, "reservations.jsonl"), "utf8")
      )
        .trim()
        .split("\n")
        .filter(Boolean)
        .map(JSON.parse);
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
    }
  });
  const event = async (session, name, extra = {}) => {
    const row = { version: 1, at: new Date(now()).toISOString(), session: session.id, source: session.source, event: name, ...extra };
    if (storage) return storage.event(row);
    return appendFile(resolve(dataDir, "events.jsonl"), JSON.stringify(row) + "\n", { mode: 0o600 });
  };
  const signupUrl = (source) => {
    const target = new URL('https://console.pyai.com/?signup=1&path=api');
    const url = /^cp_[a-z0-9]{20,40}$/.test(referralCode || '') ? new URL(`https://pyai.com/r/${referralCode}`) : target;
    if (url !== target) url.searchParams.set('next', target.toString());
    url.searchParams.set('utm_source', sourceNames.has(source) ? source : 'direct');
    url.searchParams.set('utm_medium', 'voice-demo'); url.searchParams.set('utm_campaign', 'speech-activation');
    return url.toString();
  };
  function visitorCookie(req) {
    const raw = (req.headers.cookie || '').match(/(?:^|;\s*)voice_visitor=([a-f0-9]{32}\.[0-9]{13}\.[a-f0-9]{64})(?:;|$)/)?.[1];
    const sign = (value) => createHmac('sha256', sessionSecret).update(value).digest('hex');
    if (raw) {
      const [id, expiry, signature] = raw.split('.');
      if (Number(expiry) > now() && Number(expiry) <= now() + 30 * 86400000 && equal(sign(`${id}.${expiry}`), signature)) return { id, value: raw };
    }
    const id = randomBytes(16).toString('hex'), expiry = now() + 30 * 86400000;
    return { id, value: `${id}.${expiry}.${sign(`${id}.${expiry}`)}` };
  }
  const send = (res, status, data) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(data));
  };
  async function body(req, limit) {
    const chunks = [];
    let size = 0;
    for await (const c of req) {
      size += c.length;
      if (size > limit) {
        const e = new Error("Request too large");
        e.status = 413;
        throw e;
      }
      chunks.push(c);
    }
    return Buffer.concat(chunks);
  }
  const server = createServer(async (req, res) => {
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    );
    res.setHeader("Permissions-Policy", "microphone=(self), camera=()");
    let session;
    let controller;
    let stage = "request";
    let locked = false;
    try {
      await ready;
      const url = new URL(req.url, expectedOrigin);
      if (req.method === "GET" && assets.has(url.pathname)) {
        const [file, type] = assets.get(url.pathname);
        res.writeHead(200, { "Content-Type": type });
        res.end(await readFile(new URL(`./public/${file}`, import.meta.url)));
        return;
      }
      if (req.method === "GET" && url.pathname === "/api/config")
        return send(res, 200, { publicDemo, mode, signupUrl: signupUrl(url.searchParams.get("source")) });
      if (req.method === "GET" && url.pathname === "/healthz")
        return send(res, 200, { ok: true });
      if (req.method !== "POST") return send(res, 404, { error: "Not found" });
      if (req.headers.origin !== expectedOrigin)
        return send(res, 403, {
          error: "Open this app at its configured public URL.",
        });
      for (const [id, s] of sessions)
        if (s.expires < now()) sessions.delete(id);
      if (url.pathname === "/api/session") {
        const input = JSON.parse((await body(req, 1024)).toString());
        if (!publicDemo && !equal(String(input.code || ""), accessCode))
          return send(res, 401, { error: "Check your demo access code." });
        if (sessions.size >= 500)
          return send(res, 429, {
            error: "Demo at capacity. Please try later.",
          });
        if (storage && !(await storage.start(new Date(now()).toISOString().slice(0, 10))))
          return send(res, 429, { error: "Today’s demo is full. Create your PyAI account to continue." });
        const visitor = publicDemo ? visitorCookie(req) : null;
        const id = randomBytes(24).toString("hex");
        session = {
          id,
          source: sourceNames.has(input.source) ? input.source : "direct",
          expires: now() + 1800000,
          turns: 0,
          lastTurn: null,
          events: new Set(),
          visitor: visitor?.id || id,
        };
        await event(session, "session_started");
        sessions.set(id, session);
        res.setHeader(
          "Set-Cookie",
          `voice_session=${id}; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800${expectedOrigin.startsWith("https:") ? "; Secure" : ""}`,
        );
        if (visitor) res.setHeader("Set-Cookie", [res.getHeader("Set-Cookie"), `voice_visitor=${visitor.value}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000${expectedOrigin.startsWith("https:") ? "; Secure" : ""}`]);
        return send(res, 200, { ok: true, mode, signupUrl: signupUrl(session.source) });
      }
      const token = (req.headers.cookie || "").match(
        /(?:^|;\s*)voice_session=([a-f0-9]{48})(?:;|$)/,
      )?.[1];
      session = sessions.get(token);
      if (!session)
        return send(res, 401, {
          error: publicDemo ? "Your demo session expired. Start a new demo session." : "Your demo session expired. Enter the access code again.",
        });
      if (url.pathname === "/api/event") {
        const input = JSON.parse((await body(req, 512)).toString());
        if (!publicEvents.has(input.event))
          return send(res, 400, { error: "Unknown event" });
        if (
          input.event === "playback_started" &&
          input.turn !== session.lastTurn
        )
          return send(res, 400, { error: "Unknown audio turn" });
        const eventKey = `${input.event}:${input.event === "playback_started" ? input.turn : ""}`;
        if (session.events.has(eventKey)) return send(res, 200, { ok: true });
        session.events.add(eventKey);
        await event(session, input.event, {
          ...(input.event === "playback_started" ? { turn: input.turn } : {}),
          reported_by: "browser",
        });
        return send(res, 200, { ok: true });
      }
      if (url.pathname !== "/api/turn")
        return send(res, 404, { error: "Not found" });
      // One in-flight turn per process; replicas need a shared durable limiter.
      if (busy)
        return send(res, 429, {
          error:
            "The demo is answering another question. Please try again shortly.",
        });
      busy = true;
      locked = true;
      const input = JSON.parse((await body(req, 1500000)).toString());
      let text = typeof input.text === "string" ? input.text.trim() : "";
      let wav;
      if (input.audio) {
        if (
          typeof input.audio !== "string" ||
          input.audio.length > 1400000 ||
          !/^[A-Za-z0-9+/]+={0,2}$/.test(input.audio)
        )
          return send(res, 400, { error: "Use a short WAV recording." });
        wav = Buffer.from(input.audio, "base64");
        // Only our canonical mono PCM16 WAV writer, max 15 seconds at 16kHz.
        if (
          wav.length < 46 ||
          wav.length > 480044 ||
          wav.toString("ascii", 0, 4) !== "RIFF" ||
          wav.toString("ascii", 8, 16) !== "WAVEfmt " ||
          wav.readUInt32LE(16) !== 16 ||
          wav.readUInt16LE(20) !== 1 ||
          wav.readUInt16LE(22) !== 1 ||
          wav.readUInt32LE(24) !== 16000 ||
          wav.readUInt16LE(34) !== 16 ||
          wav.toString("ascii", 36, 40) !== "data" ||
          wav.readUInt32LE(40) !== wav.length - 44 ||
          wav.readUInt32LE(4) !== wav.length - 8 ||
          wav.length % 2
        )
          return send(res, 400, {
            error: "Record up to 15 seconds of mono 16 kHz audio.",
          });
      } else if (!text || text.length > 2000)
        return send(res, 400, {
          error: "Enter a question under 2,000 characters.",
        });
      const day = new Date(now()).toISOString().slice(0, 10);
      reservations = reservations.filter((r) => r.day === day);
      if (
        session.turns >= maxSessionTurns ||
        reservations.length >= maxDailyTurns
      )
        return send(res, 429, {
          error:
            "Demo allowance reached. Create your own PyAI account to continue.",
        });
      const turn = randomBytes(12).toString("hex");
      const reservation = { day, turn };
      if (storage && !(await storage.reserve(day, session.visitor, turn, maxDailyTurns)))
        return send(res, 429, { error: "Your free demo allowance is used. Create your own PyAI account to continue." });
      if (!storage) await appendFile(
        resolve(dataDir, "reservations.jsonl"),
        JSON.stringify(reservation) + "\n",
        { mode: 0o600 },
      );
      if (!storage) reservations.push(reservation);
      session.turns++;
      await event(session, "turn_started", {
        turn,
        input: wav ? "audio" : "text",
      });
      controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      const onClose = () => {
        if (!res.writableEnded) controller.abort();
      };
      res.on("close", onClose);
      try {
        if (wav) {
          stage = "hear";
          text = (
            await audio.hear(wav, { abortSignal: controller.signal })
          ).text?.trim();
          if (!text)
            return send(res, 422, {
              error: "No speech recognized. Please try a clearer recording.",
            });
          await event(session, "transcription_succeeded", { turn });
        }
        if (text.length > 2000)
          return send(res, 422, { error: "Please ask a shorter question." });
        stage = "answer";
        const reply = await answer(text, { abortSignal: controller.signal });
        if (typeof reply !== "string" || !reply.trim() || reply.length > 1200)
          throw new Error("Invalid answer");
        await event(session, "answer_succeeded", { turn });
        stage = "speak";
        const speech = await audio.speak(reply, {
          abortSignal: controller.signal,
        });
        const bytes = speech.audio.uint8Array;
        if (!bytes?.length || bytes.length > 4000000)
          throw new Error("Invalid speech");
        await event(session, "speech_succeeded", { turn, bytes: bytes.length });
        session.lastTurn = turn;
        send(res, 200, {
          turn,
          transcript: text,
          reply,
          audio: Buffer.from(bytes).toString("base64"),
          mediaType: speech.audio.mediaType,
        });
      } finally {
        clearTimeout(timer);
        res.off("close", onClose);
      }
    } catch (e) {
      if (session)
        await event(session, "request_failed", {
          stage,
          code: controller?.signal.aborted
            ? "timeout"
            : String(e.statusCode || e.status || "failed"),
        }).catch(() => {});
      if (!res.headersSent)
        send(res, e.status || (e instanceof SyntaxError ? 400 : 502), {
          error: controller?.signal.aborted
            ? "The request timed out. Nothing was retried."
            : e.status === 413
              ? "Recording too large."
              : "Could not complete the request. Please check your connection or contact the demo owner.",
        });
    } finally {
      if (locked) busy = false;
    }
  });
  server.headersTimeout = 10000;
  server.requestTimeout = 60000;
  return server;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT || 3000);
  const origin = process.env.PUBLIC_ORIGIN || `http://localhost:${port}`;
  const answer = process.env.LLM_MODEL
    ? (await import("./llm.mjs")).createAnswer()
    : undefined;
  const server = createVoiceServer({
    audio: createPyAIAudio(),
    answer,
    mode: answer ? "llm" : "product-guide",
    accessCode: process.env.DEMO_ACCESS_CODE,
    publicDemo: process.env.PUBLIC_DEMO === "true",
    sessionSecret: process.env.SESSION_SECRET,
    referralCode: process.env.REFERRAL_CODE,
    storage: process.env.DEMO_BUCKET ? (await import("./cloud-store.mjs")).createCloudStore({ bucket: process.env.DEMO_BUCKET }) : undefined,
    origin,
    dataDir: process.env.DATA_DIR || "./.voice-data",
    maxDailyTurns: Number(process.env.MAX_DAILY_TURNS || 100),
  });
  server.listen(port, process.env.HOST || "127.0.0.1", () =>
    console.log(`PyAI voice guide: ${origin}`),
  );
}
