"""PyAI Speak (text-to-speech) service for Pipecat.

Chunked TTS over the PyAI Speak endpoint, requesting raw `pcm` at the pipeline's
output sample rate and pushing `TTSAudioRawFrame`s as the audio streams in.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

import aiohttp
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    StartFrame,
    TTSAudioRawFrame,
)
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pyai import PyAI

from ._utils import speech_url


class PyAITTSService(TTSService):
    """Text-to-speech backed by PyAI Speak (raw PCM, streamed)."""

    def __init__(
        self,
        *,
        voice: str,
        api_key: Optional[str] = None,
        base_url: str = "https://api.pyai.com",
        model: str = "pyai-speak",
        sample_rate: Optional[int] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            sample_rate=sample_rate,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model=model, voice=voice, language=None),
            **kwargs,
        )
        key = api_key or os.environ.get("PYAI_API_KEY", "")
        if not key:
            raise ValueError("A PyAI API key is required (pass api_key= or set PYAI_API_KEY).")
        if not voice:
            raise ValueError("A PyAI voice id is required (list them at GET /v1/voices).")
        self._client = PyAI(api_key=key, base_url=base_url)
        self._voice = voice
        self._model_name = model
        self._session = aiohttp_session
        self._owns_session = aiohttp_session is None

    def can_generate_metrics(self) -> bool:
        return True

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def stop(self, frame) -> None:
        await super().stop(frame)
        await self._maybe_close_session()

    async def cancel(self, frame) -> None:
        await super().cancel(frame)
        await self._maybe_close_session()

    async def _maybe_close_session(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        logger.debug(f"{self} synthesizing with PyAI Speak")

        payload = {
            "model": self._model_name,
            "input": text,
            "voice": self._voice,
            "response_format": "pcm",
            "sample_rate": self.sample_rate,
        }
        headers = {
            "Authorization": f"Bearer {self._client.api_key}",
            "Content-Type": "application/json",
        }
        received_audio = False
        ttfb_stopped = False
        try:
            assert self._session is not None
            async with self._session.post(
                speech_url(self._client.base_url), headers=headers, json=payload
            ) as resp:
                if resp.status != 200:
                    await self.stop_ttfb_metrics()
                    ttfb_stopped = True
                    yield ErrorFrame(f"PyAI Speak error (status {resp.status}).")
                    return
                await self.start_tts_usage_metrics(text)
                async for chunk in resp.content.iter_chunked(4096):
                    if chunk:
                        received_audio = True
                        yield TTSAudioRawFrame(
                            chunk,
                            self.sample_rate,
                            1,
                            context_id=context_id,
                        )
        except Exception as e:  # noqa: BLE001 - surface as a pipeline error frame
            logger.error(f"{self} PyAI Speak request failed: {e}")
            if not received_audio and not ttfb_stopped:
                await self.stop_ttfb_metrics()
                ttfb_stopped = True
            yield ErrorFrame("PyAI Speak request failed.")
        finally:
            # The base audio-context task stops TTFB on the first audio frame.
            # Empty and failed responses have no such frame, so close the metric
            # here instead.
            if not received_audio and not ttfb_stopped:
                await self.stop_ttfb_metrics()
