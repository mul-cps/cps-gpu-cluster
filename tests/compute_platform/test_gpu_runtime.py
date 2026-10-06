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
