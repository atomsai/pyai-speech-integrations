"""Behavior tests for the LiveKit streaming adapter."""

import asyncio
import json
import unittest
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace

import aiohttp
from livekit import rtc

from livekit.plugins.pyai import STT


class FakeWebSocket:
    def __init__(
        self,
        *,
        reject_canonical_commit: bool = False,
        auto_finalize: bool = True,
    ) -> None:
        self.sent_text: list[str] = []
        self.closed = False
        self.first_commit = asyncio.Event()
        self._messages: asyncio.Queue[object | None] = asyncio.Queue()
        self._reject_canonical_commit = reject_canonical_commit
        self._auto_finalize = auto_finalize
        self._accepted_commits = 0

    async def send_str(self, value: str) -> None:
        self.sent_text.append(value)
        self.first_commit.set()
        payload = json.loads(value)
        if (
            payload.get("type") == "commit"
            and self._reject_canonical_commit
        ):
            await self._messages.put(
                SimpleNamespace(
                    type=aiohttp.WSMsgType.TEXT,
                    data=json.dumps(
                        {
                            "type": "error",
                            "code": "unknown_message_type",
                        }
                    ),
                )
            )
            return
        self._accepted_commits += 1
        if not self._auto_finalize:
            return
        await self.queue_final(f"turn {self._accepted_commits}")

    async def queue_final(self, text: str) -> None:
        await self._messages.put(
            SimpleNamespace(
                type=aiohttp.WSMsgType.TEXT,
                data=json.dumps({"type": "final", "text": text}),
            )
        )

    async def send_bytes(self, value: bytes) -> None:
        _ = value

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            await self._messages.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self._messages.get()
        if value is None:
            raise StopAsyncIteration
        return value


class FakeSession:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.protocols: list[str] = []

    async def ws_connect(self, url: str, *, protocols: list[str]):
        self.url = url
        self.protocols = protocols
        return self.websocket


class StreamingLifecycleTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def audio_frame() -> rtc.AudioFrame:
        return rtc.AudioFrame(
            data=b"\x00\x00" * 160,
            sample_rate=16000,
            num_channels=1,
            samples_per_channel=160,
        )

    async def test_flush_reuses_socket_and_end_input_closes_after_final(self):
        websocket = FakeWebSocket()
        session = FakeSession(websocket)
        stt = STT(api_key="pyai_test_unit", http_session=session)
        stream = stt.stream()

        stream.push_frame(self.audio_frame())
        stream.flush()
        await asyncio.wait_for(websocket.first_commit.wait(), timeout=1)
        await asyncio.sleep(0)
        self.assertFalse(websocket.closed)

        stream.push_frame(self.audio_frame())
        stream.end_input()

        async def collect_events():
            return [event async for event in stream]

        events = await asyncio.wait_for(collect_events(), timeout=2)

        self.assertEqual(
            websocket.sent_text,
            [json.dumps({"type": "commit"}), json.dumps({"type": "commit"})],
        )
        self.assertTrue(websocket.closed)
        self.assertEqual(
            [
                event.alternatives[0].text
                for event in events
                if event.alternatives
            ],
            ["turn 1", "turn 2"],
        )
        # Two values, marker first: the edge echoes only the marker and must
        # never reflect the key, and it can only echo a value we offered.
        self.assertEqual(len(session.protocols), 2)
        self.assertEqual(session.protocols[0], "pyai.v1")
        self.assertTrue(session.protocols[1].startswith("pyai-key."))
        self.assertNotIn("language", parse_qs(urlsplit(session.url).query))

    async def test_explicit_language_hint_is_preserved(self):
        websocket = FakeWebSocket()
        session = FakeSession(websocket)
        stt = STT(api_key="pyai_test_unit", language="fr", http_session=session)
        stream = stt.stream()
        stream.push_frame(self.audio_frame())
        stream.end_input()
        await asyncio.wait_for(self._collect_events(stream), timeout=2)
        self.assertEqual(parse_qs(urlsplit(session.url).query)["language"], ["fr"])

    async def test_end_waits_for_every_overlapping_flush_final(self):
        websocket = FakeWebSocket(auto_finalize=False)
        session = FakeSession(websocket)
        stt = STT(api_key="pyai_test_unit", http_session=session)
        stream = stt.stream()
        collector = asyncio.create_task(self._collect_events(stream))

        stream.push_frame(self.audio_frame())
        stream.flush()
        await self._wait_for_sent_commits(websocket, 1)

        stream.push_frame(self.audio_frame())
        stream.flush()
        await self._wait_for_sent_commits(websocket, 2)

        stream.end_input()
        await asyncio.sleep(0)
        self.assertFalse(websocket.closed)

        await websocket.queue_final("first delayed final")
        await asyncio.sleep(0)
        self.assertFalse(websocket.closed)

        await websocket.queue_final("second delayed final")
        events = await asyncio.wait_for(collector, timeout=2)

        self.assertTrue(websocket.closed)
        self.assertEqual(
            [
                event.alternatives[0].text
                for event in events
                if event.alternatives
            ],
            ["first delayed final", "second delayed final"],
        )

    async def test_end_after_finalized_flush_does_not_commit_empty_audio(self):
        websocket = FakeWebSocket()
        session = FakeSession(websocket)
        stt = STT(api_key="pyai_test_unit", http_session=session)
        stream = stt.stream()

        stream.push_frame(self.audio_frame())
        stream.flush()
        await asyncio.wait_for(websocket.first_commit.wait(), timeout=1)
        await asyncio.sleep(0)
        stream.end_input()

        events = await asyncio.wait_for(
            asyncio.create_task(self._collect_events(stream)),
            timeout=2,
        )

        self.assertEqual(
            websocket.sent_text,
            [json.dumps({"type": "commit"})],
        )
        self.assertTrue(websocket.closed)
        self.assertEqual(
            [
                event.alternatives[0].text
                for event in events
                if event.alternatives
            ],
            ["turn 1"],
        )

    async def test_unknown_canonical_commit_falls_back_to_legacy_alias(self):
        websocket = FakeWebSocket(reject_canonical_commit=True)
        session = FakeSession(websocket)
        stt = STT(api_key="pyai_test_unit", http_session=session)
        stream = stt.stream()

        stream.push_frame(self.audio_frame())
        stream.end_input()
        events = await asyncio.wait_for(
            asyncio.create_task(self._collect_events(stream)),
            timeout=2,
        )

        self.assertEqual(
            websocket.sent_text,
            [
                json.dumps({"type": "commit"}),
                json.dumps({"type": "input_audio_buffer.commit"}),
            ],
        )
        self.assertTrue(websocket.closed)
        self.assertEqual(
            [
                event.alternatives[0].text
                for event in events
                if event.alternatives
            ],
            ["turn 1"],
        )

    @staticmethod
    async def _collect_events(stream):
        return [event async for event in stream]

    @staticmethod
    async def _wait_for_sent_commits(
        websocket: FakeWebSocket, expected: int
    ) -> None:
        async def wait() -> None:
            while len(websocket.sent_text) < expected:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait(), timeout=1)


if __name__ == "__main__":
    unittest.main()
