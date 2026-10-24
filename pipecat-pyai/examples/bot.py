"""Minimal Pipecat voice bot using PyAI for STT + TTS.

Wire PyAI Hear (STT) and PyAI Speak (TTS) into a standard cascaded pipeline with
your existing LLM. Bring your own Pipecat transport.

    export PYAI_API_KEY=pyai_live_...
    await run_bot(transport, llm)
"""

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)

from pipecat_pyai import PyAISTTService, PyAITTSService


async def run_bot(transport, llm) -> None:
    """Use an existing Pipecat transport and LLM service."""
    stt = PyAISTTService()  # reads PYAI_API_KEY
    tts = PyAITTSService(voice="stock_emma_en_gb")

    context = LLMContext(
        [{"role": "system", "content": "You are a friendly, concise voice assistant."}]
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(pipeline)
    await PipelineRunner().run(task)


# See https://docs.pipecat.ai for transport and LLM setup, then call
# `await run_bot(transport, llm)`.
