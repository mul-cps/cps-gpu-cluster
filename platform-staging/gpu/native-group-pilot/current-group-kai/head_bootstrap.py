"""Pure, staged v3-to-v4 head bootstrap; actual API readbacks bind each stage.

This module performs no API calls. Root applies candidates and supplies actual
readbacks between stages. It does not mutate workloads or migrate a journal.
"""
from copy import deepcopy
import re

from cps_compute.immutable_configmap import ImmutableConfigMapRef
from cps_compute.native_approval_head import validate_binding
from cps_compute.native_group_revision import ApprovalRevision, COMPONENTS, _uid
from cps_compute.native_groups import _canonical, canonical_sha256
from cps_compute.native_node.config import NodeConfiguration


def require(condition,message):
    if not condition:raise ValueError(message)


def _authorities(configuration,approvals,policy):
    require(type(configuration) is NodeConfiguration and configuration.document['version']==3,
        'Actual enabled v3 Node configuration required for one-time migration')
    require(isinstance(approvals,dict) and set(approvals)==COMPONENTS,'Exactly four actual approval objects required')
    result={}
    for component,cm in approvals.items():
        approval=ApprovalRevision.from_configmap(cm,policy,configuration.deployment)
        require(approval.reference['namespace']==configuration.document['component_declarations'][component]['namespace'],
            'Initial approval must remain namespace-local')
        result[component]=approval
    require(result['node'].reference==configuration.initial_approval_ref,'Actual initial Node authority changed')
    bodies=[a.document for a in result.values()]
    require(all(body==bodies[0] for body in bodies),'Four current approval registries must agree with identical initial v3 history')
    return result


def _candidate(namespace,name,key,body,*,immutable):
    value={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':namespace,'name':name},
        'data':{key:_canonical(body).decode()}}
    if immutable:value['immutable']=True
    return value


def _readback(candidate,actual,*,immutable):
    require(isinstance(actual,dict),'Actual ConfigMap readback required')
    meta=actual.get('metadata',{})
    require(actual.get('apiVersion')=='v1' and actual.get('kind')=='ConfigMap'
        and all(meta.get(k)==candidate['metadata'][k] for k in ('namespace','name'))
        and _uid(meta.get('uid')) and isinstance(meta.get('resourceVersion'),str)
        and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion'])
        and not meta.get('deletionTimestamp') and not meta.get('ownerReferences')
        and not actual.get('binaryData') and actual.get('data')==candidate['data'],
        'Actual candidate UID/resourceVersion/content readback required')
    require(actual.get('immutable') is True if immutable else actual.get('immutable') in (None,False),
        'Actual ConfigMap mutability differs')
    return deepcopy(actual)


def pointer_candidates(configuration,approvals,policy):
    current=_authorities(configuration,approvals,policy)
    return {component:_candidate(approval.reference['namespace'],
        'cps-native-current-approval-'+component.replace(':','-'),'head.json',
        {'version':1,'generation':approval.document['registry']['generation'],'reference':approval.reference},
        immutable=False) for component,approval in current.items()}


def anchor_candidates(configuration,approvals,policy,pointers):
    candidates=pointer_candidates(configuration,approvals,policy)
    require(isinstance(pointers,dict) and set(pointers)==COMPONENTS,'Four actual pointer readbacks required')
    current=_authorities(configuration,approvals,policy);result={}
    for component,candidate in candidates.items():
        actual=_readback(candidate,pointers[component],immutable=False)
        anchor={'version':1,'pointer':{k:actual['metadata'][k] for k in ('namespace','name','uid')}
            | {'key':'head.json'},'initial':current[component].reference}
        name='cps-native-head-anchor-'+canonical_sha256(anchor).removeprefix('sha256:')[:16]
        result[component]=_candidate(actual['metadata']['namespace'],name,'anchor.json',anchor,immutable=True)
    return result


def bind(configuration,approvals,policy,pointers,anchors):
    candidates=anchor_candidates(configuration,approvals,policy,pointers)
    require(isinstance(anchors,dict) and set(anchors)==COMPONENTS,'Four actual anchor readbacks required')
    heads={}
    for component,candidate in candidates.items():
        actual=_readback(candidate,anchors[component],immutable=True)
        reference={k:actual['metadata'][k] for k in ('namespace','name','uid','resourceVersion')}
        reference.update(key='anchor.json',data_sha256=canonical_sha256(actual['data']))
        ref=ImmutableConfigMapRef.from_dict(reference)
        anchor=ref.validate(actual)
        heads[component]=validate_binding({'version':2,'anchor':anchor,'projection':reference})
    body=configuration.document;body.pop('approval_ref');body.update(version=4,approval_head=heads['node'])
    name='cps-native-node-head-'+canonical_sha256(body).removeprefix('sha256:')[:16]
    return {'heads':heads,'node_configuration':_candidate(configuration.reference.to_dict()['namespace'],
        name,'config.json',body,immutable=True)}
