// Offline UI preview only. A tone is deliberately not presented as real speech.
import { createVoiceServer } from "./server.mjs";
const b = Buffer.alloc(32044);
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
b.writeUInt32LE(32000, 40);
for (let i = 0; i < 16000; i++)
  b.writeInt16LE(
    Math.round(Math.sin((i * 2 * Math.PI * 440) / 16000) * 1000),
    44 + i * 2,
  );
createVoiceServer({
  audio: {
    speak: async () => ({ audio: { uint8Array: b, mediaType: "audio/wav" } }),
    hear: async () => ({ text: "What does it cost?" }),
  },
  answer: async () =>
    "Offline preview only. This tone tests playback; no speech provider was called.",
  mode: "offline-preview",
  accessCode: "offline-preview-only",
  origin: "http://localhost:3000",
  dataDir: "/tmp/pyai-voice-preview",
}).listen(3000, "127.0.0.1");
