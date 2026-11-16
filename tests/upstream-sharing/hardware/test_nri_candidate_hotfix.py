"""Focused offline rejection tests; never invokes SSH, kubectl or fault injection."""
import copy
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
import io
import nri_candidate_hotfix as fixture

from nri_candidate_hotfix import arguments, fresh_output, require_boot, validate_fractiond, validate_node

BOOT='a39cdade-f00d-4cd1-9a81-c290d668194f'
UID='83ff65f5-b48d-4637-80b1-d924174446a6'
NODE_UID='33366666-1111-4222-8333-444444444444'
NODE='k3s-wk-gpu3'
GPU_A='GPU-16128952-b438-556a-00bb-93039ee24e56'
GPU_B='GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'


class ColdBootGuardTests(unittest.TestCase):
    def argv(self):
        return ['--expected-boot-id',BOOT,'--output','/tmp/fresh-review',
            '--fractiond-pod','gpu-fractioning-fractiond-new','--fractiond-pod-uid',UID,
            '--node',NODE,'--node-uid',NODE_UID,'--node-ip','10.21.0.40',
            '--ssh-target','ubuntu@10.21.0.40','--ssh-key','/tmp/explicit-key',
            '--gpu-a',GPU_A,'--gpu-b',GPU_B,'--release-reference','root-explicit-test-release','--execute']

    def args(self):
        return arguments(self.argv())

    def node(self):
        return {'metadata':{'name':NODE,'uid':NODE_UID,'labels':{}},
            'spec':{'unschedulable':True,'taints':[{'key':'cps.unileoben.ac.at/maintenance','effect':'NoSchedule'}]},
            'status':{'conditions':[{'type':'Ready','status':'True'}],
                'addresses':[{'type':'InternalIP','address':'10.21.0.40'}],
                'nodeInfo':{'kernelVersion':'7.0.0-43-generic','bootID':BOOT}}}

    def test_legacy_gpu2_defaults_cannot_execute(self):
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            arguments(['--expected-boot-id',BOOT,'--output','/tmp/fresh-review',
                '--fractiond-pod','gpu-fractioning-fractiond-new','--fractiond-pod-uid',UID])

    def test_explicit_cli_and_new_directory_required(self):
        a=self.args();self.assertEqual(a.expected_boot_id,BOOT)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fresh';fresh_output(p)
            with self.assertRaises(FileExistsError):fresh_output(p)
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments([])
        argv=['--expected-boot-id','invalid','--output','/tmp/review','--fractiond-pod','new','--fractiond-pod-uid',UID]
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments(argv)
        argv[1]=BOOT;argv[-1]='invalid'
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments(argv)

    def test_rejects_stale_boot(self):
        require_boot(BOOT,BOOT)
        with self.assertRaises(RuntimeError):require_boot('new-boot',BOOT)

    def test_exact_fractiond_pod_uid_and_container_required(self):
        a=self.args();p={'metadata':{'name':a.fractiond_pod,'uid':UID},'spec':{'nodeName':NODE},
            'status':{'containerStatuses':[{'name':'fractiond','containerID':'containerd://'+'a'*64,'state':{'running':{}},'ready':True}]}}
        self.assertEqual(validate_fractiond(p,a),'a'*64)
        for key in ('uid','name','deletionTimestamp'):
            bad=copy.deepcopy(p);bad['metadata'][key]='replacement'
            with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['status']['containerStatuses'][0]['state']={'waiting':{}}
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['status']['containerStatuses'][0]['containerID']='containerd://not-a-cid'
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['status']['containerStatuses'][0]['ready']=False
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['spec']['nodeName']='k3s-wk-gpu2'
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)

    def test_correct_qualification_key_and_maintenance_fence(self):
        a=self.args();p=self.node();validate_node(p,a)
        for bad in [dict(p,metadata={**p['metadata'],'uid':UID}),
                    dict(p,metadata={**p['metadata'],'name':'k3s-wk-gpu2'}),
                    dict(p,status={**p['status'],'conditions':[]}),
                    dict(p,status={**p['status'],'addresses':[]}),
                    dict(p,status={**p['status'],'nodeInfo':{'kernelVersion':'old'}}),
                    dict(p,spec={**p['spec'],'unschedulable':False}),
                    dict(p,spec={**p['spec'],'taints':[]}),
                    dict(p,metadata={**p['metadata'],'labels':{'cps.unileoben.ac.at/upstream-gpu-sharing':'qualified'}})]:
            with self.assertRaises(RuntimeError):validate_node(bad,a)

    def test_each_execution_identity_and_release_are_explicit(self):
        for flag in ('--node','--node-uid','--node-ip','--ssh-target','--ssh-key','--gpu-a','--gpu-b','--release-reference','--execute'):
            argv=self.argv();i=argv.index(flag);del argv[i:i+(1 if flag=='--execute' else 2)]
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments(argv)
        for flag,value in [('--node-uid','bad'),('--node-ip','bad'),('--ssh-target','-ProxyCommand=bad'),('--gpu-a','GPU-bad'),('--gpu-b',GPU_A),('--release-reference','')]:
            argv=self.argv();argv[argv.index(flag)+1]=value
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments(argv)

    def test_selected_worker_routes_every_fixture_and_ssh(self):
        a=self.args()
        self.assertEqual(fixture.ssh_command(a)[-1],a.ssh_target)
        self.assertIn(str(a.ssh_key),fixture.ssh_command(a))
        for template in ('hung-pod.json','hung-cpu-pod.json','recovery-pod.json'):
            import json
            original=json.loads((fixture.OLD/template).read_text())
            body=fixture.render_fixture(original,'portable',a)
            self.assertEqual(body['spec']['nodeName'],NODE)
            annotation=body['metadata'].get('annotations',{}).get('nvidia.com/container.main.gpus.devices')
            if annotation:self.assertEqual(annotation,'k8s.device-plugin.nvidia.com/gpu='+GPU_A)
            self.assertEqual(original['spec']['nodeName'],'k3s-wk-gpu2')
            reverse=fixture.render_fixture(original,'portable-b',a,GPU_B)
            if annotation:self.assertEqual(reverse['metadata']['annotations']['nvidia.com/container.main.gpus.devices'],'k8s.device-plugin.nvidia.com/gpu='+GPU_B)

    def test_fractiond_cri_identity_cannot_cross_pods_or_containers(self):
        a=self.args();cid='a'*64
        x={'container_id':cid,'pod_uid':UID,'pod_name':a.fractiond_pod,'namespace':'gpu-fractioning',
            'container_name':'fractiond','pid':123,'starttime':'456','cmdline':['/fractiond'],
            'cgroup':'0::/kubepods/pod'+UID.replace('-','_')+'/cri-containerd-'+cid+'.scope'}
        fixture.validate_fractiond_process(x,a,cid)
        for key,value in [('container_id','b'*64),('pod_uid',BOOT),('pod_name','replacement'),
                          ('namespace','other'),('container_name','metricsd'),('pid',0),
                          ('starttime','bad'),('cmdline',['/other']),('cgroup','0::/other')]:
            with self.assertRaises(RuntimeError):fixture.validate_fractiond_process({**x,key:value},a,cid)

    def test_exact_selected_candidate_driver_required(self):
        a=self.args();pod={'metadata':{'name':'driver','uid':UID},'spec':{'nodeName':NODE,
            'containers':[{'name':'nvidia-driver-ctr','image':'ghcr.io/mul-cps/cps-nvidia-driver@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73'}]},
            'status':{'containerStatuses':[{'name':'nvidia-driver-ctr','ready':True,'imageID':fixture.DRIVER,'state':{'running':{}}}]}}
        fixture.validate_driver_pods([pod],a)
        for edit in ('node','image','imageID','ready','replacement'):
            bad=copy.deepcopy(pod)
            if edit=='node':bad['spec']['nodeName']='k3s-wk-gpu2'
            if edit=='image':bad['spec']['containers'][0]['image']='stock'
            if edit=='imageID':bad['status']['containerStatuses'][0]['imageID']='containerd://sha256:'+'0'*64
            if edit=='ready':bad['status']['containerStatuses'][0]['ready']=False
            if edit=='replacement':bad['metadata']['deletionTimestamp']='now'
            with self.assertRaises(RuntimeError):fixture.validate_driver_pods([bad],a)

    def test_selected_node_is_fixed_worker_and_exact_node_boot(self):
        argv=self.argv();argv[argv.index('--node')+1]='k3s-wk-gpu5'
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):arguments(argv)
        p=self.node();p['status']['nodeInfo']['bootID']=UID
        with self.assertRaises(RuntimeError):validate_node(p,self.args())

    def test_node_api_boot_mismatch_rejected_before_host_observation(self):
        p=self.node();p['status']['nodeInfo']['bootID']=UID
        with self.assertRaises(RuntimeError):validate_node(p,self.args())

    def test_live_idle_gpu_pods_block_fault_injection(self):
        a=self.args()
        for annotations,resources in [
                ({'gpu-memory':'5120'},{}),({'gpu-fraction':'0.125'},{}),
                ({'nvidia.com/container.main.gpus.devices':'assigned'},{}),
                ({'required-plugins.nri.containerd.io':'gpu-fractioning'},{}),
                ({},{'limits':{'nvidia.com/gpu':1}}),({},{'requests':{'nvidia.com/gpu':1}})]:
            p={'metadata':{'name':'idle-owned-workspace','annotations':annotations},
                'spec':{'nodeName':NODE,'containers':[{'resources':resources}]},'status':{'phase':'Running'}}
            with self.assertRaises(RuntimeError):fixture.reject_gpu_consumers([p],a)
            for phase in ('Succeeded','Failed'):
                terminal=copy.deepcopy(p);terminal['status']['phase']=phase
                fixture.reject_gpu_consumers([terminal],a)
            other=copy.deepcopy(p);other['spec']['nodeName']='k3s-wk-gpu4'
            fixture.reject_gpu_consumers([other],a)
        cpu={'metadata':{'name':'cpu'},'spec':{'nodeName':NODE,'containers':[{'resources':{'limits':{'cpu':'1'}}}]},'status':{'phase':'Running'}}
        fixture.reject_gpu_consumers([cpu],a)


if __name__=='__main__':unittest.main()
