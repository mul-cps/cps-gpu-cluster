"""Bounded Node-only mutation phases, called only by Root's sealed executor.

No default action. No Source grant/record mutation, credential creation, expiry
release, driver write or replacement UID inference occurs here.
"""
import base64,copy,hashlib,json,os,stat,subprocess,uuid
from datetime import datetime,timezone
from pathlib import Path

PROBE_LOG_ROOT=Path('/home/bjoern/.local/state/cps-full-project-20261013/native-kai-node-epoch-handover-preparation-20261014/retained-probe-logs')


class ProbeTerminalError(Exception):
    """A real terminated reader is not a retryable absence/readiness wait."""


def need(ok,text):
    if not ok:raise ValueError(text)


def bind_existing_executor(old,m,h,r,adapter,recovery_sha):
    """Retain the pinned loader needed by the existing activation phase."""
    from types import SimpleNamespace
    prior=old.g
    scope=SimpleNamespace(m=m,h=h,r=r,validate_scope=adapter.validate_scope,
        RECOVERY_SHA=recovery_sha,load=prior.load,O=prior.O)
    old.g=scope;old.m=m;old.h=h;old.r=r
    return scope


def exact_node(api,plan,expected):
    row=plan['projection']['expected_deployments']['node'];actual=api.get('Deployment',row['namespace'],row['name'])
    need(actual['metadata']['uid']==row['uid'] and actual['spec']==expected,'Exact Node UID and complete spec required')
    return actual


def pause_node(api,m,plan,directory):
    """replicas0 is prospective only; admission barrier also requires absence."""
    before=plan['request']['observations']['deployments']['node']
    current=exact_node(api,plan,before['spec']);spec=copy.deepcopy(before['spec']);spec['replicas']=0
    patch=m.r.replace_patch(current,'/spec',current['spec'],spec)
    m.write(directory/'node-pause.patch.json',patch)
    result=m.exact_patch(api,'Deployment',current['metadata']['namespace'],current['metadata']['name'],patch)
    need(result['metadata']['uid']==current['metadata']['uid'] and result['spec']==spec,'Unknown Node pause outcome')
    m.write(directory/'node-paused.json',result)
    return result


def absent_node(api,m,plan):
    expected=copy.deepcopy(plan['request']['observations']['deployments']['node']['spec']);expected['replicas']=0
    actual=exact_node(api,plan,expected)
    old=plan['request']['observations']['pods']['node'];meta=old['metadata']
    need(api.get('Pod',meta['namespace'],meta['name'],missing=True) is None,
         'Exact old Node Pod must actually be absent; replicas0/Ready-oldPod is insufficient')
    selector=','.join(k+'='+v for k,v in sorted(actual['spec']['selector']['matchLabels'].items()))
    pods=api.command(['get','pods','-n',meta['namespace'],'-l',selector,'-o','json'])['items']
    need(not pods,'No old/replacement/foreign matching Node process may remain')
    return actual


def readonly_probe(m,plan,reader_code):
    """Trusted readonly fd reader: only SYS_ADMIN, no token/device/host write."""
    old=plan['request']['observations']['deployments']['node'];pod=old['spec']['template']['spec']
    state=[v for v in pod['volumes'] if v['name']=='state'];need(len(state)==1 and set(state[0])=={'name','hostPath'},'Retained actual state host path required')
    state_path=state[0]['hostPath']['path'];need(state_path.startswith('/') and '..' not in state_path.split('/'),'Confined actual state path required')
    pool=plan['request']['qualification']['node_pool']
    name='cps-node-epoch-quiescence-'+m.r.canonical_sha256(plan).split(':')[1][:12]
    launcher="import io,json,sys,time;v="+repr({'pool':pool})+";sys.stdin=io.StringIO(json.dumps(v));exec(compile("+repr(reader_code)+",'sealed-readonly-native-inventory','exec'),{'__name__':'__main__'});sys.stdout.flush();time.sleep(60)"
    result={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':old['metadata']['namespace'],
        'labels':{'cps.compute/node-epoch-quiescence':m.r.canonical_sha256(plan).split(':')[1][:40]}},
        'spec':{'nodeName':pool['node'],'restartPolicy':'Never','automountServiceAccountToken':False,
            'hostPID':False,'hostIPC':False,'hostNetwork':False,'shareProcessNamespace':False,
            'enableServiceLinks':False,'schedulerName':'default-scheduler','dnsPolicy':'ClusterFirst',
            'terminationGracePeriodSeconds':5,
            'imagePullSecrets':copy.deepcopy(pod.get('imagePullSecrets',[])),
            'securityContext':{'runAsUser':0,'runAsGroup':0,'seccompProfile':{'type':'RuntimeDefault'}},
            'containers':[{'name':'reader','image':plan['projection']['process_declarations']['node']['image'],
                'command':['python3','-c',launcher],
                'securityContext':{'privileged':False,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL'],'add':['SYS_ADMIN']}},
                'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'100m','memory':'128Mi'}},
                'volumeMounts':[{'name':'gpu-proc','mountPath':'/host/proc/driver/nvidia/gpus','readOnly':True},
                    {'name':'boot-id','mountPath':'/host/proc/sys/kernel/random/boot_id','readOnly':True},
                    {'name':'authority','mountPath':'/run/cps-native-gpu/authority','readOnly':True}]}],
            'volumes':[{'name':'gpu-proc','hostPath':{'path':'/proc/driver/nvidia/gpus','type':'Directory'}},
                {'name':'boot-id','hostPath':{'path':'/proc/sys/kernel/random/boot_id','type':'File'}},
                {'name':'authority','hostPath':{'path':state_path.rstrip('/')+'/authority','type':'Directory'}}]}}
    return result


def probe_spec(actual,candidate):
    """Allow only enumerated API defaults, never admission-added authority."""
    actual=copy.deepcopy(actual)
    # Kubernetes serializes these false bools with omitempty. Absence is the
    # exact safe default; explicitly true remains denied by comparison.
    for k in ('hostPID','hostIPC','hostNetwork'):
        if k not in actual and candidate.get(k) is False:actual[k]=False
    def exact_requested(a,b):
        if isinstance(b,dict):return isinstance(a,dict) and all(k in a and exact_requested(a[k],v) for k,v in b.items())
        if isinstance(b,list):return isinstance(a,list) and len(a)==len(b) and all(exact_requested(x,y) for x,y in zip(a,b))
        return type(a) is type(b) and a==b
    need(exact_requested(actual,candidate),'Probe requested spec changed')
    defaults={'serviceAccountName':'default','serviceAccount':'default','priority':0,'preemptionPolicy':'PreemptLowerPriority'}
    need(set(actual)<=set(candidate)|set(defaults)|{'tolerations'},'Unexpected probe spec field')
    for k,v in defaults.items():
        if k in actual:need(actual[k]==v,'Unexpected probe API default')
    if 'tolerations' in actual:
        seen=set()
        for t in actual['tolerations']:
            need(set(t)=={'key','operator','effect','tolerationSeconds'} and t['key'] in
                 ('node.kubernetes.io/not-ready','node.kubernetes.io/unreachable') and t['key'] not in seen
                 and t['operator']=='Exists' and t['effect']=='NoExecute' and type(t['tolerationSeconds']) is int
                 and t['tolerationSeconds']==300,'Unexpected probe toleration')
            seen.add(t['key'])
    need(actual['securityContext']==candidate['securityContext'],'Unexpected Pod security context')
    need(actual['volumes']==candidate['volumes'],'Unexpected probe volume')
    for a,b in zip(actual['containers'],candidate['containers']):
        extra={'imagePullPolicy':'IfNotPresent','terminationMessagePath':'/dev/termination-log','terminationMessagePolicy':'File'}
        need(set(a)<=set(b)|set(extra),'Unexpected probe container field')
        for k,v in extra.items():
            if k in a:need(a[k]==v,'Unexpected probe container default')
        need(a['securityContext']==b['securityContext'] and a['resources']==b['resources']
             and a['volumeMounts']==b['volumeMounts'],'Unexpected container execution authority')


def inspect_probe(api,m,plan,created,candidate):
    meta=created['metadata'];pool=plan['request']['qualification']['node_pool']
    node=api.get('Node','',pool['node']);need(node['metadata']['uid']==pool['node_uid'],'Actual Node UID changed')
    actual=api.get('Pod',meta['namespace'],meta['name'])
    need(actual['metadata']['uid']==meta['uid'] and not actual['metadata'].get('deletionTimestamp')
         and actual['spec']['nodeName']==pool['node'],'Actual owned probe identity required')
    need(not actual['metadata'].get('ownerReferences'),'Probe must retain direct operator custody')
    probe_spec(actual['spec'],candidate['spec'])
    statuses=[x for x in actual.get('status',{}).get('containerStatuses',[]) if x['name']=='reader']
    need(len(statuses)==1 and statuses[0].get('imageID','').endswith(candidate['spec']['containers'][0]['image'].split('@')[1]),
         'Actual candidate probe image must be resolved exactly')
    native=probe_log(api,m,meta)
    need(isinstance(native,dict) and set(native)=={'inventory','epoch','records','previous'},'Closed actual native fd readback required')
    need(native['epoch']=={k:pool[k] for k in ('boot_id','driver_generation')}
         and native['inventory']['gpu_uuid']==pool['gpu_uuid'] and native['records']==native['previous']=={},'Actual protected epoch changed')
    entries=native['inventory']['entries'];need(isinstance(entries,list),'Actual bounded cap inventory required')
    need(sum(not x['offline'] for x in entries)==0 and sum(x['used'] for x in entries)==0,'Post-barrier actual native inventory must be zero')
    after=api.get('Pod',meta['namespace'],meta['name']);node_after=api.get('Node','',pool['node'])
    need(after['metadata']['uid']==meta['uid'] and after['spec']==actual['spec'] and node_after['metadata']['uid']==pool['node_uid'],
         'Probe/Node changed during observation')
    return native


def retain_probe_log(m,meta,stdout,stderr,returncode,terminal):
    """Full bounded raw bytes are private and persisted before any parse."""
    need(isinstance(meta['uid'],str) and meta['uid'] and '/' not in meta['uid'] and '..' not in meta['uid'],
         'Actual created UID required for owned log custody')
    PROBE_LOG_ROOT.mkdir(mode=0o700,exist_ok=True)
    s=PROBE_LOG_ROOT.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o700,'Private operator log directory required')
    path=PROBE_LOG_ROOT/(meta['uid']+'-'+uuid.uuid4().hex[:8]);path.mkdir(mode=0o700)
    need(len(stdout)<=1048576 and len(stderr)<=1048576,'Bounded full probe logs required')
    m.write(path/'stdout.private',stdout,raw=True);m.write(path/'stderr.private',stderr,raw=True)
    m.write(path/'receipt.json',{'pod':{k:meta[k] for k in ('namespace','name','uid')},'returncode':returncode,
        'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
        'terminal':terminal,'captured_at':datetime.now(timezone.utc).isoformat()})
    return path


def probe_log(api,m,meta):
    result=subprocess.run(api.prefix+['logs','-n',meta['namespace'],meta['name'],'-c','reader','--limit-bytes=1048576'],
        capture_output=True,timeout=25,check=False)
    actual=api.get('Pod',meta['namespace'],meta['name'])
    need(actual['metadata']['uid']==meta['uid'],'Actual probe UID must remain exact while retaining logs')
    states=[s for s in actual.get('status',{}).get('containerStatuses',[]) if s.get('name')=='reader']
    terminal=states[0].get('state',{}).get('terminated') if len(states)==1 else None
    path=retain_probe_log(m,meta,result.stdout,result.stderr,result.returncode,terminal)
    if terminal is not None and terminal.get('exitCode')!=0:
        lines=(result.stdout+b'\n'+result.stderr).decode('utf-8','replace').splitlines()
        detail=next((s for s in reversed(lines) if s.strip()),'no terminal text')[-512:]
        raise ProbeTerminalError('Readonly native reader exited '+str(terminal.get('exitCode'))+': '+detail+'; full private logs '+str(path))
    need(result.returncode==0,'Probe log command failed; full private logs retained '+str(path))
    return m.r.parse(result.stdout)


def delete_probe(api,m,created):
    meta=created['metadata'];current=api.get('Pod',meta['namespace'],meta['name'])
    need(current['metadata']['uid']==meta['uid'],'Exact created probe UID required; no name fallback')
    options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':meta['uid'],'resourceVersion':current['metadata']['resourceVersion']}}
    result=api.command(['delete','--raw','/api/v1/namespaces/'+meta['namespace']+'/pods/'+meta['name'],'-f','-'],options)
    return result


def source_capture(api,m,publication):
    """Identical authenticated capture transport, solely the Source endpoint.

    The pinned /epoch endpoint requires a live Node process and is deliberately
    unusable at the process-absence barrier. It supplies no substitute proof.
    """
    old=m.CAPTURE_CODE
    fetch="    epoch=fetch_packet(endpoint='epoch',url='https://'+host+':8001/epoch',**kwargs)\n"
    output="    print(json.dumps({'source':source,'epoch':{'driver_epoch':epoch,'captured_at':datetime.now(timezone.utc).isoformat()}}))"
    need(old.count(fetch)==old.count(output)==1,'Exact pinned capture code shape required')
    m.CAPTURE_CODE=old.replace(fetch,'').replace(output,"    print(json.dumps({'source':source}))")
    try:return getattr(m,'_node_original_capture',m.capture)(api,publication)
    finally:m.CAPTURE_CODE=old


def capture_scope(api,plan):
    """Only the known original or reviewed capture-seed Gateway full spec."""
    original=plan['request']['previous_publication'];forward=plan.get('inverse_authorization',{}).get('forward',plan)
    expected=original['expected_deployments']['gateway'];target=forward['projection']['expected_deployments']['gateway']
    actual=api.get('Deployment',expected['namespace'],expected['name'])
    need(actual['metadata']['uid']==expected['uid'] and actual['spec'] in (expected['spec'],target['spec']),
         'Exact known Gateway capture-seed full spec required')
    result=copy.deepcopy(original);result['expected_deployments']['gateway']['spec']=copy.deepcopy(actual['spec'])
    return result


def fresh_authority(api,m,h,plan,epoch_proof):
    """Fresh authenticated Source plus independent actual fd/NodeUID proof."""
    need(set(epoch_proof)=={'driver_epoch','captured_at'},'Closed independent actual epoch proof required')
    h.fresh(epoch_proof['captured_at'],datetime.now(timezone.utc))
    current=source_capture(api,m,capture_scope(api,plan));current['epoch']=copy.deepcopy(epoch_proof)
    prior=plan['request']['observations']
    need(current['source']['source_sha256']==prior['source']['source_sha256']
         and current['source']['trusted_revision']==plan['projection']['revision']
         and current['epoch']['driver_epoch']==prior['epoch']['driver_epoch'],
         'Fresh exact Source revision and physical epoch required before any change')
    obs=copy.deepcopy(prior);obs.update(current)
    h.context(plan['request'],obs,datetime.now(timezone.utc))
    return current


def resume_candidate(api,m,h,adapter,plan,directory,epoch_proof):
    """Only called after actual oldPod absence AND fresh post-barrier custody0."""
    adapter.validate_scope(plan);paused=absent_node(api,m,plan)
    controller=m.controller_current(api)
    need(h.identity(controller,'Deployment')==plan['lineage']['controller']
         and m.r.canonical_sha256(controller['spec'])==plan['lineage']['controller_spec_sha256']
         and not m.controller_pods(api,controller),'Exact paused zero-Pod delivery controller required')
    m.stopped_workspaces(api,plan['request']['previous_publication'])
    fresh_authority(api,m,h,plan,epoch_proof)
    candidate=plan['bootstrap_candidates']['node'];meta=candidate['metadata']
    need(api.get('ConfigMap',meta['namespace'],meta['name'],missing=True) is None,'New immutable node bootstrap name must be unused')
    created=api.create(candidate);h.same_cm(created,candidate,bound=False)
    m.write(directory/'created-hub-bootstrap-readbacks.json',{'node':created})
    retained=plan['capture_input_preimage'];sm=retained['metadata'];current=api.get('Secret',sm['namespace'],sm['name'])
    need(h.identity(current,'Secret')==h.identity(retained,'Secret') and current.get('immutable') is True
         and current['data']==retained['data'],'Exact retained immutable capture input required')
    candidate=plan['capture_input_candidate'];cm=candidate['metadata']
    need(api.get('Secret',cm['namespace'],cm['name'],missing=True) is None,'New immutable capture input name must be unused')
    created=api.command(['create','-n',cm['namespace'],'-f','-','-o','json'],candidate)
    need(created.get('immutable') is True and created.get('type')==candidate['type'] and created['data']==candidate['data']
         and all(created['metadata'][k]==cm[k] for k in ('namespace','name')) and created['metadata'].get('uid'),
         'Actual new capture input UID/full data required')
    m.write(directory/'created-capture-input.json',created)
    secret=plan['request']['gateway_runtime'];sm=secret['metadata']
    result=m.exact_patch(api,'Secret',sm['namespace'],sm['name'],plan['gateway_runtime_patch'])
    h.runtime_secret(result,plan['request'],plan['gateway_runtime_target']['data']);m.write(directory/'gateway-runtime-applied.json',result)
    gateway=plan['projection']['expected_deployments']['gateway']
    result=m.exact_patch(api,'Deployment',gateway['namespace'],gateway['name'],plan['deployment_patches']['gateway'])
    need(result['metadata']['uid']==gateway['uid'] and result['spec']==gateway['spec'],'Unknown Gateway capture-seed rollout outcome')
    m.write(directory/'gateway-deployment-applied.json',result)
    target=plan['projection']['expected_deployments']['node'];patch=m.r.replace_patch(paused,'/spec',paused['spec'],target['spec'])
    m.write(directory/'node-resume.patch.json',patch)
    result=m.exact_patch(api,'Deployment',target['namespace'],target['name'],patch)
    need(result['metadata']['uid']==target['uid'] and result['spec']==target['spec'],'Unknown Node resume outcome')
    m.write(directory/'node-deployment-applied.json',result)


def pause_restore_node(api,m,plan,directory):
    """Only exact paused-original or candidate specs are eligible for inverse."""
    original=plan['request']['observations']['deployments']['node'];target=plan['projection']['expected_deployments']['node']
    paused_original=copy.deepcopy(original['spec']);paused_original['replicas']=0
    paused_target=copy.deepcopy(target['spec']);paused_target['replicas']=0
    current=api.get('Deployment',target['namespace'],target['name'])
    need(current['metadata']['uid']==target['uid'] and current['spec'] in (paused_original,target['spec'],paused_target),
         'Inverse cannot adopt unknown Node spec or UID')
    paused=copy.deepcopy(current['spec']);paused['replicas']=0
    result=m.exact_patch(api,'Deployment',target['namespace'],target['name'],m.r.replace_patch(current,'/spec',current['spec'],paused))
    need(result['metadata']['uid']==target['uid'] and result['spec']==paused,'Unknown inverse Node pause outcome')
    m.write(directory/'inverse-node-paused.json',result);return result


def absent_restore_node(api,m,forward,paused):
    target=forward['projection']['expected_deployments']['node'];actual=exact_node(api,forward,paused['spec'])
    need(actual['spec']['replicas']==0,'Inverse Node must remain paused')
    selector=','.join(k+'='+v for k,v in sorted(actual['spec']['selector']['matchLabels'].items()))
    need(not api.command(['get','pods','-n',target['namespace'],'-l',selector,'-o','json'])['items'],
         'All actual matching Node processes must be absent before inverse')
    return actual


def apply_restore(api,m,h,inverse,forward,paused,directory,epoch_proof):
    """Restore known exact full Node/runtime preimages; no history deletion."""
    actual=absent_restore_node(api,m,forward,paused);fresh_authority(api,m,h,inverse,epoch_proof)
    retained=inverse['projection']['bootstrap_maps']['node'];meta=retained['metadata']
    bootstrap=api.get('ConfigMap',meta['namespace'],meta['name']);h.same_cm(bootstrap,retained)
    m.write(directory/'created-hub-bootstrap-readbacks.json',{'node':bootstrap})
    sm=inverse['request']['gateway_runtime']['metadata']
    runtime=m.exact_patch(api,'Secret',sm['namespace'],sm['name'],inverse['gateway_runtime_patch'])
    h.runtime_secret(runtime,inverse['request'],inverse['gateway_runtime_target']['data'])
    m.write(directory/'gateway-runtime-applied.json',runtime)
    gateway=inverse['projection']['expected_deployments']['gateway'];current=api.get('Deployment',gateway['namespace'],gateway['name'])
    original=forward['request']['previous_publication']['expected_deployments']['gateway']
    prospective=forward['projection']['expected_deployments']['gateway']
    need(current['metadata']['uid']==gateway['uid'] and current['spec'] in (original['spec'],prospective['spec']),
         'Only exact known Gateway seed-volume specs admitted for inverse')
    result=m.exact_patch(api,'Deployment',gateway['namespace'],gateway['name'],m.r.replace_patch(current,'/spec',current['spec'],gateway['spec']))
    m.write(directory/'gateway-deployment-applied.json',result)
    # A no-template-change inverse still needs a genuine replacement consuming
    # the restored runtime. When template changes, its old Pod is also deleted
    # with exact UID/RV; there is no same-name replacement fallback.
    gw=inverse['gateway_pod_restart_precondition'];pod=api.get('Pod',gw['namespace'],gw['name'],missing=True)
    if pod is not None:
        need(pod['metadata']['uid']==gw['uid'],'Exact observed pre-inverse Gateway UID required')
        delete_probe(api,m,pod)
    target=inverse['projection']['expected_deployments']['node']
    patch=m.r.replace_patch(actual,'/spec',actual['spec'],target['spec'])
    result=m.exact_patch(api,'Deployment',target['namespace'],target['name'],patch)
    need(result['metadata']['uid']==target['uid'] and result['spec']==target['spec'],'Unknown Node restore outcome')
    m.write(directory/'node-deployment-applied.json',result)


def capture_input_readback(api,m,h,plan,directory):
    """Actual immutable Secret UID/data and init-materialized config bytes."""
    if plan.get('kind')=='qualified-node-package-inverse':
        expected=plan['inverse_authorization']['forward']['capture_input_preimage']
    else:expected=m.read(directory/'created-capture-input.json')
    meta=expected['metadata'];actual=api.get('Secret',meta['namespace'],meta['name'])
    need(h.identity(actual,'Secret')==h.identity(expected,'Secret') and actual.get('immutable') is True
         and actual.get('type')==expected.get('type') and actual['data']==expected['data'],
         'Actual retained/new capture input UID and complete immutable data required')
    scope=copy.deepcopy(plan['projection']);scope['process_declarations']={'gateway':scope['process_declarations']['gateway']}
    rows=api.processes(scope);pod=rows['pods']['gateway'];pm=pod['metadata']
    value=m.exec_json(api,pm['namespace'],pm['name'],'approval-capture',
        "import hashlib,json;from pathlib import Path;print(json.dumps({'config_sha256':hashlib.sha256(Path('/capture-private/server/config.json').read_bytes()).hexdigest()}))")
    need(value=={'config_sha256':hashlib.sha256(base64.b64decode(expected['data']['config.json'],validate=True)).hexdigest()},
         'Actual Gateway init must materialize the exact approved capture configuration')
    after=api.get('Pod',pm['namespace'],pm['name'])
    need(after['metadata']['uid']==pm['uid'] and after['spec']==pod['spec'],'Actual capture Pod changed during mounted-config readback')
    return {'secret_uid':meta['uid'],'gateway_pod_uid':pm['uid'],**value}


def restoration_intents(api,m,plan):
    """Exact structural inverse only; no unknown result or live writer is ignored."""
    original=plan['request']['observations'];target=plan['projection']['expected_deployments']['node']
    current=api.get('Deployment',target['namespace'],target['name'])
    paused=copy.deepcopy(original['deployments']['node']['spec']);paused['replicas']=0
    need(current['metadata']['uid']==target['uid'] and current['spec'] in (paused,target['spec']),
         'Inverse requires one exact known paused/prospective Node spec')
    result={'node':m.r.replace_patch(current,'/spec',current['spec'],original['deployments']['node']['spec'])}
    secret=plan['request']['gateway_runtime'];sm=secret['metadata'];actual=api.get('Secret',sm['namespace'],sm['name'])
    need(actual['metadata']['uid']==sm['uid'] and actual['data'] in (secret['data'],plan['gateway_runtime_target']['data']),
         'Inverse cannot adopt unknown runtime data/custody')
    result['runtime']=m.r.replace_patch(actual,'/data',actual['data'],secret['data'])
    return result


def gateway_recovery_intents(api,m,h,plan):
    """Known Gateway-only inverse while actual Node absence remains held.

    This intentionally does not require the failed Gateway's HTTP interface.
    It cannot resume Node, release capacity, alter a Role or activate delivery.
    """
    original=plan['request']['previous_publication'];target=plan['projection']
    node=original['expected_deployments']['node'];actual=api.get('Deployment',node['namespace'],node['name'])
    known=[]
    for spec in (node['spec'],target['expected_deployments']['node']['spec']):
        paused=copy.deepcopy(spec);paused['replicas']=0;known.append(paused)
    need(actual['metadata']['uid']==node['uid'] and actual['spec'] in known,
         'Gateway recovery requires exact known paused Node spec/UID')
    selector=','.join(k+'='+v for k,v in sorted(actual['spec']['selector']['matchLabels'].items()))
    need(not api.command(['get','pods','-n',node['namespace'],'-l',selector,'-o','json'])['items'],
         'Gateway recovery cannot proceed while any matching Node Pod remains')
    oldpod=plan['request']['observations']['pods']['node']['metadata']
    need(api.get('Pod',oldpod['namespace'],oldpod['name'],missing=True) is None,'Exact original Node Pod must remain absent')
    controller=m.controller_current(api)
    need(h.identity(controller,'Deployment')==plan['lineage']['controller'] and
         controller['spec']==plan['request']['old_state']['controller']['spec'] and not m.controller_pods(api,controller),
         'Exact original paused zero-Pod delivery custody required')
    for key,kind in [('next_journal','PersistentVolumeClaim'),('next_input_secret','Secret')]:
        row=plan['lineage'][key]
        need(api.get(kind,row['namespace'],row['name'],missing=True) is None,
             'Gateway recovery cannot adopt completed/unknown delivery activation')
    retained=plan['capture_input_preimage'];cm=retained['metadata'];capture=api.get('Secret',cm['namespace'],cm['name'])
    need(h.identity(capture,'Secret')==h.identity(retained,'Secret') and capture.get('immutable') is True
         and capture['data']==retained['data'],'Original immutable capture input custody must remain exact')
    gateway=original['expected_deployments']['gateway'];g=api.get('Deployment',gateway['namespace'],gateway['name'])
    need(g['metadata']['uid']==gateway['uid'] and g['spec'] in (gateway['spec'],target['expected_deployments']['gateway']['spec']),
         'Only exact original/prospective Gateway full specs admitted')
    secret=plan['request']['gateway_runtime'];sm=secret['metadata'];s=api.get('Secret',sm['namespace'],sm['name'])
    need(h.identity(s,'Secret')==h.identity(secret,'Secret') and s['data'] in
         (secret['data'],plan['gateway_runtime_target']['data']),'Only exact known runtime UID/full data admitted')
    return {'runtime':m.r.replace_patch(s,'/data',s['data'],secret['data']),
            'gateway':m.r.replace_patch(g,'/spec',g['spec'],gateway['spec'])}


def recover_gateway(api,m,h,plan,directory):
    """No retry of writes; repeat all absence/custody reads between CAS steps."""
    intent=gateway_recovery_intents(api,m,h,plan);m.write(directory/'gateway-only-recovery-intents.json',intent)
    secret=plan['request']['gateway_runtime']['metadata']
    runtime=m.exact_patch(api,'Secret',secret['namespace'],secret['name'],intent['runtime'])
    need(runtime['data']==plan['request']['gateway_runtime']['data'],'Unknown runtime recovery outcome')
    m.write(directory/'gateway-runtime-restored.json',runtime)
    current=gateway_recovery_intents(api,m,h,plan)
    gateway=plan['request']['previous_publication']['expected_deployments']['gateway']
    result=m.exact_patch(api,'Deployment',gateway['namespace'],gateway['name'],current['gateway'])
    need(result['metadata']['uid']==gateway['uid'] and result['spec']==gateway['spec'],'Unknown Gateway recovery outcome')
    m.write(directory/'gateway-spec-restored.json',result)
