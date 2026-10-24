"""PyAI Hear (speech-to-text) service for Pipecat.

Streaming STT over the PyAI Hear WebSocket. Use `PyAISTTService` in a Pipecat
pipeline; it sends pipeline audio to PyAI and pushes
`InterimTranscriptionFrame` / `TranscriptionFrame` as transcripts arrive.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncGenerator, Optional

import websockets
from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterimTranscriptionFrame,
    StartFrame,
    TranscriptionFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.services.stt_service import WebsocketSTTService
from pipecat.utils.time import time_now_iso8601
from pyai import PyAI

from ._utils import hear_stream_url, transcript_kind

# The non-secret marker offered ALONGSIDE the `pyai-key.<KEY>` credential on
# every PyAI WebSocket. RFC 6455 makes the server echo the subprotocol it
# SELECTS, so the edge selects this and never the key; and it can only select
# a value the client offered, so offering the credential alone leaves nothing
# safe to select. Defined here rather than imported from pyai-sdk: this adapter
# is installed against whatever SDK version the user already has.
REALTIME_SUBPROTOCOL_MARKER = "pyai.v1"



class PyAISTTService(WebsocketSTTService):
    """Streaming speech-to-text backed by PyAI Hear."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = "https://api.pyai.com",
        model: str = "pyai-hear",
        language: str = "",
        sample_rate: Optional[int] = None,
        **kwargs,
    ) -> None:
        super().__init__(sample_rate=sample_rate, **kwargs)
        key = api_key or os.environ.get("PYAI_API_KEY", "")
        if not key:
            raise ValueError("A PyAI API key is required (pass api_key= or set PYAI_API_KEY).")
        # Reuse the official SDK for the base URL + the WS subprotocol helper.
        self._client = PyAI(api_key=key, base_url=base_url)
        self._model_name = model
        self._language = language
        self._receive_task = None
        self._canonical_commits_pending = 0
        self._finals_pending = 0
        self._finals_drained = asyncio.Event()
        self._finals_drained.set()

    async def start(self, frame: StartFrame) -> None:
        await super().start(frame)
        await self._connect()

    async def stop(self, frame: EndFrame) -> None:
        await self._wait_for_pending_finals()
        await super().stop(frame)
        if self._websocket is not None or self._receive_task is not None:
            await self._disconnect()

    async def cancel(self, frame: CancelFrame) -> None:
        await super().cancel(frame)
        if self._websocket is not None or self._receive_task is not None:
            await self._disconnect()

    async def _connect(self) -> None:
        await super()._connect()
        await self._connect_websocket()
        if self._websocket and self._receive_task is None:
            self._receive_task = self.create_task(self._receive_task_handler(self._report_error))

    async def _disconnect(self) -> None:
        await super()._disconnect()
        if self._receive_task is not None:
            await self.cancel_task(self._receive_task, timeout=1.0)
            self._receive_task = None
        await self._disconnect_websocket()
        self._reset_pending_finals()

    async def _connect_websocket(self) -> None:
        if self._websocket:
            return
        url = hear_stream_url(
            self._client.base_url,
            model=self._model_name,
            sample_rate=self.sample_rate,
            language=self._language,
        )
        logger.debug(f"{self} connecting to PyAI Hear stream")
        self._websocket = await websockets.connect(
            url,
            subprotocols=[
                REALTIME_SUBPROTOCOL_MARKER,
                self._client.realtime_subprotocol(),
            ],
        )
        self._reset_pending_finals()
        await self._call_event_handler("on_connected")

    async def _disconnect_websocket(self) -> None:
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
            await self._call_event_handler("on_disconnected")

    async def _receive_messages(self) -> None:
        websocket = self._websocket
        if websocket is None:
            return
        async for message in websocket:
            if isinstance(message, (bytes, bytearray)):
                continue  # Hear sends transcripts as JSON text only.
            try:
                data = json.loads(message)
            except (ValueError, TypeError):
                continue

            if data.get("type") == "error":
                code = str(data.get("code") or "stream_error")
                if (
                    code == "unknown_message_type"
                    and self._canonical_commits_pending > 0
                ):
                    self._canonical_commits_pending -= 1
                    # Temporary compatibility for an older serving fleet.
                    # The canonical control remains the first attempt.
                    try:
                        await self.send_with_retry(
                            json.dumps({"type": "input_audio_buffer.commit"}),
                            self._report_error,
                        )
                    except Exception:
                        self._abandon_pending_final(canonical_attempt=False)
                        raise
                    continue
                await self.push_error_frame(
                    ErrorFrame("PyAI Hear stream error.")
                )
                continue

            kind = transcript_kind(str(data.get("type", "")))
            text = (data.get("text") or "").strip()
            if kind == "final" and data.get("endpoint_reason") in (
                None, "commit", "client_commit"
            ):
                # Automatic engine/turn-detector finals still deliver their
                # words, but cannot acknowledge a later manual VAD commit.
                # Absent reasons retain compatibility with older Hear fleets.
                self._complete_pending_final()
            if not kind or not text:
                continue

            if kind == "interim":
                await self.push_frame(
                    InterimTranscriptionFrame(
                        text, self._user_id, time_now_iso8601(), None
                    )
                )
            else:
                await self.push_frame(
                    TranscriptionFrame(
                        text,
                        self._user_id,
                        time_now_iso8601(),
                        None,
                        finalized=True,
                    )
                )
                emit_usage = getattr(self, "emit_stt_usage_metrics", None)
                if callable(emit_usage):
                    await emit_usage()

    async def _handle_vad_user_stopped_speaking(
        self, frame: VADUserStoppedSpeakingFrame
    ) -> None:
        await super()._handle_vad_user_stopped_speaking(frame)
        self._register_pending_commit()
        try:
            await self.send_with_retry(
                json.dumps({"type": "commit"}),
                self._report_error,
            )
        except Exception:
            self._abandon_pending_final()
            raise

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        await self.send_with_retry(audio, self._report_error)
        yield None

    def _reset_pending_finals(self) -> None:
        self._canonical_commits_pending = 0
        self._finals_pending = 0
        self._finals_drained.set()

    def _register_pending_commit(self) -> None:
        self._canonical_commits_pending += 1
        self._finals_pending += 1
        self._finals_drained.clear()

    def _abandon_pending_final(self, *, canonical_attempt: bool = True) -> None:
        if canonical_attempt:
            self._canonical_commits_pending = max(
                0, self._canonical_commits_pending - 1
            )
        self._finals_pending = max(0, self._finals_pending - 1)
        if self._finals_pending == 0:
            self._finals_drained.set()

    def _complete_pending_final(self) -> None:
        self._canonical_commits_pending = max(
            0, self._canonical_commits_pending - 1
        )
        self._finals_pending = max(0, self._finals_pending - 1)
        if self._finals_pending == 0:
            self._finals_drained.set()

    async def _wait_for_pending_finals(self) -> None:
        if self._finals_pending == 0:
            return
        try:
            await asyncio.wait_for(self._finals_drained.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                f"{self} disconnecting with "
                f"{self._finals_pending} final transcript(s) still pending"
            )
