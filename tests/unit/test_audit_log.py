"""Unit tests for SessionAuditLog and AuditEvent classes."""
import json
import time
import threading
from datetime import datetime
from pathlib import Path
import pytest
from openai_apis import SessionAuditLog, AuditEvent


class TestAuditEvent:
    """Test cases for AuditEvent dataclass."""

    def test_creation_with_all_fields(self):
        """AuditEvent stores all fields correctly."""
        now = datetime.utcnow()
        event = AuditEvent(
            timestamp=now,
            session_id="test-session-123",
            event_type="test.event",
            data={"key": "value"},
            duration_ms=42.5,
        )
        assert event.timestamp == now
        assert event.session_id == "test-session-123"
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}
        assert event.duration_ms == 42.5

    def test_creation_with_defaults(self):
        """duration_ms defaults to None."""
        now = datetime.utcnow()
        event = AuditEvent(
            timestamp=now,
            session_id="test-session-456",
            event_type="test.event",
            data={"foo": "bar"},
        )
        assert event.duration_ms is None
        assert event.data == {"foo": "bar"}


class TestSessionAuditLog:
    """Test cases for SessionAuditLog class."""

    def test_init_stores_session_id(self):
        """session_id property returns the ID passed to __init__."""
        audit_log = SessionAuditLog("my-session-id")
        assert audit_log.session_id == "my-session-id"

    def test_log_appends_event(self):
        """log() creates an AuditEvent and appends it to events."""
        audit_log = SessionAuditLog("session-123")
        audit_log.log("event.type", {"data": "value"})

        events = audit_log.events
        assert len(events) == 1
        assert events[0].session_id == "session-123"
        assert events[0].event_type == "event.type"
        assert events[0].data == {"data": "value"}
        assert events[0].duration_ms is None
        assert isinstance(events[0].timestamp, datetime)

    def test_log_default_data(self):
        """log() with no data arg uses empty dict."""
        audit_log = SessionAuditLog("session-456")
        audit_log.log("event.type")

        events = audit_log.events
        assert len(events) == 1
        assert events[0].data == {}

    def test_log_with_duration(self):
        """log() stores duration_ms when provided."""
        audit_log = SessionAuditLog("session-789")
        audit_log.log("event.type", {"key": "value"}, duration_ms=123.45)

        events = audit_log.events
        assert len(events) == 1
        assert events[0].duration_ms == 123.45

    def test_events_returns_copy(self):
        """events property returns a copy, not the internal list."""
        audit_log = SessionAuditLog("session-abc")
        audit_log.log("event1")

        events1 = audit_log.events
        events2 = audit_log.events

        # Different objects
        assert events1 is not events2

        # But same content
        assert len(events1) == len(events2) == 1

        # Modifying returned list doesn't affect internal state
        events1.append("fake")
        assert len(audit_log.events) == 1

    def test_multiple_events_ordered(self):
        """Events are stored in insertion order."""
        audit_log = SessionAuditLog("session-xyz")
        audit_log.log("event.first", {"n": 1})
        audit_log.log("event.second", {"n": 2})
        audit_log.log("event.third", {"n": 3})

        events = audit_log.events
        assert len(events) == 3
        assert events[0].event_type == "event.first"
        assert events[1].event_type == "event.second"
        assert events[2].event_type == "event.third"

    def test_export_json_structure(self):
        """export_json() returns valid JSON with session_id and events array."""
        audit_log = SessionAuditLog("session-json")
        audit_log.log("event.one", {"foo": "bar"}, duration_ms=10.5)
        audit_log.log("event.two", {"baz": 42})

        json_str = audit_log.export_json()
        data = json.loads(json_str)

        assert data["session_id"] == "session-json"
        assert len(data["events"]) == 2

        # First event
        assert data["events"][0]["event_type"] == "event.one"
        assert data["events"][0]["session_id"] == "session-json"
        assert data["events"][0]["data"] == {"foo": "bar"}
        assert data["events"][0]["duration_ms"] == 10.5
        assert "timestamp" in data["events"][0]

        # Second event
        assert data["events"][1]["event_type"] == "event.two"
        assert data["events"][1]["data"] == {"baz": 42}
        assert data["events"][1]["duration_ms"] is None

    def test_export_json_empty(self):
        """export_json() with no events returns empty events array."""
        audit_log = SessionAuditLog("empty-session")
        json_str = audit_log.export_json()
        data = json.loads(json_str)

        assert data["session_id"] == "empty-session"
        assert data["events"] == []

    def test_export_to_file(self, tmp_path):
        """export_to_file() writes JSON to the given path."""
        audit_log = SessionAuditLog("file-session")
        audit_log.log("test.event", {"test": "data"})

        output_file = tmp_path / "audit.json"
        audit_log.export_to_file(output_file)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["session_id"] == "file-session"
        assert len(data["events"]) == 1

    def test_export_to_file_creates_parent_dirs(self, tmp_path):
        """export_to_file() creates parent directories if missing."""
        audit_log = SessionAuditLog("nested-session")
        audit_log.log("test.event")

        output_file = tmp_path / "deep" / "nested" / "path" / "audit.json"
        audit_log.export_to_file(output_file)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["session_id"] == "nested-session"


class TestPerformanceContext:
    """Test cases for _PerformanceContext via measure() method."""

    def test_measure_logs_duration(self):
        """measure() context manager logs event with duration_ms > 0."""
        audit_log = SessionAuditLog("perf-session")

        with audit_log.measure("operation.test"):
            time.sleep(0.01)  # Sleep for 10ms

        events = audit_log.events
        assert len(events) == 1
        assert events[0].event_type == "operation.test"
        assert events[0].duration_ms is not None
        assert events[0].duration_ms >= 10.0  # At least 10ms

    def test_measure_with_data(self):
        """measure() passes data through to the logged event."""
        audit_log = SessionAuditLog("perf-session-2")

        with audit_log.measure("operation.with_data", {"endpoint": "/test"}):
            pass

        events = audit_log.events
        assert len(events) == 1
        assert events[0].data == {"endpoint": "/test"}
        assert events[0].duration_ms is not None

    def test_measure_on_exception(self):
        """measure() logs event with error info when exception occurs."""
        audit_log = SessionAuditLog("perf-session-3")

        with pytest.raises(ValueError, match="test error"):
            with audit_log.measure("operation.failure", {"task": "fail"}):
                raise ValueError("test error")

        events = audit_log.events
        assert len(events) == 1
        assert events[0].data["task"] == "fail"
        assert events[0].data["error"] == "test error"
        assert events[0].duration_ms is not None

    def test_measure_does_not_suppress_exception(self):
        """Exception inside measure() context propagates."""
        audit_log = SessionAuditLog("perf-session-4")

        with pytest.raises(RuntimeError, match="propagated"):
            with audit_log.measure("operation.error"):
                raise RuntimeError("propagated")


class TestThreadSafety:
    """Test cases for thread safety of SessionAuditLog."""

    def test_concurrent_logging(self):
        """Multiple threads can log events concurrently without data loss."""
        audit_log = SessionAuditLog("thread-session")
        num_threads = 10
        events_per_thread = 50

        def log_events(thread_id):
            for i in range(events_per_thread):
                audit_log.log(f"thread.{thread_id}.event", {"index": i})

        threads = [
            threading.Thread(target=log_events, args=(tid,))
            for tid in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = audit_log.events
        expected_count = num_threads * events_per_thread
        assert len(events) == expected_count

        # Verify no events were lost by checking unique thread IDs
        thread_ids = set()
        for event in events:
            # Extract thread ID from event_type like "thread.5.event"
            parts = event.event_type.split(".")
            if len(parts) >= 2:
                thread_ids.add(int(parts[1]))

        assert len(thread_ids) == num_threads
