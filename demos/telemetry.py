"""Opt-in JSONL demo events. Never record audio, transcripts, keys or exceptions."""

import json
import os
import uuid
from datetime import datetime, timezone


class Activation:
    def __init__(self, source):
        self.source = source
        self.session = uuid.uuid4().hex
        self.path = os.environ.get("PYAI_DEMO_EVENTS")
        self.seen = set()

    def emit(self, event):
        if not self.path or event in self.seen:
            return
        if event not in {
            "session_started",
            "transcription_succeeded",
            "speech_started",
            "interruption_observed",
            "session_closed",
        }:
            raise ValueError("Unknown activation event")
        self.seen.add(event)
        row = {
            "version": 1,
            "at": datetime.now(timezone.utc).isoformat(),
            "source": self.source,
            "session": self.session,
            "event": event,
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(row) + "\n")
