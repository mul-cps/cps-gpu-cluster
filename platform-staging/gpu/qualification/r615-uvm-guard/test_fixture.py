import hashlib
import json
import unittest
import render_fixture


class FixtureTests(unittest.TestCase):
    def test_bytes_are_immutable_and_exact_source_owned(self):
        objects=render_fixture.render()['items'];cm=next(item for item in objects if item['kind']=='ConfigMap')
        digest=hashlib.sha256(json.dumps(cm['data'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertTrue(cm['immutable']);self.assertEqual(cm['metadata']['annotations']['source.data.sha256'],digest)
        self.assertEqual(cm['metadata']['name'],'r615-uvm-guard-'+digest[:12])
        self.assertEqual(set(cm['data']),{'runtime_probe.py','cuda_probe.py','pod_cap.py','gate_wait.py'})

    def test_manual_root_gate_and_ordinary_main_are_preserved(self):
        pods=[item for item in render_fixture.render()['items'] if item['kind']=='Pod']
        self.assertEqual({pod['metadata']['name'] for pod in pods},{'uvm-guard-main','uvm-guard-peer'})
        for pod in pods:
            spec=pod['spec'];gate=spec['initContainers'][0];main=spec['containers'][0]
            self.assertEqual(spec['nodeName'],'k3s-wk-gpu2');self.assertFalse(spec['automountServiceAccountToken'])
            self.assertNotIn('imagePullSecrets',spec)
            self.assertEqual(gate['imagePullPolicy'],'Never');self.assertEqual(main['imagePullPolicy'],'Never')
            self.assertEqual({v['hostPath']['path'] for v in spec['volumes'] if 'hostPath' in v},
                             {'/sys/fs/cgroup','/sys/module/nvidia_uvm/parameters'})
            self.assertEqual(gate['name'],'cps-driver-cap-gate');self.assertIn('512',gate['command'])
            self.assertEqual(main['securityContext']['runAsUser'],1000);self.assertEqual(main['securityContext']['runAsGroup'],100)
            self.assertEqual(main['securityContext']['capabilities']['drop'],['ALL'])
            self.assertNotIn('privileged',main['securityContext']);self.assertTrue(main['securityContext']['readOnlyRootFilesystem'])
            self.assertTrue(all(mount['readOnly'] for mount in main['volumeMounts'] if mount['name'] in ('cgroup','driver','uvm-parameters')))
            self.assertIn("v.get('pod_uid')==os.environ['POD_UID']",main['command'][-1])
            self.assertFalse(any(env['name']=='LD_LIBRARY_PATH' for env in main['env']))
            if pod['metadata']['name']=='uvm-guard-main':
                self.assertEqual(main['image'],render_fixture.TORCH_IMAGE);self.assertEqual(main['imagePullPolicy'],'Never')


if __name__=='__main__':unittest.main()
