"""Synthetic API/CPU intent, never publication or hardware qualification."""
import copy
import json
import pytest

from test_personal_qualification_promotion import promoted_node_fixture


def test_personal_intent_retains_full_cas_and_inverse(monkeypatch):
    import personal_configuration_intent as module
    f=promoted_node_fixture(monkeypatch)
    source=f.source
    policy={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'policy','namespace':'control',
        'uid':'12121212-1212-4212-8212-121212121212','resourceVersion':'5'},
        'data':{'policy.json':json.dumps(source.source.catalog),'unrelated':'retain exact bytes'}}
    deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'node','namespace':'control',
        'uid':'13131313-1313-4313-8313-131313131313','resourceVersion':'9'},
        'spec':{'replicas':0,'selector':{'matchLabels':{'app':'node'}},'template':{'metadata':{'labels':{'app':'node'}},
        'spec':{'containers':[{'name':'node','image':'unchanged','env':[{'name':'KEEP','value':'exact'}]}],
        'volumes':[{'name':'configuration','configMap':{'name':source.node['metadata']['name']}}]}}}}
    node=source.loaded.document['component_declarations']['node']
    deployment['metadata'].update(name=node['name'],namespace=node['namespace'])
    baselines={'policy':policy,'node':source.node,'node_deployment':deployment}
    before=copy.deepcopy(baselines)
    result=module.personal_configuration_intent(f.loaded,f.node,baselines)
    assert baselines==before and result['baseline']==before
    assert result['live_applied'] is False and result['enabled'] is False
    assert result['inverse']['original_objects']==before
    assert result['inverse']['fresh_uid_resource_version_and_full_current_tests_required'] is True
    for name,path in (('policy','/data'),('node_deployment','/spec')):
        patch=result['patches'][name]
        assert patch[:2]==[
            {'op':'test','path':'/metadata/uid','value':before[name]['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':before[name]['metadata']['resourceVersion']}]
        assert patch[2]=={'op':'test','path':path,'value':before[name][path[1:]]}
    updated=result['patches']['node_deployment'][-1]['value']
    restored=copy.deepcopy(updated)
    restored['template']['spec']['volumes'][0]['configMap']['name']=source.node['metadata']['name']
    assert restored==deployment['spec']
    assert result['patches']['policy'][-1]['value']['unrelated']=='retain exact bytes'
    assert result['target_node_ref']==f.loaded.reference.to_dict()
    # A mutable/incomplete baseline cannot authorize even offline CAS output.
    baselines['node']['metadata']['resourceVersion']='moved'
    with pytest.raises(ValueError):module.personal_configuration_intent(f.loaded,f.node,baselines)
