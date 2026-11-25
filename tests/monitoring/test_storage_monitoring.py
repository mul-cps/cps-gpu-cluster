import importlib.util
from pathlib import Path

MONITORING = Path(__file__).resolve().parents[2] / (
    "cluster-maintenance/clusters/cit-cps-gpu/system/observability/monitoring"
)


def load(name):
    spec = importlib.util.spec_from_file_location(name, MONITORING / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_longhorn_allocation_uses_reserved_space_and_live_settings():
    exporter = load("storage_exporter")
    gib = 1024**3
    assert exporter.scheduled_headroom(500*gib, 150*gib, 694*gib, 200) == 6*gib
    assert exporter.scheduled_headroom(500*gib, 150*gib, 710*gib, 200) == -10*gib
    assert exporter.physical_headroom(500*gib, 50*gib, 10) == 0


def test_digest_window_includes_weekend_and_handles_dst(monkeypatch):
    monkeypatch.syspath_prepend(str(MONITORING))
    from datetime import datetime
    from zoneinfo import ZoneInfo

    digest = load("warning_digest")
    now = datetime(2026, 3, 30, 9, 5, tzinfo=ZoneInfo("Europe/Vienna"))
    start, end = digest.business_window(now)
    assert start.isoformat() == "2026-03-27T09:00:00+01:00"
    assert end.isoformat() == "2026-03-30T09:00:00+02:00"
    assert end.timestamp() - start.timestamp() == 71 * 3600
