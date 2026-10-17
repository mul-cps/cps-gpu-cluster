"""Versioned, synthetic head permission rendering; no live API or GPU access."""
import copy
import pytest
from test_render import module
head_fixtures=pytest.importorskip('test_native_observer_head_permissions')
fixture,advance=head_fixtures.fixture,head_fixtures.advance


def captured(f):
    base=f.f
    return {'version':1,'configmaps':copy.deepcopy(list(f.objects.values())),
        'deployments':[base.apps.read_namespaced_deployment(d['name'],d['namespace'])
            for d in base.body['component_declarations'].values()],
        'roles':[base.rbac.read_namespaced_role(name,ns) for ns,name in base.roles]}


def rendered(f):
    m=module();release=f.release.document
    return m.render(release,m.digest(release),f.f.policy.catalog,captured(f),
        'registry.example/operator@sha256:'+'b'*64)


def test_v2_operator_named_reads_cover_actual_head_authorities():
    f=fixture();docs=rendered(f)
    for component,binding in f.heads.items():
        ns=binding['projection']['namespace']
        role=next(d for d in docs if d['kind']=='Role' and d['metadata']['namespace']==ns)
        row=next(r for r in role['rules'] if r['resources']==['configmaps'])
        required={binding['projection']['name'],binding['anchor']['pointer']['name'],f.current[component].reference['name']}
        assert required <= set(row['resourceNames'])
        assert row['verbs']==['get'] and '*' not in row['resourceNames']
    assert next(d for d in docs if d['kind']=='Deployment')['spec']['replicas']==0


def test_reconciled_head_get_names_remain_valid_without_trusting_arbitrary_reads():
    f=fixture();advance(f);assert f.controller.run_once()['state']=='reconciled'
    docs=rendered(f)
    for component,head in f.current.items():
        role=next(d for d in docs if d['kind']=='Role' and d['metadata']['namespace']==head.reference['namespace'])
        assert head.reference['name'] in next(r for r in role['rules'] if r['resources']==['configmaps'])['resourceNames']
    ns,name=next(iter(f.f.roles));f.f.roles[(ns,name)]['rules'][0]['resourceNames'].append('forged-extra-authority')
    with pytest.raises(ValueError):rendered(f)


def test_mixed_heads_and_missing_immutable_readbacks_are_refused():
    f=fixture();advance(f,['node'])
    with pytest.raises(ValueError):rendered(f)
    f=fixture();advance(f);head=f.current['hub:cit'].reference
    del f.objects[(head['namespace'],head['name'])]
    with pytest.raises(ValueError):rendered(f)


def test_retained_head_history_above_legacy_inventory_limit_is_renderable():
    import json
    from cps_compute.native_group_revision import ApprovalRevision
    f=fixture()
    for generation in range(5):
        advance(f)
        for component,current in list(f.current.items()):
            old_key=(current.reference['namespace'],current.reference['name'])
            cm=f.objects.pop(old_key);f.allowed.discard(old_key)
            cm['metadata']['name']+='-'+str(generation)
            key=(cm['metadata']['namespace'],cm['metadata']['name'])
            f.objects[key]=cm;f.allowed.add(key)
            actual=ApprovalRevision.from_configmap(cm,f.f.policy,f.qualification)
            f.current[component]=actual
            pointer=f.pointers[component]
            pointer['metadata']['resourceVersion']=str(20+generation)
            pointer['data']['head.json']=json.dumps({'version':1,'generation':actual.document['registry']['generation'],
                'reference':actual.reference},sort_keys=True,separators=(',',':'))
    assert len(captured(f)['configmaps'])>32
    assert f.controller.run_once()['state']=='reconciled'
    docs=rendered(f)
    assert len([d for d in docs if d['kind']=='Role'])==4


@pytest.mark.parametrize('version,limit',[(1,32),(2,4*128+32)])
def test_configmap_capture_remains_bounded_for_each_release_version(version,limit):
    from test_render import fixture as legacy_fixture
    m=module()
    if version==1:
        value=legacy_fixture();release=value['release'];policy=value['policy'];capture=value['capture']
    else:
        f=fixture();release=f.release.document;policy=f.f.policy.catalog;capture=captured(f)
    while len(capture['configmaps'])<=limit:
        capture['configmaps'].append({'apiVersion':'v1','kind':'ConfigMap','metadata':{
            'namespace':'unused','name':'unused-'+str(len(capture['configmaps']))},'data':{}})
    with pytest.raises(ValueError,match='Bounded explicit ConfigMap'):
        m.render(release,m.digest(release),policy,capture,'registry.example/operator@sha256:'+'b'*64)
