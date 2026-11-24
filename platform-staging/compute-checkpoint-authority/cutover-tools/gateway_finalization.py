"""Checks for resuming a paused single-writer gateway Deployment."""

import copy


HANDOFF_ANNOTATION = "cps.compute/handoff-id"
TEMPLATE_HASH_LABEL = "pod-template-hash"


class FinalizationError(RuntimeError):
    """The prepared candidate cannot safely be used to finalize the handoff."""


def stamp_candidate_template(template, handoff_id):
    """Stamp the desired template once, before creating the parked ReplicaSet."""
    if not handoff_id or not handoff_id.strip():
        raise FinalizationError("The handoff ID must be nonempty")
    candidate = copy.deepcopy(template)
    candidate["metadata"].setdefault("annotations", {})[HANDOFF_ANNOTATION] = handoff_id
    return candidate


def _controller(resource):
    return next((ref for ref in resource["metadata"].get("ownerReferences", []) if ref.get("controller")), {})


def _owned(resource, kind, uid):
    controller = _controller(resource)
    return controller.get("kind") == kind and controller.get("uid") == uid


def _without_template_hash(template):
    normalized = copy.deepcopy(template)
    normalized.get("metadata", {}).get("labels", {}).pop(TEMPLATE_HASH_LABEL, None)
    return normalized


def require_candidate_selection(deployment, replica_sets, candidate_replica_set_uid):
    """Check controller template selection before retiring the incumbent."""
    spec = deployment["spec"]
    deployment_uid = deployment["metadata"]["uid"]
    if spec.get("paused") is not True or spec["replicas"] != 1:
        raise FinalizationError("Expected a paused one-replica gateway Deployment")
    selector = spec["selector"]
    labels = selector.get("matchLabels", {})
    if not labels or selector.get("matchExpressions"):
        raise FinalizationError("Expected the gateway Deployment's matchLabels selector")

    def owned_or_claimable(replica_set):
        rs_labels = replica_set["metadata"].get("labels", {})
        return _owned(replica_set, "Deployment", deployment_uid) or (
            not _controller(replica_set) and all(rs_labels.get(key) == value for key, value in labels.items())
        )

    template = _without_template_hash(spec["template"])
    matches = [
        rs for rs in replica_sets
        if owned_or_claimable(rs) and _without_template_hash(rs["spec"]["template"]) == template
    ]
    if len(matches) != 1:
        raise FinalizationError(f"Expected one matching ReplicaSet, found {len(matches)}")
    candidate = matches[0]
    metadata = candidate["metadata"]
    if (
        metadata["uid"] != candidate_replica_set_uid
        or metadata.get("deletionTimestamp")
        or not _owned(candidate, "Deployment", deployment_uid)
    ):
        raise FinalizationError("The sole match is not the attached candidate ReplicaSet")
    return candidate


def check_finalization(deployment, replica_sets, pods, candidate_replica_set_uid, candidate_pod_uid):
    """Check ReplicaSet ownership and Pod readiness just before the strategy change."""
    candidate = require_candidate_selection(deployment, replica_sets, candidate_replica_set_uid)
    deployment_uid = deployment["metadata"]["uid"]
    owned_sets = [rs for rs in replica_sets if _owned(rs, "Deployment", deployment_uid)]
    if candidate["spec"]["replicas"] != 1:
        raise FinalizationError("The candidate ReplicaSet must request one replica")
    if any(
        rs["spec"]["replicas"] != 0 or rs.get("status", {}).get("replicas", 0) != 0
        for rs in owned_sets if rs["metadata"]["uid"] != candidate_replica_set_uid
    ):
        raise FinalizationError("Expected zero replicas in every other ReplicaSet")

    owned_uids = {rs["metadata"]["uid"] for rs in owned_sets}
    live_pods = [
        pod for pod in pods if _controller(pod).get("kind") == "ReplicaSet"
        and _controller(pod).get("uid") in owned_uids
        and pod.get("status", {}).get("phase") not in ("Succeeded", "Failed")
    ]
    if len(live_pods) != 1 or live_pods[0]["metadata"]["uid"] != candidate_pod_uid:
        raise FinalizationError("The candidate must be the sole live Pod")
    pod = live_pods[0]
    status = pod["status"]
    if (
        not _owned(pod, "ReplicaSet", candidate_replica_set_uid)
        or pod["metadata"].get("deletionTimestamp")
        or status.get("phase") != "Running"
        or not any(c["type"] == "Ready" and c["status"] == "True" for c in status.get("conditions", []))
    ):
        raise FinalizationError("The candidate Pod must be Running and Ready in the selected ReplicaSet")
    return {
        "deploymentUid": deployment_uid,
        "deploymentGeneration": deployment["metadata"]["generation"],
        "candidateReplicaSetUid": candidate_replica_set_uid,
        "candidatePodUid": candidate_pod_uid,
    }
