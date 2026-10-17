"""Temporary read proof for the installed SDK rotation; no API access."""
import copy
import importlib.util
from pathlib import Path

import pytest

HERE=Path(__file__).parent


def load(name):
    spec=importlib.util.spec_from_file_location('read_permissions_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_only_exact_seven_roles_get_and_four_namespace_pod_lists_are_added():
    _,configuration=load('test_render').fixture();before=copy.deepcopy(configuration.document)
    docs=load('rotation_read_permissions').render(configuration=configuration)
    from cps_compute.native_observer_permissions import role_targets
    expected=role_targets(configuration.document)
    assert len(docs)==8 and {d['kind'] for d in docs}=={'Role','RoleBinding'}
    for namespace in {ns for ns,_ in expected}:
        role=next(d for d in docs if d['kind']=='Role' and d['metadata']['namespace']==namespace)
        assert role=={'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{
            'namespace':namespace,'name':'cps-native-head-rotation-reader'},'rules':[
            {'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'verbs':['get'],
             'resourceNames':sorted(name for ns,name in expected if ns==namespace)},
            {'apiGroups':[''],'resources':['pods'],'verbs':['list']}]}
        binding=next(d for d in docs if d['kind']=='RoleBinding' and d['metadata']['namespace']==namespace)
        assert binding=={'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{
            'namespace':namespace,'name':'cps-native-head-rotation-reader'},'roleRef':{
            'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'cps-native-head-rotation-reader'},
            'subjects':[{'kind':'ServiceAccount','namespace':'cps-compute','name':'cps-native-head-delivery'}]}
    assert configuration.document==before
    for doc in docs:
        for row in doc.get('rules',[]):
            assert not set(row['verbs'])&{'patch','update','create','delete','escalate','bind','*'}
            assert not set(row['resources'])&{'secrets','serviceaccounts','*'}
            assert '*' not in row.get('resourceNames',[])


@pytest.mark.parametrize('invalid',[None,{},object()])
def test_requires_actual_typed_node_configuration(invalid):
    with pytest.raises(ValueError):load('rotation_read_permissions').render(configuration=invalid)


@pytest.mark.parametrize('namespace',['Bad_Name','*','',False,'a'*64])
def test_rejects_foreign_or_noncanonical_delivery_actor_namespace(namespace):
    _,configuration=load('test_render').fixture()
    with pytest.raises(ValueError):load('rotation_read_permissions').render(configuration=configuration,namespace=namespace)


def test_existing_legacy_node_configuration_is_not_rotation_authority():
    from test_native_observer_permissions import fixture
    from test_native_node_config import ref
    from cps_compute.native_node.config import NodeConfiguration
    f=fixture();configuration=NodeConfiguration.load(f.core,ref(f.cm),f.policy)
    assert configuration.document['version']==3
    with pytest.raises(ValueError):load('rotation_read_permissions').render(configuration=configuration)
