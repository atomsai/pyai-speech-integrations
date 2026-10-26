import json
import os
import tempfile
import unittest
from unittest.mock import patch
from telemetry import Activation


class ActivationTests(unittest.TestCase):
    def test_explicit_opt_in_and_first_occurrence_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "events.jsonl")
            with patch.dict(os.environ, {"PYAI_DEMO_EVENTS": path}):
                log = Activation("livekit")
                log.emit("session_started")
                log.emit("session_started")
                log.emit("transcription_succeeded")
            with open(path) as f:
                rows = [json.loads(line) for line in f]
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                set(rows[0]), {"version", "at", "source", "session", "event"}
            )
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_unknown_event_rejected(self):
        with patch.dict(os.environ, {"PYAI_DEMO_EVENTS": "unused"}):
            with self.assertRaises(ValueError):
                Activation("pipecat").emit("paid_customer")


if __name__ == "__main__":
    unittest.main()
