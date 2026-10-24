"""PyAI (Hear + Speak) services for Pipecat.

    from pipecat_pyai import PyAISTTService, PyAITTSService

    stt = PyAISTTService()                      # PYAI_API_KEY
    tts = PyAITTSService(voice="stock_emma_en_gb")
"""

from .stt import PyAISTTService
from .tts import PyAITTSService

__version__ = "0.1.3"

__all__ = ["PyAISTTService", "PyAITTSService", "__version__"]
