"""Runnable local WebRTC demo: python pipecat_bot.py -t webrtc --host 127.0.0.1."""

import asyncio
import os
from dotenv import load_dotenv
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMRunFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import (
    PipelineParams,
    PipelineWorker,
    ProcessorUnusablePolicy,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner
from pipecat_pyai import PyAISTTService, PyAITTSService
from telemetry import Activation

load_dotenv()


class Observe(FrameProcessor):
    def __init__(self, events):
        super().__init__()
        self.events = events

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            self.events.emit("transcription_succeeded")
        if isinstance(frame, TTSAudioRawFrame) and frame.audio:
            self.events.emit("speech_started")
        if isinstance(frame, InterruptionFrame):
            self.events.emit("interruption_observed")
        await self.push_frame(frame, direction)


async def bot(runner_args):
    if not isinstance(runner_args, SmallWebRTCRunnerArguments):
        raise ValueError("This demo supports only local WebRTC; use -t webrtc.")
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    events = Activation("pipecat")
    context = LLMContext()
    user, assistant = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            system_instruction="You are a friendly voice assistant. Use at most two short sentences, no markdown. Do not claim to take actions or make purchases.",
        ),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            PyAISTTService(),
            Observe(events),
            user,
            llm,
            PyAITTSService(voice=os.getenv("PYAI_VOICE", "stock_emma_en_gb")),
            Observe(events),
            transport.output(),
            assistant,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def connected(transport, client):
        events.emit("session_started")
        context.add_message(
            {
                "role": "developer",
                "content": "Say hello and offer help in one short sentence.",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def disconnected(transport, client):
        await runner.cancel()

    try:
        await asyncio.wait_for(
            runner.run(), timeout=int(os.getenv("DEMO_SECONDS", "60"))
        )
    except asyncio.TimeoutError:
        await runner.cancel()
    finally:
        events.emit("session_closed")


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
