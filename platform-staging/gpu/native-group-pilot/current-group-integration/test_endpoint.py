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
    return dict(gateway_account=sa('cps-compute','cps-compute-controller',1),binder_account=sa('kai-scheduler','binder',2),hub_accounts={s:sa(ns,'hub',i) for s,ns,i in (('cps','jupyterhub',3),('cit','cit-jhub',4))},hub_settings=plain,readiness=readiness,reservation_template=reservation,api_audience='reviewed-api-audience',binder_pod_labels={'app':'cps-native-binder'},gateway_pod_security_context={'fsGroup':10001},gateway_data_volume_name='data')


def test_actual_qualified_configuration_and_epoch_interoperability(request,monkeypatch,tmp_path):
    c,api,h,service,f,current,maps,core,node=harness(request,monkeypatch,tmp_path)
    # The production installer reloads authenticated Node/head references from
    # the actual backend Core client; expose the same captured API in this fixture.
    from types import SimpleNamespace
    captured_core=SimpleNamespace(read_namespaced_config_map=lambda name,namespace,**kwargs: core.read_namespaced_config_map(name,namespace))
    monkeypatch.setattr(h.native.backend,'core',captured_core,raising=False)
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


@pytest.mark.asyncio
async def test_v4_head_generations_one_through_seven_keep_node_ref_and_select_head_epoch(request,monkeypatch,tmp_path):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from cps_compute import native_scheduler_coordinator_server as server
    from cps_compute import native_group_capture_server as capture
    from cps_compute.native_approval_head import HeadSnapshot
    from cps_compute.native_group_revision import ApprovalRevision
    from cps_compute.native_groups import _canonical
    from cps_compute.native_scheduler_group_contract import GroupPendingContext
    from test_native_head_coordinator import dynamic,advance
    from test_native_node_config import ref

    values=dynamic(request,monkeypatch,tmp_path)
    c,api,h,service,f,current,maps,core,node=values
    def advance_head(generation):
        actual=advance(values)
        cm=maps.pop(actual.reference['name']);cm['metadata']['name']='endpoint-head-'+str(generation)
        actual=ApprovalRevision.from_configmap(cm,h.policy,h.group)
        maps[cm['metadata']['name']]=cm;h.documents.update(cm=cm,actual=actual)
        pointer=json.loads(maps['coordinator-head']['data']['head.json']);pointer['reference']=actual.reference
        maps['coordinator-head']['data']['head.json']=_canonical(pointer).decode()
    advance_head(1)
    c.group_context=GroupPendingContext.load(core,ref(node),h.policy)
    stable=c.group_context.node_configuration_ref
    proposal=endpoint.render(c.group_context,**inputs(c))
    config=copy.deepcopy(proposal['coordinator'])
    private=tmp_path/'endpoint-private';private.mkdir(mode=0o700)
    config.update(custodyPath=str(private/'custody.sqlite'),writerLockPath=str(c.writer_lock_path))
    for field,name in (('policyPath','policy.json'),('qualificationPath','deployment.json')):
        config['epoch'][field]=str(private/name)
    files=dict(proposal['gateway']['private_files'],**{'coordinator.json':config})
    for name,value in files.items():
        path=private/name;path.write_text(json.dumps(value));path.chmod(0o600)
    class ConfigMaps:
        def read_namespaced_config_map(self,name,namespace,**kwargs):
            assert kwargs=={'_request_timeout':(5,15)}
            return core.read_namespaced_config_map(name,namespace)
    monkeypatch.setattr(h.native.backend,'core',ConfigMaps(),raising=False)
    monkeypatch.setattr(server,'RawKubernetesAPI',lambda *a,**kw:api)
    observed=[]
    def receipt_io(observer):
        assert type(observer) is capture.HeadNodeEpochObserver
        assert observer.head_binding==c.group_context._configuration.approval_head
        head=HeadSnapshot.load(core,observer.head_binding,h.policy,observer.qualification)
        observed.append(head.document['generation'])
        return c.group_context.epoch
    # Only external receipt/process I/O is substituted. The real installer,
    # closed config parser, head observer constructor and head loader execute.
    monkeypatch.setattr(capture.HeadNodeEpochObserver,'observe',receipt_io)
    installed=server.install_from_environment(FastAPI(),h.native,
        environ={'CPS_NATIVE_KAI_COORDINATOR_CONFIG':str(private/'coordinator.json')})
    with monkeypatch.context() as legacy_observer:
        legacy_observer.setattr(capture,'HeadNodeEpochObserver',capture.NodeEpochObserver)
        with pytest.raises(TypeError,match='head_binding'):await installed.epoch()
    for generation in range(1,8):
        context=GroupPendingContext.load(core,ref(node),h.policy)
        assert context._configuration.document['version']==4
        assert context._approval.document['registry']['generation']==generation
        result=endpoint.render(context,**inputs(SimpleNamespace(group_context=context)))
        validate_configuration(result['coordinator'],h.native)
        assert result['coordinator']['nodeConfigurationRef']==stable==installed.group_context.node_configuration_ref
        assert await installed.epoch()==context.epoch
        if generation==7:break
        advance_head(generation+1)
    assert observed==list(range(1,8))


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


def test_nested_token_paths_keep_full_rotating_projections_and_original_trust(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    r=endpoint.render(c.group_context,**inputs(c))
    assert r['coordinator']['api']['tokenFile']=='/var/run/cps-kai-api/credentials/token'
    assert r['coordinator']['api']['caFile']=='/var/run/cps-kai-api/ca.crt'
    assert '--native-coordinator-token-file=/var/run/cps-kai-service/credentials/token' in r['binder']['args']
    assert r['binder']['args'][1:]==r['binder']['opt_in_args'][1:]
    for fragment,audience in [(r['gateway'],'reviewed-api-audience'),(r['binder'],endpoint.AUDIENCE),
                              *((r['hubs'][s],endpoint.AUDIENCE)for s in ('cps','cit'))]:
        volume=next(v for v in fragment['volumes']if 'projected'in v)
        token,ca=volume['projected']['sources']
        assert volume['projected']['defaultMode']==0o440
        assert token=={'serviceAccountToken':{'audience':audience,'expirationSeconds':3600,'path':'credentials/token'}}
        assert ca=={'configMap':{'name':'kube-root-ca.crt','items':[{'key':'ca.crt','path':'ca.crt'}]}}
        mount=next(v for v in fragment['volumeMounts']if v['name']==volume['name'])
        assert mount['readOnly'] is True and 'subPath'not in mount and 'subPathExpr'not in mount
    for source in ('cps','cit'):
        assert r['hubs'][source]['settings']['coordinator']['tokenFile']=='/var/run/cps-kai-service/credentials/token'


def test_emitted_nested_token_is_read_by_strict_sdk_across_atomic_rotation(request,monkeypatch,tmp_path):
    from cps_compute.native_scheduler_coordinator_auth import projected_token
    c,*_=harness(request,monkeypatch,tmp_path)
    r=endpoint.render(c.group_context,**inputs(c))
    volume=r['gateway']['volumes'][0]
    relative=volume['projected']['sources'][0]['serviceAccountToken']['path']
    root=tmp_path/'projection';root.mkdir();root.chmod(0o3777)
    # Kube's AtomicWriter projects a stable top-level symlink through ..data.
    # A nested file gives the strict reader a non-writable credentials parent.
    for generation,value in (('generation-1','header.payload.first'),('generation-2','header.payload.rotated')):
        target=root/generation/relative;target.parent.mkdir(parents=True,mode=0o755)
        target.write_text(value);target.chmod(0o440)
    (root/'..data').symlink_to('generation-1',target_is_directory=True)
    top=relative.split('/')[0];(root/top).symlink_to('..data/'+top,target_is_directory='/'in relative)
    path=str(root/relative)
    assert projected_token(path)=='header.payload.first'
    (root/'..data-next').symlink_to('generation-2',target_is_directory=True)
    (root/'..data-next').replace(root/'..data')
    assert projected_token(path)=='header.payload.rotated'
    assert root.stat().st_mode&0o7777==0o3777


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
    code=r['gateway']['initContainer']['command'][2].replace('/kai-private/config',str(target/'config')).replace('/kai-seed',str(seed)).replace('/data/native-kai-private',str(tmp_path/'state'))
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


def test_new_custody_and_writer_lock_use_owned_private_pvc_child(request,monkeypatch,tmp_path):
    import subprocess,sys,stat
    c,*_=harness(request,monkeypatch,tmp_path)
    result=endpoint.render(c.group_context,**inputs(c))
    assert result['coordinator']['custodyPath']=='/data/native-kai-private/custody.sqlite'
    assert result['coordinator']['writerLockPath']=='/data/native-kai-private/writer.lock'
    init=result['gateway']['initContainer']
    assert {'name':'data','mountPath':'/data'} in init['volumeMounts']
    seed=tmp_path/'seed';seed.mkdir();private=tmp_path/'private';private.mkdir();private.chmod(0o2770);data=tmp_path/'data';data.mkdir(mode=0o775);data.chmod(0o2775)
    db=data/'control.sqlite';db.write_bytes(b'existing database sentinel')
    before=(data.stat().st_mode,db.read_bytes(),db.stat().st_mode)
    for name,raw in result['seed']['data'].items():(seed/name).write_text(raw)
    code=init['command'][2].replace('/kai-private/config',str(private/'config')).replace('/kai-seed',str(seed)).replace('/data/native-kai-private',str(data/'native-kai-private'))
    subprocess.run([sys.executable,'-I','-c',code],check=True)
    state=data/'native-kai-private'
    assert stat.S_IMODE((private/'config').stat().st_mode)==0o700
    subprocess.run([sys.executable,'-I','-c',code],check=True)
    assert stat.S_IMODE(state.stat().st_mode)==0o700
    assert before==(data.stat().st_mode,db.read_bytes(),db.stat().st_mode)
    # A preexisting symbolic link cannot redirect the persistent writer lock.
    import shutil
    shutil.rmtree(private/'config');state.rmdir();state.symlink_to(seed,target_is_directory=True)
    refused=subprocess.run([sys.executable,'-I','-c',code],capture_output=True,text=True)
    assert refused.returncode!=0


def _existing_private_state_init(request,monkeypatch,tmp_path):
    c,*_=harness(request,monkeypatch,tmp_path)
    result=endpoint.render(c.group_context,**inputs(c))
    seed=tmp_path/'seed';seed.mkdir()
    for name,raw in result['seed']['data'].items():(seed/name).write_text(raw)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    state=tmp_path/'state';state.mkdir(mode=0o700)
    code=result['gateway']['initContainer']['command'][2].replace('/kai-private/config',str(private/'config')).replace('/kai-seed',str(seed)).replace('/data/native-kai-private',str(state))
    return state,code


def test_existing_fsgroup_widened_private_state_is_repaired_without_replacing_inodes(request,monkeypatch,tmp_path):
    import stat,subprocess,sys
    state,code=_existing_private_state_init(request,monkeypatch,tmp_path)
    names=('writer.lock','custody.sqlite','custody.sqlite-journal','custody.sqlite-wal','custody.sqlite-shm')
    before={}
    for name in names:
        path=state/name;path.write_bytes(('unchanged '+name).encode());path.chmod(0o660)
        before[name]=(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
    unrelated=state/'not-coordinator-owned';unrelated.write_bytes(b'unchanged');unrelated.chmod(0o660)
    for _ in range(2):
        subprocess.run([sys.executable,'-I','-B','-c',code],check=True)
        for name in names:
            path=state/name
            assert stat.S_IMODE(path.stat().st_mode)==0o600
            assert before[name]==(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
    assert stat.S_IMODE(unrelated.stat().st_mode)==0o660
    assert unrelated.read_bytes()==b'unchanged'


@pytest.mark.parametrize('fault',['symlink','hardlink','foreign-owner','locked','missing-lock'])
def test_private_state_repair_refuses_unsafe_existing_inodes(request,monkeypatch,tmp_path,fault):
    import os,fcntl,subprocess,sys,stat
    state,code=_existing_private_state_init(request,monkeypatch,tmp_path)
    lock=state/'writer.lock';lock.write_bytes(b'lock contents');lock.chmod(0o660)
    db=state/'custody.sqlite';db.write_bytes(b'custody contents');db.chmod(0o660)
    descriptor=None
    if fault=='symlink':
        db.unlink();db.symlink_to(lock)
    elif fault=='hardlink':
        os.link(db,state/'extra-link')
    elif fault=='foreign-owner':
        # Tests run without chown privilege. Change only fstat's reported owner
        # for this real open inode; all opens/modes/link checks remain real.
        code="import os; original_fstat=os.fstat\n"+"def foreign_stat(fd):\n s=original_fstat(fd)\n if os.readlink('/proc/self/fd/'+str(fd)).endswith('/custody.sqlite'):\n  v=list(s);v[4]=os.geteuid()+1;return os.stat_result(v)\n return s\nos.fstat=foreign_stat\n"+code
    elif fault=='locked':
        descriptor=os.open(lock,os.O_RDONLY);fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    elif fault=='missing-lock':
        lock.unlink()
    try:
        result=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True)
        assert result.returncode!=0
        assert db.read_bytes() in (b'custody contents',b'lock contents')
        assert stat.S_IMODE(db.stat().st_mode)==0o660
    finally:
        if descriptor is not None:os.close(descriptor)
