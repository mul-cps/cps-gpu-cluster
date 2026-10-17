"""Pure temporary read-only prerequisites for the explicit delivery rotation.

Root must CREATE, read back and later remove these separate objects. They do
not replace existing delivery Roles, create a ServiceAccount, or grant writes.
"""
import re

NAME='cps-native-head-rotation-reader'
SERVICE_ACCOUNT='cps-native-head-delivery'


def render(*,configuration,namespace='cps-compute'):
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.native_observer_permissions import role_targets
    if type(configuration) is not NodeConfiguration or configuration.document['version']!=4:
        raise ValueError('Actual current immutable NodeConfiguration v4 required')
    if not isinstance(namespace,str) or not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?',namespace):
        raise ValueError('Explicit canonical existing delivery ServiceAccount namespace required')
    targets=role_targets(configuration.document)
    result=[]
    for ns in sorted({ns for ns,_ in targets}):
        metadata={'namespace':ns,'name':NAME}
        result.append({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':dict(metadata),'rules':[
            {'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'verbs':['get'],
                'resourceNames':sorted(name for target_ns,name in targets if target_ns==ns)},
            {'apiGroups':[''],'resources':['pods'],'verbs':['list']}]})
        result.append({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':dict(metadata),
            'subjects':[{'kind':'ServiceAccount','namespace':namespace,'name':SERVICE_ACCOUNT}],
            'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':NAME}})
    return result
