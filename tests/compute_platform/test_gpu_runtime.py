import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[2]/'scripts/compute-platform/qualify-gpu-runtime.py'
spec=importlib.util.spec_from_file_location('gpu_runtime',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class TrustedGpuProbeGuards(unittest.TestCase):
    def test_output_in_git_is_rejected_before_cluster_access(self):
        with patch.object(module,'kubectl') as call:
            with self.assertRaises(ValueError):module.run('node',SCRIPT.parent/'unsafe.json')
            call.assert_not_called()

    def test_required_namespace_is_checked_before_pod_creation(self):
        response=subprocess.CompletedProcess([],0,json.dumps({'metadata':{'labels':{}}}), '')
        with patch.object(module,'kubectl',return_value=response) as call:
            with self.assertRaises(ValueError):module.run('node',Path('/tmp/unused-gpu-probe.json'))
            self.assertEqual(call.call_count,1)

    def test_active_gpu_workload_or_reservation_blocks_probe(self):
        for fields in ({'annotations':{'gpu-memory':'10240'}},{'limits':{'nvidia.com/gpu':'1'}},{'requests':{'nvidia.com/gpu':'1'}}):
            pod={'metadata':{'annotations':fields.get('annotations',{})},'spec':{'nodeName':'node','containers':[{'resources':fields}]},'status':{'phase':'Running'}}
            ns={'metadata':{'labels':{'compute.cps.unileoben.ac.at/isolation':'required'}}}
            responses=[subprocess.CompletedProcess([],0,json.dumps(d),'') for d in (ns,{'items':[pod]})]
            with self.subTest(fields=fields),patch.object(module,'kubectl',side_effect=responses) as call:
                with self.assertRaises(ValueError):module.run('node',Path('/tmp/unused-gpu-probe.json'))
                self.assertEqual(call.call_count,2)

class CombinedMpsProbe(unittest.TestCase):
    def fixture(self, clients='4321\n', include_daemon=True):
        created=[];deleted=[]
        base={'metadata':{'name':'hami-20g-peer'},'spec':{'containers':[{'name':'main','image':'registry/trusted@sha256:'+'a'*64}]}}
        daemon={'metadata':{'name':'mps-operator','namespace':'gpu-operator','labels':{'app':'mps-control-daemon-standalone'}},'spec':{'nodeName':'node','containers':[{'name':'mps-control-daemon-ctr'}]},'status':{'phase':'Running','conditions':[{'type':'Ready','status':'True'}]}}
        cases=['ordinary','unset-preload','larger-environment-limit','disable-control','larger-limit-fresh-cache','disable-mps-fresh-cache']
        peer=[{'event':'ready','gpu':'gpu-a'}]+[{'event':'alive','tick':i} for i in range(60)]+[{'event':'result','cuda_result':0}]
        attempts=[{'event':'attempt','case':case,'returncode':0,'results':[{'gpu':'gpu-a','cuda_result':2}]} for case in cases]
        def kubectl(*args,data=None,check=True):
            if args[:2]==('get','namespace'): out={'metadata':{'labels':{'compute.cps.unileoben.ac.at/isolation':'required'}}}
            elif args[:2]==('get','pods'): out={'items':[daemon] if include_daemon else []}
            elif args[:2]==('get','pod'): out={'metadata':{'annotations':{'kubectl.kubernetes.io/last-applied-configuration':json.dumps(base)}}}
            elif args[0]=='create': created.append(json.loads(data));out={}
            elif args[0]=='logs': return subprocess.CompletedProcess([],0,'\n'.join(json.dumps(x) for x in (peer if 'peer' in args[-1] else attempts)),'')
            elif args[0]=='exec':
                command=' '.join(args)
                return subprocess.CompletedProcess([],0,'1234\n' if 'get_server_list' in command else clients,'')
            elif args[0]=='delete': deleted.append(args[2]);out={}
            else: raise AssertionError(args)
            return subprocess.CompletedProcess([],0,json.dumps(out),'')
        return kubectl,created,deleted

    def test_combined_probe_records_mps_participation_and_mounts(self):
        import tempfile
        fake,created,deleted=self.fixture()
        with tempfile.TemporaryDirectory() as tmp,patch.object(module,'kubectl',side_effect=fake):
            result=module.run('node',Path(tmp)/'result.json',mps=True)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['mpsClientsObserved'],{'1234':['4321']})
        self.assertEqual(len(result['attempts']),6)
        for pod in created:
            self.assertEqual(pod['spec']['nodeSelector'],{'kubernetes.io/hostname':'node'})
            mounts={v['name']:v['hostPath']['path'] for v in pod['spec']['volumes']}
            self.assertEqual(mounts['qualification-mps-pipe'],'/run/nvidia/mps/nvidia.com/gpu/pipe')
            self.assertEqual(mounts['qualification-mps-shm'],'/run/nvidia/mps/shm')
            env={e['name']:e['value'] for e in pod['spec']['containers'][0]['env']}
            self.assertEqual(env['CUDA_MPS_PIPE_DIRECTORY'],'/mps/pipe')
            self.assertEqual(env['PROBE_MPS'],'1')
        self.assertEqual(set(deleted),{p['metadata']['name'] for p in created})

    def test_no_mps_participant_cannot_pass_and_cleans_up(self):
        import tempfile
        fake,created,deleted=self.fixture(clients='')
        with tempfile.TemporaryDirectory() as tmp,patch.object(module,'kubectl',side_effect=fake):
            path=Path(tmp)/'result.json'
            with self.assertRaisesRegex(ValueError,'MPS client'):module.run('node',path,mps=True)
            self.assertEqual(json.loads(path.read_text())['status'],'incomplete')
        self.assertEqual(set(deleted),{p['metadata']['name'] for p in created})

    def test_missing_node_daemon_refuses_before_pod_creation(self):
        import tempfile
        fake,created,deleted=self.fixture(include_daemon=False)
        with tempfile.TemporaryDirectory() as tmp,patch.object(module,'kubectl',side_effect=fake):
            with self.assertRaisesRegex(ValueError,'MPS daemon'):module.run('node',Path(tmp)/'result.json',mps=True)
        self.assertEqual(created,[])
        self.assertEqual(deleted,[])
