"""Filesystem/protocol tests of the Root-only observer; no hardware/API calls."""
import base64
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import test_approval_before_gate as fixtures

HERE=Path(__file__).parent


class FenceTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('approval_abort_fence'),
            'Source-owned live Root fence runner is missing')
        self.mod=__import__('approval_abort_fence')
    def test_existing_real_lock_is_held_and_busy_or_replaced_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.writer.lock';path.write_bytes(b'');path.chmod(0o600)
            fd=self.mod.acquire_lock(path,uid=os.getuid())
            try:
                with self.assertRaises((ValueError,BlockingIOError)):self.mod.acquire_lock(path,uid=os.getuid())
                self.mod.verify_lock(path,fd,uid=os.getuid())
                path.unlink();path.write_bytes(b'');path.chmod(0o600)
                with self.assertRaises(ValueError):self.mod.verify_lock(path,fd,uid=os.getuid())
            finally:os.close(fd)
    def test_actual_private_raw_journals_are_complete_and_target_or_changed_mode_denied(self):
        _,_,_,_,e=fixtures.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700);item=e['retired_journals'][0]
            path=root/(item['pod_uid']+'.json');path.write_bytes(base64.b64decode(item['raw_base64']));path.chmod(0o600)
            self.assertEqual(self.mod.capture_journals(root,fixtures.TARGET,uid=os.getuid()),e['retired_journals'])
            path.chmod(0o644)
            with self.assertRaises(ValueError):self.mod.capture_journals(root,fixtures.TARGET,uid=os.getuid())
            path.chmod(0o600);target=root/(fixtures.TARGET+'.json');target.write_text('{}');target.chmod(0o600)
            with self.assertRaises(ValueError):self.mod.capture_journals(root,fixtures.TARGET,uid=os.getuid())
    def test_complete_cgroup_walk_detects_target_tasks_and_denies_symlinks_or_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/('kubepods-pod'+fixtures.TARGET.replace('-','_')+'.slice')
            target.mkdir();(target/'cgroup.procs').write_text('')
            self.assertEqual(self.mod.target_tasks(root,fixtures.TARGET),0)
            (target/'cgroup.procs').write_text('123\n')
            self.assertEqual(self.mod.target_tasks(root,fixtures.TARGET),1)
            with self.assertRaises(ValueError):self.mod.target_tasks(root,fixtures.TARGET,limit=1)
            (root/'foreign').symlink_to(target,target_is_directory=True)
            with self.assertRaises(ValueError):self.mod.target_tasks(root,fixtures.TARGET)
    def test_cleaned_history_requires_actual_original_completion_without_writing_state(self):
        f,_,_,_,e=fixtures.fixture();original=f.fixture
        original.config['authority_namespace']=fixtures.old.NAMESPACE
        original.cm['metadata']['namespace']=fixtures.old.NAMESPACE
        _,record=original.agent_cleanup_fixture('cleaned',False,False,'unlimited')
        envelope=original.check();uid=record.intent.pod_uid
        cleanup=original.agent.cleanup_object(envelope,record)
        cleanup['metadata'].update(uid='66666666-6666-4666-8666-666666666666')
        tombstone=dict(enrollment_uid=envelope['configmap_uid'],receipt_uid=cleanup['metadata']['uid'],
            receipt=json.loads(cleanup['data']['receipt.json']))
        raw=(fixtures.old.canonical(record.to_dict())+'\n').encode()
        journals=[dict(pod_uid=uid,raw_base64=base64.b64encode(raw).decode(),
            raw_sha256='sha256:'+fixtures.hashlib.sha256(raw).hexdigest())]
        state=Path('/protected-existing');files={
            str(state/'enrollments'/(uid+'.json')):envelope,
            str(state/'intents'/(uid+'.json')):record.intent.to_dict(),
            str(state/'published-cleanup'/(uid+'.json')):tombstone}
        maps={original.cm['metadata']['name']:original.cm,cleanup['metadata']['name']:cleanup}
        def read(path,trusted_uid):return copy.deepcopy(files.get(str(path)))
        backend=SimpleNamespace(private_read=read)
        kube=SimpleNamespace(configmap=lambda ns,name:copy.deepcopy(maps.get(name)))
        self.assertTrue(self.mod.verify_cleaned_history(original.agent,kube,backend,state,f.models,journals))
        for fault in ('missing_enrollment','replaced_enrollment','intent','receipt','receipt_uid','tombstone'):
            before_files=copy.deepcopy(files);before_maps=copy.deepcopy(maps)
            if fault=='missing_enrollment':maps.pop(original.cm['metadata']['name'])
            elif fault=='replaced_enrollment':maps[original.cm['metadata']['name']]['metadata']['uid']=fixtures.TARGET
            elif fault=='intent':files[str(state/'intents'/(uid+'.json'))]['cap_mib']=10240
            elif fault=='receipt':maps.pop(cleanup['metadata']['name'])
            elif fault=='receipt_uid':maps[cleanup['metadata']['name']]['metadata']['uid']=fixtures.TARGET
            else:files[str(state/'published-cleanup'/(uid+'.json'))]=None
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                self.mod.verify_cleaned_history(original.agent,kube,backend,state,f.models,journals)
            files.clear();files.update(before_files);maps.clear();maps.update(before_maps)

    def test_request_has_exact_reviewed_actual_identity_and_no_unknown_fields(self):
        _,body,cm,_,e=fixtures.fixture()
        request=dict(version=1,qualification_only=True,binding_id=body['binding_id'],attempt=body['attempt'],
            enrollment_uid=cm['metadata']['uid'],approval_ref=e['approval_ref'])
        self.mod.validate_request(request)
        for key,value in (('qualification_only',False),('enrollment_uid','not-an-actual-uid'),('override',True)):
            changed=dict(request);changed[key]=value
            with self.assertRaises(ValueError):self.mod.validate_request(changed)
    def test_query_uses_actual_container_binary_and_original_environment(self):
        observer=object.__new__(self.mod.HostProbe);seen=[]
        def run(command,**kwargs):
            seen.append((command,kwargs));return SimpleNamespace(stdout='0\n')
        with patch.object(self.mod.subprocess,'run',run):
            self.assertEqual(observer.query(['--query-gpu=memory.used']),'0')
        command,kwargs=seen[0]
        self.assertEqual(command,['/usr/local/bin/nvidia-smi','--query-gpu=memory.used'])
        self.assertEqual(kwargs['env'],dict(os.environ))
    def test_default_cli_is_inert_and_does_not_open_requested_inputs(self):
        result=subprocess.run([os.sys.executable,str(HERE/'approval_abort_fence.py'),'--request','/does/not/exist'],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['state'],'inert')
        self.assertFalse(value['api_calls']);self.assertFalse(value['device_calls'])


if __name__=='__main__':unittest.main()
