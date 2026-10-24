"""PyAI (Hear + Speak) plugin for LiveKit Agents.

    from livekit.plugins import pyai

    session = AgentSession(
        stt=pyai.STT(),
        llm=llm,
        tts=pyai.TTS(voice="stock_emma_en_gb"),
        vad=vad,
    )
"""

from .stt import STT
from .tts import TTS
from .version import __version__

# Explicit, unambiguous aliases for when `STT`/`TTS` are too generic at a glance.
PyAISTT = STT
PyAITTS = TTS

__all__ = ["STT", "TTS", "PyAISTT", "PyAITTS", "__version__"]
