#!/usr/bin/env python3
"""Bounded stock-KAI15-fixture witness. Default render only; explicit root release required."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time
from urllib.parse import quote, urlencode

import kai_placement_render as renderer


def require_uid(resource, uid):
    if resource['metadata']['uid'] != uid:
        raise RuntimeError('Refuse same-name replacement: ' + resource['metadata']['name'])


def validate_qualified_nodes(nodes, selected, selected_uid, accepted_peers):
    expected = {selected: selected_uid, **accepted_peers}
    names = [node['metadata']['name'] for node in nodes]
    if selected in accepted_peers or len(names) != len(set(names)) or set(names) != set(expected):
        raise RuntimeError('Qualified workers must be exactly selected worker plus accepted peers')
    observed = []
    for node in nodes:
        meta = node['metadata']
        if (meta['uid'] != expected[meta['name']] or meta.get('deletionTimestamp')
                or meta.get('labels', {}).get('cps.unileoben.ac.at/upstream-gpu-sharing') != 'qualified'
                or not any(c['type'] == 'Ready' and c['status'] == 'True'
                           for c in node.get('status', {}).get('conditions', []))):
            raise RuntimeError('Qualified worker identity/readiness mismatch: ' + meta['name'])
        observed.append({'name': meta['name'], 'uid': meta['uid'], 'ready': True})
    return sorted(observed, key=lambda node: node['name'])


def validate_assignment(pod, br, node, allowed, expected):
    meta, spec = pod['metadata'], br['spec']
    owners = [x['uid'] for x in br['metadata'].get('ownerReferences', []) if x.get('kind') == 'Pod']
    if (pod['spec'].get('nodeName') != node or spec.get('selectedNode') != node
            or spec.get('podName') != meta['name'] or (owners and owners != [meta['uid']])
            or spec.get('receivedResourceType') != 'Fraction'
            or spec.get('receivedGPU', {}).get('count') != 1):
        raise RuntimeError('Actual scheduler BindRequest/Pod custody mismatch')
    value = meta.get('annotations', {}).get('nvidia.com/container.main.gpus.devices', '')
    prefix = 'k8s.device-plugin.nvidia.com/gpu='
    gpu = value[len(prefix):] if value.startswith(prefix) else None
    if gpu not in allowed or gpu != expected:
        raise RuntimeError('Unexpected CDI GPU/slot or multiple devices: ' + value)
    return gpu


def watch_command(namespace, resource_version):
    url = '/apis/scheduling.run.ai/v1alpha2/namespaces/' + quote(namespace, safe='') + '/bindrequests?'
    url += urlencode({'watch': 'true', 'resourceVersion': resource_version,
                      'allowWatchBookmarks': 'true', 'timeoutSeconds': '640'})
    # The raw watch is long lived; the ordinary 15s request timeout would cut it off.
    return ['kubectl', '--request-timeout=650s', 'get', '--raw', url]


def main():
    a = renderer.arguments(execution=True)
    if a.execute and (not a.parent_idle_release or not a.ssh_target or not a.ssh_key):
        raise SystemExit('Execution requires explicit --parent-idle-release, --ssh-target and --ssh-key')
    if a.ssh_target and not re.fullmatch(r'(?:[\w.-]+@)?[\w.-]+', a.ssh_target):
        raise SystemExit('Invalid SSH target')
    cm, manifests, summary = renderer.render(a)
    a.output.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (a.output / name).write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + '\n')

    save('configmap.json', cm)
    for role, pod in manifests.items(): save(role + '.input.json', pod)
    summary.update(parent_idle_release=getattr(a, 'parent_idle_release', None), observations={})
    save('summary.json', summary)
    if not a.execute:
        print('Prepared15 fixtures/sequence; no cluster or SSH calls: ' + str(a.output))
        return
    started = time.monotonic()
    deadline = started + 600
    kube = ['kubectl', '--request-timeout=15s']
    cleanup_mode = False

    def command(argv, data=None, timeout=25):
        if not cleanup_mode:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Overall600s run bound reached')
            timeout = min(timeout, remaining)
        return subprocess.check_output(argv, input=data, text=True, timeout=timeout, stderr=subprocess.STDOUT)

    def get(*args): return json.loads(command(kube + ['get', *args, '-o', 'json']))

    def bound():
        if time.monotonic() > deadline: raise TimeoutError('Overall600s run bound reached')
        if watcher.poll() is not None: raise RuntimeError('BindRequest watch terminated unexpectedly')

    observer = (Path(__file__).with_name('extended_host_observer.py')).read_text()
    anchor = '    print(json.dumps(result))'
    assert observer.count(anchor) == 1
    observer = observer.replace("    a = p.parse_args()", "    p.add_argument('--skip-limits', action='store_true')\n    a = p.parse_args()")
    observer = observer.replace(anchor, '''    outer = Path('/usr/local/bin/k3s')
    pids = [p for p in Path('/proc').iterdir() if p.name.isdigit() and (p/'comm').exists() and (p/'comm').read_text().strip() == 'containerd']
    if len(pids) != 1: raise RuntimeError('Exactly one running containerd required')
    exe = pids[0]/'exe'
    result['runtime'] = {'outer_sha256': hashlib.sha256(outer.read_bytes()).hexdigest(),
        'containerd_pid': int(pids[0].name), 'containerd_exe': str(exe.resolve()),
        'inner_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
        'kernel': os.uname().release, 'k3s_version': command(['k3s','--version']),
        'mem_available_bytes': int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024}
    if a.container_id:
        if not a.skip_limits:
            result['memory_limits'] = command([smi,'memory-limits','--get','-n','/sys/fs/cgroup'+rows[0],'-i',a.gpu_uuid])
        spec = body['info'].get('runtimeSpec', {})
        result['oci_devices'] = spec.get('linux', {}).get('devices', [])
        result['oci_gpu_annotations'] = {k:v for k,v in spec.get('annotations',{}).items() if k.startswith(('cdi.','nvidia.','required-plugins.'))}
    print(json.dumps(result))''')
    save('host-observer.py', observer)
    compile(observer, 'observer', 'exec')

    def observe(gpu, cid=None, limits=True):
        args = ['sudo', '-n', 'python3', '-', '--node', a.node, '--gpu-uuid', gpu]
        if cid: args += ['--container-id', cid]
        if not limits: args += ['--skip-limits']
        state = json.loads(command(['ssh', '-i', str(a.ssh_key), '-o', 'IdentitiesOnly=yes', '-o',
            'BatchMode=yes', '-o', 'ConnectTimeout=8', a.ssh_target, shlex.join(args)], observer, 35))
        uvm, runtime = state['uvm'], state['runtime']
        if (state['boot_id'] != a.expected_boot_id or uvm.get('srcversion') != a.expected_module_srcversion
                or state.get('uvm_source_sha256') != summary['uvm_source_sha256']
                or any(uvm.get('parameters/'+x) != 'Y' for x in ('uvm_reject_managed_memory','uvm_disable_hmm'))
                or runtime['outer_sha256'] != renderer.OUTER or runtime['inner_sha256'] != renderer.INNER
                or runtime['kernel'] != '7.0.0-43-generic'
                or 'v1.34.9+k3s1' not in runtime['k3s_version']):
            raise RuntimeError('Actual driver/module/source/kernel/running runtime identity mismatch')
        fields = [x.strip() for x in state['gpu'].split(',')]
        if fields[1] != '620.70.06' or int(fields[3]) != 40960:
            raise RuntimeError('Physical driver/card size changed')
        return state

    node = get('node', a.node)
    node_uid = node['metadata']['uid']
    if (node['spec'].get('unschedulable') or node['metadata']['labels'].get('cps.unileoben.ac.at/upstream-gpu-sharing') != 'qualified'
            or any(x['effect'] in ('NoSchedule','NoExecute') and x['key'] != 'nvidia.com/gpu' for x in node['spec'].get('taints',[]))
            or not any(x['type']=='Ready' and x['status']=='True' for x in node['status']['conditions'])
            or not any(x['type']=='InternalIP' and x['address']==a.node_ip for x in node['status']['addresses'])
            or node['metadata']['labels'].get('nvidia.com/gpu.memory') != '40960'):
        raise RuntimeError('Root must open only selected Ready matching worker for scheduling')
    qualified = get('nodes','-l','cps.unileoben.ac.at/upstream-gpu-sharing=qualified')['items']
    summary['qualified_workers_before'] = validate_qualified_nodes(
        qualified, a.node, node_uid, a.accepted_qualified_peers)
    save('summary.json', summary)
    drivers = [p for p in get('pods','-n','gpu-operator')['items'] if p['spec'].get('nodeName')==a.node
               and p['status'].get('phase')=='Running' and any(c['name']=='nvidia-driver-ctr' for c in p['spec']['containers'])]
    if (len(drivers)!=1 or drivers[0]['metadata'].get('deletionTimestamp')
            or not any(c['image']==renderer.DRIVER for c in drivers[0]['spec']['containers'])
            or not any(renderer.DRIVER.split('@')[1] in c.get('imageID','') for c in drivers[0]['status'].get('containerStatuses',[]))):
        raise RuntimeError('Exactly one actual candidatec3b driver required')
    config=get('configs.kai.scheduler','kai-config')
    if config['spec'].get('global',{}).get('gpuSharingMode')!='NvFractions':raise RuntimeError('Stock NvFractions mode required')
    kai=get('pods','-n','kai-scheduler')['items']
    for component in ('admission','binder','scheduler'):
        matching=[p for p in kai if any(c['image']=='ghcr.io/kai-scheduler/kai-scheduler/'+component+':v0.18.1' for c in p['spec']['containers'])]
        if len(matching)!=1 or matching[0]['metadata'].get('deletionTimestamp') or not all(c.get('ready') for c in matching[0]['status'].get('containerStatuses',[])):
            raise RuntimeError('Exactly one Ready stock KAI0.18.1 '+component+' required')
    fraction=get('gpufractioningconfig','default')
    if not any(x['type']=='Ready' and x['status']=='True' for x in fraction.get('status',{}).get('conditions',[])):raise RuntimeError('Fractioning config not Ready')
    fp=[p for p in get('pods','-n','gpu-fractioning')['items'] if p['spec'].get('nodeName')==a.node]
    for component in ('fractiond','mpsd'):
        matching=[p for p in fp if any(c['image'].endswith('/'+component+':v0.1.9') for c in p['spec']['containers'])]
        if len(matching)!=1 or matching[0]['metadata'].get('deletionTimestamp') or not all(c.get('ready') for c in matching[0]['status'].get('containerStatuses',[])):
            raise RuntimeError('Selected fractioning0.1.9 '+component+' not stably Ready')
    save('fractioning-before.json', {'config_conditions':fraction.get('status',{}).get('conditions',[]),
        'pods':[{'name':p['metadata']['name'],'uid':p['metadata']['uid']} for p in fp]})
    save('kai-before.json', {'config_uid':config['metadata']['uid'],'mode':'NvFractions',
        'pods':[{'name':p['metadata']['name'],'uid':p['metadata']['uid'],'images':[c['image']for c in p['spec']['containers']]}for p in kai]})
    save('node-before.json', node)
    save('driver-before.json', drivers[0])
    summary.update(node_uid=node_uid, driver_pod_uid=drivers[0]['metadata']['uid'])
    for p in get('pods','-A','--field-selector','spec.nodeName='+a.node)['items']:
        if p['status'].get('phase') in ('Succeeded','Failed'): continue
        anns=p['metadata'].get('annotations',{})
        if any(k.startswith(('nvidia.com/container.','gpu-memory','gpu-fraction','required-plugins.')) for k in anns) or any(
                k.startswith('nvidia.com/') for c in p['spec'].get('containers',[]) for tier in ('requests','limits') for k in c.get('resources',{}).get(tier,{})):
            raise RuntimeError('Concurrent GPU consumer: '+p['metadata']['name'])

    def idle():
        states=[observe(g) for g in (a.gpu_a,a.gpu_b)]
        if any(s['compute_processes'].strip() or int(s['gpu'].split(',')[2])>1 for s in states):
            raise RuntimeError('GPUs did not return to no clients/<=1MiB')
        return states

    baseline=idle()
    if min(s['runtime']['mem_available_bytes'] for s in baseline)<128*1024**3:
        raise RuntimeError('Less than128GiB currently available host memory for peak fixture guarantees')
    def reservations():
        return [p for p in get('pods','-n','kai-resource-reservation')['items'] if p['spec'].get('nodeName')==a.node]
    baseline_reservations=reservations()
    if baseline_reservations:raise RuntimeError('Selected worker has pre-existing KAI resource reservation Pods')
    save('baseline.json', baseline)
    # Snapshot RV then watch from it BEFORE first create. Only matching fixture
    # events are retained, including fast-deleted BindRequests.
    rv=get('bindrequests','-n',a.namespace)['metadata']['resourceVersion']
    watcher=subprocess.Popen(watch_command(a.namespace, rv), stdout=subprocess.PIPE,
        stderr=(a.output/'bindrequest-watch.stderr').open('w'), text=True)
    bindings=[]
    def watch():
        buf=''; decoder=json.JSONDecoder()
        with (a.output/'bindrequest-watch.jsonl').open('w') as out:
            for line in watcher.stdout:
                buf+=line
                while buf.strip():
                    try: event,end=decoder.raw_decode(buf.lstrip())
                    except json.JSONDecodeError: break
                    buf=buf.lstrip()[end:]
                    obj=event.get('object',event)
                    if obj.get('spec',{}).get('podName','').startswith(a.run_id+'-'):
                        bindings.append(event);out.write(json.dumps(event)+'\n');out.flush()
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    created={};cm_uid=None;identities={};mapping={}

    def owned(role):
        p=get('pod',manifests[role]['metadata']['name'],'-n',a.namespace)
        require_uid(p,created[role]);return p

    def execute(role,*argv):
        owned(role)
        return command(kube+['exec','-n',a.namespace,manifests[role]['metadata']['name'],'-c','main','--',*argv])

    def logs(role):
        owned(role)
        value=command(kube+['logs','-n',a.namespace,manifests[role]['metadata']['name'],'-c','main'])
        save(role+'.log',value)
        return [json.loads(x) for x in value.splitlines() if x.startswith('{')]

    def wait_step(role,step,seconds=45,cleanup=False):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            if not cleanup:bound()
            p=owned(role);rows=logs(role)
            if any(x.get('step')==step for x in rows): return rows
            if p['status'].get('phase') in ('Failed','Succeeded'):raise RuntimeError(role+' terminated before '+step)
            time.sleep(.4)
        raise TimeoutError(role+':'+step)

    def delete(kind,name,uid):
        obj=get(kind,name,'-n',a.namespace);require_uid(obj,uid)
        options={'apiVersion':'v1','kind':'DeleteOptions','gracePeriodSeconds':15,
                 'preconditions':{'uid':uid,'resourceVersion':obj['metadata']['resourceVersion']}}
        plural='pods' if kind=='pod' else 'configmaps'
        command(kube+['delete','--raw',f'/api/v1/namespaces/{a.namespace}/{plural}/{name}','-f','-'],json.dumps(options))
        command(kube+['wait','--for=delete',kind+'/'+name,'-n',a.namespace,'--timeout=45s'],timeout=50)

    def release(roles,cleanup=False):
        errors=[]
        # Signal all live holds first; never start an unstarted CUDA probe for cleanup.
        for role in roles:
            try:
                if owned(role)['status'].get('phase')=='Running' and any(x.get('step')=='holding-filled-vram' for x in logs(role)):
                    execute(role,'touch','/tmp/release')
            except Exception as e:errors.append(role+':release '+str(e))
        for role in roles:
            try:
                p=owned(role)
                if any(x.get('step')=='holding-filled-vram' for x in logs(role)):
                    rows=wait_step(role,'process-finished',30,cleanup)
                    if any(x.get('result',0)!=0 for x in rows if x.get('step') in ('free','destroy')):raise RuntimeError('CUDA cleanup failed')
                    command(kube+['wait','--for=jsonpath={.status.phase}=Succeeded','pod/'+p['metadata']['name'],'-n',a.namespace,'--timeout=20s'],timeout=25)
                save(role+'.final.json',owned(role));logs(role)
                delete('pod',p['metadata']['name'],created[role]);del created[role]
            except Exception as e:errors.append(role+':delete '+str(e))
        if errors:raise RuntimeError('; '.join(errors))

    def binding(role):
        name=manifests[role]['metadata']['name'];until=time.monotonic()+10
        while time.monotonic()<until:
            bound()
            rows=[e.get('object',e) for e in bindings if e.get('object',e).get('spec',{}).get('podName')==name]
            if rows:return rows[-1]
            time.sleep(.2)
        raise RuntimeError('No pre-create-watch BindRequest captured: '+name)

    def start(role):
        bound()
        p=json.loads(command(kube+['create','-f','-','-o','json'],json.dumps(manifests[role])))
        created[role]=p['metadata']['uid']
        command(kube+['wait','--for=condition=Ready','pod/'+p['metadata']['name'],'-n',a.namespace,'--timeout=60s'],timeout=65)
        p=owned(role);save(role+'.admitted.json',p)
        if p['spec'].get('nodeName')!=a.node or get('node',a.node)['metadata']['uid']!=node_uid:raise RuntimeError('Node placement/identity changed')
        statuses=p['status']['containerStatuses']
        if any(x.get('restartCount',0) for x in statuses):raise RuntimeError('Fixture restarted')
        cid=next(x['containerID'].split('://',1)[1] for x in statuses if x['name']=='main')
        br=binding(role);save(role+'.bindrequest.json',br)
        if role!='seed-exclusive':
            card=role.split('-')[1] if role.startswith('r') else role[-1]
            gpu=validate_assignment(p,br,a.node,[a.gpu_a,a.gpu_b],mapping[card])
            state=observe(gpu,cid);limit=int(manifests[role]['metadata']['annotations']['nvidia.com/container.main.gpu-memory.limit'][:-2])
            for tier in ('soft','hard'):
                if not re.search(rf'{tier} limit:\s*{limit}\s*MiB',state['memory_limits'],re.I):raise RuntimeError('Actual leaf budget mismatch')
            if state['accounting'].get('memory.max','').strip()!=str(16*1024**3):raise RuntimeError('Actual16GiB hostbudget mismatch')
        execute(role,'touch','/tmp/start');rows=wait_step(role,'holding-filled-vram')
        identity=next(x for x in rows if x.get('step')=='cuda-identity');gpu=identity['gpu_uuid']
        if identity['device_count']!=1 or gpu not in (a.gpu_a,a.gpu_b):raise RuntimeError('Unexpected physical CUDA identity')
        if role=='seed-exclusive':
            if br['spec'].get('podName')!=p['metadata']['name'] or br['spec'].get('selectedNode')!=a.node:raise RuntimeError('Seed binding mismatch')
            mapping.update(b=gpu,a=next(x for x in (a.gpu_a,a.gpu_b) if x!=gpu));summary['physical_order_mapping']=mapping.copy()
        elif gpu!=mapping[card]:raise RuntimeError('CUDA identity differs from scheduler slot')
        if role!='seed-exclusive':
            oom=[x for x in rows if x.get('step')=='above-hard-limit-allocation']
            if len(oom)!=1 or oom[0]['result']!=2 or oom[0]['mib']!=limit+1024:raise RuntimeError('TypedOOM witness missing')
        state=observe(gpu,cid,limits=role!='seed-exclusive')
        pids={int(x['pid']) for x in state['processes']}
        if not any(int(x.split(',')[1]) in pids for x in state['compute_processes'].splitlines() if x.strip()):raise RuntimeError('No matching physical CUDA PID')
        identities[role]={'uid':created[role],'container_id':cid,'gpu':gpu,'observation':state}
        summary['observations'][role]=identities[role];save('summary.json',summary)

    try:
        cm_uid=json.loads(command(kube+['create','-f','-','-o','json'],json.dumps(cm)))['metadata']['uid']
        for index,action in enumerate(summary['sequence']):
            bound()
            if 'create' in action:
                for role in action['create']:start(role)
            elif 'release_delete' in action:
                release(action['release_delete'])
            else:
                roles=[r for r in created if r.startswith('r')]
                if len(roles)!=6:raise RuntimeError('Expected six coexistent payloads')
                before={r:sum(x.get('step')=='progress' and x.get('result')==0 for x in logs(r)) for r in roles}
                time.sleep(6);snapshot={}
                for r in roles:
                    rows=logs(r)
                    if any(x.get('step')=='progress-error' for x in rows) or sum(x.get('step')=='progress' and x.get('result')==0 for x in rows)<=before[r]:raise RuntimeError('Independent progress stalled: '+r)
                    snapshot[r]=observe(identities[r]['gpu'],identities[r]['container_id'])
                save(f'checkpoint-{index}.json',snapshot)
        summary['status']='PASS'
    except BaseException as error:
        summary.update(status='FAIL',error=str(error));raise
    finally:
        cleanup_mode = True
        try:
            if created:release(list(created),cleanup=True)
            if cm_uid:delete('configmap',a.run_id,cm_uid)
            # Original fixture-owned BindRequests must disappear; binder-owned
            # reservation cleanup is observed, never edited/deleted by this test.
            until=time.monotonic()+30
            while True:
                remaining=[b for b in get('bindrequests','-n',a.namespace)['items'] if b.get('spec',{}).get('podName','').startswith(a.run_id+'-')]
                if not remaining:break
                if time.monotonic()>until:raise RuntimeError('Owned BindRequest cleanup incomplete')
                time.sleep(.5)
            until=time.monotonic()+45
            while True:
                leftover=reservations()
                if not leftover:break
                if time.monotonic()>until:
                    save('remaining-reservations.json',[{'name':p['metadata']['name'],'uid':p['metadata']['uid'],
                        'labels':p['metadata'].get('labels',{})}for p in leftover])
                    raise RuntimeError('Selected-worker stock KAI reservations did not return to empty baseline')
                time.sleep(.5)
            leftovers=get('pods','-n',a.namespace,'-l','cps.unileoben.ac.at/kai-placement-run='+a.run_id)['items']
            if leftovers:raise RuntimeError('Owned-prefix Pods remain, including possible uncertain CREATE response; no adoption/force deletion')
            save('final-idle.json',idle())
            summary['cleanup']='PASS'
        except BaseException as error:
            summary.update(status='FAIL',cleanup='FAIL',cleanup_error=str(error));raise
        finally:
            watcher.terminate()
            try:watcher.wait(timeout=5)
            except subprocess.TimeoutExpired:watcher.kill();watcher.wait(timeout=5)
            thread.join(timeout=5)
            summary['elapsed_seconds']=time.monotonic()-started;save('summary.json',summary)
    print('Stock KAI two-order placement PASS; window returned: '+str(a.output))


if __name__=='__main__':main()
