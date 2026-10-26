"""Behavior tests for the Pipecat STT and TTS services."""

import asyncio
import json
import unittest
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pipecat.frames.frames import (
    EndFrame,
    StartFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSSpeakFrame,
    TranscriptionFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from pipecat_pyai import PyAISTTService, PyAITTSService


class FakeWebSocket:
    def __init__(self, messages=None) -> None:
        self.sent: list[object] = []
        self.closed = False
        self._messages = asyncio.Queue()
        for message in messages or []:
            self._messages.put_nowait(message)
        if messages is not None:
            self._messages.put_nowait(None)

    async def send(self, value) -> None:
        self.sent.append(value)

    async def close(self) -> None:
        self.closed = True
        await self._messages.put(None)

    async def queue_message(self, message: str) -> None:
        await self._messages.put(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self._messages.get()
        if value is None:
            raise StopAsyncIteration
        return value


async def cancel_task(task, timeout=None):
    _ = timeout
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class STTServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_starts_receive_task_and_disconnect_cleans_up(self):
        websocket = FakeWebSocket()
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service.create_task = lambda coroutine, name=None: asyncio.create_task(
            coroutine, name=name
        )
        service.cancel_task = cancel_task

        with patch(
            "pipecat_pyai.stt.websockets.connect",
            new=AsyncMock(return_value=websocket),
        ) as connect_mock:
            await service._connect()
            self.assertEqual(
                connect_mock.call_args.kwargs["subprotocols"],
                ["pyai.v1", "pyai-key.pyai_test_unit"],
            )
            self.assertNotIn(
                "language", parse_qs(urlsplit(connect_mock.call_args.args[0]).query)
            )
            self.assertIsNotNone(service._receive_task)
            await service._disconnect()

        self.assertTrue(websocket.closed)
        self.assertIsNone(service._receive_task)

    async def test_explicit_language_hint_is_preserved(self):
        websocket = FakeWebSocket()
        service = PyAISTTService(
            api_key="pyai_test_unit", language="fr", sample_rate=16000
        )
        with patch(
            "pipecat_pyai.stt.websockets.connect",
            new=AsyncMock(return_value=websocket),
        ) as connect_mock:
            await service._connect_websocket()
            query = parse_qs(urlsplit(connect_mock.call_args.args[0]).query)
            self.assertEqual(query["language"], ["fr"])
            await service._disconnect_websocket()

    async def test_stop_and_cancel_disconnect_once_across_pipecat_versions(self):
        for method_name in ("stop", "cancel"):
            with self.subTest(method_name=method_name):
                service = PyAISTTService(
                    api_key="pyai_test_unit",
                    sample_rate=16000,
                )
                service._websocket = object()

                async def clear_connection_state():
                    service._websocket = None
                    service._receive_task = None

                disconnect = AsyncMock(side_effect=clear_connection_state)
                with patch.object(service, "_disconnect", new=disconnect):
                    await getattr(service, method_name)(object())

                disconnect.assert_awaited_once()

    async def test_stop_waits_for_pending_final_before_disconnect(self):
        websocket = FakeWebSocket()
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._websocket = websocket
        service._user_id = "caller-1"
        service.push_frame = AsyncMock()
        service.cancel_task = cancel_task
        service._receive_task = asyncio.create_task(service._receive_messages())

        await service._handle_vad_user_stopped_speaking(VADUserStoppedSpeakingFrame())
        stop_task = asyncio.create_task(service.stop(EndFrame()))
        await asyncio.sleep(0)

        self.assertFalse(stop_task.done())
        self.assertFalse(websocket.closed)

        await websocket.queue_message(
            json.dumps({"type": "final", "text": "delayed final"})
        )
        await asyncio.wait_for(stop_task, timeout=1)

        self.assertTrue(websocket.closed)
        finals = [
            call.args[0]
            for call in service.push_frame.await_args_list
            if isinstance(call.args[0], TranscriptionFrame)
        ]
        self.assertEqual([frame.text for frame in finals], ["delayed final"])

    async def test_automatic_final_does_not_close_before_requested_commit_final(self):
        websocket = FakeWebSocket()
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._websocket = websocket
        service._user_id = "caller-1"
        service.push_frame = AsyncMock()
        service.cancel_task = cancel_task
        service._receive_task = asyncio.create_task(service._receive_messages())
        stop_task = None
        try:
            await service._handle_vad_user_stopped_speaking(
                VADUserStoppedSpeakingFrame()
            )
            stop_task = asyncio.create_task(service.stop(EndFrame()))
            await websocket.queue_message(
                json.dumps(
                    {
                        "type": "final",
                        "text": "Earlier words.",
                        "endpoint_reason": "endpoint",
                    }
                )
            )
            for _ in range(10):
                await asyncio.sleep(0)
            self.assertFalse(stop_task.done())
            self.assertFalse(websocket.closed)
            self.assertEqual(service._finals_pending, 1)
            await websocket.queue_message(
                json.dumps(
                    {
                        "type": "final",
                        "text": "Quiet suffix.",
                        "endpoint_reason": "client_commit",
                    }
                )
            )
            await asyncio.wait_for(stop_task, 1)
            finals = [
                call.args[0].text
                for call in service.push_frame.await_args_list
                if isinstance(call.args[0], TranscriptionFrame)
            ]
            self.assertEqual(finals, ["Earlier words.", "Quiet suffix."])
            self.assertTrue(websocket.closed)
        finally:
            if stop_task is not None:
                stop_task.cancel()
                await asyncio.gather(stop_task, return_exceptions=True)
            await service._disconnect()

    async def test_only_commit_finals_release_manual_completion_slots(self):
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._user_id = "caller-1"
        service.push_frame = AsyncMock()
        service._register_pending_commit()
        service._register_pending_commit()
        for reason in ("endpoint", "max_utterance", "peak_te_early", "eof"):
            service._websocket = FakeWebSocket(
                [
                    json.dumps(
                        {"type": "final", "text": reason, "endpoint_reason": reason}
                    )
                ]
            )
            await service._receive_messages()
            self.assertEqual(service._finals_pending, 2)
        for reason, remaining in (("client_commit", 1), ("commit", 0)):
            service._websocket = FakeWebSocket(
                [json.dumps({"type": "final", "text": "", "endpoint_reason": reason})]
            )
            await service._receive_messages()
            self.assertEqual(service._finals_pending, remaining)
        self.assertTrue(service._finals_drained.is_set())

    async def test_vad_stop_sends_canonical_commit(self):
        websocket = FakeWebSocket()
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._websocket = websocket

        await service._handle_vad_user_stopped_speaking(VADUserStoppedSpeakingFrame())

        self.assertEqual(
            websocket.sent,
            [json.dumps({"type": "commit"})],
        )

    async def test_final_transcript_is_marked_finalized(self):
        websocket = FakeWebSocket(
            [json.dumps({"type": "final", "text": "hello there"})]
        )
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._websocket = websocket
        service._user_id = "caller-1"
        pushed = []

        async def capture(frame, direction=None):
            _ = direction
            pushed.append(frame)

        service.push_frame = capture
        service.emit_stt_usage_metrics = AsyncMock()

        await service._receive_messages()

        finals = [frame for frame in pushed if isinstance(frame, TranscriptionFrame)]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0].text, "hello there")
        self.assertEqual(finals[0].user_id, "caller-1")
        self.assertTrue(finals[0].finalized)
        service.emit_stt_usage_metrics.assert_awaited_once()

    async def test_final_transcript_does_not_require_usage_metrics_api(self):
        websocket = FakeWebSocket(
            [json.dumps({"type": "final", "text": "minimum compatible"})]
        )
        service = PyAISTTService(api_key="pyai_test_unit", sample_rate=16000)
        service._websocket = websocket
        service._user_id = "caller-1"
        service.push_frame = AsyncMock()
        service.emit_stt_usage_metrics = None

        await service._receive_messages()

        finals = [
            call.args[0]
            for call in service.push_frame.await_args_list
            if isinstance(call.args[0], TranscriptionFrame)
        ]
        self.assertEqual([frame.text for frame in finals], ["minimum compatible"])

    async def test_unknown_canonical_commit_falls_back_to_legacy_alias(self):
        websocket = FakeWebSocket(
            [
                json.dumps(
                    {
                        "type": "error",
                        "code": "unknown_message_type",
                    }
                ),
                json.dumps({"type": "final", "text": "fallback worked"}),
            ]
        )
        service = PyAISTTService(
            api_key="pyai_test_unit",
            sample_rate=16000,
        )
        service._websocket = websocket
        service._user_id = "caller-1"
        service.push_frame = AsyncMock()
        service.push_error_frame = AsyncMock()
        service.emit_stt_usage_metrics = AsyncMock()

        await service._handle_vad_user_stopped_speaking(VADUserStoppedSpeakingFrame())
        await service._receive_messages()

        self.assertEqual(
            websocket.sent,
            [
                json.dumps({"type": "commit"}),
                json.dumps({"type": "input_audio_buffer.commit"}),
            ],
        )
        service.push_error_frame.assert_not_awaited()
        finals = [
            call.args[0]
            for call in service.push_frame.await_args_list
            if isinstance(call.args[0], TranscriptionFrame)
        ]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0].text, "fallback worked")


class FakeContent:
    async def iter_chunked(self, size):
        _ = size
        yield b"\x01\x02"
        yield b"\x03\x04"


class FakeEmptyContent:
    async def iter_chunked(self, size):
        _ = size
        if False:
            yield b""


class FakeResponse:
    status = 200
    content = FakeContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        _ = (exc_type, exc, traceback)


class FakeEmptyResponse(FakeResponse):
    content = FakeEmptyContent()


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()

    def post(self, *args, **kwargs):
        _ = (args, kwargs)
        return self.response


class TTSServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_frames_keep_context_id(self):
        service = PyAITTSService(
            api_key="pyai_test_unit",
            voice="stock_emma_en_gb",
            sample_rate=24000,
            aiohttp_session=FakeSession(),
        )
        service._sample_rate = 24000
        service.start_ttfb_metrics = AsyncMock()
        service.stop_ttfb_metrics = AsyncMock()
        service.start_tts_usage_metrics = AsyncMock()

        frames = [
            frame
            async for frame in service.run_tts(
                "hello",
                context_id="turn-1",
            )
        ]

        audio = [frame for frame in frames if isinstance(frame, TTSAudioRawFrame)]
        self.assertEqual(len(audio), 2)
        self.assertTrue(all(frame.context_id == "turn-1" for frame in audio))
        service.stop_ttfb_metrics.assert_not_awaited()

    async def test_pipeline_routes_audio_through_a_created_context(self):
        service = PyAITTSService(
            api_key="pyai_test_unit",
            voice="stock_emma_en_gb",
            sample_rate=24000,
            aiohttp_session=FakeSession(),
            reuse_context_id_within_turn=False,
            stop_frame_timeout_s=0.05,
        )
        service.start_ttfb_metrics = AsyncMock()
        service.stop_ttfb_metrics = AsyncMock()
        service.start_tts_usage_metrics = AsyncMock()
        service.push_error_frame = AsyncMock()
        service.create_task = lambda coroutine, name=None: asyncio.create_task(
            coroutine,
            name=name,
        )
        service.cancel_task = cancel_task
        service.get_clock = lambda: SimpleNamespace(get_time=lambda: 0)
        pushed = []
        finished = asyncio.Event()

        async def capture(frame, direction=FrameDirection.DOWNSTREAM):
            _ = direction
            pushed.append(frame)
            if isinstance(frame, TTSStoppedFrame):
                finished.set()

        service.push_frame = capture

        await service.start(StartFrame(audio_out_sample_rate=24000))
        await service.process_frame(
            TTSSpeakFrame("hello"),
            FrameDirection.DOWNSTREAM,
        )
        await asyncio.wait_for(finished.wait(), timeout=2)
        await service.stop(EndFrame())

        audio = [frame for frame in pushed if isinstance(frame, TTSAudioRawFrame)]
        self.assertEqual(len(audio), 2)
        self.assertTrue(any(isinstance(frame, TTSStartedFrame) for frame in pushed))
        self.assertTrue(any(isinstance(frame, TTSStoppedFrame) for frame in pushed))
        self.assertFalse(
            service.get_audio_contexts()
            if hasattr(service, "get_audio_contexts")
            else service._audio_contexts
        )
        service.start_ttfb_metrics.assert_awaited_once()
        service.stop_ttfb_metrics.assert_awaited_once()
        service.push_error_frame.assert_not_awaited()

    async def test_empty_success_response_stops_ttfb_metrics(self):
        service = PyAITTSService(
            api_key="pyai_test_unit",
            voice="stock_emma_en_gb",
            sample_rate=24000,
            aiohttp_session=FakeSession(FakeEmptyResponse()),
        )
        service._sample_rate = 24000
        service.start_ttfb_metrics = AsyncMock()
        service.stop_ttfb_metrics = AsyncMock()
        service.start_tts_usage_metrics = AsyncMock()

        frames = [
            frame
            async for frame in service.run_tts(
                "hello",
                context_id="turn-empty",
            )
        ]

        self.assertEqual(frames, [])
        service.stop_ttfb_metrics.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
