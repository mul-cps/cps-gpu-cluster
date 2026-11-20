"""Offline contract/regression tests. All runtime evidence here is synthetic."""
import ast
import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import mixed_contract as contract
import mixed_evaluate as evaluator
import mixed_render as renderer
import test_dynamic_cache as baseline

WHEEL = Path(os.environ.get('CPS_MIXED_COMPILER_WHEEL',
    '/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-runtime-packaging/40b9525/dist/cps_compute-0.1.0-py3-none-any.whl'))
NOW = baseline.NOW
NS = int(NOW.timestamp()*1e9)
PODS = [f'12345678-1234-1234-1234-123456789ab{v}' for v in ('1','2','3')]


def preflight():
    value = baseline.preflight();value['image'] = contract.IMAGE;value['node']['ready'] = True
    server = {'pid':300,'startTimeTicks':400,'uid':1000,'status':'ACTIVE','clients':[],
        'deviceMemoryLimitsMiB':{g['uuid']:5120 for g in value['gpus']},'activeThreadPercentage':12}
    reference = {'schemaVersion':1,'observedAt':NOW.isoformat(),'nodeUid':value['node']['uid'],
        'daemon':{'namespace':'gpu-operator','name':'mps-control-daemon-standalone-m2587',
                  'uid':contract.DAEMON_UID,'resourceVersion':'100','image':contract.DAEMON_IMAGE},
        'controller':{'pid':200,'uid':0,'command':['nvidia-cuda-mps-control','-d']},'server':server,
        'defaults':{'deviceMemoryLimitsMiB':{'0':5120,'1':5120},'activeThreadPercentage':12},
        'uidCompatibilityEvidenceSha256':'b'*64}
    value['mpsReference'] = reference
    value['mpsServers'] = [{'gpuUuid':g['uuid'],'pid':server['pid'],'ready':True} for g in value['gpus']]
    value['mpsMaintenanceReview'] = {'status':'reviewed-offline-candidate','candidateSha256':'c'*64,'reviewSha256':'d'*64,
        'server':{k:server[k] for k in ('pid','startTimeTicks','uid')},'daemonUid':contract.DAEMON_UID,
        'daemonResourceVersion':'100','activeDeviceMemoryLimitsMiB':{g['uuid']:40960 for g in value['gpus']},
        'activeThreadPercentage':100,'defaults':copy.deepcopy(reference['defaults']),'maxWindowSeconds':180,
        'uidCompatibilityEvidenceSha256':'b'*64}
    return value


def approval(proof,role,uid):
    reference = proof['mpsReference'];review = proof['mpsMaintenanceReview']
    mps = {k:copy.deepcopy(review[k]) for k in ('candidateSha256','reviewSha256','server','daemonUid',
        'daemonResourceVersion','activeDeviceMemoryLimitsMiB','activeThreadPercentage','defaults','uidCompatibilityEvidenceSha256')}
    mps.update(observedAt=NOW.isoformat(),windowEndsAtNs=NS+180*10**9)
    return {'runtimeReviewed':True,'allGatesReviewed':True,'role':role,'podUid':uid,'podUids':list(PODS),
        'runId':proof['runId'],'nodeUid':proof['nodeUid'],'uid':1000,'gid':100,'gpuUuid':baseline.GPU,
        'probeSha256':proof['probeSha256'],'compilerWheelSha256':contract.WHEEL_SHA,
        'hamiSha256':proof['hami']['sha256'],'mps':mps}


def injected_pod(job,uid,gib):
    template = job['spec']['template']
    pod = {'metadata':{**copy.deepcopy(template['metadata']),'uid':uid,'name':job['metadata']['name']+'-abcde',
        'namespace':'cps-gpu-qualification'},'spec':copy.deepcopy(template['spec']),'status':{'phase':'Succeeded'}}
    pod['metadata']['annotations'][baseline.render.REVIEWED_GPU_ANNOTATION] = baseline.GPU
    pod['spec']['nodeName'] = baseline.render.NODE
    cm_name = pod['metadata']['name']+'-shared-gpu-0';quota = contract.QUOTAS[gib]
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':cm_name,'namespace':pod['metadata']['namespace'],
        'uid':cm_name+'-uid','resourceVersion':'100','ownerReferences':[{'kind':'Pod','apiVersion':'v1',
            'name':pod['metadata']['name'],'uid':uid}]},'data':{'CUDA_DEVICE_MEMORY_LIMIT':str(quota['globalMiB'])+'m',
            'GPU_PORTION':quota['portion'],'RUNAI_NUM_OF_GPUS':quota['portion'],
            'NVIDIA_VISIBLE_DEVICES':'k8s.device-plugin.nvidia.com/gpu='+baseline.GPU}}
    empty = {'apiVersion':'v1','kind':'ConfigMap','metadata':{**copy.deepcopy(cm['metadata']),
        'name':cm_name+'-evar','uid':cm_name+'-empty-uid'},'data':None}
    main = pod['spec']['containers'][0]
    main['env'].extend([
        {'name':'POD_UID','valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.uid'}}},
        {'name':'CONTAINER_NAME','value':'main'},{'name':'CONTAINER_VGPU_MOUNT','value':'/usr/local/vgpu'},
        *[{'name':key,'valueFrom':{'configMapKeyRef':{'name':cm_name,'key':key,
           **({'optional':True} if key == 'CUDA_DEVICE_MEMORY_LIMIT' else {})}}}
          for key in ('NVIDIA_VISIBLE_DEVICES','RUNAI_NUM_OF_GPUS','GPU_PORTION','CUDA_DEVICE_MEMORY_LIMIT')]])
    main['envFrom'] = [{'configMapRef':{'name':cm_name+'-evar','optional':False}}]
    main['volumeMounts'].extend([
        {'name':'kai-resource-isolator-vgpu','mountPath':'/usr/local/vgpu'},
        {'name':'kai-resource-isolator-vgpu','mountPath':'/etc/ld.so.preload','readOnly':True,'subPath':'ld.so.preload'},
        {'name':'kai-resource-isolator-containers','mountPath':'/usr/local/vgpu/containers'},
        {'name':'kai-resource-isolator-vgpulock','mountPath':'/tmp/vgpulock'}])
    pod['spec']['volumes'].extend([
        {'name':'kai-resource-isolator-vgpu','hostPath':{'path':'/usr/local/vgpu','type':'DirectoryOrCreate'}},
        {'name':'kai-resource-isolator-containers','hostPath':{'path':'/usr/local/vgpu/containers','type':'DirectoryOrCreate'}},
        {'name':'kai-resource-isolator-vgpulock','hostPath':{'path':'/tmp/vgpulock','type':'DirectoryOrCreate'}},
        {'name':cm_name+'-vol','configMap':{'name':cm_name,'defaultMode':420}}])
    for status_field,spec_field in (('containerStatuses','containers'),('initContainerStatuses','initContainers')):
        pod['status'][status_field] = [{'name':v['name'],'imageID':contract.IMAGE.split(':qualification-')[0]+'@'+contract.IMAGE.split('@')[1],
            'restartCount':0,'state':{'terminated':{'exitCode':0}}} for v in pod['spec'][spec_field]]
    return pod,[cm,empty]


def evidence():
    inventory = preflight();fixture = renderer.render(inventory,'mix01234',WHEEL,now=NOW)
    proof = json.loads(fixture['items'][0]['data']['preflight.json']);events,pods,cms = {},{},[]
    for index,(role,gib) in enumerate(contract.ROLES.items()):
        uid = PODS[index];pod,owned = injected_pod(fixture['items'][index+1],uid,gib);pods[role] = pod;cms.extend(owned)
        review = approval(proof,role,uid);stream = []
        identity = {'podUid':uid,'runId':proof['runId'],'role':role,'profileGiB':gib}
        hami = {'referenceSourceRevision':baseline.render.HAMI_REVISION,'sourceRevisionVerified':False,
            'libraryPath':baseline.render.HAMI_PATH,'sha256':inventory['hami']['sha256'],'loaded':True,'preloadVerified':True,
            'perDeviceLimitVerified':True,'singleVisibleDeviceVerified':True,'effectiveLimitBytes':gib*1024**3,
            'canonicalLimitBytes':gib*1024**3,'schedulerInjectedLimitBytes':contract.QUOTAS[gib]['globalMiB']*1024**2}
        cache = {'device':20,'inode':1000+index,'uid':1000,'gid':100,'path':evaluator.CACHE_PATH,
            'mappingVerified':True,'noTmpFallback':True}
        ready = [{**identity,'event':'ready','pid':101+child,'gpu':baseline.probe.normalized_uuid(baseline.GPU),
            'compiler':copy.deepcopy(evaluator.COMPILER),'cache':copy.deepcopy(cache),'hami':copy.deepcopy(hami)} for child in (0,1)]
        for child,value in zip(('a','b'),ready):stream.append({**identity,'event':'mixed-child-evidence','child':child,'value':value})
        def response(child,ident,action,label,when,code=0,mib=None):
            value = {**copy.deepcopy(ready[child]),'event':'response','id':ident,'action':action,'label':label,
                'cudaResult':code,'operationStartedNs':when,'operationFinishedNs':when+10**6,'observedNs':when+10**6}
            if mib is not None:value.update(allocationMiB=mib,startMonotonicNs=when,endMonotonicNs=when+10**5)
            if code == 0 and action in ('allocate','tick'):
                value.update(writeBytes=mib*1024**2 if action == 'allocate' else 1024**2,
                    writeStartedNs=when+10**5,writeFinishedNs=when+2*10**5)
            stream.append({**identity,'event':'mixed-child-evidence','child':('a','b')[child],'value':value})
            return value
        sizes = contract.HOLD_ALLOCATIONS[gib]
        allocations = [response(i,f'hold-{i}-allocate','allocate','mixed-hold',NS+29*10**9+i*10**7,mib=size)
                       for i,size in enumerate(sizes)]
        ticks = [{'tick':tick,'observedNs':NS+30*10**9+tick*500_000_000+20_000_000,
            'values':[response(i,f'hold-{tick}-{i}','tick','mixed-hold',NS+30*10**9+tick*500_000_000+i*10**7)
                      for i in range(len(sizes))]} for tick in range(40)]
        frees = [response(i,f'hold-{i}-free','free','mixed-hold',NS+50*10**9+i*10**7) for i in range(len(sizes))]
        hold = {'startTargetNs':NS+30*10**9,'startedNs':NS+30*10**9,'finishedNs':NS+50*10**9,
            'durationSeconds':20,'payloadMiB':sum(sizes),'allocations':allocations,'ticks':ticks,'frees':frees}
        ordinary_start = NS+(51 if role == 'peer5' else 60)*10**9
        ordinary = {}
        keys = [('aHold',0,'a-hold','allocate'),('bDenied',1,'b-denied','allocate'),('aContinued',0,'a-continued','tick'),
            ('aFree',0,'a-free','free'),('bAfterFree',1,'b-after-free','allocate'),('bContinued',1,'b-continued','tick'),
            ('bFree',1,'b-free','free')]
        for number,(key,child,ident,action) in enumerate(keys):
            ordinary[key] = response(child,ident,action,'ordinary',ordinary_start+number*100_000_000,
                code=2 if key == 'bDenied' else 0,mib=contract.ALLOCATIONS[gib] if action == 'allocate' else None)
        progress = []
        if role == 'peer5':
            progress = [{'tick':tick,'observedNs':NS+52*10**9+tick*500_000_000+10**6,
                'value':response(0,f'peer-alive-{tick}','tick','peer-heartbeat',NS+52*10**9+tick*500_000_000)} for tick in range(90)]
        report = {**identity,'event':'mixed-result','profileGiB':gib,'startedNs':NS+10**9,
            'finishedNs':NS+(98 if role == 'peer5' else 64)*10**9,'requestedMiB':gib*1024,
            'allocationMiB':contract.ALLOCATIONS[gib],'compiler':evaluator.COMPILER,'approval':review,'children':ready,
            'ordinaryStartedNs':ordinary_start,'ordinaryFinishedNs':ordinary_start+10**9,'ordinary':ordinary,
            'ordinaryPassed':True,'hold':hold,'peerProgress':progress,'status':'bounded-mixed-role-passed',
            'productionQualified':False,'hostileIsolationQualified':False,'mpsThreeClientQualified':False}
        stream.insert(0,{**identity,'event':'mixed-cpu-gate-released','approval':review,'observedNs':NS+10**6})
        stream.append(report);events[role] = stream
    node = {'metadata':{'name':baseline.render.NODE,'uid':inventory['node']['uid']},
            'status':{'conditions':[{'type':'Ready','status':'True'}]}}
    return [events,pods,node,inventory,{'before':{'items':cms},'after':{'items':copy.deepcopy(cms)}}],fixture


class MixedRuntimeTests(unittest.TestCase):
    def check(self,values,fixture,wheel=WHEEL):
        return evaluator.evaluate(*values,fixture=fixture,compiler_wheel=wheel)

    def test_synthetic_full_contract_never_qualifies_production(self):
        values,fixture = evidence();result = self.check(values,fixture)
        self.assertTrue(result['boundedMixedCasesPassed'],result)
        for key in ('productionQualified','hostileIsolationQualified','mpsThreeClientQualified','mixedPackingQualified',
                    'schedulerQuotaCandidatesLiveQualified','temporaryMpsMutationImplemented'):
            self.assertIs(result[key],False)
        self.assertEqual(result['simultaneousPayloadMiB'],32896)
        self.assertEqual(result['nominalBudgetMiB'],35840)

    def test_actual_probe_protocol_simulation_feeds_strict_evaluator(self):
        import test_mixed_probe as protocol
        import mixed_probe
        values,fixture = evidence();proof = json.loads(fixture['items'][0]['data']['preflight.json'])
        with patch.object(protocol,'NOW',NOW),patch.object(protocol,'NOW_NS',NS), \
                patch.object(protocol,'GPU',baseline.probe.normalized_uuid(baseline.GPU)):
            for index,role in enumerate(contract.ROLES):
                simulation = protocol.Simulation(role)
                uid = PODS[index];marker = approval(proof,role,uid)
                existing = values[0][role]
                ready_receipt = next(e['value'] for e in existing if e['event'] == 'mixed-child-evidence')
                def factory(name,simulation=simulation,uid=uid,ready_receipt=ready_receipt):
                    worker = protocol.FakeChild(name,simulation)
                    worker.ready.update(podUid=uid,runId=proof['runId'],cache=copy.deepcopy(ready_receipt['cache']),
                        hami=copy.deepcopy(ready_receipt['hami']))
                    simulation.children.append(worker)
                    simulation.events.append({'event':'mixed-child-evidence','child':name,'value':copy.deepcopy(worker.ready)})
                    return worker
                simulation.factory = factory
                simulation.prepare = lambda role,marker=marker:(proof,marker,evaluator.COMPILER)
                self.assertEqual(simulation.run(),0)
                for event in simulation.events:event.update(podUid=uid,runId=proof['runId'],role=role)
                gate = {'event':'mixed-cpu-gate-released','podUid':uid,'runId':proof['runId'],
                    'role':role,'observedNs':NS+10**6,'approval':marker}
                values[0][role] = [gate,*simulation.events]
        result = self.check(values,fixture)
        self.assertTrue(result['boundedMixedCasesPassed'],result)

    def test_compiler_generates_three_suspended_private_profiles(self):
        fixture = renderer.render(preflight(),'mix01234',WHEEL,now=NOW)
        proof = json.loads(fixture['items'][0]['data']['preflight.json'])
        for role,job in zip(contract.ROLES,fixture['items'][1:]):
            self.assertTrue(job['spec']['suspend'])
            spec = job['spec']['template']['spec'];gib = contract.ROLES[role]
            self.assertEqual(spec['securityContext']['runAsUser'],1000)
            self.assertEqual(spec['securityContext']['runAsGroup'],100)
            self.assertEqual(spec['initContainers'][0],proof['runtimePlans'][role]['init_containers'][0])
            self.assertEqual(spec['containers'][0]['command'],['python','-u','/probe/mixed_probe.py',role])
            env = {v['name']:v for v in spec['containers'][0]['env']}
            self.assertEqual(env['CUDA_DEVICE_MEMORY_LIMIT_0']['value'],str(gib*1024)+'m')
            self.assertNotIn('NVIDIA_VISIBLE_DEVICES',env)
            self.assertNotIn(baseline.render.REVIEWED_GPU_ANNOTATION,job['spec']['template']['metadata']['annotations'])
            self.assertFalse(spec['automountServiceAccountToken'])

    def test_unsupported_old_server_and_unreviewed_settings_rejected(self):
        for change in ('uid','pid','clients','node','defaults','review','thread','source','stale'):
            value = preflight()
            if change == 'uid':value['mpsReference']['server']['uid'] = 10001
            if change == 'pid':value['mpsReference']['server']['pid'] += 1
            if change == 'clients':value['mpsReference']['server']['clients'] = [100]
            if change == 'node':value['node']['ready'] = False
            if change == 'defaults':value['mpsReference']['defaults']['activeThreadPercentage'] = 100
            if change == 'review':value['mpsMaintenanceReview']['reviewSha256'] = 'wrong'
            if change == 'thread':value['mpsMaintenanceReview']['activeThreadPercentage'] = 12
            if change == 'source':value['image'] = 'other@sha256:'+'0'*64
            if change == 'stale':value['mpsReference']['observedAt'] = (NOW-dt.timedelta(minutes=16)).isoformat()
            with self.subTest(change=change),self.assertRaises(ValueError):renderer.render(value,'mix01234',WHEEL,now=NOW)

    def test_forged_executable_fields_rejected_for_all_profiles(self):
        for role in contract.ROLES:
            for field in ('args','command','lifecycle','startupProbe','env','security','hostPID','init','mount','serviceAccount'):
                values,fixture = evidence();pod = values[1][role];main = pod['spec']['containers'][0]
                if field == 'args':main['args'] = ['--unsafe']
                if field == 'command':main['command'] = ['sh','-c','echo bypass']
                if field == 'lifecycle':main['lifecycle'] = {'postStart':{'exec':{'command':['sh','-c','echo bypass']}}}
                if field == 'startupProbe':main['startupProbe'] = {'exec':{'command':['sh','-c','echo bypass']}}
                if field == 'env':main['env'].append({'name':'LD_PRELOAD','value':'evil'})
                if field == 'security':main['securityContext']['allowPrivilegeEscalation'] = True
                if field == 'hostPID':pod['spec']['hostPID'] = True
                if field == 'init':pod['spec']['initContainers'].insert(0,copy.deepcopy(main))
                if field == 'mount':main['volumeMounts'][0]['readOnly'] = False
                if field == 'serviceAccount':pod['spec']['serviceAccountName'] = 'admin'
                with self.subTest(role=role,field=field):self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])

    def test_matching_forged_template_and_pod_still_rejected(self):
        values,fixture = evidence()
        fixture['items'][2]['spec']['template']['spec']['containers'][0]['command'] = ['python','-c','print(1)']
        values[1]['workspace10']['spec']['containers'][0]['command'] = ['python','-c','print(1)']
        self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])

    def test_actual_image_and_owned_configmap_bindings(self):
        for change in ('imageID','initImageID','ownership','newCM','data','envFrom','quota20'):
            values,fixture = evidence();pod = values[1]['workspace20']
            if change == 'imageID':pod['status']['containerStatuses'][0]['imageID'] = 'other@sha256:'+'0'*64
            if change == 'initImageID':pod['status']['initContainerStatuses'][0]['imageID'] = 'other@sha256:'+'0'*64
            cm = values[4]['after']['items'][4]
            if change == 'ownership':cm['metadata']['ownerReferences'][0]['uid'] = PODS[0]
            if change == 'newCM':cm['metadata']['uid'] = 'replacement'
            if change == 'data':cm['data']['CUDA_DEVICE_MEMORY_LIMIT'] = '40960m'
            if change == 'envFrom':pod['spec']['containers'][0]['envFrom'][0]['configMapRef']['optional'] = True
            if change == 'quota20':
                for stage in ('before','after'):values[4][stage]['items'][4]['data']['GPU_PORTION'] = '0.51'
            with self.subTest(change=change):self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])

    def test_cpu_approval_rejects_stale_old_server_or_unbound_candidate(self):
        for change in ('oldUID','PID','start','window','stale','candidate','thread','podUID','gpu','unknown'):
            values,fixture = evidence();marker = values[0]['workspace10'][0]['approval']
            if change == 'oldUID':marker['mps']['server']['uid'] = 10001
            if change == 'PID':marker['mps']['server']['pid'] += 1
            if change == 'start':marker['mps']['server']['startTimeTicks'] += 1
            if change == 'window':marker['mps']['windowEndsAtNs'] = NS+181*10**9
            if change == 'stale':values[0]['workspace10'][0]['observedNs'] = NS+16*10**9
            if change == 'candidate':marker['mps']['candidateSha256'] = 'e'*64
            if change == 'thread':marker['mps']['activeThreadPercentage'] = 12
            if change == 'podUID':marker['podUids'][1] = 'unknown'
            if change == 'gpu':marker['gpuUuid'] = baseline.OTHER_GPU
            if change == 'unknown':marker['mps']['writeSettingsAutomatically'] = True
            with self.subTest(change=change):self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])

    def test_source_and_wheel_identity_rejected(self):
        values,fixture = evidence();fixture['items'][0]['data']['mixed_probe.py'] += '\n# changed\n'
        self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory)/'wrong.whl';wheel.write_bytes(b'not reviewed')
            values,fixture = evidence();self.assertFalse(self.check(values,fixture,wheel)['boundedMixedCasesPassed'])

    def test_false_cuda_or_cache_progress_receipts_rejected(self):
        for change in ('OOM','write','peer','overlap','cache','ordinaryOrder','node','holdmissing'):
            values,fixture = evidence();report = values[0]['workspace10'][-1]
            if change == 'OOM':report['ordinary']['bDenied']['cudaResult'] = 0
            if change == 'write':report['hold']['ticks'][0]['values'][0]['writeBytes'] = 0
            if change == 'peer':values[0]['peer5'][-1]['peerProgress'] = values[0]['peer5'][-1]['peerProgress'][:-1]
            if change == 'overlap':report['hold']['startedNs'] += 3*10**9
            if change == 'cache':report['children'][0]['cache']['inode'] = 1000
            if change == 'ordinaryOrder':report['ordinary']['bAfterFree']['operationStartedNs'] = NS+30*10**9
            if change == 'node':values[2]['status']['conditions'][0]['status'] = 'False'
            if change == 'holdmissing':report['hold']['ticks'].pop()
            with self.subTest(change=change):self.assertFalse(self.check(values,fixture)['boundedMixedCasesPassed'])

    def test_sources_have_no_live_cluster_or_settings_calls(self):
        for filename in ('mixed_contract.py','mixed_render.py','mixed_evaluate.py'):
            tree = ast.parse((Path(__file__).parent/filename).read_text())
            imports = {node.name for node in ast.walk(tree) if isinstance(node,ast.alias)}
            self.assertFalse(imports & {'subprocess','socket','requests','kubernetes','paramiko'})

if __name__ == '__main__':unittest.main()
