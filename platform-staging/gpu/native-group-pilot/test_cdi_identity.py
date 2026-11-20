import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
OTHER = 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'


class CdiTest(unittest.TestCase):
    def setUp(self):
        self.cdi = importlib.import_module('cdi_identity')
        self.old = json.loads((HERE / 'cdi-template.json').read_text())
        self.inventory = [{'gpu_uuid':GPU,'pci_bdf':'0000:06:10.0','minor':1,'device':{'major':195,'minor':1}},
            {'gpu_uuid':OTHER,'pci_bdf':'0000:06:11.0','minor':0,'device':{'major':195,'minor':0}}]
        self.current = self.cdi.refresh_selected_cdi(self.old, self.inventory, GPU)

    def test_minor_flip_refresh_preserves_all_common_mounts_hooks_and_environment(self):
        self.assertEqual(self.current['containerEdits'], self.old['containerEdits'])
        self.assertEqual(self.old['devices'][0]['containerEdits']['deviceNodes'][0]['path'], '/dev/nvidia0')
        self.assertEqual(self.current['devices'][0]['containerEdits']['deviceNodes'],
            [{'path':'/dev/nvidia1','hostPath':'/run/nvidia/driver/dev/nvidia1'}])
        self.assertEqual(self.cdi.validate_current_cdi(self.current,self.inventory,GPU),self.inventory[0])
        with self.assertRaisesRegex(ValueError,'Stale'): self.cdi.validate_current_cdi(self.old,self.inventory,GPU)

    def test_wrong_uuid_foreign_shared_node_host_swap_or_extra_edits_fail_closed(self):
        for change in ('uuid','shared','host','major','common','device_edit','missing','duplicate','boolean'):
            document=copy.deepcopy(self.current); inventory=copy.deepcopy(self.inventory)
            if change=='uuid': document['devices'][0]['name']=OTHER
            elif change=='shared': document['devices'][0]['containerEdits']['deviceNodes'].append({'path':'/dev/nvidia0','hostPath':'/run/nvidia/driver/dev/nvidia0'})
            elif change=='host': document['devices'][0]['containerEdits']['deviceNodes'][0]['hostPath']='/dev/nvidia1'
            elif change=='major': inventory[0]['device']['major']=1
            elif change=='common': document['containerEdits']['deviceNodes'].append({'path':'/dev/nvidia0','hostPath':'/run/nvidia/driver/dev/nvidia0'})
            elif change=='device_edit': document['devices'][0]['containerEdits']['env']=['LD_PRELOAD=x']
            elif change=='missing': inventory.pop(0)
            elif change=='duplicate': inventory.append(copy.deepcopy(inventory[0]))
            elif change=='boolean': inventory[0]['minor']=True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.cdi.validate_current_cdi(document,inventory,GPU)

    def test_protected_cdi_rejects_symlink_nonroot_or_writable_even_with_valid_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cdi.json'; path.write_text(json.dumps(self.current)); path.chmod(0o444)
            link=Path(tmp)/'link';link.symlink_to(path)
            with self.assertRaises(OSError): self.cdi.read_root_file(link,trusted_uid=os.getuid())
            with self.assertRaises(ValueError): self.cdi.read_root_file(path,trusted_uid=os.getuid()+1)
            path.chmod(0o666)
            with self.assertRaises(ValueError): self.cdi.read_root_file(path,trusted_uid=os.getuid())

    def test_alternate_search_provider_config_or_file_changes_fail_closed(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); directory=root/'run/cdi';directory.mkdir(parents=True)
            selected=directory/'management.nvidia.com-native-pilot-r615.json';selected.write_text(json.dumps(self.current))
            other, runtime = {}, {}
            for name in self.cdi.OTHER_CDI_PINS:
                raw=('reviewed '+name).encode();(directory/name).write_bytes(raw)
                other[name]=hashlib.sha256(raw).hexdigest()
            for name in self.cdi.RUNTIME_PINS:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                raw=('reviewed '+name).encode();path.write_bytes(raw)
                runtime[name]=hashlib.sha256(raw).hexdigest()
            with patch.object(self.cdi,'OTHER_CDI_PINS',other),patch.object(self.cdi,'RUNTIME_PINS',runtime):
                self.cdi.validate_cdi_search(host_root=root,trusted_uid=os.getuid())
                (directory/'forged.json').write_text('{}')
                with self.assertRaisesRegex(ValueError,'provider'):self.cdi.validate_cdi_search(host_root=root,trusted_uid=os.getuid())
                (directory/'forged.json').unlink()
                etc=root/'etc/cdi';etc.mkdir(parents=True);(etc/'duplicate.yaml').write_text('{}')
                with self.assertRaisesRegex(ValueError,'provider'):self.cdi.validate_cdi_search(host_root=root,trusted_uid=os.getuid())
                (etc/'duplicate.yaml').unlink()
                (root/next(iter(runtime))).write_text('changed runtime')
                with self.assertRaisesRegex(ValueError,'resolution'):self.cdi.validate_cdi_search(host_root=root,trusted_uid=os.getuid())

    def test_current_observation_rejects_duplicate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cdi.json';path.write_text('{"kind":"x","kind":"y"}');path.chmod(0o444)
            with patch.object(self.cdi,'validate_cdi_search',return_value={}), self.assertRaisesRegex(ValueError,'Duplicate'):
                self.cdi.observe_current_cdi(GPU,cdi_path=path,trusted_uid=os.getuid())


class GateGuardTest(unittest.TestCase):
    def setUp(self): self.agent=importlib.import_module('node_agent')

    def test_cdi_guard_requires_same_healthy_epoch_and_same_actual_mapping_twice(self):
        intent=SimpleNamespace(node_uid='node',gpu_uuid=GPU)
        first={'cdi_sha256':'a'*64,'mapping':{'minor':1}}
        cdi=SimpleNamespace(observe_current_cdi=lambda _: first)
        args=(intent,Path('/state'),object(),object(),cdi,object())
        with patch.object(self.agent,'abort_current_epoch',side_effect=['epoch','epoch']):
            self.assertEqual(self.agent.validate_cdi_binding(*args),first)
        with patch.object(self.agent,'abort_current_epoch',side_effect=['epoch','new']):
            with self.assertRaisesRegex(ValueError,'changed'): self.agent.validate_cdi_binding(*args)
        cdi.observe_current_cdi=iter([first,{'cdi_sha256':'b'*64,'mapping':{'minor':0}}]).__next__
        cdi.observe_current_cdi=lambda _, reader=cdi.observe_current_cdi: reader()
        with patch.object(self.agent,'abort_current_epoch',return_value='epoch'):
            with self.assertRaisesRegex(ValueError,'changed'): self.agent.validate_cdi_binding(*args)

    def test_exact_compiled_barrier_rejects_missing_wrong_uuid_or_code(self):
        from cps_compute.native_gpu_runtime import GPU_IDENTITY_SOURCE
        barrier={'name':'cps-native-device-identity','image':'notebook@sha256:'+'a'*64,
            'command':['python','-I','-S','-c',GPU_IDENTITY_SOURCE], 'args':[GPU],
            'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':GPU},{'name':'CUDA_VISIBLE_DEVICES','value':'0'}]}
        pod={'spec':{'initContainers':[{'name':'cps-native-cap-gate'},barrier],
            'containers':[{'image':barrier['image']}]}}
        self.agent.validate_device_identity_barrier(pod,SimpleNamespace(gpu_uuid=GPU))
        for change in ('missing','uuid','source','image','env'):
            candidate=copy.deepcopy(pod); row=candidate['spec']['initContainers'][1]
            if change=='missing':candidate['spec']['initContainers'].pop(1)
            elif change=='uuid':row['args']=[OTHER]
            elif change=='source':row['command'][-1]='pass'
            elif change=='image':row['image']='other@sha256:'+'b'*64
            elif change=='env':row['env'][1]['value']='1'
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.agent.validate_device_identity_barrier(candidate,SimpleNamespace(gpu_uuid=GPU))


if __name__=='__main__': unittest.main()
