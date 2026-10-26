"""PyAI speech + your LLM. Run console locally, or dev with LiveKit credentials."""

import asyncio
import os
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, pyai, silero
from telemetry import Activation

load_dotenv()


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=pyai.STT(),
        tts=pyai.TTS(voice=os.getenv("PYAI_VOICE", "stock_emma_en_gb")),
        llm=openai.LLM(model=os.getenv("LLM_MODEL", "gpt-4o-mini")),
        vad=silero.VAD.load(),
    )
    events = Activation("livekit")

    @session.on("user_input_transcribed")
    def on_transcript(event):
        if event.is_final and event.transcript.strip():
            events.emit("transcription_succeeded")

    @session.on("agent_state_changed")
    def on_agent(event):
        if event.new_state == "speaking":
            events.emit("speech_started")

    @session.on("conversation_item_added")
    def on_item(event):
        if event.item.role == "assistant" and event.item.interrupted:
            events.emit("interruption_observed")

    @session.on("close")
    def on_close(event):
        events.emit("session_closed")

    await session.start(
        room=ctx.room,
        agent=Agent(
            instructions="You are a friendly voice assistant. Answer briefly, with no markdown. Do not claim to take actions or make purchases."
        ),
    )
    events.emit("session_started")

    # Always close the demo, including when a browser/client is left open.
    async def deadline():
        await asyncio.sleep(int(os.getenv("DEMO_SECONDS", "60")))
        await session.aclose()

    timer = asyncio.create_task(deadline())

    async def cleanup():
        timer.cancel()
        await session.aclose()

    ctx.add_shutdown_callback(cleanup)
    await session.generate_reply(
        instructions="Say hello and ask how you can help in one sentence."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
