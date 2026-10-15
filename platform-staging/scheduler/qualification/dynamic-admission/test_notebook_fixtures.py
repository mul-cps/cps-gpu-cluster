"""Offline regressions using the released notebook SDK, never a policy mirror."""
import base64
import copy
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import notebook_fixtures as fixture


class NotebookFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (patch.object(socket,'create_connection',side_effect=AssertionError('No network')),
              patch.object(socket.socket,'connect',side_effect=AssertionError('No network'))):
            cls.value=fixture.generate()

    def harness(self, root):
        sdk,_=fixture.modules(fixture.compiled.DEFAULT_WHEEL)
        base=json.loads(fixture.compiled.DEFAULT_CATALOG.read_bytes())
        policy=sdk['policy'].Policy(fixture.compiled.fixture_catalog(base,fixture.compiled.NAMESPACE))
        return fixture.Harness(sdk,policy,Path(root)/'snapshots')

    def test_actual_api_notebook_runtime_and_artifact_shape(self):
        v=self.value
        self.assertEqual(set(v['fixtures']),{'batch-shared-5','batch-shared-10','batch-shared-20'})
        uids=set()
        for profile,f in v['fixtures'].items():
            w=f['compiledWorkflow'];t=w['spec']['templates'][0];g=f['profileGiB'];uids.add(w['metadata']['uid'])
            self.assertEqual(f['evidenceStage'],'actual-sdk-serialized-pre-controller')
            self.assertEqual(t['container']['command'],['python','-m','cps_compute.runner'])
            self.assertEqual(t['container']['args'],['--input','/inputs/snapshot.tar','--output','/tmp/cps-output/executed.ipynb'])
            self.assertEqual(t['container']['securityContext']['runAsUser'],10001)
            self.assertEqual(f['runtimeProjection']['containers'][0]['securityContext']['runAsUser'],1000)
            self.assertEqual(f['runtimeProjection']['securityContext']['runAsGroup'],100)
            env={x['name']:x['value'] for x in f['runtimeProjection']['containers'][0]['env']}
            self.assertEqual(env['CUDA_DEVICE_MEMORY_LIMIT_0'],str(g*1024)+'m')
            self.assertEqual(t['inputs']['artifacts'][0]['name'],'snapshot')
            self.assertEqual(t['inputs']['artifacts'][0]['s3']['endpoint'],'artifacts.fixture.invalid:443')
            self.assertFalse(t['inputs']['artifacts'][0]['s3']['insecure'])
            self.assertEqual(t['outputs']['artifacts'][0]['name'],'executed-notebook')
            self.assertTrue(t['outputs']['artifacts'][0]['optional'])
            self.assertEqual(w['spec']['ttlStrategy']['secondsAfterCompletion'],93*86400)
            self.assertNotIn('wait',str(f['workflowPodSpecProjection']))
        self.assertEqual(len(uids),3)
        self.assertFalse(v['qualification']['production'])
        self.assertFalse(v['qualification']['argoControllerMaterialization'])

    def test_snapshot_selected_files_outputs_typed_parameters_and_uid_provenance(self):
        for f in self.value['fixtures'].values():
            r=f['snapshot'];w=f['compiledWorkflow'];identifier=w['metadata']['annotations']['cps.compute/notebook-id']
            self.assertEqual(set(r['files']),{'submitted.ipynb','parameters.json','manifest.json','files/helper.py','files/data/settings.json'})
            self.assertTrue(all(x['mode']=='0o440' for x in r['files'].values()))
            original=json.loads(base64.b64decode(f['request']['notebook']))
            self.assertEqual(original['cells'][0]['outputs'][0]['text'],'saved output')
            self.assertTrue(all(c['outputs']==[] and c['execution_count'] is None for c in r['submittedNotebook']['cells']))
            self.assertEqual(r['parameters'],f['request']['parameters'])
            self.assertIs(r['parameters']['enabled'],True)
            self.assertIsNone(r['parameters']['items'][1])
            self.assertEqual(r['archive']['metadata']['cps-workflow-uid'],w['metadata']['uid'])
            self.assertEqual(r['binding']['uid'],w['metadata']['uid'])
            self.assertEqual(r['binding']['notebook_id'],identifier)
            self.assertEqual(r['intent']['snapshot_hash'],r['archive']['sha256'])
            self.assertEqual(r['archive']['tags'],{'active':'true','retained':'false','retention':'temporary-expirable'})
            self.assertEqual({m['name']:m['sha256'] for m in r['archive']['members']},{k:x['sha256'] for k,x in r['files'].items()})
            self.assertTrue(f['idempotentRetryPreservedSnapshot'])

    def test_real_sdk_rejects_missing_parameter_tag_and_non_json_values(self):
        async def check():
            with tempfile.TemporaryDirectory(dir='/tmp') as root:
                h=self.harness(root)
                body=fixture.request(5);n=json.loads(base64.b64decode(body['notebook']))
                n['cells'][0]['metadata']['tags']=[]
                body['notebook']=base64.b64encode(json.dumps(n).encode()).decode()
                with self.assertRaisesRegex(ValueError,'Tagged parameter cell'):await h.submit(body,'missing-tag')
                for bad in ([1],{'not_json':object()},{'nan':float('nan')}):
                    body=fixture.request(5);body['parameters']=bad
                    with self.subTest(parameters=str(bad)),self.assertRaises((ValueError,TypeError)):
                        await h.submit(body,'bad-parameters')
                self.assertFalse(h.s3.objects);self.assertFalse(h.http.workflows)
        fixture.offline_run(check())

    def test_real_sdk_rejects_unsafe_selected_files_bad_base64_and_walltime(self):
        async def check():
            with tempfile.TemporaryDirectory(dir='/tmp') as root:
                h=self.harness(root)
                for name in ('../escape.py','/absolute.py','source.ipynb',''):
                    b=fixture.request(5);b['files']={name:base64.b64encode(b'bad').decode()}
                    with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Unsafe selected path'):
                        await h.submit(b,'unsafe-files')
                b=fixture.request(5);b['notebook']='invalid!'
                with self.assertRaises(ValueError):await h.submit(b,'bad-base64')
                for walltime in (True,0,3601,'180'):
                    b=fixture.request(5);b['walltime']=walltime
                    with self.subTest(walltime=walltime),self.assertRaisesRegex(ValueError,'Walltime'):
                        await h.submit(b,'bad-walltime')
                self.assertFalse(h.s3.objects);self.assertFalse(h.http.workflows)
        fixture.offline_run(check())

    def test_real_sdk_50_mib_guard_runs_before_decode_or_upload(self):
        async def check():
            with tempfile.TemporaryDirectory(dir='/tmp') as root:
                h=self.harness(root);b=fixture.request(5)
                b['files']={'large.bin':'A'*(4*((h.sdk['notebooks'].MAX_BYTES+2)//3)+1)}
                with self.assertRaisesRegex(ValueError,'Snapshot exceeds 50 MiB'):await h.submit(b,'oversized')
                self.assertFalse(h.s3.objects);self.assertFalse(h.http.workflows)
                self.assertFalse(h.root.exists())
        fixture.offline_run(check())

    def test_actual_snapshot_50_mib_selected_file_limit_uses_real_stat(self):
        sdk,_=fixture.modules(fixture.compiled.DEFAULT_WHEEL)
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            source=Path(root)/'source.ipynb';source.write_bytes(base64.b64decode(fixture.request(5)['notebook']))
            large=Path(root)/'large.bin'
            with large.open('wb') as output:output.truncate(sdk['notebooks'].MAX_BYTES-source.stat().st_size+1)
            target=Path(root)/'published'
            with self.assertRaisesRegex(ValueError,'Snapshot exceeds 50 MiB'):
                sdk['notebooks'].snapshot(source,target,parameters={},files=['large.bin'])
            self.assertFalse(target.exists())

    def test_real_sdk_retry_refuses_changed_request_missing_snapshot_or_replaced_uid(self):
        async def check():
            with tempfile.TemporaryDirectory(dir='/tmp') as root:
                h=self.harness(root);body=fixture.request(5);w=await h.submit(body,'retry')
                altered=copy.deepcopy(body);altered['files']['helper.py']=base64.b64encode(b'value = 9').decode()
                with self.assertRaisesRegex(ValueError,'Idempotency key reused'):await h.submit(altered,'retry')
                h.http.workflows[w['metadata']['name']]['metadata']['uid']='00000000-0000-0000-0000-000000000000'
                with self.assertRaisesRegex(ValueError,'First workflow UID binding changed'):await h.submit(body,'retry')
                h.http.workflows[w['metadata']['name']]=copy.deepcopy(w)
                identifier=w['metadata']['annotations']['cps.compute/notebook-id']
                del h.s3.objects[(fixture.BUCKET,'notebook-inputs/'+identifier+'/snapshot.tar')]
                with self.assertRaisesRegex(ValueError,'snapshot is missing'):await h.submit(body,'retry')
        fixture.offline_run(check())

    def test_proposed_executor_patch_is_detached_closed_and_source_bound(self):
        p=self.value['proposedExecutorPatch'];patch_=p['patch']
        self.assertFalse(p['embeddedInCompiledWorkflows']);self.assertFalse(p['qualified']);self.assertFalse(p['actualControllerExecuted'])
        self.assertEqual(patch_['volumes'],[{'name':'tmp-dir-argo','emptyDir':{}}])
        for c in [*patch_['containers'],*patch_['initContainers']]:
            s=c['securityContext'];self.assertEqual(s['runAsUser'],10001);self.assertEqual(s['runAsGroup'],10001)
            self.assertTrue(s['readOnlyRootFilesystem']);self.assertEqual(s['seccompProfile'],{'type':'RuntimeDefault'})
        self.assertEqual(patch_['initContainers'][0]['volumeMounts'],[{'name':'tmp-dir-argo','mountPath':'/tmp','subPath':'init'}])
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            altered=Path(root)/'controller.go';altered.write_bytes(fixture.CONTROLLER_SOURCE.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'controller source required'):fixture.proposed_executor_patch(altered)

    def test_regeneration_rejects_forged_shape_and_self_hashes(self):
        self.assertTrue(fixture.verify(self.value))
        changes=[lambda v:v['fixtures']['batch-shared-5']['compiledWorkflow']['spec']['templates'][0]['inputs']['artifacts'][0]['s3'].update(insecure=True),
                 lambda v:v['fixtures']['batch-shared-10']['compiledWorkflow']['spec']['templates'][0]['container']['securityContext'].update(runAsUser=0),
                 lambda v:v['fixtures']['batch-shared-20']['runtimeProjection']['containers'][0]['env'][0].update(value='/forged'),
                 lambda v:v['proposedExecutorPatch'].update(qualified=True),
                 lambda v:v['fixtures']['batch-shared-5']['snapshot']['binding'].update(uid='forged')]
        for change in changes:
            bad=copy.deepcopy(self.value);change(bad);bad.pop('manifestSha256');bad['manifestSha256']=fixture.compiled.digest(bad)
            with self.subTest(change=str(change)),self.assertRaisesRegex(ValueError,'pinned SDK regeneration'):fixture.verify(bad)
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            wheel=Path(root)/'tampered.whl';wheel.write_bytes(fixture.compiled.DEFAULT_WHEEL.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'wheel SHA256 required'):fixture.generate(wheel=wheel)


if __name__ == '__main__':unittest.main()
