"""PyAI Speak (text-to-speech) for LiveKit Agents.

Chunked TTS over the PyAI Speak endpoint, requesting raw `pcm` at the session's
sample rate and streaming it straight into the agent's audio output. Use as
`pyai.TTS(voice="stock_emma_en_gb")` in an AgentSession.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aiohttp
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    NotGivenOr,
    tts,
    utils,
)
from livekit.agents.tts import ChunkedStream, TTSCapabilities
from pyai import PyAI

from ._utils import speech_url
from .log import logger

DEFAULT_SAMPLE_RATE = 24000


@dataclass
class _TTSOptions:
    voice: str
    model: str
    sample_rate: int


class TTS(tts.TTS):
    def __init__(
        self,
        *,
        voice: str,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: str = "https://api.pyai.com",
        model: str = "pyai-speak",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        key = api_key if isinstance(api_key, str) and api_key else os.environ.get("PYAI_API_KEY", "")
        if not key:
            raise ValueError("A PyAI API key is required (pass api_key= or set PYAI_API_KEY).")
        if not voice:
            raise ValueError("A PyAI voice id is required (list them at GET /v1/voices).")
        self._client = PyAI(api_key=key, base_url=base_url)
        self._opts = _TTSOptions(voice=voice, model=model, sample_rate=sample_rate)
        self._session = http_session

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "PyAI"

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> "ChunkedStream":
        return PyAIChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            client=self._client,
            opts=self._opts,
            session=self._ensure_session(),
        )


class PyAIChunkedStream(ChunkedStream):
    def __init__(
        self,
        *,
        tts: TTS,
        input_text: str,
        conn_options: APIConnectOptions,
        client: PyAI,
        opts: _TTSOptions,
        session: aiohttp.ClientSession,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._client = client
        self._opts = opts
        self._session = session

    async def _run(self, output_emitter) -> None:  # type: ignore[override]
        payload = {
            "model": self._opts.model,
            "input": self._input_text,
            "voice": self._opts.voice,
            "response_format": "pcm",
            "sample_rate": self._opts.sample_rate,
        }
        try:
            async with self._session.post(
                speech_url(self._client.base_url),
                headers={
                    "Authorization": f"Bearer {self._client.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30, connect=self._conn_options.timeout),
            ) as resp:
                if resp.status != 200:
                    raise APIStatusError(message="PyAI Speak synthesis failed.", status_code=resp.status)

                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=self._opts.sample_rate,
                    num_channels=1,
                    mime_type="audio/pcm",
                )
                async for chunk in resp.content.iter_chunked(4096):
                    if chunk:
                        output_emitter.push(chunk)
                output_emitter.flush()
        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except aiohttp.ClientError as e:
            raise APIConnectionError() from e
        logger.debug("PyAI Speak synthesis complete")
