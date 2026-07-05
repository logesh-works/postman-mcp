"""The safety subsystem — snapshots, audit log, rollback."""

from __future__ import annotations

from postman_mcp.safety.audit import append_event, read_events
from postman_mcp.safety.rollback import diff_rollback, render_rollback_preview
from postman_mcp.safety.snapshots import list_snapshots, load_snapshot, save_snapshot


def test_snapshot_save_and_load_round_trip(tmp_path):
    collection = {"info": {"name": "X"}, "item": [{"name": "a"}]}
    snap_id = save_snapshot(collection, "col-1", tmp_path, label="test")
    loaded = load_snapshot(snap_id, tmp_path)
    assert loaded["collection"] == collection
    assert loaded["collection_id"] == "col-1"


def test_snapshot_retention_prunes_oldest(tmp_path):
    collection = {"info": {"name": "X"}, "item": []}
    ids = [save_snapshot(collection, "col-1", tmp_path, retention=3) for _ in range(5)]
    remaining = list_snapshots(tmp_path, collection_id="col-1", limit=10)
    assert len(remaining) == 3
    remaining_ids = {e["snapshot_id"] for e in remaining}
    # The newest 3 survive; the oldest 2 are pruned.
    assert remaining_ids == set(ids[-3:])


def test_audit_append_and_read(tmp_path):
    append_event(tmp_path, "submit", model_id="sha256:abc", outcome="ok")
    append_event(tmp_path, "apply", plan_id="p1", outcome="ok", endpoints={"new": 1})
    events = read_events(tmp_path, last=10)
    assert len(events) == 2
    assert events[0]["event"] == "submit"
    assert events[1]["endpoints"] == {"new": 1}


def test_audit_read_respects_last_n(tmp_path):
    for i in range(5):
        append_event(tmp_path, f"event{i}")
    events = read_events(tmp_path, last=2)
    assert [e["event"] for e in events] == ["event3", "event4"]


def test_audit_log_is_append_only_and_never_mutated(tmp_path):
    append_event(tmp_path, "first")
    events_before = read_events(tmp_path, last=10)
    append_event(tmp_path, "second")
    events_after = read_events(tmp_path, last=10)
    assert events_after[0] == events_before[0]
    assert len(events_after) == 2


def test_diff_rollback_detects_added_removed_changed():
    snapshot = {"item": [
        {"name": "A", "request": {"method": "GET", "url": "{{base_url}}/a"}},
        {"name": "B", "request": {"method": "GET", "url": "{{base_url}}/b"}},
    ]}
    current = {"item": [
        {"name": "A changed", "request": {"method": "GET", "url": "{{base_url}}/a"}},
        {"name": "C", "request": {"method": "GET", "url": "{{base_url}}/c"}},
    ]}
    diff = diff_rollback(current, snapshot)
    assert diff["restore"] == ["GET:/b"]         # in snapshot, missing now
    assert diff["revert_delete"] == ["GET:/c"]   # added since the snapshot
    assert diff["revert_modify"] == ["GET:/a"]   # changed since the snapshot


def test_render_rollback_preview_reports_no_difference():
    text = render_rollback_preview("snap-1", {"restore": [], "revert_delete": [], "revert_modify": []})
    assert "No difference" in text


def test_render_rollback_preview_lists_changes():
    text = render_rollback_preview("snap-1", {"restore": ["GET:/x"], "revert_delete": [], "revert_modify": []})
    assert "GET:/x" in text
    assert "Restore? [y / n]" in text
