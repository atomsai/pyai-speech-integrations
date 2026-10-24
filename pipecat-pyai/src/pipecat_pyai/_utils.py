"""Pure helpers for the PyAI Pipecat services.

Free of any `pipecat` import so the URL/mapping logic can be unit tested without
the framework installed.
"""

from __future__ import annotations

from urllib.parse import urlencode


def normalize_base(base_url: str) -> str:
    return base_url.rstrip("/")


def ws_base(base_url: str) -> str:
    b = normalize_base(base_url)
    if b.startswith("https://"):
        return "wss://" + b[len("https://") :]
    if b.startswith("http://"):
        return "ws://" + b[len("http://") :]
    return b


def hear_stream_url(
    base_url: str,
    *,
    model: str,
    sample_rate: int,
    language: str | None = None,
    encoding: str = "pcm16",
    interim_results: bool = True,
) -> str:
    """Build the PyAI Hear streaming-STT WebSocket URL."""
    q = {
        "protocol": "pyai-hear-v1",
        "model": model,
        "sample_rate": str(sample_rate),
        "encoding": encoding,
        "interim_results": "true" if interim_results else "false",
    }
    if language:
        q["language"] = language
    return f"{ws_base(base_url)}/v1/audio/transcriptions/stream?{urlencode(q)}"


def speech_url(base_url: str) -> str:
    return f"{normalize_base(base_url)}/v1/audio/speech"


def transcript_kind(pyai_type: str) -> str | None:
    """Classify a PyAI Hear frame for Pipecat.

    PyAI's `final` is the corrected, definitive transcript; `partial` and
    `speech_final` are provisional (interim). Anything else returns None.
    """
    if pyai_type == "final":
        return "final"
    if pyai_type in ("partial", "speech_final"):
        return "interim"
    return None
