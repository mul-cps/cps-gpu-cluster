from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gateway_start import PERMIT, permit_start, template_digest


@pytest.fixture
def objects():
    namespace = "cps-compute"
    name = "compute-gateway"
    image = "example.invalid/compute@sha256:" + "a" * 64
    declaration = {"namespace":namespace, "kind":"Deployment", "name":name,
                   "uid":str(uuid4()), "container":"gateway", "image":image,
                   "service_account":"gateway"}
    labels = {"app":"compute-gateway"}
    template = {"metadata":{"labels":labels}, "spec":{"serviceAccountName":"gateway",
        "containers":[{"name":"gateway","image":image,"command":["python","/start/gateway_start.py"]}]}}
    deployment = {"apiVersion":"apps/v1","kind":"Deployment",
        "metadata":{"namespace":namespace,"name":name,"uid":declaration["uid"],
                    "annotations":{PERMIT:template_digest(template)}},
        "spec":{"template":template,"selector":{"matchLabels":labels},"replicas":1}}
    replica = {"apiVersion":"apps/v1","kind":"ReplicaSet",
        "metadata":{"namespace":namespace,"name":"compute-gateway-ready","uid":str(uuid4()),
                    "ownerReferences":[{"apiVersion":"apps/v1","kind":"Deployment","name":name,
                                        "uid":declaration["uid"],"controller":True}]},
        "spec":{"template":deepcopy(template),"replicas":1}}
    replica["spec"]["template"]["metadata"]["labels"]["pod-template-hash"]="ready"
    pod = {"apiVersion":"v1","kind":"Pod",
        "metadata":{"namespace":namespace,"name":"compute-gateway-ready-one","uid":str(uuid4()),
                    "labels":deepcopy(replica["spec"]["template"]["metadata"]["labels"]),
                    "ownerReferences":[{"apiVersion":"apps/v1","kind":"ReplicaSet",
                                        "name":replica["metadata"]["name"],"uid":replica["metadata"]["uid"],
                                        "controller":True}]},
        "spec":deepcopy(template["spec"]),
        "status":{"phase":"Running","conditions":[{"type":"Ready","status":"False"}]}}
    return declaration, pod, replica, deployment


def authorize(objects):
    declaration, pod, replica, deployment = objects
    core = SimpleNamespace(read_namespaced_pod=lambda *args, **kwargs:deepcopy(pod))
    apps = SimpleNamespace(read_namespaced_replica_set=lambda *args, **kwargs:deepcopy(replica),
                           read_namespaced_deployment=lambda *args, **kwargs:deepcopy(deployment))
    return permit_start(core, apps, declaration, pod["metadata"]["name"], pod["metadata"]["uid"])


def test_controller_can_activate_the_same_template_before_app_readiness(objects):
    authorize(objects)


def test_the_same_template_can_start_a_managed_replacement_pod(objects):
    pod = objects[1]
    pod["metadata"].update(name="compute-gateway-ready-two", uid=str(uuid4()))
    authorize(objects)


@pytest.mark.parametrize("fault", ["missing-permit", "wrong-permit", "previous-template",
                                   "orphan", "foreign-parent", "terminating", "scaled"])
def test_declines_a_candidate_outside_the_current_activation(objects, fault):
    _, pod, replica, deployment = objects
    if fault=="missing-permit":
        del deployment["metadata"]["annotations"][PERMIT]
    elif fault=="wrong-permit":
        deployment["metadata"]["annotations"][PERMIT]="sha256:" + "b"*64
    elif fault=="previous-template":
        deployment["spec"]["template"]["metadata"]["labels"]["revision"]="different"
        deployment["metadata"]["annotations"][PERMIT]=template_digest(deployment["spec"]["template"])
    elif fault=="orphan":
        del replica["metadata"]["ownerReferences"]
    elif fault=="foreign-parent":
        replica["metadata"]["ownerReferences"][0]["uid"]=str(uuid4())
    elif fault=="terminating":
        pod["metadata"]["deletionTimestamp"]="2026-11-24T04:00:00Z"
    else:
        replica["spec"]["replicas"]=2
    with pytest.raises(ValueError):
        authorize(objects)


def test_recheck_declines_authority_removed_during_observation(objects):
    declaration,pod,replica,deployment=objects
    withdrawn=deepcopy(deployment)
    del withdrawn["metadata"]["annotations"][PERMIT]
    reads=iter([deployment,withdrawn])
    core=SimpleNamespace(read_namespaced_pod=lambda *args,**kwargs:deepcopy(pod))
    apps=SimpleNamespace(read_namespaced_replica_set=lambda *args,**kwargs:deepcopy(replica),
                         read_namespaced_deployment=lambda *args,**kwargs:deepcopy(next(reads)))
    with pytest.raises(ValueError):
        permit_start(core,apps,declaration,pod["metadata"]["name"],pod["metadata"]["uid"])
