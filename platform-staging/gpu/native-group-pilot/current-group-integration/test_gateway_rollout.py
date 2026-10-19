"""Pure rollout composition from public fixtures; no Kubernetes client."""
from copy import deepcopy
import importlib
import uuid

import pytest

import endpoint
from test_endpoint import inputs
from test_native_scheduler_current_groups import harness


@pytest.fixture
def cohort(request,monkeypatch,tmp_path):
    coordinator,*_=harness(request,monkeypatch,tmp_path)
    proposal=endpoint.render(coordinator.group_context,**inputs(coordinator))
    def deployment(namespace,name,container,service_account,image,group):
        return {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':namespace,'name':name,
            'uid':str(uuid.uuid4()),'resourceVersion':'29'},'spec':{'replicas':1,'strategy':{'type':'Recreate'},
            'selector':{'matchLabels':{'app':name}},'template':{'metadata':{'labels':{'app':name},'annotations':{'keep':'yes'}},
            'spec':{'serviceAccountName':service_account,'securityContext':{'fsGroup':group,'runAsNonRoot':True},
                'nodeSelector':{'preserve':'placement'},'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'existing-data'}}],
                'initContainers':[{'name':'existing-init','image':image,'command':['true']}],
                'containers':[{'name':container,'image':image,'command':['unchanged'],
                    'args':['--plugins=unchanged','--resource-reservation-pod-image=upstream:old'] if container=='binder' else ['--keep=true'],
                    'env':[{'name':'PRESERVE','value':'yes'}],'resources':{'requests':{'cpu':'100m'}},
                    'volumeMounts':[{'name':'data','mountPath':'/data'}]}]}}}}
    gateway=deployment('cps-compute','compute-gateway','gateway','cps-compute-controller',proposal['gateway']['initContainer']['image'],10001)
    binder=deployment('kai-scheduler','binder','binder','binder','ghcr.io/example/binder@sha256:'+'b'*64,10000)
    binder['spec']['template']['metadata']['labels']={'app':'cps-native-binder'}
    seed=deepcopy(proposal['seed']);seed['metadata'].update(uid=str(uuid.uuid4()),resourceVersion='31')
    return proposal,gateway,binder,seed


def pin(deployment):
    return {key:deployment['metadata'][key] for key in ('namespace','name','uid','resourceVersion')}


def compose(cohort,component,**kwargs):
    proposal,gateway,binder,seed=cohort
    module=importlib.import_module('gateway_rollout')
    deployment=gateway if component=='gateway' else binder
    method=getattr(module,'compose_'+component)
    args=(deployment,proposal,seed) if component=='gateway' else (deployment,proposal)
    return method(*args,expected=kwargs.pop('expected',pin(deployment)),**kwargs)


def applied(deployment,plan):
    result=deepcopy(deployment)
    for operation in plan['patch']:
        path=operation['path'].strip('/').split('/');target=result
        for part in path[:-1]:target=target[part]
        if operation['op']=='test':assert target[path[-1]]==operation['value']
        else:target[path[-1]]=deepcopy(operation['value'])
    return result


def test_gateway_appends_exact_fragments_preserves_cohort_and_guards_full_spec(cohort):
    before=deepcopy(cohort);proposal,gateway,binder,seed=cohort
    result=compose(cohort,'gateway');desired=applied(gateway,result)['spec']
    assert cohort==before and desired==result['spec']
    pod=desired['template']['spec'];old=gateway['spec']['template']['spec'];main=pod['containers'][0]
    expected=deepcopy(gateway['spec']);future=expected['template']['spec']
    future['containers'][0]['env']+=proposal['gateway']['env']
    future['containers'][0]['volumeMounts']+=proposal['gateway']['volumeMounts']
    future['volumes']+=proposal['gateway']['volumes'];future['initContainers'].append(proposal['gateway']['initContainer'])
    assert desired==expected and pod['containers'][0]['image']==old['containers'][0]['image']
    assert result['seed_ref']['uid']==seed['metadata']['uid']
    for field in ('uid','resourceVersion','spec'):
        drift=deepcopy(gateway)
        if field=='spec':drift['spec']['replicas']=0
        else:drift['metadata'][field]='changed'
        with pytest.raises(AssertionError):applied(drift,result)
    with pytest.raises(ValueError):compose((proposal,applied(gateway,result),binder,seed),'gateway')


@pytest.mark.parametrize('fault',['uid','rv','group','env','volume','mount','nested-mount','init','image',
    'seed-uid','seed-data','seed-name','seed-mutable','seed-owner','seed-extra','proposal-name'])
def test_gateway_rejects_drift_collisions_and_unverified_seed(cohort,fault):
    proposal,gateway,binder,seed=cohort;expected=pin(gateway);pod=gateway['spec']['template']['spec'];main=pod['containers'][0]
    if fault=='uid':gateway['metadata']['uid']=str(uuid.uuid4())
    elif fault=='rv':gateway['metadata']['resourceVersion']='30'
    elif fault=='group':pod['securityContext']['fsGroup']=10000
    elif fault=='env':main['env']*=2
    elif fault=='volume':pod['volumes'].append(deepcopy(proposal['gateway']['volumes'][0]))
    elif fault=='mount':main['volumeMounts'].append({'name':'other','mountPath':'/kai-private'})
    elif fault=='nested-mount':main['volumeMounts'].append({'name':'other','mountPath':'/kai-private/child'})
    elif fault=='init':pod['initContainers'].append(deepcopy(proposal['gateway']['initContainer']))
    elif fault=='image':main['image']='unreviewed:tag'
    elif fault=='seed-uid':seed['metadata'].pop('uid')
    elif fault=='seed-data':seed['data']['coordinator.json']='{}'
    elif fault=='seed-name':seed['metadata']['name']='unreviewed-seed'
    elif fault=='seed-mutable':seed['immutable']=False
    elif fault=='seed-owner':seed['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif fault=='seed-extra':seed['data']['extra']='unreviewed'
    elif fault=='proposal-name':proposal['seed']['metadata']['name']=seed['metadata']['name']='cps-native-kai-config-'+'0'*16
    with pytest.raises(ValueError):compose(cohort,'gateway',expected=expected)


@pytest.mark.parametrize('form',['equals','split','missing-group'])
def test_binder_preserves_all_unrelated_spec_and_stays_disabled(cohort,form):
    before=deepcopy(cohort);proposal,gateway,binder,seed=cohort
    main=binder['spec']['template']['spec']['containers'][0]
    if form=='split':main['args']=['--plugins=unchanged','--resource-reservation-pod-image','upstream:old']
    if form=='missing-group':binder['spec']['template']['spec']['securityContext'].pop('fsGroup')
    main['args']+=['--native-pending-coordinator-enabled','false']
    old=deepcopy(binder);result=compose(cohort,'binder');future=applied(binder,result)
    new=future['spec']['template']['spec']['containers'][0]
    assert new['args'].count('--resource-reservation-pod-image='+proposal['coordinator']['reservationTemplate']['image'])==1
    assert new['args'].count('--native-pending-coordinator-enabled')==1 and 'true' not in new['args']
    expected=deepcopy(old['spec']);pod=expected['template']['spec']
    pod['securityContext']['fsGroup']=10000
    pod['containers'][0]['args']=new['args'];pod['containers'][0]['volumeMounts']+=proposal['binder']['volumeMounts']
    pod['volumes']+=proposal['binder']['volumes']
    assert future['spec']==expected and binder==old and cohort[0]==before[0] and cohort[1]==before[1]
    drift=deepcopy(binder);drift['spec']['replicas']=0
    with pytest.raises(AssertionError):applied(drift,result)
    with pytest.raises(ValueError):compose((proposal,gateway,future,seed),'binder')


@pytest.mark.parametrize('fault',['uid','rv','enabled','duplicate','missing-image','missing-value','wrong-url','mount','group','sa','digest','unknown-flag'])
def test_binder_rejects_unsafe_or_ambiguous_merges(cohort,fault):
    proposal,gateway,binder,seed=cohort;expected=pin(binder);pod=binder['spec']['template']['spec'];main=pod['containers'][0]
    if fault=='uid':binder['metadata']['uid']=str(uuid.uuid4())
    elif fault=='rv':binder['metadata']['resourceVersion']='30'
    elif fault=='enabled':main['args'].append('--native-pending-coordinator-enabled=true')
    elif fault=='duplicate':main['args'].append('--resource-reservation-pod-image=duplicate:tag')
    elif fault=='missing-image':main['args']=['--plugins=unchanged']
    elif fault=='missing-value':main['args']=['--resource-reservation-pod-image']
    elif fault=='wrong-url':main['args'].append('--native-coordinator-url=https://foreign.invalid')
    elif fault=='mount':main['volumeMounts'].append({'name':'other','mountPath':'/etc/cps-kai-trust'})
    elif fault=='group':pod['securityContext']['fsGroup']=10001
    elif fault=='sa':pod['serviceAccountName']='foreign'
    elif fault=='digest':proposal['coordinator']['reservationTemplate']['image']='unreviewed:tag'
    elif fault=='unknown-flag':proposal['binder']['args'][1]='--unreviewed=bad'
    with pytest.raises(ValueError):compose(cohort,'binder',expected=expected)


def test_gateway_plan_carries_deployable_binder_only_ingress(cohort):
    proposal,gateway,binder,seed=cohort
    expected={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy',
        'metadata':{'namespace':'cps-compute','name':'cps-native-kai-binder-to-gateway'},
        'spec':{'podSelector':{'matchLabels':{'app':'compute-gateway'}},'policyTypes':['Ingress'],
            'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kai-scheduler'}},
                'podSelector':{'matchLabels':{'app':'cps-native-binder'}}}], 'ports':[{'protocol':'TCP','port':8000}]}]}}
    assert proposal['network_policy']==expected
    result=compose(cohort,'gateway')
    assert result['create_resources']==[expected]
    assert proposal['network_policy_intent']=={'namespace':'cps-compute',**{k:v for k,v in expected['spec'].items() if k!='policyTypes'}}


def test_binder_plan_rejects_network_peer_selector_mismatch(cohort):
    cohort[2]['spec']['template']['metadata']['labels']={'app':'foreign'}
    with pytest.raises(ValueError,match='Binder.*labels'):
        compose(cohort,'binder')

@pytest.mark.parametrize('fault',['namespace-wide','all-pods','other-namespace','other-port','egress','extra-peer'])
def test_policy_composition_rejects_broad_or_foreign_ingress(cohort,fault):
    policy=cohort[0]['network_policy'];rule=policy['spec']['ingress'][0];peer=rule['from'][0]
    if fault=='namespace-wide':del peer['podSelector']
    elif fault=='all-pods':peer['podSelector']['matchLabels']={}
    elif fault=='other-namespace':peer['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name']='other'
    elif fault=='other-port':rule['ports'][0]['port']=443
    elif fault=='egress':policy['spec']['egress']=[{}]
    else:rule['from'].append({'podSelector':{}})
    with pytest.raises(ValueError):compose(cohort,'gateway')
