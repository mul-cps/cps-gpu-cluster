import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('imports', Path(__file__).with_name('same_pod_imports.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def receipt(mode):
    needed = {'vmm-direct': ['vmm-create-64','vmm-map','vmm-set-access','fill-64','readback','vmm-unmap','vmm-release',
        'vmm-over-cap-never-touch','vmm-create-64','fill-64','readback'],
        'ipc-export': ['ipc-allocate','ipc-export','ordinary-free'],
        'ipc-import': ['importer-own-fill-allocate','ipc-import','import-readback','ipc-close','ordinary-free'],
        'vmm-export': ['vmm-export','exporter-references-released-importer-retains','vmm-unmap','vmm-release'],
        'vmm-import': ['importer-own-fill-allocate','vmm-import','vmm-map','vmm-set-access','import-readback',
            'importer-retained-backing-start','fill-64','importer-retained-backing-end','vmm-unmap','vmm-release','ordinary-free']}
    return [{'kind':'identity','gpu_uuid':m.GPU,'uid':1000,'gid':100,'driver_api_version':13040},
        {'kind':'initial-cap-info','total_bytes':m.CAP,'free_bytes':m.CAP-1048576},
        *[{'kind':'cuda','phase':phase,'result':2 if phase=='vmm-over-cap-never-touch' else 0,'pid':1,'time_ns':i+1}
          for i,phase in enumerate(needed[mode])],
        {'kind':'final','status':'bounded-measurement-completed','production_qualified':False}]

class Tests(unittest.TestCase):
    def test_default_never_reads_binary_spawns_child_or_observes_gpu(self):
        with patch.object(m,'run',side_effect=AssertionError), patch.object(m.subprocess,'Popen',side_effect=AssertionError), \
             patch.object(m.Path,'lstat',side_effect=AssertionError), redirect_stdout(io.StringIO()) as output:
            m.main([])
        value=json.loads(output.getvalue());self.assertEqual(value['phase'],'inert');self.assertFalse(value['gpu_calls'])
    def test_explicit_gpu_and_directory_are_required_before_any_binary_access(self):
        with patch.object(m,'run',side_effect=AssertionError):
            for argv in (['--execute'],['--execute','--gpu-uuid',m.GPU],
                         ['--execute','--gpu-uuid','GPU-wrong','--directory','/tmp/test']):
                with self.subTest(argv=argv),self.assertRaises(ValueError):m.main(argv)
    def test_all_existing_modes_are_measurements_without_cross_pod_claims(self):
        for mode in ('vmm-direct','ipc-export','ipc-import','vmm-export','vmm-import'):
            value=m.assess(receipt(mode),0,mode)
            self.assertTrue(value['successful_raw_cuda_measurement'])
            self.assertFalse(value['production_qualified']);self.assertFalse(value['cross_pod_import_isolation_qualified'])
    def test_exit_identity_cap_version_or_missing_phase_cannot_pass(self):
        for kind in ('exit','gpu','uid','driver','cap','free','final','phase','boolean-code','cuda-error'):
            events=receipt('vmm-direct');code=1 if kind=='exit' else 0
            if kind=='gpu':events[0]['gpu_uuid']='GPU-wrong'
            elif kind=='uid':events[0]['uid']=0
            elif kind=='driver':events[0]['driver_api_version']=13030
            elif kind=='cap':events[1]['total_bytes']=m.CAP*2
            elif kind=='free':events[1]['free_bytes']=m.CAP
            elif kind=='final':events[-1]['status']='inconclusive'
            elif kind=='phase':events=[e for e in events if e.get('phase')!='vmm-map']
            elif kind=='boolean-code':events[2]['result']=False
            elif kind=='cuda-error':events[2]['result']=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):m.assess(events,code,'vmm-direct')
    def test_over_allocation_success_or_recovery_before_oom_cannot_pass(self):
        for kind in ('success','recovery'):
            events=receipt('vmm-direct')
            if kind=='success':next(e for e in events if e.get('phase')=='vmm-over-cap-never-touch')['result']=0
            else:
                index=next(i for i,e in enumerate(events)if e.get('phase')=='vmm-over-cap-never-touch')
                events=events[:index+1]+[events[-1]]
            with self.subTest(kind=kind),self.assertRaises(ValueError):m.assess(events,0,'vmm-direct')
    def test_vmm_import_requires_post_export_release_retained_touch(self):
        events=receipt('vmm-import');events=[e for e in events if e.get('phase')!='fill-64']
        with self.assertRaises(ValueError):m.assess(events,0,'vmm-import')

if __name__=='__main__':unittest.main()
