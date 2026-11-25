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


def test_allocation_classification_excludes_services_and_cronjobs(monkeypatch):
    monkeypatch.syspath_prepend(str(MONITORING))
    workloads = load("workload_allocations")
    personal = {"metadata": {"labels": {"component": "singleuser-server"}}}
    service = {"metadata": {"labels": {"component": "hub"}}}
    compute = {"metadata": {"ownerReferences": [{"kind": "Job", "uid": "user-job"}]}}
    assert workloads.scope_for("cit-jhub", personal, set()) == "cit-jhub"
    assert workloads.scope_for("jupyterhub", personal, set()) == "cps-jhub"
    assert workloads.scope_for("jupyterhub", service, set()) is None
    assert workloads.scope_for("cps-compute", compute, {"user-job"}) == "compute-jobs"
    assert workloads.scope_for("cps-compute", compute, set()) is None


def test_fractional_claim_uses_requested_mib_separately_from_device_slot(monkeypatch):
    monkeypatch.syspath_prepend(str(MONITORING))
    workloads = load("workload_allocations")
    container = {"resources": {"limits": {"nvidia.com/gpu": "1"}},
                 "env": [{"name": "NVIDIA_GPU_MEMORY_REQUEST", "value": "2048"},
                         {"name": "NVIDIA_GPU_MEMORY_LIMIT", "value": "5120"}]}
    assert workloads.gpu_claim(container) == (1, 2*1024**3, 5*1024**3)
