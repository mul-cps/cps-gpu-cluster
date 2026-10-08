"""NEW reviewed replacement candidate for the adjacent mutable quota policy.

Must replace the original QA quota-policy binding, not coexist with its Deny.
This does not modify, install, or activate any adjacent or production policy.
"""
import copy

import fence


def build(registry, *, quota_writers=()):
    fence.validate_registry(registry)
    namespace = registry['namespace']
    coordinator = registry['sealWriter']
    rows = [row for record in registry['records'] for row in fence.quota_records(record, namespace)]
    bundle = fence.quota_policy.build(namespace=namespace, writers=list(dict.fromkeys([*quota_writers, *registry['cleanupWriters'], coordinator])), records=rows)
    crd, params, policy, binding = bundle['items']
    group = namespace + '.sealed.compute.cps.unileoben.ac.at'
    crd['metadata']['name'] = 'dynamicgpuquotapolicies.' + group
    crd['spec']['group'] = group
    params['apiVersion'] = group + '/v1alpha1'
    policy['metadata']['name'] += '-seal-transition'
    binding['metadata']['name'] += '-seal-transition'
    policy['spec']['paramKind']['apiVersion'] = group + '/v1alpha1'
    binding['spec']['policyName'] = policy['metadata']['name']
    params['coordinator'] = coordinator
    params['cleanupWriters'] = registry['cleanupWriters']
    schema = crd['spec']['versions'][0]['schema']['openAPIV3Schema']
    schema['properties']['coordinator'] = {'type': 'string', 'maxLength': 343, 'pattern': '^' + fence.quota_policy.ACTOR_PATTERN + '$'}
    schema['required'].append('coordinator')
    schema['properties']['cleanupWriters'] = {'type': 'array', 'maxItems': 8, 'x-kubernetes-list-type': 'set',
        'items': {'type': 'string', 'maxLength': 343, 'pattern': '^' + fence.quota_policy.ACTOR_PATTERN + '$'}}
    schema['required'].append('cleanupWriters')
    properties = schema['properties']['records']['items']['properties']
    properties['sealResourceVersion'] = {'type': 'string', 'maxLength': 20, 'pattern': '^[1-9][0-9]{0,19}$'}
    maps = {cm['metadata']['name']: cm for record in registry['records'] for cm in record['configMaps']}
    for row in params['records']:
        row['sealResourceVersion'] = maps[row['name']]['metadata']['resourceVersion']
    validations = policy['spec']['validations']
    for rule in validations:
        if rule['message'] == 'Binary data and immutable quota ConfigMaps are outside the reviewed contract':
            rule['expression'] = "!has(variables.subject.binaryData) && (!has(variables.subject.immutable) || !variables.subject.immutable || request.operation in ['UPDATE','DELETE'])"
            rule['message'] = 'Native seal is allowed only by the separate exact coordinator transition; sealed cleanup still requires the generation-fence webhook'
        if rule['message'] == 'Updates preserve the observed ConfigMap UID, name, namespace and exact owner references':
            rule['expression'] = rule['expression'].replace('!has(oldObject.immutable)', '(!has(oldObject.immutable) || !oldObject.immutable)')
    seal = "request.operation == 'UPDATE' && request.userInfo.username == params.coordinator"
    complete = "(variables.record.type == 'evar' && size(variables.data) == 0 && size(variables.oldData) == 0) || (variables.record.type == 'capabilities' && variables.stage == 3 && variables.oldStage == 3)"
    transition = "has(object.immutable) && object.immutable && (!has(oldObject.immutable) || !oldObject.immutable) && has(variables.record.cmUid) && object.metadata.uid == variables.record.cmUid && has(variables.record.sealResourceVersion) && oldObject.metadata.resourceVersion == variables.record.sealResourceVersion && object.metadata.resourceVersion == oldObject.metadata.resourceVersion && variables.data == variables.oldData && object.metadata == oldObject.metadata && (" + complete + ')'
    cleanup = "request.operation == 'DELETE' && request.userInfo.username in params.cleanupWriters"
    validations.extend([
        {'expression': "request.userInfo.username != params.coordinator || (" + seal + ' && ' + transition + ') || (' + cleanup + ')', 'message': 'Coordinator may only seal complete pinned generations or request explicitly reviewed cleanup checked by the fence webhook'},
        {'expression': "request.operation != 'UPDATE' || !has(object.immutable) || !object.immutable || (" + seal + ' && ' + transition + ')', 'message': 'Only the trusted coordinator may transition a complete mutable map to immutable once'},
    ])
    for item in bundle['items']:
        item['metadata'].setdefault('annotations', {})['compute.cps.unileoben.ac.at/qualification-state'] = 'qa-only-inactive-seal-transition'
    return copy.deepcopy(bundle)
