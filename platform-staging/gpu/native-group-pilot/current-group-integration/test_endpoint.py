import copy,json
import pytest
import endpoint
from test_native_scheduler_current_groups import harness
from cps_compute.native_scheduler_coordinator_server import validate_configuration,node_epoch_contract,ReservationTemplate


def inputs(c):
    def sa(namespace,name,n):return {'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':namespace,'name':name,'uid':f'{n:08d}-1111-4111-8111-111111111111'}}
    dep=c.group_context.deployment
    plain={s:{'enabled':True,'source':s,'gatewayUrl':endpoint.ORIGIN,'gatewayCAFile':'/etc/cps-native-hub/ca.crt','groupDeployment':json.loads(dep.document)} for s in ('cps','cit')}
    readiness={'enabled':True,'ttlSeconds':30,'acknowledgments':{'node':{'namespace':dep.authority_namespace,'name':'ack-node','uid':'99999999-1111-4111-8111-111111111111'}},'processes':{'node':c.group_context._configuration.document['component_declarations']['node']}}
    reservation={'namespace':'kai-resource-reservation','serviceAccount':'kai-resource-reservation','image':'ghcr.io/example/reservation@sha256:'+'a'*64,'appLabel':'kai-resource-reservation','runtimeClassName':'','containerResources':{'requests':{'nvidia.com/gpu':'1'},'limits':{'nvidia.com/gpu':'1'}},'podSecurityContext':{},'containerSecurityContext':{}}
    return dict(gateway_account=sa('cps-compute','cps-compute-controller',1),binder_account=sa('kai-scheduler','binder',2),hub_accounts={s:sa(ns,'hub',i) for s,ns,i in (('cps','jupyterhub',3),('cit','cit-jhub',4))},hub_settings=plain,readiness=readiness,reservation_template=reservation,api_audience='reviewed-api-audience',binder_pod_labels={'app':'cps-native-binder'},gateway_pod_security_context={'fsGroup':10001})


def test_actual_be0_configuration_and_epoch_interoperability(request,monkeypatch,tmp_path):
    c,api,h,*_=harness(request,monkeypatch,tmp_path)
    args=inputs(c); before=copy.deepcopy(args)
    result=endpoint.render(c.group_context,**args)
    settings,rules=validate_configuration(result['coordinator'],h.native)
    assert settings.authority_namespace==h.group.authority_namespace
    assert {r.source:r.central_actor for r in rules if r.role=='hub'}=={'cps':'cps','cit':'cit'}
    assert result['coordinator']['nodeConfigurationRef']==c.group_context.node_configuration_ref
    assert result['gateway']['private_files']['policy.json']==h.policy.catalog
    epoch,_=node_epoch_contract(h.policy,result['gateway']['private_files']['deployment.json'],h.native)
    assert epoch.node_pool==h.group.node_pool
    assert args==before


def test_signed_routes_tokens_mounts_and_no_new_gateway(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    result=endpoint.render(c.group_context,**inputs(c))
    roles=[x for x in result['rbac'] if x['kind']=='ClusterRole']
    hub=next(x for x in roles if x['metadata']['name']=='cps-native-kai-hub-cps')
    assert hub['rules']==[{'nonResourceURLs':['/internal/native-kai/v2/'+x for x in endpoint.SEED],'verbs':['post']}]
    assert not any(x['kind']=='Deployment' for x in result['rbac'])
    assert all('secrets' not in r.get('resources',[]) and '*' not in json.dumps(r) for x in roles for r in x['rules'])
    for s in ('cps','cit'):
        v=result['hubs'][s]['volumes'][0]['projected'];assert v['defaultMode']==0o440
        assert v['sources'][0]['serviceAccountToken']['audience']==endpoint.AUDIENCE
        assert result['hubs'][s]['settings']['coordinator']['origin']==endpoint.ORIGIN


def test_untrusted_or_incomplete_operator_input_rejected(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    with pytest.raises(ValueError):endpoint.render({},**inputs(c))
    for key in ('api_audience','reservation_template'):
        args=inputs(c);args[key]='' if key=='api_audience' else {}
        with pytest.raises(ValueError):endpoint.render(c.group_context,**args)
    args=inputs(c);args['hub_settings']['cps']['gatewayUrl']='http://gateway:8000'
    with pytest.raises(ValueError):endpoint.render(c.group_context,**args)
    args=inputs(c);args['binder_account']['metadata']['deletionTimestamp']='now'
    with pytest.raises(ValueError):endpoint.render(c.group_context,**args)


def test_private_materializer_matches_exact_owned_file_contract(request,monkeypatch,tmp_path):
    import subprocess,sys,stat
    from cps_compute.native_scheduler_coordinator_auth import private_bytes
    c,*_=harness(request,monkeypatch,tmp_path)
    r=endpoint.render(c.group_context,**inputs(c))
    seed=tmp_path/'seed';seed.mkdir();target=tmp_path/'private';target.mkdir()
    for name,raw in r['seed']['data'].items():(seed/name).write_text(raw)
    code=r['gateway']['initContainer']['command'][2].replace('/kai-private/config',str(target/'config')).replace('/kai-seed',str(seed))
    subprocess.run([sys.executable,'-I','-c',code],check=True)
    assert stat.S_IMODE((target/'config').stat().st_mode)==0o700
    for name,body in r['gateway']['private_files'].items():
        path=target/'config'/name
        assert stat.S_IMODE(path.stat().st_mode)==0o600
        assert json.loads(private_bytes(str(path)))==body
    assert r['gateway']['volumeMounts'][1]['readOnly'] is True


def test_rejects_mismatched_node_process_and_missing_materializer_group(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    for change in ('process','group'):
        args=inputs(c)
        if change=='process':args['readiness']['processes']['node']['image']='foreign@sha256:'+'f'*64
        else:args['gateway_pod_security_context']={}
        with pytest.raises(ValueError):endpoint.render(c.group_context,**args)


def test_binder_staged_off_flags_and_signed_projection(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    r=endpoint.render(c.group_context,**inputs(c));b=r['binder']
    assert len(b['args'])==6 and b['args'][0]=='--native-pending-coordinator-enabled=false'
    assert b['opt_in_args'][0]=='--native-pending-coordinator-enabled=true'
    assert b['volumes'][0]['projected']['sources'][0]['serviceAccountToken']['audience']==endpoint.AUDIENCE
    assert all(x['readOnly'] for x in b['volumeMounts'])
    assert r['gateway']['podSecurityContextPrerequisite']=={'fsGroup':10001}
    assert b['args'][1]=='--native-coordinator-url='+endpoint.ORIGIN


@pytest.mark.asyncio
@pytest.mark.parametrize('source',['cps','cit'])
async def test_actual_pending_hub_parser_both_sources(request,monkeypatch,tmp_path,source):
    from types import SimpleNamespace
    from traitlets.config import Config
    from kubespawner import KubeSpawner
    from cps_compute_hub.native_hub import NativeHubPilotAdapter
    from cps_compute_hub.native_pending_hub import install_pending_group_hub_configuration,GroupPendingNativeHubAdapter
    import cps_compute_hub.native_hub_config as hc
    c,api,h,*_=harness(request,monkeypatch,tmp_path)
    args=inputs(c);dep=c.group_context.deployment
    scopes={k:v for k,v in dep.workspaces.items() if k.startswith(source+':')}
    plain=args['hub_settings'][source]
    plain.update(policyPath='/trusted/policy.json',serviceTokenEnv=source.upper()+'_CONSOLE_POLICY_TOKEN',
        profiles=sorted({p for v in scopes.values() for p in v['profiles']}),workspaces=sorted(scopes),
        owners=sorted({v['owner'] for v in scopes.values()}),gateImage=dep.gate_image,workloadImages=[dep.workload_image],
        writablePVCClaims=sorted({v['storage']['pvc'] for v in scopes.values()}),writableMountPaths=['/workspace'],
        readonlyNFS=[],groupShareTokenCompatibility=False,gatewayCAFile='/etc/ssl/certs/ca-certificates.crt')
    parsed=[]
    async def forbidden(*a,**k):raise AssertionError('No runtime/API operations during parser check')
    base=NativeHubPilotAdapter(h.policy,c.runtime,profiles=frozenset(plain['profiles']),workspaces=frozenset(scopes),
        qualified_group=dep,resolve_binding=forbidden,admit_pod=forbidden,read_pod=forbidden,
        register_intent=forbidden,release_binding=forbidden,recover_binding=forbidden)
    base.approval_document=c.group_context._approval
    def captured_install(config,settings):
        # Only infrastructure construction is replaced. Both actual closed
        # parsers and the actual typed pending-adapter constructor execute.
        hc._validate({k:v for k,v in settings.items() if k!='groupDeployment'})
        assert settings==plain
        parsed.append(True)
        return SimpleNamespace(native_pilot=base)
    monkeypatch.setattr(hc,'install_native_group_hub_configuration',captured_install)
    proposal=endpoint.render(c.group_context,**args)
    config=Config();config.JupyterHub.spawner_class=KubeSpawner
    adapter=install_pending_group_hub_configuration(config,proposal['hubs'][source]['settings'])
    try:
        assert parsed==[True] and type(adapter.native_pilot) is GroupPendingNativeHubAdapter
        assert adapter.native_pilot.approval_document.reference==c.group_context.approval_ref
        assert adapter.native_pilot.pending_authority.route_prefix=='/internal/native-kai/v2/'
    finally:
        await adapter.native_pilot.pending_authority.close()


def test_binder_projection_declares_readable_nonroot_group(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    binder=endpoint.render(c.group_context,**inputs(c))['binder']
    # The actual stock binder has no Pod fsGroup. Its added 0440 projected
    # volume must be readable by its unchanged runAsUser10000 container.
    assert binder['podSecurityContext']=={'fsGroup':10000}


def test_binder_reservation_flag_matches_exact_coordinator_template(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    args=inputs(c)
    result=endpoint.render(c.group_context,**args)
    required='--resource-reservation-pod-image='+args['reservation_template']['image']
    for mode in ('args','opt_in_args'):
        flags=result['binder'][mode]
        assert [x for x in flags if x.startswith('--resource-reservation-pod-image=')]==[required]
    assert result['coordinator']['reservationTemplate']['image']==args['reservation_template']['image']
