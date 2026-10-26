const $ = (id) => document.getElementById(id);
let busy = false,
  recording = null,
  blobURL = null,
  lastTurn = null;
const status = (text) => ($("status").textContent = text);
async function api(path, data) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await r.json();
  if (!r.ok) throw new Error(result.error || "Request failed");
  return result;
}
function track(event, turn) {
  void api("/api/event", { event, turn }).catch(() => {});
}
function message(role, text) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  const name = document.createElement("strong");
  name.textContent = role === "user" ? "You" : "PyAI guide";
  el.append(name, document.createTextNode(text));
  $("messages").append(el);
  el.scrollIntoView({ block: "nearest" });
}
function stopAudio() {
  $("player").pause();
  $("stop").hidden = true;
}
async function ask(input) {
  if (busy || recording) return;
  busy = true;
  stopAudio();
  $("send").disabled = true;
  $("record").disabled = true;
  status(
    input.audio ? "Listening to your recording…" : "Preparing your answer…",
  );
  try {
    const r = await api("/api/turn", input);
    message("user", r.transcript);
    message("assistant", r.reply);
    lastTurn = r.turn;
    if (blobURL) URL.revokeObjectURL(blobURL);
    blobURL = URL.createObjectURL(
      new Blob([Uint8Array.from(atob(r.audio), (c) => c.charCodeAt(0))], {
        type: r.mediaType,
      }),
    );
    $("player").src = blobURL;
    $("player").hidden = false;
    status("Your answer is ready.");
    try {
      await $("player").play();
    } catch {
      status("Press play to hear your answer.");
    }
  } catch (e) {
    status(e.message);
  } finally {
    busy = false;
    $("send").disabled = false;
    $("record").disabled = false;
  }
}
$("login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("login").querySelector("button");
  button.disabled = true;
  try {
    const connected = await api("/api/session", {
      code: $("code").value,
      source: new URL(location.href).searchParams.get("source") || "direct",
    });
    if (connected.mode === "llm")
      $("mode").textContent =
        "This demo sends your question to the host’s configured language model, with PyAI Hear and Speak for audio. Replies may be inaccurate.";
    if (connected.mode === "offline-preview")
      $("mode").textContent =
        "Offline preview: canned answers and a test tone. No speech or language-model provider is called.";
    if (connected.signupUrl) $("signup").href = connected.signupUrl;
    $("code").value = "";
    $("login").hidden = true;
    $("chat").hidden = false;
    status("Connected. Ask your first question.");
  } catch (e) {
    status(e.message);
  } finally {
    button.disabled = false;
  }
});
$("question").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("text").value.trim();
  if (text) {
    $("text").value = "";
    void ask({ text });
  }
});
for (const b of document.querySelectorAll("[data-prompt]"))
  b.addEventListener("click", () => void ask({ text: b.dataset.prompt }));
$("player").addEventListener("playing", () => {
  track("playback_started", lastTurn);
  $("stop").hidden = false;
});
$("player").addEventListener("ended", () => {
  $("stop").hidden = true;
});
$("stop").addEventListener("click", () => {
  stopAudio();
  status("Playback stopped. You can ask another question.");
});
$("signup").addEventListener("click", () => track("signup_clicked"));
$("pricing").addEventListener("click", () => track("pricing_clicked"));
function wav(samples) {
  const buffer = new ArrayBuffer(44 + samples.length * 2),
    v = new DataView(buffer);
  const str = (i, s) =>
    [...s].forEach((c, j) => v.setUint8(i + j, c.charCodeAt(0)));
  str(0, "RIFF");
  v.setUint32(4, buffer.byteLength - 8, true);
  str(8, "WAVEfmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, 16000, true);
  v.setUint32(28, 32000, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, "data");
  v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++)
    v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 32767, true);
  return new Uint8Array(buffer);
}
$("record").addEventListener("click", async () => {
  if (recording) {
    recording.stop();
    return;
  }
  stopAudio();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    recording = recorder;
    const chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    $("record").textContent = "■ Finish recording";
    $("send").disabled = true;
    status("Recording… up to 15 seconds.");
    const timer = setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 15000);
    recorder.onstop = async () => {
      clearTimeout(timer);
      stream.getTracks().forEach((t) => t.stop());
      recording = null;
      $("record").textContent = "● Record a question";
      $("send").disabled = false;
      let ctx;
      try {
        ctx = new AudioContext();
        const decoded = await ctx.decodeAudioData(
          await new Blob(chunks).arrayBuffer(),
        );
        const count = Math.min(240000, Math.floor(decoded.duration * 16000));
        if (!count) throw new Error("Recording is empty.");
        const offline = new OfflineAudioContext(1, count, 16000);
        const src = offline.createBufferSource();
        src.buffer = decoded;
        src.connect(offline.destination);
        src.start();
        const pcm = (await offline.startRendering()).getChannelData(0);
        const bytes = wav(pcm);
        let binary = "";
        for (let i = 0; i < bytes.length; i += 8192)
          binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        await ask({ audio: btoa(binary) });
      } catch (e) {
        status(`Could not read the recording: ${e.message}`);
      } finally {
        await ctx?.close();
      }
    };
    recorder.start();
  } catch {
    stream?.getTracks().forEach((t) => t.stop());
    recording = null;
    status(
      "Microphone unavailable. Allow microphone access or type a question.",
    );
  }
});
window.addEventListener("pagehide", () => {
  recording?.stream.getTracks().forEach((t) => t.stop());
  stopAudio();
  if (blobURL) URL.revokeObjectURL(blobURL);
});

fetch(`/api/config?source=${encodeURIComponent(new URL(location.href).searchParams.get('source') || 'direct')}`)
  .then(r => r.json()).then(config => {
    if (config.signupUrl) $('signup').href = config.signupUrl;
    if (config.publicDemo) {
      $('code').hidden = true; $('code').required = false;
      document.querySelector('label[for="code"]').hidden = true;
      $('login').querySelector('button').textContent = 'Try three free questions';
      status('Start the demo, then type or record a question. No account needed.');
    }
  }).catch(() => status('Could not load the demo. Please refresh.'));
