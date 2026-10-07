"""Offline checks for the separately pinned compiler-runtime fixture."""
import ast
import copy
import contextlib
import io
import stat
from types import SimpleNamespace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import evaluate_compiled as evaluator
import probe_compiled as probe
import render_compiled as renderer
import test_dynamic_cache as old

WHEEL = Path(os.environ.get('CPS_QUALIFICATION_COMPILER_WHEEL',
 '/home/bjoern/cps-platform-evidence/2026-10-07/dynamic-runtime-packaging/2f43f59aa319/dist/cps_compute-0.1.0-py3-none-any.whl'))

def preflight():
    value=old.preflight();value['image']=renderer.IMAGE;return value

def evidence(uid=10001,gid=10001):
    values=list(old.valid_evidence())
    workspace,peer,old_workspace,old_peer,node,_,cms=values
    fixture=renderer.render(preflight(),'abcd1234',WHEEL,uid=uid,gid=gid,now=old.NOW)
    pods=[]
    for old_pod,item in zip((old_peer,old_workspace),fixture['items'][1:]):
        pod={'metadata':{**copy.deepcopy(item['spec']['template']['metadata']),
             'uid':old_pod['metadata']['uid'],'name':old_pod['metadata']['name'],'namespace':renderer.NAMESPACE},
             'spec':{**copy.deepcopy(item['spec']['template']['spec']),'nodeName':renderer.NODE},
             'status':{'phase':'Succeeded'}}
        pod['metadata']['annotations'][renderer.REVIEWED_GPU_ANNOTATION]=old.GPU
        cm_name=old_pod['metadata']['name']+'-shared-gpu-0'
        pod['spec']['containers'][0]['env'].extend({'name':name,'valueFrom':{
            'configMapKeyRef':{'name':cm_name,'key':name}}} for name in
            ('NVIDIA_VISIBLE_DEVICES','CUDA_DEVICE_MEMORY_LIMIT','GPU_PORTION'))
        pods.append(pod)
    report=workspace[-1]
    report.update(compiler={'sourceCommit':renderer.SOURCE_COMMIT,'moduleSha256':renderer.MODULE_SHA256,'version':'0.1.0'},
                  mpsThreeClientQualified=False,startedNs=9_000_000_000,finishedNs=40_000_000_000)
    for value in [e['value'] for e in workspace if e['event']=='child-evidence']+list(report['ordinary'].values()):
        value['cache'].update(uid=uid,gid=gid)
    report['cache'].update(uid=uid,gid=gid)
    start,finish=10_000_000_000,30_000_000_000
    hold={'startedNs':start,'finishedNs':finish,'durationSeconds':20,'childPids':[101,102],
          'ticks':[],'allocations':[],'frees':[],'mpsThreeClientQualified':False}
    events=[{'event':'mps-hold-start','startedNs':start,'durationSeconds':20,'childPids':[101,102],
             'mpsThreeClientQualified':False}]
    for action,key in [('allocate','allocations'),('free','frees')]:
        for name,pid in [('a',101),('b',102)]:
            value={**old.value(pid=pid),'event':'response','id':f'hold-{name}-{action}',
                   'action':action,'label':'mps-hold','cache':copy.deepcopy(report['cache'])}
            hold[key].append(value);events.append({'event':'child-evidence','child':name,'value':value})
    for tick in range(40):
        receipts=[]
        for name,pid in [('a',101),('b',102)]:
            value={**old.value(pid=pid),'event':'response','id':f'hold-{tick}-{name}',
                   'action':'tick','label':'mps-hold','cache':copy.deepcopy(report['cache'])}
            receipts.append(value);events.append({'event':'child-evidence','child':name,'value':value})
        record={'tick':tick,'observedNs':start+tick*500_000_000,'values':receipts}
        hold['ticks'].append(record);events.append({'event':'mps-hold-progress',**record,'mpsThreeClientQualified':False})
    events.append({'event':'mps-hold-finished','startedNs':start,'finishedNs':finish,'childPids':[101,102],
                   'mpsThreeClientQualified':False})
    report['hold']=hold;workspace[-1:-1]=events
    ready=peer[0];ready['cache'].update(uid=uid,gid=gid);ready.update(pid=201,compiler=report['compiler'])
    peer=[ready,*[{'event':'peer-alive','gpu':ready['gpu'],'cache':ready['cache'],'hami':ready['hami'],
                  'cudaResult':0,'observedNs':n*500_000_000} for n in range(17,82)],peer[-1]]
    for events,pod in ((workspace,pods[1]),(peer,pods[0])):
        for event in events:event.update(podUid=pod['metadata']['uid'],runId='abcd1234')
    return [workspace,peer,pods[1],pods[0],node,preflight(),cms],fixture

class CompiledRuntimeTests(unittest.TestCase):
    def evaluate(self,values,fixture):
        return evaluator.evaluate(*values,fixture=fixture,compiler_wheel=WHEEL)

    def test_exact_packaged_compiler_and_initializer(self):
        fixture=renderer.render(preflight(),'abcd1234',WHEEL,now=old.NOW)
        proof=json.loads(fixture['items'][0]['data']['preflight.json'])
        self.assertEqual(proof['compiler']['wheelSha256'],renderer.WHEEL_SHA256)
        self.assertEqual(proof['runtimePlan'],renderer.compile_plan(WHEEL))
        for job in fixture['items'][1:]:
            self.assertTrue(job['spec']['suspend']);self.assertEqual(job['spec']['backoffLimit'],0)
            spec=job['spec']['template']['spec'];self.assertFalse(spec['automountServiceAccountToken'])
            self.assertEqual(spec['imagePullSecrets'],[{'name':'cps-compute-image-pull'}])
            self.assertEqual(spec['nodeSelector'],{'kubernetes.io/hostname':'k3s-wk-gpu2'})
            init=spec['initContainers'][0]
            self.assertEqual(init['name'],'cps-gpu-cache-init')
            self.assertEqual(init['command'],['python','-m','cps_compute.gpu_runtime'])
            self.assertEqual(init['args'],['initialize-cache','--directory','/cache-root','--uid','10001','--gid','10001'])
            self.assertEqual(spec['initContainers'][1]['name'],'await-operator-runtime-review')
            main=spec['containers'][0];self.assertEqual(main['image'],renderer.IMAGE)
            self.assertEqual([m for m in main['volumeMounts'] if m['mountPath']==probe.CACHE_PATH],
                [{'name':'cps-gpu-cache','mountPath':probe.CACHE_PATH,'subPath':'private/usage.cache'}])
            env={e['name']:e for e in main['env']}
            self.assertEqual(env['CUDA_DEVICE_MEMORY_LIMIT_0']['value'],'5120m')
            for name in ['CUDA_DEVICE_MEMORY_LIMIT','GPU_PORTION','NVIDIA_VISIBLE_DEVICES']:self.assertNotIn(name,env)
            self.assertNotIn(renderer.REVIEWED_GPU_ANNOTATION,job['spec']['template']['metadata']['annotations'])
            self.assertEqual(len({v['name'] for v in spec['volumes']}),len(spec['volumes']))

    def test_only_reviewed_pairs_and_all_container_owners(self):
        for uid,gid in [(10001,10001),(1000,1000),(1000,100)]:
            fixture=renderer.render(preflight(),'abcd1234',WHEEL,uid=uid,gid=gid,now=old.NOW)
            for job in fixture['items'][1:]:
                spec=job['spec']['template']['spec']
                self.assertEqual((spec['securityContext']['runAsUser'],spec['securityContext']['runAsGroup']),(uid,gid))
                for container in spec['initContainers']+spec['containers']:
                    self.assertEqual((container['securityContext']['runAsUser'],container['securityContext']['runAsGroup']),(uid,gid))
        for pair in [(0,0),(1000,101),(True,100),(10001,100)]:
            with self.assertRaises(ValueError):renderer.compile_plan(WHEEL,*pair)

    def test_wrong_wheel_image_inventory_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            bad=Path(directory)/'wrong.whl';bad.write_bytes(b'wrong')
            with self.assertRaises(ValueError):renderer.compile_plan(bad)
        bad=preflight();bad['image']=old.render.IMAGE
        with self.assertRaises(ValueError):renderer.render(bad,'abcd1234',WHEEL,now=old.NOW)
        bad=preflight();bad['mpsServers'].pop()
        with self.assertRaises(ValueError):renderer.render(bad,'abcd1234',WHEEL,now=old.NOW)

    def test_synthetic_success_keeps_full_mps_hostile_and_production_pending(self):
        for pair in [(10001,10001),(1000,100)]:
            values,fixture=evidence(*pair);result=self.evaluate(values,fixture)
            self.assertEqual(result['status'],'bounded-standard-cases-passed',result)
            self.assertTrue(result['compilerGeneratedRuntimeQualified'])
            for key in ['productionQualified','hostileIsolationQualified','exactProfileQuotaQualified','mpsThreeClientQualified']:
                self.assertFalse(result[key])

    def test_missing_changed_hold_cannot_pass(self):
        for mutation in ['missing','short','tick-failed','false-claim','phase-missing','receipt-missing','reused-tick']:
            values,fixture=evidence();workspace=values[0];report=workspace[-1]
            if mutation=='missing':report['hold']=None
            elif mutation=='short':report['hold']['finishedNs']=report['hold']['startedNs']+1
            elif mutation=='tick-failed':report['hold']['ticks'][0]['values'][0]['cudaResult']=2
            elif mutation=='false-claim':report['mpsThreeClientQualified']=True
            elif mutation=='phase-missing':workspace[:]=[e for e in workspace if e['event']!='mps-hold-start']
            elif mutation=='reused-tick':report['hold']['ticks'][1]['values']=report['hold']['ticks'][0]['values']
            else:
                ident=report['hold']['ticks'][0]['values'][0]['id']
                workspace[:]=[e for e in workspace if not(e['event']=='child-evidence' and e['value'].get('id')==ident)]
            self.assertEqual(self.evaluate(values,fixture)['status'],'failed-or-inconclusive',mutation)

    def test_mount_initializer_security_gate_owner_cm_receipts_required(self):
        for mutation in ['subpath','initializer','gate','security','owner','cm-uid']:
            values,fixture=evidence();spec=values[2]['spec']
            if mutation=='subpath':spec['containers'][0]['volumeMounts'][2]['subPath']='usage.cache'
            elif mutation=='initializer':spec['initContainers'][0]['command']=['true']
            elif mutation=='gate':spec['initContainers'].pop()
            elif mutation=='security':spec['containers'][0]['securityContext']['runAsUser']=1000
            elif mutation=='owner':values[0][-1]['cache']['gid']=100
            else:values[6]['after']['items'][1]['metadata']['uid']='changed'
            self.assertEqual(self.evaluate(values,fixture)['status'],'failed-or-inconclusive',mutation)

    def test_peer_must_cover_complete_hold_window(self):
        values,fixture=evidence()
        values[1][:]=[e for e in values[1] if e['event']!='peer-alive' or not 15_000_000_000<e['observedNs']<18_000_000_000]
        self.assertEqual(self.evaluate(values,fixture)['status'],'failed-or-inconclusive')

    def test_cpu_gate_exec_rejects_unbound_marker_before_main(self):
        for uid,gid in [(10001,10001),(1000,100)]:
            fixture=renderer.render(preflight(),'abcd1234',WHEEL,uid=uid,gid=gid,now=old.NOW)
            proof=json.loads(fixture['items'][0]['data']['preflight.json'])
            marker={'runtimeReviewed':True,'role':'peer','podUid':'actual-pod','runId':'abcd1234',
                'nodeUid':old.UID,'uid':uid,'gid':gid,'gpuUuid':old.GPU,'hamiSha256':'a'*64,
                'probeSha256':proof['probeSha256'],'compilerWheelSha256':renderer.WHEEL_SHA256}
            class FakePath:
                def __init__(self,value):self.path=value
                def exists(self):return True
                def stat(self,**kwargs):
                    return SimpleNamespace(st_uid=uid,st_gid=gid,st_size=1024,
                                           st_mode=stat.S_IFREG|0o600,st_nlink=1)
                def read_text(self):
                    return json.dumps(proof if self.path=='/probe/preflight.json' else marker)
            with patch('pathlib.Path',FakePath),patch('os.getuid',return_value=uid),patch('os.getgid',return_value=gid), \
                 patch.dict(os.environ,{'FIXTURE_POD_UID':'actual-pod'}), \
                 patch('sys.argv',['gate','peer',proof['probeSha256']]),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as complete:
                    exec(compile(renderer.OPERATOR_GATE,'operator-gate','exec'),{})
                self.assertEqual(complete.exception.code,0)
                for key in ('podUid','runId','uid','gid','nodeUid','hamiSha256','probeSha256','compilerWheelSha256'):
                    original=marker[key];marker[key]='changed'
                    with self.assertRaises(AssertionError):exec(compile(renderer.OPERATOR_GATE,'operator-gate','exec'),{})
                    marker[key]=original
                marker['gpuUuid']='GPU-00000000-0000-0000-0000-000000000000'
                with self.assertRaisesRegex(AssertionError,'observed GPU allowlist'):
                    exec(compile(renderer.OPERATOR_GATE,'operator-gate','exec'),{})

    def test_duplicate_environment_or_changed_gate_source_cannot_pass(self):
        for mutation in ('environment','gate-source','probe-source','gate-security','init-order'):
            values,fixture=evidence()
            if mutation=='environment':values[2]['spec']['containers'][0]['env'].append({'name':'FIXTURE_UID','value':'10001'})
            elif mutation=='gate-source':fixture['items'][0]['data']['operator-gate.py']='raise SystemExit(0)'
            elif mutation=='probe-source':fixture['items'][0]['data']['probe_compiled.py']+='\n# changed'
            elif mutation=='gate-security':values[2]['spec']['initContainers'][1]['securityContext']['allowPrivilegeEscalation']=True
            else:values[2]['spec']['initContainers'].reverse()
            self.assertEqual(self.evaluate(values,fixture)['status'],'failed-or-inconclusive',mutation)

    def test_cpu_gate_identity_wheel_pod_no_cuda_and_bounded_probe(self):
        source=renderer.OPERATOR_GATE;ast.parse(source)
        for text in ["proof['runtimeIdentity']",'compilerWheelSha256','FIXTURE_POD_UID',"proof['gpuUuidAllowlist']",'time.monotonic()+60','stat.S_ISREG','0o600']:
            self.assertIn(text,source)
        for text in ['ctypes','libcuda','kubectl','socket','requests','os.chmod','os.remove','unlink']:self.assertNotIn(text,source)
        source=Path(probe.__file__).read_text()
        for text in ['report["hold"] = hold_contexts(workers)','range(675)','HOLD_SECONDS = 20']:self.assertIn(text,source)
        self.assertNotIn('os.unlink',source)
        with patch.dict(os.environ,{'FIXTURE_UID':'1000','FIXTURE_GID':'100'}),patch.object(probe.os,'getuid',return_value=1000),patch.object(probe.os,'getgid',return_value=100):
            self.assertEqual(probe.runtime_identity(),(1000,100))
        with patch.dict(os.environ,{'FIXTURE_UID':'1000','FIXTURE_GID':'100'}),patch.object(probe.os,'getuid',return_value=10001):
            with self.assertRaises(RuntimeError):probe.runtime_identity()

if __name__=='__main__':unittest.main()
