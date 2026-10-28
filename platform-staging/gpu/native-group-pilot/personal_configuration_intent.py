"""Offline personal promotion Node/policy CAS intent; no transport or apply.

The target must already be a fully loaded immutable Node with its real protected
proof/transition references. This renderer cannot publish those objects or bypass
the existing fenced/drained delivery controller, Source, Hub or runtime gates.
"""
import copy
import json

from cps_compute.immutable_configmap import require
from cps_compute.native_groups import canonical_sha256
from cps_compute.native_node.config import NodeConfiguration
from cps_compute.personal_qualification_promotion import validate_promotion
from cps_compute.policy import Policy
from qualification_transition_proposal import object_guard,replace_patch,canonical


def personal_configuration_intent(configuration,target_node,baselines):
    """Retain full original objects; render only the exact policy and Node pointer."""
    require(type(configuration) is NodeConfiguration and type(baselines) is dict
        and set(baselines)=={'policy','node','node_deployment'},
        'Actual loaded target Node and full policy/Node/Deployment baselines required')
    authority=configuration.deployment.qualification_authority
    require(authority is not None and authority.proof['version']==4
        and configuration.previous_configuration is not None,
        'Actual fresh v4 promotion with full immediate predecessor required')
    policy=authority.current_policy;variant=authority.proof['personal_variant']
    require('promotion' in variant,'Closed personal promotion binding required')
    validate_promotion(variant,policy)
    previous=configuration.previous_configuration
    require(configuration.reference.validate(target_node)==configuration.document
        and previous.reference.validate(baselines['node'])==previous.document,
        'Exact actual target and immediate predecessor Node API objects required')
    cm=baselines['policy'];object_guard(cm,'ConfigMap')
    old=Policy(json.loads(cm['data']['policy.json']))
    require(old.hash==previous.deployment.qualification_authority.current_policy.hash
        and old.catalog==previous.deployment.qualification_authority.current_policy.catalog,
        'Complete source policy baseline must equal the retained immediate Node policy')
    deployment=baselines['node_deployment'];object_guard(deployment,'Deployment')
    require(deployment['spec'].get('replicas')==0,'Offline personal intent requires the held Node Deployment baseline')
    node=previous.document['component_declarations']['node']
    require(deployment['metadata']['name']==node['name'] and deployment['metadata']['namespace']==node['namespace'],
        'Exact immediate predecessor Node Deployment identity required')
    spec=copy.deepcopy(deployment['spec']);changed=0
    for volume in spec['template']['spec'].get('volumes',[]):
        if volume.get('configMap',{}).get('name')==previous.reference.to_dict()['name']:
            volume['configMap']['name']=configuration.reference.to_dict()['name'];changed+=1
    require(changed==1,'One exact predecessor Node configuration volume required')
    data=copy.deepcopy(cm['data']);data['policy.json']=canonical(policy.catalog)
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'scope':'personal-policy-and-node-reference-intent',
        'activation':'existing-fenced-drained-transition-required',
        'remaining_delivery_gates':['authenticated-source','runtime-and-hub-configuration',
            'released-ledger','external-quiescence','fresh-component-acknowledgments'],
        'promotion_sha256':variant['promotion']['artifact_sha256'],
        'target_node_ref':configuration.reference.to_dict(),'target_node':copy.deepcopy(target_node),
        'baseline':copy.deepcopy(baselines),'baseline_sha256':canonical_sha256(baselines),
        'patches':{'policy':replace_patch(cm,'/data',cm['data'],data),
            'node_deployment':replace_patch(deployment,'/spec',deployment['spec'],spec)},
        'inverse':{'enabled':False,'original_objects':copy.deepcopy(baselines),
            'fresh_uid_resource_version_and_full_current_tests_required':True}}
