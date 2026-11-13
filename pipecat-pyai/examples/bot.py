"""Single-file PyAI STT/LLM/TTS WebRTC example, adapted from demos/pipecat_bot.py.

Python 3.12; install pipecat-pyai==0.1.4, pipecat-ai[webrtc,runner,openai]==1.14.0,
and python-dotenv==1.1.1. Set PYAI_API_KEY and OPENAI_API_KEY server-side.
Before use, verify the PyAI project and limits with GET /v1/me.
Run: python bot.py -t webrtc --host 127.0.0.1
Open the runner URL and connect with microphone permission. Requests can incur
PyAI and LLM charges. DEMO_SECONDS defaults to 60; this is not a monetary cap.
Offline startup checks do not establish live speech or interruption behavior.
"""

import asyncio
import os
from dotenv import load_dotenv
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import (
    PipelineParams,
    PipelineWorker,
    ProcessorUnusablePolicy,
)
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

load_dotenv()


async def bot(runner_args):
    if not isinstance(runner_args, SmallWebRTCRunnerArguments):
        raise ValueError("This demo supports only local WebRTC; use -t webrtc.")
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
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
            user,
            llm,
            PyAITTSService(voice=os.getenv("PYAI_VOICE", "stock_emma_en_gb")),
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


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
