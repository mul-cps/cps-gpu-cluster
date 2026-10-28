"""Tests for the fail-closed offline GPU2 evidence reviewer."""
import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("review_actual_gpu2", HERE / "review_actual_gpu2.py")
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def cross_receipt():
    return {
        "state": "bounded-cross-parent-vmm-kernel-denial-measured",
        "direction": "cit-to-cps",
        "trial_id": "trial-1",
        "production_qualified": False,
        "cross_parent_isolation_qualified": False,
        "same_parent_positive_control": True,
        "kernel_witness_correlated": True,
        "peer_vector_continuity": True,
        "final_postflight_observed": True,
        "remote_endpoint_cleanup": "verified",
        "unchanged_native_authorities": True,
        "explicitly_completed_endpoints": ["cross-parent-importer", "exporter", "same-parent-positive"],
    }


def test_cross_parent_bounded_measurement_pass_is_distinct_from_promotion_flag():
    result = REVIEW.assess_cross_parent(
        cross_receipt(), positive_result={"expect": "allow", "cuda_result": 0, "cuda_name": "CUDA_SUCCESS"},
        denied_result={"expect": "deny", "cuda_result": 800, "cuda_name": "CUDA_ERROR_NOT_PERMITTED"},
        cleanup_receipts=2,
    )
    assert result["measurement_status"] == "measured_pass"
    assert result["cross_parent_isolation_qualified"] is False
    assert "unconditionally" in result["qualification_flag_explanation"]


def test_cross_parent_missing_kernel_witness_fails_closed():
    receipt = cross_receipt()
    receipt["kernel_witness_correlated"] = False
    result = REVIEW.assess_cross_parent(
        receipt, positive_result={"expect": "allow", "cuda_result": 0, "cuda_name": "CUDA_SUCCESS"},
        denied_result={"expect": "deny", "cuda_result": 800, "cuda_name": "CUDA_ERROR_NOT_PERMITTED"},
        cleanup_receipts=2,
    )
    assert result["measurement_status"] == "unproved"


def test_restart_combines_independent_proofs_but_preserves_missing_postflight():
    before = {"metadata": {"uid": "pod-a"}, "status": {"containerStatuses": [
        {"name": "notebook", "restartCount": 0, "containerID": "containerd://old"}]}}
    after = {"metadata": {"uid": "pod-a"}, "status": {"containerStatuses": [
        {"name": "notebook", "restartCount": 1, "containerID": "containerd://new"}]}}
    stop = {"stopped_exact_original_cid": "old", "old_pid_lifetime_absent": True,
            "stop_begin_monotonic_ns": 20, "stop_end_monotonic_ns": 30}
    peers = [{"phase": "peer_tick", "monotonic_ns": 10}, {"phase": "peer_tick", "monotonic_ns": 40}]
    oom = {"measurement_passed": True, "typed_oom": {"kind": "torch.OutOfMemoryError"},
           "unchanged_seals_and_processes": True, "recovery_byte": 37, "production_qualified": False}
    cleanup = {"all10_retired_offline_pinned_used0": True, "both_gpu_clients_zero": True,
               "whole10_original_journals_verified": True}
    def snapshot(container_id, pid):
        target = {"pod_uid": "pod-a", "intent": {}, "identity": {}, "seal_id": "seal-a",
                  "journal_sha256": "journal-a", "gate_sha256": "gate-a"}
        peer = {"pod_uid": "pod-b", "intent": {}, "identity": {}, "seal_id": "seal-b",
                "journal_sha256": "journal-b", "gate_sha256": "gate-b"}
        return {"host": {"targets": [target, peer], "processes": [
            {"container_id": container_id, "host_pid": pid},
            {"container_id": "peer", "host_pid": 2}]}}
    result = REVIEW.assess_restart(before, after, stop, peers, oom, cleanup, postflight_saved=False,
                                   restart_before=snapshot("old", 1), post_oom_before=snapshot("new", 3))
    assert result["measurement_status"] == "measured_pass"
    assert "bounded postflight failed" in result["original_runner_note"]
    assert result["production_qualified"] is False


def test_restart_does_not_pass_without_peer_bracketing_stop():
    before = {"metadata": {"uid": "pod-a"}, "status": {"containerStatuses": [
        {"name": "notebook", "restartCount": 0, "containerID": "containerd://old"}]}}
    after = {"metadata": {"uid": "pod-a"}, "status": {"containerStatuses": [
        {"name": "notebook", "restartCount": 1, "containerID": "containerd://new"}]}}
    stop = {"stopped_exact_original_cid": "old", "old_pid_lifetime_absent": True,
            "stop_begin_monotonic_ns": 20, "stop_end_monotonic_ns": 30}
    peers = [{"phase": "peer_tick", "monotonic_ns": 15}]
    result = REVIEW.assess_restart(before, after, stop, peers,
                                   {"measurement_passed": True},
                                   {"all10_retired_offline_pinned_used0": True},
                                   postflight_saved=True)
    assert result["measurement_status"] == "unproved"
