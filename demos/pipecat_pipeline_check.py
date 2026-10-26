"""Actual PipelineWorker speech path with a deterministic reply and captured audio.

Default uses a loopback fake provider; --live uses one Hear stream and one Speak
request with a stdin credential and an existing synthetic question.wav fixture.
Interruption is frame-injected, not microphone-driven or physical playback proof.
"""

import asyncio
import json
import sys
import wave
from pathlib import Path
from aiohttp import web
from pipecat.frames.frames import (
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    TTSAudioRawFrame,
    TTSStoppedFrame,
    InputAudioRawFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
    InterruptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.workers.runner import WorkerRunner
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat_pyai import PyAISTTService, PyAITTSService

REPLY = "Speak costs four cents per generated audio minute."


async def check(key, base, pcm):
    result = {
        "mode": "live"
        if base.startswith("https://api.pyai")
        else "controlled_provider",
        "transcripts": [],
        "audio_bytes": 0,
        "interruption": "not_observed",
        "physical_playback": "not_tested",
        "llm": "deterministic fixture",
    }
    ready = asyncio.Event()
    spoken = asyncio.Event()
    interrupted = asyncio.Event()
    ended = asyncio.Event()

    class Answer(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TranscriptionFrame) and frame.text.strip():
                result["transcripts"].append(frame.text)
                await self.push_frame(TTSSpeakFrame(REPLY))
            await self.push_frame(frame, direction)

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSAudioRawFrame):
                result["audio_bytes"] += len(frame.audio)
                spoken.set()
                # Simulated pending playback: do not pretend these bytes reached a speaker.
            if isinstance(frame, InterruptionFrame) and result["audio_bytes"]:
                result["interruption"] = "frame_delivered_to_sink"
                interrupted.set()
            if isinstance(frame, TTSStoppedFrame):
                ended.set()
            await self.push_frame(frame, direction)

    stt = PyAISTTService(api_key=key, base_url=base, sample_rate=16000)
    tts = PyAITTSService(
        api_key=key, base_url=base, voice="stock_emma_en_gb", sample_rate=24000
    )
    worker = PipelineWorker(
        Pipeline([stt, Answer(), tts, Sink()]),
        params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=24000),
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    run = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 10)
        await worker.queue_frames([VADUserStartedSpeakingFrame()])
        for i in range(0, len(pcm), 640):
            await worker.queue_frames([InputAudioRawFrame(pcm[i : i + 640], 16000, 1)])
            await asyncio.sleep(0.02)
        await worker.queue_frames([VADUserStoppedSpeakingFrame()])
        await asyncio.wait_for(spoken.wait(), 30)
        await worker.queue_frames([InterruptionFrame()])
        await asyncio.wait_for(interrupted.wait(), 5)
        assert any(
            "cost" in t.lower() and "voice" in t.lower() for t in result["transcripts"]
        )
        assert result["audio_bytes"] > 0
        result["result"] = "PASS"
    finally:
        await runner.cancel()
        await asyncio.wait_for(run, 10)
    return result


async def main():
    live = "--live" in sys.argv
    if live:
        key = sys.stdin.readline().strip()
        with wave.open("live-results/question.wav", "rb") as f:
            pcm = f.readframes(f.getnframes())
        result = await asyncio.wait_for(check(key, "https://api.pyai.com", pcm), 60)
        Path("live-results/pipecat-pipeline.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    else:
        requests = {"hear": 0, "speak": 0}

        async def hear(request):
            assert request.query["sample_rate"] == "16000"
            assert request.query["model"] == "pyai-hear"
            requests["hear"] += 1
            ws = web.WebSocketResponse(protocols=["pyai.v1"])
            await ws.prepare(request)
            async for msg in ws:
                if (
                    msg.type == web.WSMsgType.TEXT
                    and json.loads(msg.data).get("type") == "commit"
                ):
                    await ws.send_json(
                        {
                            "type": "final",
                            "text": "What does it cost to add a voice?",
                            "endpoint_reason": "commit",
                        }
                    )
            return ws

        async def speak(request):
            requests["speak"] += 1
            assert (await request.json())["input"] == REPLY
            r = web.StreamResponse(headers={"Content-Type": "audio/pcm"})
            await r.prepare(request)
            try:
                for _ in range(50):
                    await r.write(bytes(960))
                    await asyncio.sleep(0.02)
            except (ConnectionResetError, RuntimeError):
                pass
            return r

        app = web.Application()
        app.router.add_get("/v1/audio/transcriptions/stream", hear)
        app.router.add_post("/v1/audio/speech", speak)
        http = web.AppRunner(app)
        await http.setup()
        site = web.TCPSite(http, "127.0.0.1", 8766)
        await site.start()
        try:
            result = await asyncio.wait_for(
                check("offline-contract", "http://127.0.0.1:8766", bytes(6400)), 30
            )
        finally:
            await http.cleanup()
        assert requests == {"hear": 1, "speak": 1}, requests
        result["requests"] = requests
    print(json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
