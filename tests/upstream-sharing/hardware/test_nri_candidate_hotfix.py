"""Focused offline rejection tests; never invokes SSH, kubectl or fault injection."""
import copy
from pathlib import Path
import tempfile
import unittest

from nri_candidate_hotfix import arguments, fresh_output, require_boot, validate_fractiond, validate_node

BOOT='a39cdade-f00d-4cd1-9a81-c290d668194f'
UID='83ff65f5-b48d-4637-80b1-d924174446a6'


class ColdBootGuardTests(unittest.TestCase):
    def args(self):
        return arguments(['--expected-boot-id',BOOT,'--output','/tmp/fresh-review',
            '--fractiond-pod','gpu-fractioning-fractiond-new','--fractiond-pod-uid',UID])

    def test_explicit_cli_and_new_directory_required(self):
        a=self.args();self.assertEqual(a.expected_boot_id,BOOT)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fresh';fresh_output(p)
            with self.assertRaises(FileExistsError):fresh_output(p)
        with self.assertRaises(SystemExit):arguments([])
        argv=['--expected-boot-id','invalid','--output','/tmp/review','--fractiond-pod','new','--fractiond-pod-uid',UID]
        with self.assertRaises(SystemExit):arguments(argv)
        argv[1]=BOOT;argv[-1]='invalid'
        with self.assertRaises(SystemExit):arguments(argv)

    def test_rejects_stale_boot(self):
        require_boot(BOOT,BOOT)
        with self.assertRaises(RuntimeError):require_boot('new-boot',BOOT)

    def test_exact_fractiond_pod_uid_and_container_required(self):
        a=self.args();p={'metadata':{'name':a.fractiond_pod,'uid':UID},'spec':{'nodeName':'k3s-wk-gpu2'},
            'status':{'containerStatuses':[{'name':'fractiond','containerID':'containerd://'+'a'*64,'state':{'running':{}}}]}}
        self.assertEqual(validate_fractiond(p,a),'a'*64)
        for key in ('uid','name','deletionTimestamp'):
            bad=copy.deepcopy(p);bad['metadata'][key]='replacement'
            with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['status']['containerStatuses'][0]['state']={'waiting':{}}
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['status']['containerStatuses'][0]['containerID']='containerd://not-a-cid'
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)
        bad=copy.deepcopy(p);bad['spec']['nodeName']='k3s-wk-gpu3'
        with self.assertRaises(RuntimeError):validate_fractiond(bad,a)

    def test_correct_qualification_key_and_maintenance_fence(self):
        p={'metadata':{'labels':{}},'spec':{'unschedulable':True,'taints':[{
            'key':'cps.unileoben.ac.at/maintenance','value':'upstream-pilot','effect':'NoSchedule'}]}}
        validate_node(p)
        p['metadata']['labels']['cps.unileoben.ac.at/upstream-gpu-sharing']='qualified'
        with self.assertRaises(RuntimeError):validate_node(p)
        del p['metadata']['labels']['cps.unileoben.ac.at/upstream-gpu-sharing']
        p['spec']['taints']=[]
        with self.assertRaises(RuntimeError):validate_node(p)


if __name__=='__main__':unittest.main()
