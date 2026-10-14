#!/home/bjoern/git/cps-compute/.venv/bin/python
"""Root-only staged Node handover. Default inert; no live execution by worker.

refresh is read-only. begin establishes actual process absence. finish refuses
any unresolved Source/native reservation or enrollment custody. Root performs
normal authenticated Source Close when required; no release is manufactured.
"""
import argparse,ast,base64,copy,hashlib,importlib.util,json,os,subprocess,time,uuid
from datetime import datetime,timezone
from pathlib import Path

HERE=Path('/home/bjoern/.local/state/cps-full-project-20261013/native-kai-node-epoch-handover-preparation-20261014')
SOURCE=Path('/home/bjoern/git/cps-gpu-cluster-worktrees/native-kai-node-epoch-handover-20261014/platform-staging/scheduler/native-kai-node-epoch-image')
RECOVERY=Path('/home/bjoern/.local/state/cps-full-project-20261013/current-pair-mps-preparation-20261014/recovery-review-only-20261014/execute_normal_close.py')
EXECUTOR=Path('/home/bjoern/.local/state/cps-full-project-20261013/gateway-readiness-handover-preparation-20261014/execute_gateway_handover.py')

def load(name,path,sha=None):
    if sha and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Exact existing software bytes required')
    s=importlib.util.spec_from_file_location(name,path);x=importlib.util.module_from_spec(s);s.loader.exec_module(x);return x

def setup():
    c=load('sealed_node_capture',HERE/'capture.py');m,h,r=c.m,c.h,c.r
    adapter_module=load('sealed_node_adapter',SOURCE/'handover_adapter.py')
    adapter=adapter_module.install(h,m.read(HERE/'node-code-current.json'),m.read(HERE/'capture-input-preimage.json'));m.h=h
    m._node_original_capture=m.capture
    e=load('sealed_node_mutations',SOURCE/'handover_execution.py')
    old=load('sealed_existing_executor',EXECUTOR,'48bf9424814833508c60a8c51b824926439500076026191de366f4fa5ce112c5')
    # Existing pause and new-seed activation interfaces, with a narrow Node scope.
    e.bind_existing_executor(old,m,h,r,adapter,hashlib.sha256((HERE/'fresh-preparation-native.json').read_bytes()).hexdigest())
    return c,m,h,r,adapter,e,old

def bounded(m,action,stage,seconds=150):
    deadline=time.monotonic()+seconds
    while True:
        try:return action()
        except (ValueError,RuntimeError,m.delivery.Pending) as error:
            if time.monotonic()>=deadline:raise RuntimeError('Bounded readback failed: '+stage) from error
            m.event('awaiting_actual_readback',stage=stage,error=type(error).__name__);time.sleep(3)

def source_status(api,m,directory,*,require_zero=True):
    result={}
    code=(HERE/'source_snapshot_code.py').read_text();reserve=(HERE/'source_reservation_code.py').read_text()
    for source,ws in [('cps','native-group-b'),('cit','native-group-a')]:
        prior=m.read(HERE/(source+'-console-preimage.json'));expected=prior['pod']
        actual=api.get('Pod',expected['metadata']['namespace'],expected['metadata']['name'])
        m.require(actual['metadata']['uid']==expected['metadata']['uid'] and not actual['metadata'].get('deletionTimestamp'),
                  'Exact current Source console UID required')
        for script,key in [(code,'records'),(reserve,'reservation')]:
            value=m.exec_json(api,actual['metadata']['namespace'],actual['metadata']['name'],'console',script,
                             {'source':source,'workspace':ws})
            result.setdefault(source,{})[key]=value
        if require_zero:
            m.require(all(w.get('state')=='stopped' for w in result[source]['records']['same_group_writers']),
                      'Prior in-flight Source attempt: normal Source Close required before handover')
            row=result[source]['reservation']['reservation']
            m.require(row['active'] is False and row.get('attempt') is None,'Held generic charge: normal Source Close required')
    m.write(directory/('source-status-'+uuid.uuid4().hex[:8]+'.json'),result)
    return result

def ledger_zero(api,m,plan,directory):
    before=m.read(HERE/'fresh-preparation-native.json');actual=api.get('ConfigMap','cps-native-system','cps-native-gpu-allocations')
    m.require(actual['metadata']['uid']==before['ledger_uid'],'Retained global native ledger UID required')
    rows=m.r.parse(actual['data']['state.json'])['allocations']
    m.require(all(x['state']=='released' for x in rows.values()),'Pending/enrolling/enrolled/unknown native custody requires genuine Close/cleanup; no expiry release')
    for scope,row in plan['request']['qualification']['workspaces'].items():
        m.require(api.get('Pod',row['namespace'],row['pod'],missing=True) is None,'Actual approved workload Pod must remain absent')
    result={'uid':actual['metadata']['uid'],'resourceVersion':actual['metadata']['resourceVersion'],
            'full_data_sha256':m.r.canonical_sha256(actual['data']),'all_rows_released':True}
    m.write(directory/('ledger-zero-'+uuid.uuid4().hex[:8]+'.json'),result);return result

def packet(api,c,m,h,r,adapter,directory):
    base=m.preflight(api,'read-only-root-review');obs=m.observe(api,base['publication'])
    current=api.get('ConfigMap','cps-native-system',adapter.code['metadata']['name'])
    m.require(current['metadata']['uid']==adapter.code['metadata']['uid'] and current['metadata']['resourceVersion']==adapter.code['metadata']['resourceVersion']
              and current['data']==adapter.code['data'],'Retained exact code object required')
    controller=copy.deepcopy(base['controller']);controller['spec']['replicas']=0;suffix=directory.name[-8:]
    journal=r.parse(base64.b64decode(base['journal_packet']['raw'],validate=True))
    request={'version':1,'previous_publication':base['publication'],'previous_publication_sha256':r.canonical_sha256(base['publication']),
      'policy':base['seed']['policy'],'qualification':base['seed']['qualification'],
      'reviewed_images':{'node':{'previous':h.REVIEWED_IMAGE,'next':h.ACCOUNT_IMAGE}},'observations':obs,'gateway_runtime':obs['gateway_runtime'],
      'old_state':{'seed':base['seed'],'seed_sha256':c.SEED,'journal':journal,'journal_sha256':r.canonical_sha256(journal),
        'controller':controller,'journal_pvc':base['pvc'],
        'next_journal':{'namespace':m.NS,'name':'cps-native-delivery-journal-node-'+suffix},
        'next_input_secret':{'namespace':m.NS,'name':'cps-native-delivery-input-node-'+suffix}}}
    plan=h.plan_intent(request,now=datetime.now(timezone.utc));adapter.validate_scope(plan)
    for key,kind in [('next_journal','PersistentVolumeClaim'),('next_input_secret','Secret')]:
        row=plan['lineage'][key];m.require(api.get(kind,row['namespace'],row['name'],missing=True) is None,'New owned lineage name must be unused')
    m.write(directory/'preflight.json',base);m.write(directory/'plan-request.json',request);m.write(directory/'plan.json',plan)
    source_status(api,m,directory);ledger_zero(api,m,plan,directory);native_baseline(api,m,plan,directory)
    return plan

def reader_code(m):
    tree=ast.parse(Path('/home/bjoern/git/cps-gpu-cluster-worktrees/full-project-completion-20261013/platform-staging/gpu/qualification/concurrent-source5/host.py').read_text())
    code=next(ast.literal_eval(x.value) for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id=='NATIVE_READER' for y in x.targets))
    m.require(hashlib.sha256(code.encode()).hexdigest()=='e206dd57ebbb61fd9317549ab8606d7ccb47baf0cf538c05eb9aeb2e87e7cbda','Exact existing read-only native fd reader required')
    return code

def native_baseline(api,m,plan,directory):
    expected=plan['request']['observations']['pods']['node'];meta=expected['metadata']
    current=api.get('Pod',meta['namespace'],meta['name'])
    m.require(current['metadata']['uid']==meta['uid'] and not current['metadata'].get('deletionTimestamp'),'Exact current Node Pod required for readonly baseline')
    pool=plan['request']['qualification']['node_pool']
    value=m.exec_json(api,meta['namespace'],meta['name'],plan['request']['previous_publication']['process_declarations']['node']['container'],reader_code(m),{'pool':pool})
    m.require(set(value)=={'inventory','epoch','records','previous'} and value['epoch']=={k:pool[k] for k in ('boot_id','driver_generation')}
      and value['inventory']['gpu_uuid']==pool['gpu_uuid'] and value['records']==value['previous']=={}
      and sum(not x['offline'] for x in value['inventory']['entries'])==0 and sum(x['used'] for x in value['inventory']['entries'])==0,'Actual current protected native inventory must be zero')
    after=api.get('Pod',meta['namespace'],meta['name']);node=api.get('Node','',pool['node'])
    m.require(after['metadata']['uid']==meta['uid'] and after['spec']==current['spec'] and node['metadata']['uid']==pool['node_uid'],'Actual readonly inventory process/Node custody changed')
    m.write(directory/('pre-barrier-native-'+uuid.uuid4().hex[:8]+'.json'),value);return value

def probe(api,m,plan,e,directory):
    directory=directory/('observer-'+uuid.uuid4().hex[:8]);directory.mkdir(mode=0o700)
    code=reader_code(m)
    candidate=e.readonly_probe(m,plan,code);meta=candidate['metadata']
    m.require(api.get('Pod',meta['namespace'],meta['name'],missing=True) is None,'Owned native observer name must be unused')
    m.write(directory/'native-observer-candidate.json',candidate)
    created=api.command(['create','-n',meta['namespace'],'-f','-','-o','json'],candidate);m.write(directory/'native-observer-created.json',created)
    try:
        result=bounded(m,lambda:e.inspect_probe(api,m,plan,created,candidate),'post-barrier-protected-native-zero',seconds=45)
        m.write(directory/'post-barrier-native-zero.json',result)
        pool=plan['request']['qualification']['node_pool']
        epoch={'driver_epoch':{k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')},'captured_at':datetime.now(timezone.utc).isoformat()}
        m.write(directory/'independent-physical-epoch.json',epoch)
        return epoch
    finally:
        # Unknown CREATE outcomes are held; only a returned actual UID can be cleaned.
        e.delete_probe(api,m,created)
        bounded(m,lambda:m.require(api.get('Pod',meta['namespace'],meta['name'],missing=True) is None,'Owned probe absence required'),
                'exact-observer-cleanup',seconds=45)

def code_manifest(m,context):
    paths=[HERE/'capture.py',HERE/'source_snapshot_code.py',HERE/'source_reservation_code.py',HERE/'node-code-current.json',HERE/'fresh-preparation-native.json',HERE/'cps-console-preimage.json',HERE/'cit-console-preimage.json',HERE/'capture-input-preimage.json',EXECUTOR.with_name('gateway_handover.py'),EXECUTOR.parent.parent/'activate-reviewed-hub-neutral-delivery-20261014.py']
    return {'context':context,'runner_sha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
      'helper_sha256':hashlib.sha256(Path(m.h.__file__).read_bytes()).hexdigest(),
      'adapter_sha256':hashlib.sha256((SOURCE/'handover_adapter.py').read_bytes()).hexdigest(),
      'executor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'mutation_module_sha256':hashlib.sha256((SOURCE/'handover_execution.py').read_bytes()).hexdigest(),
      'observer_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
      'software':m.verified_software(),'live_applied':False}

def process_epoch(api,m,publication,directory):
    scope=copy.deepcopy(publication);scope['process_declarations']={'node':scope['process_declarations']['node']}
    rows=api.processes(scope);pod=rows['pods']['node'];meta=pod['metadata']
    pool=m.read(HERE/'fresh-preflight.json')['seed']['qualification']['node_pool']
    value=m.exec_json(api,meta['namespace'],meta['name'],scope['process_declarations']['node']['container'],reader_code(m),{'pool':pool})
    m.require(value['epoch']=={k:pool[k] for k in ('boot_id','driver_generation')} and value['inventory']['gpu_uuid']==pool['gpu_uuid']
      and sum(not x['offline'] for x in value['inventory']['entries'])==0 and sum(x['used'] for x in value['inventory']['entries'])==0,'Actual permission-bootstrap physical epoch/inventory must match')
    after=api.get('Pod',meta['namespace'],meta['name']);node=api.get('Node','',pool['node'])
    m.require(after['metadata']['uid']==meta['uid'] and after['spec']==pod['spec'] and node['metadata']['uid']==pool['node_uid'],'Actual permission-bootstrap Pod/Node custody changed')
    proof={'driver_epoch':{k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')},'captured_at':datetime.now(timezone.utc).isoformat()}
    m.write(directory/('permission-bootstrap-native-'+uuid.uuid4().hex[:8]+'.json'),{'epoch':proof,'native':value,'pod_uid':meta['uid']})
    return proof

def finalize_phase(api,m,h,e,old,context,work,plan):
    old_gateway=plan['gateway_pod_restart_precondition']
    bounded(m,lambda:m.require(api.get('Pod',old_gateway['namespace'],old_gateway['name'],missing=True) is None,'Old Gateway Pod must be absent'),
            'exact-old-gateway-process-absence')
    # Structural discovery precedes Node-dependent /epoch permission bootstrap.
    bounded(m,lambda:api.processes(plan['projection']),'actual-node-and-gateway-structure')
    binding=bounded(m,lambda:e.capture_input_readback(api,m,h,plan,work),'actual-capture-input-and-mounted-config')
    m.write(work/'capture-input-readback.json',binding)
    # Permission bootstrap uses the independent actual fd/NodeUID epoch;
    # after exact RoleCAS, the unchanged authenticated /epoch route must pass.
    original_capture=m.capture
    def permission_capture(api,publication):
        packet=e.source_capture(api,m,publication)
        packet['epoch']=process_epoch(api,m,publication,work)
        return packet
    m.capture=permission_capture
    try:m.process_access(api,work)
    finally:m.capture=original_capture
    access=m.read(work/'process-access.json')
    bounded(m,lambda:h.finalize_intent(plan,access,m.observe(api,plan['projection']),now=datetime.now(timezone.utc)),'fresh-four-process-acknowledgments')
    m.finalize(api,work)
    a=old.activation();activation=a.software(context,work);a.plan_activation(api,work,activation);a.activate(api,work,activation)
    bounded(m,lambda:a.readback(api,work,activation),'new-completed-delivery-journal',seconds=240)

def inverse_phase(api,m,h,adapter,e,old,context,directory,work,fresh,code):
    controller=m.controller_current(api)
    m.require(h.identity(controller,'Deployment')==fresh['lineage']['controller']
      and controller['spec']==fresh['request']['old_state']['controller']['spec']
      and not m.controller_pods(api,controller),'Pre-activation inverse requires exact retained paused zero-Pod delivery controller')
    for key,kind in [('next_journal','PersistentVolumeClaim'),('next_input_secret','Secret')]:
        row=fresh['lineage'][key]
        m.require(api.get(kind,row['namespace'],row['name'],missing=True) is None,
          'Delivery activation started or outcome unknown: hold; capture a separate sealed successor instead')
    restore=load('sealed_node_adapter_restore',SOURCE/'handover_adapter.py').RestoreHandover(adapter)
    source_status(api,m,directory);ledger_zero(api,m,fresh,directory)
    invdir=directory/('inverse-phase-'+uuid.uuid4().hex[:8]);invdir.mkdir(mode=0o700)
    roles={k:api.get('Role',*k.split('/')) for k in fresh['request']['observations']['roles']}
    # Authenticated capture proves Source/epoch without requiring the absent Node.
    gateway_scope=e.capture_scope(api,fresh)
    e.source_capture(api,m,gateway_scope)
    gateway_scope['process_declarations']={'gateway':gateway_scope['process_declarations']['gateway']}
    gateway=api.processes(gateway_scope)['pods']['gateway']
    runtime=api.get('Secret',fresh['request']['gateway_runtime']['metadata']['namespace'],fresh['request']['gateway_runtime']['metadata']['name'])
    access=m.read(work/'process-access.json') if (work/'process-access.json').exists() else None
    inverse=restore.plan(fresh,roles,runtime,gateway,access)
    paused=e.pause_restore_node(api,m,fresh,invdir)
    bounded(m,lambda:e.absent_restore_node(api,m,fresh,paused),'inverse-node-process-absence')
    source_status(api,m,invdir);ledger_zero(api,m,fresh,invdir);epoch=probe(api,m,inverse,e,invdir)
    restore.install()
    for name in ('old-journal-exact.json','old-journal-byte-receipt.json'):
        m.write(invdir/name,m.raw_private(work/name),raw=True)
    m.write(invdir/'preflight.json',m.read(directory/'preflight.json'));m.write(invdir/'operator-code.json',code)
    m.write(invdir/'plan.json',inverse)
    e.apply_restore(api,m,h,inverse,fresh,paused,invdir,epoch)
    finalize_phase(api,m,h,e,old,context,invdir,inverse)
    m.event('node_inverse_completed',directory=str(invdir),ready=True,old_journal_untouched=True,production_qualified=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['refresh','begin','finish','inverse-intent','restore','recover-gateway'])
    p.add_argument('--directory',type=Path);p.add_argument('--reviewed-plan-sha256');p.add_argument('--execute',action='store_true');args=p.parse_args()
    if args.mode is None:print('{"inert":true,"api_calls":false,"mutations":false}');return
    c,m,h,r,adapter,e,old=setup();context=subprocess.check_output(['kubectl','config','current-context'],text=True).strip();api=m.delivery.Kubectl(context)
    if args.mode=='refresh':
        directory=HERE/('run-'+uuid.uuid4().hex[:8]);directory.mkdir(mode=0o700)
        plan=packet(api,c,m,h,r,adapter,directory)
        m.write(directory/'operator-code.json',code_manifest(m,context))
        m.event('root_review_required',directory=str(directory),plan_sha256=r.canonical_sha256(plan),live_applied=False);return
    directory=args.directory;m.require(directory is not None and directory.parent==HERE and directory.name.startswith('run-'),'Exact owned reviewed packet directory required')
    plan=m.read(directory/'plan.json');code=m.read(directory/'operator-code.json')
    m.require(args.reviewed_plan_sha256==r.canonical_sha256(plan) and code==code_manifest(m,context),
        'Exact Root-reviewed complete packet, observers, data custody and code bytes required')
    adapter.validate_scope(plan)
    if args.mode=='inverse-intent':
        m.write(directory/('inverse-'+uuid.uuid4().hex[:8]+'.json'),e.restoration_intents(api,m,plan));return
    m.require(args.execute,'Root must explicitly execute the reviewed mutation phase')
    work=directory/('phase-'+directory.name[-8:])
    if args.mode=='begin':
        work.mkdir(mode=0o700)
        source_status(api,m,directory);ledger_zero(api,m,plan,directory);native_baseline(api,m,plan,directory)
        # Existing stable retained-journal stop/read protocol; its admitted scope
        # regenerates fresh CAS RVs without changing the reviewed target.
        old.pause(api,directory,plan);m.write(work/'operator-code.json',code)
        m.write(work/'preflight.json',m.read(directory/'preflight.json'))
        fresh=m.read(work/'plan.json');adapter.validate_scope(fresh)
        e.pause_node(api,m,fresh,work)
        bounded(m,lambda:e.absent_node(api,m,fresh),'exact-old-node-process-absence')
        source_status(api,m,work);ledger_zero(api,m,fresh,work);probe(api,m,fresh,e,work)
        m.event('node_admission_barrier_ready',directory=str(work),node_process_absent=True,preview_is_not_gpu_admission=True,live_applied=True);return
    fresh=m.read(work/'plan.json');adapter.validate_scope(fresh)
    if args.mode=='recover-gateway':
        recovery=directory/('gateway-recovery-'+uuid.uuid4().hex[:8]);recovery.mkdir(mode=0o700)
        e.recover_gateway(api,m,h,fresh,recovery)
        m.event('gateway_only_preimages_restored',directory=str(recovery),node_process_absence_barrier_retained=True,
          Source_HTTP_and_ledger_fd_zero_still_required=True,node_resumed=False,capacity_released=False,delivery_activated=False);return
    if args.mode=='restore':
        inverse_phase(api,m,h,adapter,e,old,context,directory,work,fresh,code);return
    e.absent_node(api,m,fresh)
    source_status(api,m,work);ledger_zero(api,m,fresh,work)
    epoch=probe(api,m,fresh,e,work)
    e.resume_candidate(api,m,h,adapter,fresh,work,epoch)
    finalize_phase(api,m,h,e,old,context,work,fresh)
    m.event('node_handover_completed',directory=str(work),ready=True,production_qualified=False)

if __name__=='__main__':main()
