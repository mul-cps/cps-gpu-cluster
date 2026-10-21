"""Offline executor integration: real typed configurations and SQLite; fake APIs."""
import copy
import json
import sqlite3
import subprocess
import sys
import uuid
from types import SimpleNamespace

import pytest

import aborted_reuse_guard as guard
from cps_compute.native_groups import _canonical, canonical_sha256 as sha
from cps_compute.native_group_approvals import ApprovalSnapshot
from cps_compute.native_registry_aborted_reuse import plan_aborted_policy_reuse
from test_native_delivery_addon_node_rollout import inputs
from test_native_node_config import ref


def module():
    import importlib
    return importlib.import_module('source_reuse_operator')


def fixture(tmp_path, monkeypatch):
    from cps_compute import native_registry_migration as migration
    from cps_compute import native_registry_aborted_reuse as reuse
    from cps_compute.native_approval_head import HeadSnapshot
    f, _, _, _, _, _, _, _, _ = inputs(tmp_path, monkeypatch)
    x = f.x
    previous_body = HeadSnapshot.load(x.core, f.previous.approval_head,
        f.old_policy, f.previous.deployment, component='node').approval.document['registry']
    previous = ApprovalSnapshot.from_document(previous_body, f.old_policy, f.previous.deployment,
        expected_revision=sha(previous_body))
    target = ApprovalSnapshot.from_document(x.source, f.policy, f.configuration.deployment,
        expected_revision=sha(x.source))
    database, reservations = tmp_path/'control.sqlite', tmp_path/'reservations.sqlite'
    with sqlite3.connect(database) as db:
        db.executescript('CREATE TABLE native_group_approval_revision(revision TEXT PRIMARY KEY,document TEXT);'
            'CREATE TABLE native_group_approval_head(id INTEGER PRIMARY KEY,revision TEXT);'
            'CREATE TABLE audit_record(seq INTEGER PRIMARY KEY,record TEXT);')
        # The current age snapshot carries the full old-policy registry; preserve
        # its authenticated earlier Source rows from the real delivery fixture.
        # plan_policy_upgrade validates the two captured typed rows, not a fabricated history.
        db.executemany('INSERT INTO native_group_approval_revision VALUES(?,?)',
            [(previous.revision,previous._document.decode()),(target.revision,target._document.decode())])
        db.execute('INSERT INTO native_group_approval_head VALUES(1,?)',(previous.revision,))
        db.execute('INSERT INTO audit_record VALUES(1,?)',('{"operation":"reviewed-abort"}',))
        revision_rows=db.execute('SELECT revision,document FROM native_group_approval_revision ORDER BY revision').fetchall()
        audit_rows=db.execute('SELECT seq,record FROM audit_record ORDER BY seq').fetchall()
    with sqlite3.connect(reservations) as db:
        db.executescript('CREATE TABLE reservation(person TEXT,workspace TEXT); CREATE TABLE reservation_binding(workspace TEXT,attempt TEXT,binding TEXT);')
    real_database=migration._database; opens=[]
    def mapped_database(primary, secondary, *, write):
        assert str(primary)=='/data/control.sqlite' and str(secondary)=='/data/reservations.sqlite'
        opens.append(write)
        return real_database(database,reservations,write=write)
    monkeypatch.setattr(migration,'_database',mapped_database)
    monkeypatch.setattr(reuse,'_database',mapped_database)
    def obj(kind,name,**kwargs):
        return dict(apiVersion='apps/v1' if kind=='Deployment' else 'v1',kind=kind,
            metadata={'namespace':'test','name':name,'uid':str(uuid.uuid4()),'resourceVersion':'1'},**kwargs)
    deployments={}
    for component in ('gateway','hub:cps','hub:cit','writer'):
        deployments[component]=obj('Deployment',component.replace(':','-'),spec={'replicas':0,
            'template':{'spec':{'serviceAccountName':component.replace(':','-')}}})
    services={key:obj('Service','source-'+key,spec={'selector':{'maintenance':'fenced'}}) for key in ('cps','cit')}
    binder=obj('Deployment','binder',spec={'replicas':1,'template':{'spec':{'containers':[
        {'name':'binder','args':['--native-pending-coordinator-enabled=false']}]}}})
    epoch=f.configuration.deployment.node_pool
    epoch={key:epoch[key] for key in ('node_uid','boot_id','driver_generation','gpu_uuid')}
    capsule=obj('ConfigMap','abort',immutable=True,data={'plan.json':_canonical({
        'operation':'abort-unacknowledged-policy-handover','sql_before_revision':target.revision,'old_epoch':epoch}).decode()})
    compact={key:capsule['metadata'][key] for key in ('namespace','name','uid')}; compact['data_sha256']=sha(capsule['data'])
    physical={'version':1,'operation':'reuse-exact-retained-aborted-source','capsule':compact,
        'capsule_sha256':sha(capsule['data']),'deployments':deployments,'services':services,
        'roles':{},'heads':{},'acks':{},'ledger':obj('ConfigMap','ledger',data={'state.json':json.dumps({'allocations':{}})}),
        'epoch':epoch,'node_configuration':f.previous.reference.to_dict(),'policy':f.old_policy.catalog,
        'target_revision':target.revision,'target_policy_hash':f.policy.hash}
    evidence={'identity':capsule['metadata']['uid'],'sha256':sha(capsule['data'])}
    pure=dict(old_policy=f.old_policy,policy=f.policy,previous=previous,target=target,
        revision_rows=revision_rows,head_rows=[(1,previous.revision)],audit_rows=audit_rows,
        retained_target_document=target._document.decode(),abort_evidence=evidence,actor='reviewed-operator')
    source={'old_policy':f.old_policy.catalog,'policy':f.policy.catalog,
        'previous_node_configuration':f.previous.reference.to_dict(),'node_configuration':f.configuration.reference.to_dict(),
        'previous_revision':previous.revision,'target_revision':target.revision,'actor':pure['actor'],
        'revision_rows_sha256':sha(revision_rows),'revision_rows_count':len(revision_rows),
        'audit_rows_sha256':sha(audit_rows),'audit_rows_count':len(audit_rows),'head_rows':[[1,previous.revision]],
        'retained_target_document_sha256':'sha256:'+__import__('hashlib').sha256(target._document).hexdigest(),
        'retained_target_document_bytes':len(target._document)}
    body={'version':1,'physical_plan':physical,'quiescence_plan':{'version':1,'source_services':services,
        'writer':deployments['writer'],'binder':binder},'source':source}
    sealed=obj('ConfigMap','sealed',immutable=True,data={'operator.json':_canonical(body).decode()})
    packet={'version':1,'capsule_ref':ref(sealed).to_dict(),'abort_evidence':evidence}
    # Fake clients expose actual independent GETs; only the preexisting physical
    # guard is replaced by its actual validator + a synthetic full observation.
    maps={(c['metadata']['namespace'],c['metadata']['name']):c for c in (sealed,capsule,physical['ledger'])}
    original_cm=x.core.read_namespaced_config_map
    reads=[]
    def cm(name,namespace,**kwargs):
        reads.append((namespace,name))
        return copy.deepcopy(maps[(namespace,name)]) if (namespace,name) in maps else original_cm(name,namespace)
    x.core.read_namespaced_config_map=cm
    x.core.read_namespaced_service=lambda name,namespace,**kw:copy.deepcopy(next(v for v in services.values() if v['metadata']['name']==name))
    x.core.read_namespaced_endpoints=lambda name,namespace,**kw:obj('Endpoints',name,subsets=[])
    apps=SimpleNamespace(read_namespaced_deployment=lambda name,namespace,**kw:copy.deepcopy(binder if name=='binder' else deployments['writer']))
    calls=[]
    def capture(plan,*clients):
        calls.append(copy.deepcopy(plan))
        value={k:copy.deepcopy(plan[k]) for k in ('capsule','deployments','services','roles','heads','acks','ledger','epoch')}
        value.update(publishers_absent=True,fenced_endpoints_empty=True)
        return value
    actual_capture=guard.capture
    monkeypatch.setattr(guard,'capture',capture)
    return SimpleNamespace(**locals())


def test_default_inert_needs_no_sdk_or_inputs():
    result=subprocess.run([sys.executable,'-I','-B',str(__import__('pathlib').Path(__file__).with_name('source_reuse_operator.py'))],capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)['execute'] is False


def test_typed_plan_real_transaction_and_fresh_both_boundary_capsules(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    result=module().execute(f.packet,sha(plan_aborted_policy_reuse(**f.pure)),core=f.x.core,apps=f.apps,rbac=object(),batch=object())
    assert result['committed'] is True
    assert f.opens==[False,True] and len(f.calls)==2
    assert all(c['capsule']==f.capsule for c in f.calls)
    assert f.reads.count(('test','sealed'))>=5 and f.reads.count(('test','abort'))==3
    with sqlite3.connect(f.database) as db:
        assert db.execute('SELECT revision,document FROM native_group_approval_revision ORDER BY revision').fetchall()==f.revision_rows
        assert db.execute('SELECT revision FROM native_group_approval_head').fetchone()==(f.target.revision,)
        assert db.execute('SELECT seq,record FROM audit_record ORDER BY seq').fetchall()[:-1]==f.audit_rows


def unchanged(f):
    with sqlite3.connect(f.database) as db:
        assert db.execute('SELECT revision,document FROM native_group_approval_revision ORDER BY revision').fetchall()==f.revision_rows
        assert db.execute('SELECT id,revision FROM native_group_approval_head ORDER BY id').fetchall()==[(1,f.previous.revision)]
        assert db.execute('SELECT seq,record FROM audit_record ORDER BY seq').fetchall()==f.audit_rows


@pytest.mark.parametrize('fault',['sealed-uid','sealed-data','abort-uid','abort-data','abort-owner',
    'abort-mutable','descriptor','review','sql-history','sql-audit','target-config','source-fence',
    'writer-unpaused','binder-enabled','ready-endpoint','not-ready-endpoint'])
def test_changed_authority_preimage_or_quiescence_denies_without_sql_mutation(tmp_path,monkeypatch,fault):
    f=fixture(tmp_path,monkeypatch); reviewed=sha(plan_aborted_policy_reuse(**f.pure))
    if fault=='sealed-uid': f.sealed['metadata']['uid']=str(uuid.uuid4())
    elif fault=='sealed-data': f.sealed['data']['operator.json']+=' '
    elif fault=='abort-uid': f.capsule['metadata']['uid']=str(uuid.uuid4())
    elif fault=='abort-data': f.capsule['data']['plan.json']+=' '
    elif fault=='abort-owner': f.capsule['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    elif fault=='abort-mutable': f.capsule['immutable']=False
    elif fault=='descriptor': f.packet['abort_evidence']['identity']=str(uuid.uuid4())
    elif fault=='review': reviewed='sha256:'+'f'*64
    elif fault.startswith('sql-'):
        with sqlite3.connect(f.database) as db:
            if fault=='sql-history':db.execute('UPDATE native_group_approval_revision SET document=document||? WHERE revision=?',(' ',f.target.revision))
            else:db.execute('UPDATE audit_record SET record=?',('rewritten',))
    elif fault=='target-config':
        r=f.f.configuration.reference.to_dict(); f.x.f.objects[(r['namespace'],r['name'])]['data']['config.json']+=' '
    elif fault=='source-fence':f.services['cps']['spec']['selector']['maintenance']='open'
    elif fault=='writer-unpaused':f.deployments['writer']['spec']['replicas']=1
    elif fault=='binder-enabled':f.binder['spec']['template']['spec']['containers'][0]['args']=['--native-pending-coordinator-enabled=true']
    else:
        original=f.x.core.read_namespaced_endpoints
        def endpoint(*a,**kw):
            value=original(*a,**kw);value['subsets']=[{'addresses' if fault=='ready-endpoint' else 'notReadyAddresses':[{'ip':'10.0.0.1'}]}];return value
        f.x.core.read_namespaced_endpoints=endpoint
    with sqlite3.connect(f.database) as db: before=db.iterdump(); snapshot=list(before)
    with pytest.raises((ValueError,KeyError)):
        module().execute(f.packet,reviewed,core=f.x.core,apps=f.apps,rbac=object(),batch=object())
    with sqlite3.connect(f.database) as db: assert list(db.iterdump())==snapshot


@pytest.mark.parametrize('fault',['sealed','original-capsule','quiescence','physical-false','physical-truthy'])
def test_before_commit_drift_rolls_back_real_head_and_audit(tmp_path,monkeypatch,fault):
    f=fixture(tmp_path,monkeypatch); original=f.x.core.read_namespaced_config_map
    sealed_calls=0
    def read(name,namespace,**kwargs):
        nonlocal sealed_calls
        if (namespace,name)==('test','sealed'):
            sealed_calls+=1
            # initial, firstQ, firstP, secondQ, secondP: mutate only after CAS.
            if sealed_calls==4:
                if fault=='sealed':f.sealed['metadata']['uid']=str(uuid.uuid4())
                elif fault=='original-capsule':f.capsule['data']['plan.json']+=' '
                elif fault=='quiescence':f.deployments['writer']['spec']['replicas']=1
        return original(name,namespace,**kwargs)
    f.x.core.read_namespaced_config_map=read
    if fault.startswith('physical-'):
        actual_observe=guard.observe; count=0
        def observe(*args):
            nonlocal count
            count+=1
            if count==2:return False if fault=='physical-false' else 1
            return actual_observe(*args)
        monkeypatch.setattr(guard,'observe',observe)
    with pytest.raises(ValueError):
        module().execute(f.packet,sha(plan_aborted_policy_reuse(**f.pure)),core=f.x.core,apps=f.apps,rbac=object(),batch=object())
    unchanged(f)
    assert f.opens==[False,True]  # no callback reenters any DB capture


def test_protected_input_pin_denies_before_client_creation(tmp_path,monkeypatch):
    p=tmp_path/'input.json';p.write_text('{}');p.chmod(0o600)
    with pytest.raises(ValueError,match='raw SHA'):
        module().main(['--execute','--input',str(p),'--input-sha256','sha256:'+'f'*64,
            '--reviewed-plan-sha256','sha256:'+'e'*64])


def test_full_existing_physical_capture_with_real_old_node_epoch_and_api_reads(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    # The original can approach the API limit without being duplicated in the seal.
    f.capsule['data']['retained-proof.txt']='x'*950000
    f.compact['data_sha256']=f.physical['capsule_sha256']=f.evidence['sha256']=sha(f.capsule['data'])
    assert set(f.body['physical_plan']['capsule'])=={'namespace','name','uid','data_sha256'}
    assert len(_canonical(f.body))<1024*1024
    # Exercise the unchanged guard's real capture, including typed old Node,
    # current Pod/RS/ACK and complete Pod/Job API lists, instead of synthetic view.
    node=f.f.previous.document['component_declarations']['node']
    actual_apps=f.x.f.f.apps
    node_dep=f.x.f.f.deps[(node['namespace'],node['name'])]
    f.physical['deployments']['node']=node_dep
    node_target=f.f.previous.document['acknowledgment_targets']['node']
    f.physical['acks']['node']=f.x.core.read_namespaced_config_map(node_target['name'],node_target['namespace'])
    pointer=f.f.previous.approval_head['anchor']['pointer']
    f.physical['heads']['node']=f.x.core.read_namespaced_config_map(pointer['name'],pointer['namespace'])
    f.sealed['data']['operator.json']=_canonical(f.body).decode()
    f.packet['capsule_ref']=ref(f.sealed).to_dict()
    def deployment(name,ns,**kwargs):
        if (ns,name)==(node['namespace'],node['name']):return copy.deepcopy(node_dep)
        if name=='binder':return copy.deepcopy(f.binder)
        return copy.deepcopy(next(d for d in f.deployments.values() if d['metadata']['name']==name))
    f.apps.read_namespaced_deployment=deployment
    f.apps.read_namespaced_replica_set=actual_apps.read_namespaced_replica_set
    def listing(kind,values):
        return {'apiVersion':'v1' if kind=='PodList' else 'batch/v1','kind':kind,
            'metadata':{'resourceVersion':'500'},'items':copy.deepcopy(values)}
    f.x.core.list_namespaced_pod=lambda ns,**kw:listing('PodList',[
        p for (namespace,_),p in f.x.f.f.pods.items() if namespace==ns
        and p['spec'].get('serviceAccountName')==node['service_account']])
    batch=SimpleNamespace(list_namespaced_job=lambda ns,**kw:listing('JobList',[]))
    monkeypatch.setattr(guard,'capture',f.actual_capture)
    result=module().execute(f.packet,sha(plan_aborted_policy_reuse(**f.pure)),
        core=f.x.core,apps=f.apps,rbac=SimpleNamespace(read_namespaced_role=None),batch=batch)
    assert result['committed'] is True and f.opens==[False,True]
    # initial hydration, plus independent hydration AND guard reread per phase
    assert f.reads.count(('test','abort'))==5
