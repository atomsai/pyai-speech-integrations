"""PyAI Hear (speech-to-text) for LiveKit Agents.

Streaming STT over the PyAI Hear WebSocket, plus a batch `recognize()` fallback
over the sync transcription endpoint. Use as `pyai.STT(...)` in an AgentSession.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, replace

import aiohttp
from livekit import rtc
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    NotGivenOr,
    stt,
    utils,
)
from livekit.agents.stt import (
    RecognizeStream,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
    STTCapabilities,
)
from livekit.agents.utils import AudioBuffer
from pyai import PyAI

from ._utils import hear_stream_url, transcript_kind, transcriptions_url
from .log import logger

# The non-secret marker offered ALONGSIDE the `pyai-key.<KEY>` credential on
# every PyAI WebSocket. RFC 6455 makes the server echo the subprotocol it
# SELECTS, so the edge selects this and never the key; and it can only select
# a value the client offered, so offering the credential alone leaves nothing
# safe to select. Defined here rather than imported from pyai-sdk: this adapter
# is installed against whatever SDK version the user already has.
REALTIME_SUBPROTOCOL_MARKER = "pyai.v1"


DEFAULT_SAMPLE_RATE = 16000


@dataclass
class _STTOptions:
    model: str
    language: str
    sample_rate: int


class STT(stt.STT):
    def __init__(
        self,
        *,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: str = "https://api.pyai.com",
        model: str = "pyai-hear",
        language: str = "",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(capabilities=STTCapabilities(streaming=True, interim_results=True))
        key = api_key if isinstance(api_key, str) and api_key else os.environ.get("PYAI_API_KEY", "")
        if not key:
            raise ValueError("A PyAI API key is required (pass api_key= or set PYAI_API_KEY).")
        # Reuse the official SDK for the base URL + the WS subprotocol helper.
        self._client = PyAI(api_key=key, base_url=base_url)
        self._opts = _STTOptions(model=model, language=language, sample_rate=sample_rate)
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

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> SpeechEvent:
        lang = language if isinstance(language, str) and language else self._opts.language
        wav = rtc.combine_audio_frames(buffer).to_wav_bytes()

        form = aiohttp.FormData()
        form.add_field("model", self._opts.model)
        if lang:
            form.add_field("language", lang)
        form.add_field("file", wav, filename="audio.wav", content_type="audio/wav")

        try:
            async with self._ensure_session().post(
                transcriptions_url(self._client.base_url),
                headers={"Authorization": f"Bearer {self._client.api_key}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=conn_options.timeout),
            ) as resp:
                if resp.status != 200:
                    raise APIStatusError(
                        message="PyAI Hear transcription failed.", status_code=resp.status
                    )
                data = await resp.json()
        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except aiohttp.ClientError as e:
            raise APIConnectionError() from e

        text = (data.get("text") or "") if isinstance(data, dict) else ""
        detected_language = (data.get("language") or lang) if isinstance(data, dict) else lang
        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[SpeechData(language=detected_language, text=text)],
        )

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SpeechStream":
        lang = language if isinstance(language, str) and language else self._opts.language
        return SpeechStream(
            stt=self,
            conn_options=conn_options,
            client=self._client,
            opts=replace(self._opts, language=lang),
            session=self._ensure_session(),
        )


class SpeechStream(RecognizeStream):
    def __init__(
        self,
        *,
        stt: STT,
        conn_options: APIConnectOptions,
        client: PyAI,
        opts: _STTOptions,
        session: aiohttp.ClientSession,
    ) -> None:
        # Ask the base to resample inbound frames to the rate PyAI Hear expects.
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=opts.sample_rate)
        self._client = client
        self._opts = opts
        self._session = session

    async def _run(self) -> None:
        url = hear_stream_url(
            self._client.base_url,
            model=self._opts.model,
            sample_rate=self._opts.sample_rate,
            language=self._opts.language,
        )
        try:
            ws = await self._session.ws_connect(
                url,
                protocols=[
                    REALTIME_SUBPROTOCOL_MARKER,
                    self._client.realtime_subprotocol(),
                ],
            )
        except aiohttp.WSServerHandshakeError as e:
            raise APIStatusError(
                message="PyAI Hear stream handshake failed.",
                status_code=e.status,
                retryable=e.status >= 500,
            ) from e
        except aiohttp.ClientError as e:
            raise APIConnectionError("failed to connect to PyAI Hear stream") from e

        speaking = False
        canonical_commits_pending = 0
        finals_pending = 0
        finals_drained = asyncio.Event()
        finals_drained.set()

        def register_commit() -> None:
            nonlocal canonical_commits_pending, finals_pending
            canonical_commits_pending += 1
            finals_pending += 1
            finals_drained.clear()

        def abandon_commit(*, canonical_attempt: bool = True) -> None:
            nonlocal canonical_commits_pending, finals_pending
            if canonical_attempt:
                canonical_commits_pending = max(
                    0, canonical_commits_pending - 1
                )
            finals_pending = max(0, finals_pending - 1)
            if finals_pending == 0:
                finals_drained.set()

        def complete_final() -> None:
            nonlocal canonical_commits_pending, finals_pending
            canonical_commits_pending = max(0, canonical_commits_pending - 1)
            finals_pending = max(0, finals_pending - 1)
            if finals_pending == 0:
                finals_drained.set()

        async def wait_for_pending_finals() -> None:
            if finals_pending == 0:
                return
            try:
                await asyncio.wait_for(
                    finals_drained.wait(),
                    timeout=max(1.0, self._conn_options.timeout),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "PyAI Hear stream closed with %d final transcript(s) still pending",
                    finals_pending,
                )

        async def send_audio() -> None:
            has_uncommitted_audio = False
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    ending = self._input_ch.closed
                    if has_uncommitted_audio:
                        register_commit()
                        try:
                            await ws.send_str(json.dumps({"type": "commit"}))
                        except Exception:
                            abandon_commit()
                            raise
                        has_uncommitted_audio = False
                    if ending:
                        await wait_for_pending_finals()
                        await ws.close()
                        return
                    continue
                await ws.send_bytes(data.data.tobytes())
                has_uncommitted_audio = True

        async def recv_events() -> None:
            nonlocal canonical_commits_pending, speaking
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                try:
                    d = json.loads(msg.data)
                except (ValueError, TypeError):
                    continue
                if d.get("type") == "error":
                    code = str(d.get("code") or "stream_error")
                    if (
                        code == "unknown_message_type"
                        and canonical_commits_pending > 0
                    ):
                        canonical_commits_pending -= 1
                        # Temporary compatibility for an older serving fleet.
                        # The canonical control remains the first attempt.
                        try:
                            await ws.send_str(
                                json.dumps({"type": "input_audio_buffer.commit"})
                            )
                        except Exception:
                            abandon_commit(canonical_attempt=False)
                            raise
                        continue
                    raise APIStatusError(
                        message=f"PyAI Hear stream error ({code}).",
                        status_code=400,
                        body=d,
                        retryable=False,
                    )
                kind = transcript_kind(str(d.get("type", "")))
                if kind == "final":
                    complete_final()
                text = (d.get("text") or "").strip()
                if not kind or not text:
                    continue
                if not speaking:
                    speaking = True
                    self._event_ch.send_nowait(SpeechEvent(type=SpeechEventType.START_OF_SPEECH))
                speech = SpeechEvent(
                    type=(
                        SpeechEventType.FINAL_TRANSCRIPT
                        if kind == "final"
                        else SpeechEventType.INTERIM_TRANSCRIPT
                    ),
                    alternatives=[SpeechData(language=self._opts.language, text=text)],
                )
                self._event_ch.send_nowait(speech)
                if kind == "final" and speaking:
                    speaking = False
                    self._event_ch.send_nowait(SpeechEvent(type=SpeechEventType.END_OF_SPEECH))

        tasks = [
            asyncio.create_task(send_audio()),
            asyncio.create_task(recv_events()),
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            await utils.aio.cancel_and_wait(*tasks)
            await ws.close()
            logger.debug("PyAI Hear stream closed")
