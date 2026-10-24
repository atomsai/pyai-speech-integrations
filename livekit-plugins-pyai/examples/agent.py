"""Minimal LiveKit voice agent using PyAI for STT + TTS.

Run:
    export PYAI_API_KEY=pyai_live_...
    export OPENAI_API_KEY=sk-...                # for the LLM brain
    export LIVEKIT_URL=... LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=...
    python agent.py dev
"""

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, pyai, silero

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a warm, concise voice assistant speaking with a PyAI voice."
        )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        # PyAI Hear (STT), reads PYAI_API_KEY from the environment.
        stt=pyai.STT(),
        # Any LLM brain; PyAI is the voice in/out, not the model.
        llm=openai.LLM(model="gpt-4o-mini"),
        # PyAI Speak (TTS). Pick a streaming-capable voice from GET /v1/voices.
        tts=pyai.TTS(voice="stock_emma_en_gb"),
        # VAD handles turn-taking in the cascaded pipeline.
        vad=silero.VAD.load(),
    )

    await session.start(agent=Assistant(), room=ctx.room)
    await session.generate_reply(instructions="Greet the caller and offer help.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
