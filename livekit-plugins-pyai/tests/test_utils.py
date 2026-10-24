"""Unit tests for the livekit-free helpers.

We load `_utils.py` by path so the suite runs without installing the (heavy)
livekit-agents framework that the STT/TTS classes import.
"""

import importlib.util
import os
import unittest

_UTILS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "livekit", "plugins", "pyai", "_utils.py"
)


def _load_utils():
    spec = importlib.util.spec_from_file_location("pyai_lk_utils", _UTILS_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


u = _load_utils()


class TestUtils(unittest.TestCase):
    def test_ws_base(self):
        self.assertEqual(u.ws_base("https://api.pyai.com"), "wss://api.pyai.com")
        self.assertEqual(u.ws_base("http://localhost:8080/"), "ws://localhost:8080")

    def test_hear_stream_url(self):
        url = u.hear_stream_url("https://api.pyai.com", model="pyai-hear", sample_rate=16000, language="en")
        self.assertTrue(url.startswith("wss://api.pyai.com/v1/audio/transcriptions/stream?"))
        self.assertIn("protocol=pyai-hear-v1", url)
        self.assertIn("model=pyai-hear", url)
        self.assertIn("sample_rate=16000", url)
        self.assertIn("encoding=pcm16", url)
        self.assertIn("interim_results=true", url)
        self.assertIn("language=en", url)

    def test_hear_stream_url_omits_language_when_absent(self):
        url = u.hear_stream_url("https://api.pyai.com", model="pyai-hear", sample_rate=24000)
        self.assertNotIn("language=", url)

    def test_speech_and_transcriptions_url(self):
        self.assertEqual(u.speech_url("https://api.pyai.com/"), "https://api.pyai.com/v1/audio/speech")
        self.assertEqual(
            u.transcriptions_url("https://api.pyai.com"), "https://api.pyai.com/v1/audio/transcriptions"
        )

    def test_transcript_kind(self):
        self.assertEqual(u.transcript_kind("final"), "final")
        self.assertEqual(u.transcript_kind("partial"), "interim")
        self.assertEqual(u.transcript_kind("speech_final"), "interim")
        self.assertIsNone(u.transcript_kind("error"))
        self.assertIsNone(u.transcript_kind(""))


if __name__ == "__main__":
    unittest.main()
