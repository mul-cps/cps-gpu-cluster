import copy
import unittest

from gateway_finalization import (
    FinalizationError, check_finalization, require_candidate_selection, stamp_candidate_template,
)


def owner(kind, uid):
    return {"kind": kind, "uid": uid, "controller": True}


class GatewayFinalizationTest(unittest.TestCase):
    def setUp(self):
        self.template = {
            "metadata": {"labels": {"app": "gateway"}, "annotations": {"cps.compute/handoff-id": "tx-2"}},
            "spec": {"containers": [{"name": "gateway", "image": "gateway@sha256:example"}]},
        }
        self.deployment = {
            "metadata": {"uid": "deployment-uid", "generation": 32},
            "spec": {
                "template": self.template, "paused": True, "replicas": 1,
                "selector": {"matchLabels": {"app": "gateway"}},
            },
        }
        self.candidate = self.replica_set("candidate", "candidate-hash", 1)
        self.previous = self.replica_set("previous", "previous-hash", 0)
        self.previous["spec"]["template"]["metadata"]["annotations"]["cps.compute/handoff-id"] = "tx-1"
        self.pod = self.make_pod("candidate-pod", "candidate")

    def replica_set(self, uid, hash_label, count):
        template = copy.deepcopy(self.template)
        template["metadata"]["labels"]["pod-template-hash"] = hash_label
        return {
            "metadata": {
                "uid": uid, "labels": {"app": "gateway"},
                "ownerReferences": [owner("Deployment", "deployment-uid")],
            },
            "spec": {"template": template, "replicas": count},
            "status": {"replicas": count},
        }

    def make_pod(self, uid, replica_set_uid):
        return {
            "metadata": {"uid": uid, "ownerReferences": [owner("ReplicaSet", replica_set_uid)]},
            "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
        }

    def verify(self, *pods):
        return check_finalization(
            self.deployment, [self.previous, self.candidate], list(pods), "candidate", "candidate-pod"
        )

    def test_unique_active_candidate_with_historical_rollback(self):
        result = self.verify(self.pod, self.make_pod("unrelated-pod", "unrelated-rs"))
        self.assertEqual(result["candidatePodUid"], "candidate-pod")
        self.assertEqual(result["deploymentGeneration"], 32)

    def test_matching_older_template_rejected_before_incumbent_retirement(self):
        self.previous["spec"]["template"]["metadata"]["annotations"]["cps.compute/handoff-id"] = "tx-2"
        with self.assertRaisesRegex(FinalizationError, "found 2"):
            require_candidate_selection(self.deployment, [self.previous, self.candidate], "candidate")

    def test_claimable_orphan_can_conflict(self):
        self.previous["metadata"]["ownerReferences"] = []
        self.previous["spec"]["template"]["metadata"]["annotations"]["cps.compute/handoff-id"] = "tx-2"
        with self.assertRaisesRegex(FinalizationError, "found 2"):
            self.verify(self.pod)

    def test_stamp_keeps_labels_and_does_not_change_prior_template(self):
        stamped = stamp_candidate_template(self.template, "tx-3")
        self.assertEqual(stamped["metadata"]["labels"], self.template["metadata"]["labels"])
        self.assertEqual(stamped["metadata"]["annotations"]["cps.compute/handoff-id"], "tx-3")
        self.assertEqual(self.template["metadata"]["annotations"]["cps.compute/handoff-id"], "tx-2")

    def test_unattached_candidate_never_counts_as_selected(self):
        self.candidate["metadata"]["ownerReferences"] = []
        self.candidate["metadata"]["labels"] = {"parked": "true"}
        with self.assertRaisesRegex(FinalizationError, "found 0"):
            self.verify(self.pod)

    def test_stale_replica_status_rejected(self):
        self.previous["status"]["replicas"] = 1
        with self.assertRaisesRegex(FinalizationError, "every other ReplicaSet"):
            self.verify(self.pod)

    def test_terminating_writer_still_blocks_finalization(self):
        outgoing = self.make_pod("previous-pod", "previous")
        outgoing["metadata"]["deletionTimestamp"] = "2026-11-24T08:00:00Z"
        with self.assertRaisesRegex(FinalizationError, "sole live Pod"):
            self.verify(self.pod, outgoing)

    def test_terminal_rollback_pod_does_not_block(self):
        outgoing = self.make_pod("previous-pod", "previous")
        outgoing["status"]["phase"] = "Succeeded"
        self.verify(self.pod, outgoing)

    def test_candidate_must_be_ready_with_same_uid(self):
        with self.assertRaisesRegex(FinalizationError, "sole live Pod"):
            self.verify(self.make_pod("replacement", "candidate"))
        self.pod["status"]["conditions"] = []
        with self.assertRaisesRegex(FinalizationError, "must be Running and Ready"):
            self.verify(self.pod)

    def test_unpaused_deployment_is_rejected(self):
        self.deployment["spec"]["paused"] = False
        with self.assertRaisesRegex(FinalizationError, "paused"):
            self.verify(self.pod)
