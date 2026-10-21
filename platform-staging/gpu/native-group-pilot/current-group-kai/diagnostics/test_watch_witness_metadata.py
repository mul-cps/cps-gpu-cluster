import io,json,sys,threading,uuid
from types import SimpleNamespace
import pytest
import watch_witness_metadata as m

UID='11111111-1111-4111-8111-111111111111'
def cm(name=m.ACK,uid=UID,rv='1'):
    raw={'component':'node','observed_at':'2026-10-22T00:00:00+00:00','process':{'uid':UID,'private':'SECRET'},'members':['SECRET'],'token':'SECRET'}
    if name==m.LEDGER:raw={'version':1,'allocations':{'private-binding':{'state':'released','members':['SECRET'],'token':'SECRET'}}}
    return {'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':m.NAMESPACE,'name':name,'uid':uid,'resourceVersion':rv,'annotations':{'secret':'SECRET'}},'data':{'ack.json' if name==m.ACK else 'state.json':json.dumps(raw)}}

def test_default_never_loads_clients_or_creates_file(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(m,'clients',lambda:pytest.fail('Credentials must remain unread'))
    path=tmp_path/'trace.jsonl';assert m.main(['--output',str(path)])==0
    assert json.loads(capsys.readouterr().out)['inert'] is True and not path.exists()

def test_projection_drops_all_credential_and_member_bodies():
    for name in (m.ACK,m.LEDGER):
        value=m.project(cm(name),name,UID);out=json.dumps(value)
        assert 'SECRET' not in out and 'members' not in out and 'private-binding' not in out
        assert value['uid']==UID and value['resource_version']=='1'
    assert m.project(cm(m.LEDGER),m.LEDGER,UID)['state_counts']=={'released':1}

def test_uid_replacement_fails_closed():
    with pytest.raises(m.SampleError,match='uid_replaced'):m.project(cm(uid=str(uuid.uuid4())),m.ACK,UID)

def test_private_output_exclusive_symlink_and_mode(tmp_path):
    tmp_path.chmod(0o700);path=tmp_path/'trace.jsonl'
    with m.private_output(path) as out:out.write('{}\n')
    assert path.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):m.private_output(path)
    link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(OSError):m.private_output(link)
    tmp_path.chmod(0o755)
    with pytest.raises(m.SampleError):m.private_output(tmp_path/'other')

def test_watch_reconnect_uses_last_event_or_bookmark_rv_and_two_named_read_only_calls():
    calls=[];records=[];now=[0.0];stop=threading.Event()
    class Watch:
        def stop(self):pass
        def stream(self,method,**kwargs):
            calls.append(kwargs);now[0]+=1
            if len(calls)==1:yield {'type':'MODIFIED','raw_object':cm(rv='2')}
            elif len(calls)==2:yield {'type':'BOOKMARK','raw_object':{'metadata':{'resourceVersion':'3'}}}
            else:now[0]=5
    m.watch_one(SimpleNamespace(list_namespaced_config_map=lambda:None),Watch,m.ACK,UID,'1',5,stop,records.append,lambda:now[0])
    assert [c['resource_version'] for c in calls]==['1','2','3']
    assert all(c['field_selector']=='metadata.name='+m.ACK and c['namespace']==m.NAMESPACE and 1<=c['timeout_seconds']<=30 for c in calls)
    assert all(c['allow_watch_bookmarks'] is True for c in calls)

def test_410_never_regets_or_silently_skips_history():
    class Expired(Exception):status=410
    class Watch:
        def stop(self):pass
        def stream(self,*a,**k):raise Expired('SECRET BODY');yield
    records=[]
    with pytest.raises(m.SampleError,match='history_lost'):
        m.watch_one(SimpleNamespace(list_namespaced_config_map=lambda:None),Watch,m.ACK,UID,'1',10,threading.Event(),records.append,lambda:0)
    assert 'SECRET' not in json.dumps(records)

def test_parsed_witness_metadata_preserves_ledger_and_enrollment_hashes_only():
    obj=cm();ack=json.loads(obj['data']['ack.json']);target={'namespace':m.NAMESPACE,'name':m.ACK,'uid':UID}
    config={'namespace':m.NAMESPACE,'name':'node-config','uid':UID,'resourceVersion':'4','data_sha256':'sha256:'+'a'*64,'key':'config.json'}
    common={'version':1,'acknowledgment':target,'ack_sha256':m.sha(m.canonical(ack)),'node_configuration_ref':config}
    custody=dict(common,ledger={'namespace':m.NAMESPACE,'name':m.LEDGER,'uid':UID,'resource_version':'77','data_sha256':'sha256:'+'b'*64},enrollments=[{
        'namespace':m.NAMESPACE,'name':'cps-native-enrollment-'+'c'*40,'uid':UID,'pod_uid':UID,'binding_id':'c'*60,'data_sha256':'sha256:'+'d'*64}])
    pending=dict(common,pending=[{'binding_id':'c'*60,'pod_uid':UID,'document_sha256':'sha256:'+'e'*64}])
    obj['metadata']['annotations'].update({m.CUSTODY:m.canonical(custody),m.PENDING:m.canonical(pending)})
    projected=m.project(obj,m.ACK,UID)
    assert projected[m.CUSTODY]['valid'] and projected[m.CUSTODY]['matches_ack']
    assert projected[m.CUSTODY]['ledger']['resource_version']=='77'
    assert projected[m.CUSTODY]['enrollments'][0]['data_sha256']=='sha256:'+'d'*64
    assert projected[m.PENDING]['pending']==[{'pod_uid':UID,'document_sha256':'sha256:'+'e'*64}]
    assert 'SECRET' not in json.dumps(projected) and 'binding_id' not in json.dumps(projected)

def test_two_worker_failure_drains_and_exports_no_error_body():
    out=io.StringIO();gets=[];instances=[]
    class Core:
        def list_namespaced_config_map(self,namespace,**kwargs):
            name=kwargs['field_selector'].split('=')[1];gets.append(name)
            return {'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'100'},'items':[cm(name)]}
    class Watch:
        def __init__(self):instances.append(self);self.stopped=False
        def stop(self):self.stopped=True
        def stream(self,*args,**kwargs):yield {'type':'MODIFIED','raw_object':cm(kwargs['field_selector'].split('=')[1],uid=str(uuid.uuid4()))}
    with pytest.raises(m.SampleError,match='uid_replaced'):m.collect(Core(),Watch,out,10)
    records=[json.loads(line) for line in out.getvalue().splitlines()]
    assert gets==[m.ACK,m.LEDGER] and len(instances)<=2 and all(w.stopped for w in instances)
    assert records[-1]['event']=='END' and records[-1]['threads_drained'] is True and records[-1]['complete'] is False
    assert all('observed_at' in row and row['monotonic_elapsed']>=0 for row in records)
    assert 'SECRET' not in out.getvalue()

def test_initial_list_failure_never_claims_complete():
    out=io.StringIO()
    class Core:
        def list_namespaced_config_map(self,*args,**kwargs):raise RuntimeError('SECRET ERROR BODY')
    with pytest.raises(RuntimeError):m.collect(Core(),lambda:pytest.fail('Must not start watch'),out,10)
    last=json.loads(out.getvalue().splitlines()[-1]);assert last['complete'] is False and last['threads_drained'] is True
    assert 'SECRET' not in out.getvalue()

@pytest.mark.parametrize('seconds',['9','421'])
def test_execute_outside_duration_bounds_never_loads_credentials_or_opens_output(tmp_path,monkeypatch,seconds,capsys):
    monkeypatch.setattr(m,'clients',lambda:pytest.fail('Credentials must remain unread'))
    path=tmp_path/'trace.jsonl';assert m.main(['--execute','--seconds',seconds,'--output',str(path)])==1
    assert not path.exists() and 'bounded_seconds_and_output_required' in capsys.readouterr().err

def test_stale_object_rv_uses_fresh_exact_list_collection_cursor():
    out=io.StringIO();gets=[];lists=[];versions=[]
    class Expired(Exception):status=410
    class Core:
        def read_namespaced_config_map(self,name,namespace,**kwargs):gets.append(name);return cm(name,rv='1')
        def list_namespaced_config_map(self,namespace,**kwargs):
            lists.append(kwargs);name=kwargs['field_selector'].split('=')[1]
            return {'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'100' if name==m.ACK else '101'},'items':[cm(name,rv='1')]}
    class Watch:
        def stop(self):pass
        def stream(self,*args,**kwargs):
            versions.append(kwargs['resource_version'])
            if kwargs['resource_version']=='1':raise Expired('SECRET expired object RV')
            yield {'type':'MODIFIED','raw_object':cm(kwargs['field_selector'].split('=')[1],uid=str(uuid.uuid4()),rv='102')}
    with pytest.raises(m.SampleError,match='uid_replaced'):m.collect(Core(),Watch,out,10)
    assert gets==[] and len(lists)==2 and all(row['limit']==2 and 'resource_version' not in row for row in lists)
    assert versions and versions[0] in ('100','101')
    initial=[json.loads(line) for line in out.getvalue().splitlines() if json.loads(line)['event']=='INITIAL']
    assert [row['resource_version'] for row in initial]==['1','1']
    assert [row['collection_resource_version'] for row in initial]==['100','101']

@pytest.mark.parametrize('fault',['zero','two','name','namespace','uid','continue','remaining','kind','rv'])
def test_initial_exact_list_requires_one_valid_named_uid_and_complete_collection(fault):
    value={'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'100'},'items':[cm()]}
    if fault=='zero':value['items']=[]
    elif fault=='two':value['items']*=2
    elif fault=='name':value['items'][0]['metadata']['name']=m.LEDGER
    elif fault=='namespace':value['items'][0]['metadata']['namespace']='foreign'
    elif fault=='uid':value['items'][0]['metadata']['uid']='not-uuid'
    elif fault=='continue':value['metadata']['continue']='next'
    elif fault=='remaining':value['metadata']['remainingItemCount']=False
    elif fault=='kind':value['kind']='List'
    else:value['metadata'].pop('resourceVersion')
    core=SimpleNamespace(list_namespaced_config_map=lambda **kwargs:value)
    with pytest.raises(m.SampleError):m.initial_snapshot(core,m.ACK,10)

def test_typed_configmap_list_items_may_omit_gvk_without_changing_standalone_guard():
    obj=cm();obj.pop('apiVersion');obj.pop('kind')
    value={'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'100'},'items':[obj]}
    core=SimpleNamespace(list_namespaced_config_map=lambda **kwargs:value)
    projected,version=m.initial_snapshot(core,m.ACK,10)
    assert projected['uid']==UID and projected['resource_version']=='1' and version=='100'
    assert set(obj)=={'metadata','data'}
    with pytest.raises(m.SampleError,match='invalid_configmap'):m.project(obj,m.ACK)

@pytest.mark.parametrize('key,bad',[('apiVersion','apps/v1'),('kind','Secret')])
def test_typed_list_never_overwrites_present_conflicting_item_type(key,bad):
    obj=cm();obj[key]=bad
    value={'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'100'},'items':[obj]}
    with pytest.raises(m.SampleError):m.initial_snapshot(SimpleNamespace(list_namespaced_config_map=lambda **kwargs:value),m.ACK,10)
