"""CPU-only application/ASGI fixtures; synthetic qualification is not evidence."""
import asyncio
import copy
import io
import json
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import source_qualification_handover as h

import cps_compute
SDK = Path(cps_compute.__file__).resolve().parents[2]
sys.path.insert(0, str(SDK / 'tests'))
from test_native_groups import fixture as group_fixture
from e2x_course_hub.cps.compute import ComputePolicyClient
from e2x_course_hub.cps.providers import LocalCourseProvider
from e2x_course_hub.cps.workspaces import WorkspaceService, HubWorkspaceAdapter
from cps_compute.internal import ControlStore, ServiceIdentity, install_internal
from cps_compute.native_gpu_control import KubernetesNativeAuthorityBackend, LEDGER_NAME, LABEL
from cps_compute.native_qualification import NativeGroupQualification
from cps_compute.reservations import Reservations
from fastapi import FastAPI
import httpx


def uid():
    return str(uuid.uuid4())


class NotFound(Exception):
    status = 404


class Core:
    def __init__(self):
        self.maps = {}; self.live_pod = None; self.gets = 0
    def read_namespaced_config_map(self, name, namespace, **kwargs):
        self.gets += 1
        if name not in self.maps: raise NotFound()
        return copy.deepcopy(self.maps[name])
    def read_namespaced_pod(self, name, namespace, **kwargs):
        if self.live_pod is None: raise NotFound()
        return copy.deepcopy(self.live_pod)


class Fixture:
    async def setup(self, directory, source='cps', *, fresh_profile=None):
        self.policy, config = group_fixture()
        self.source = source; self.workspace = ('operator-qualification-531-test-'+str(fresh_profile) if fresh_profile else ('native-group-b' if source == 'cps' else 'native-group-a')); self.members = [
            '00000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002']
        approval = config['workspaces'].pop('cps:group-a')
        approval.update(owner=source+'nativegroup'+self.workspace[-1], group_id='native-pilot-group-'+self.workspace[-1],
            pod='jupyter-'+source+'nativegroup'+self.workspace[-1]+'--rtc', members=self.members,
            namespace='jupyterhub' if source=='cps' else 'cit-jhub', principal='workspace:'+source+':'+self.workspace)
        if fresh_profile:
            approval.update(owner='cps-ws-'+'a'*32,pod='jupyter-cps-ws-'+'a'*32+'--rtc')
        approval['storage']['namespace']=approval['namespace']
        name=h.PROFILES[source] if fresh_profile is None else 'interactive-native-qualification-'+str(fresh_profile);size=fresh_profile or (5 if source=='cps' else 10)
        catalog=copy.deepcopy(self.policy.catalog)
        profile=copy.deepcopy(catalog['profiles']['interactive-shared-5'])
        profile['enabled']=False;profile['gpu']['nominalMemoryGiB']=size
        profile['gpu']['qualification']={'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'}
        catalog['profiles'][name]=profile
        from cps_compute.policy import Policy
        self.policy=Policy(catalog)
        approval['profiles']=[name];approval['ceiling']['gpuMemoryGiB']=size
        pool=copy.deepcopy(config['node_pool']);pool.update(total_memory_mib=40960,free_memory_mib=40470,headroom_mib=1024,memory_budget_mib=25600 if fresh_profile else 15360,boot_id='209f8bc9-a478-48e4-925a-6e07ffa56f7a',driver_generation='b10498fc-9153-4394-875a-ea7cfb498625')
        config={'enabled':True,'version':1,'operator_only':True,'policy_hash':self.policy.hash,'policy_version':self.policy.version,
            'node_pool':pool,'authorityNamespace':'cps-native-system','gateImage':config['gateImage'],'workloadImage':config['workloadImage'],
            'profile_caps':{name:size*1024},'capacity_observation_sha256':'sha256:'+'d'*64,
            'workspaces':{source+':'+self.workspace:approval}}
        self.groups=NativeGroupQualification.from_config(config,self.policy)
        if fresh_profile:
            mode=json.loads(self.groups.document);mode['node_pool'].update(memory_budget_mib=25600,max_workspaces=2)
            image='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4'
            mode['workloadImage']=image;catalog['profiles'][name]['images']=[image]
            peer=copy.deepcopy(approval);peer_scope='cps:operator-qualification-531-peer-'+str(20 if size==5 else 5)
            peer.update(owner='cps-ws-'+'b'*32,pod='jupyter-cps-ws-'+'b'*32+'--rtc',principal='workspace:'+peer_scope,members=['00000000-0000-4000-8000-000000000003'],profiles=['interactive-native-qualification-'+str(20 if size==5 else 5)])
            peer['storage']['pvc']='peer-pvc';peer['storage']['pv']='peer-pv';peer['storage']['path']='/mnt/peer'
            peer['ceiling']['gpuMemoryGiB']=20 if size==5 else 5
            mode['profile_caps'][peer['profiles'][0]]=(20 if size==5 else 5)*1024
            mode['workspaces'][peer_scope]=peer
            peer_profile=copy.deepcopy(profile);peer_profile['gpu']['nominalMemoryGiB']=20 if size==5 else 5;peer_profile['images']=[image]
            catalog['profiles'][peer['profiles'][0]]=peer_profile
            self.policy=Policy(catalog);mode['policy_hash']=self.policy.hash
            self.groups=NativeGroupQualification.from_config(mode,self.policy)
        old_profile='interactive-cpu' if fresh_profile else h.OLD_PROFILE
        original_ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':0 if fresh_profile else 5}
        self.provider = LocalCourseProvider(directory / 'console.sqlite',self.source)
        self.calls = []
        await self.provider.put('courses',{'id':'course','resource_ceiling':original_ceiling,
            'workspace_bindings':[{'group_id':approval['group_id'],'hub_user':approval['owner'],
                'hub_server':'rtc','namespace':approval['namespace'],'pod':approval['pod']}]},actor='admin')
        await self.provider.put('terms',{'id':'term','course_id':'course'},actor='admin')
        await self.provider.put('groups',{'id':approval['group_id'],'course_id':'course','term_id':'term'},actor='admin')
        for index, member in enumerate(self.members):
            await self.provider.link_identities([{'hub':self.source,'username':'member'+str(index),
                'email':'member'+str(index)+'@example.edu','person_id':member,
                'administrator_reviewed':True,'verified':True}],actor='admin')
            await self.provider.put('memberships',{'id':'m'+str(index),'course_id':'course','term_id':'term',
                'group_id':approval['group_id'],'person_id':'member'+str(index),'canonical_person_id':member},actor='admin')
        local = {'id':self.workspace,'course_id':'course','term_id':'term','group_id':approval['group_id'],
            'hub_user':approval['owner'],'hub_server':'rtc','profile':old_profile,'state':'stopped',
            'course_ceiling':original_ceiling,'namespace':approval['namespace'],'pod':approval['pod'],
            'notice':'Files retained; revalidation required.'}
        self.local = await self.provider.put('workspaces',local,actor='admin')
        self.store = ControlStore(directory / 'central.sqlite')
        self.reservations = Reservations(directory / 'reservations.sqlite')
        old = {'workspace':self.workspace,'policy_hash':'sha256:'+'e'*64,**copy.deepcopy(approval),
            'profiles':[old_profile],'workspace_label':self.policy.labels['workspace'],
            'workspace_hash':self.policy.owner_label(self.source+':'+self.workspace)}
        old['ceiling']=copy.deepcopy(original_ceiling)
        old['storage'].update(state='active', proof_of_preservation={'sentinel':'unchanged'})
        self.store.put_workspace(old,ServiceIdentity(self.source,self.source),self.reservations)
        self.old = self.store.workspace(self.source,self.workspace)
        self.app = FastAPI()
        async def auth(token):
            if token != 'private-fixture': raise ValueError('Untrusted CPU token')
            return ServiceIdentity(self.source,self.source)
        async def stopped(source,workspace): return source == self.source and workspace == self.workspace
        async def neutral(source,body):
            self.calls.append('owner-check')
            return source == self.source and body['owner'] == approval['owner']
        install_internal(self.app,self.store,self.reservations,auth,stopped,self.policy,
            canonical_people={self.source:{'member0':self.members[0],'member1':self.members[1]}},
            workspace_owner_check=neutral,native_pilot_workspaces={source+':'+self.workspace:{'profile':name}})
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://fixture.invalid')
        self.compute = ComputePolicyClient('https://fixture.invalid','private-fixture',self.source)
        async def request(path,method='GET',payload=None):
            self.calls.append(method+' '+path)
            response = await self.http.request(method,'/internal/v1/'+path,json=payload,
                headers={'Authorization':'Bearer private-fixture'})
            response.raise_for_status()
            return response.json() if response.content else None
        self.compute._request = request
        self.admin = True; self.server = None
        fixture = self
        class Hub:
            api_url = 'https://hub.invalid'
            async def get_user(self,name):
                if name == 'admin': return {'name':name,'admin':fixture.admin,'servers':{}}
                return {'name':name,'admin':False,'servers':{} if fixture.server is None else {'rtc':fixture.server}}
        self.service = WorkspaceService(self.provider,self.compute,HubWorkspaceAdapter(Hub()))
        self.core = Core(); self.backend = KubernetesNativeAuthorityBackend(self.core,'cps-native-system')
        binding = 'a'*60; self.attempt = uid()
        intent = {'namespace':approval['namespace'],'name':approval['pod'],'pod_uid':uid(),
            'node':self.groups.node_pool['node'],'node_uid':self.groups.node_pool['node_uid'],
            'gpu_uuid':self.groups.node_pool['gpu_uuid'],'cap_mib':5120,'spec_sha256':'b'*64,
            'policy_hash':'sha256:'+'e'*64}
        enrollment = {'version':1,'binding_id':binding,'source':self.source,'actor':self.source,'workspace':self.workspace,
            'principal':approval['principal'],'members':self.members,'attempt':self.attempt,'profile':h.OLD_PROFILE,
            'policy_hash':intent['policy_hash'],'namespace':intent['namespace'],'name':intent['name'],
            'node':intent['node'],'node_uid':intent['node_uid'],'gpu_uuid':intent['gpu_uuid'],'cap_mib':5120,'intent':intent}
        cleanup = {'version':1,'binding_id':binding,'attempt':self.attempt,'intent':intent,'cleanup_confirmed':True}
        def cm(name,payload,key,immutable=False):
            return {'apiVersion':'v1','kind':'ConfigMap','immutable':immutable,
                'metadata':{'name':name,'namespace':'cps-native-system','uid':uid(),'resourceVersion':'7',
                    **({'labels':{LABEL:binding}} if immutable else {})},'data':{key:h.canonical(payload)}}
        self.enrollment_name = 'cps-native-enrollment-'+binding[:40]
        self.cleanup_name = 'cps-native-cleanup-'+binding[:40]
        self.core.maps[self.enrollment_name] = cm(self.enrollment_name,enrollment,'enrollment.json',True)
        self.core.maps[self.cleanup_name] = cm(self.cleanup_name,cleanup,'receipt.json',True)
        self.ledger = {'version':1,'allocations':{binding:{**enrollment,'state':'released'}}}
        self.core.maps[LEDGER_NAME] = cm(LEDGER_NAME,self.ledger,'state.json')
        self.review = {'version':1,'source':self.source,'workspace':self.workspace,'actor':'admin','new_profile':name,
            'original_local':copy.deepcopy(self.local),'original_registration':copy.deepcopy(self.old),'members':self.members,
            'policy_hash':self.policy.hash,'qualification_config_sha256':h.digest(json.loads(self.groups.document)),
            'freeze_id':uid(),'stopped':{'binding_id':binding,'attempt':self.attempt,'intent':intent,
                'ledger_uid':self.core.maps[LEDGER_NAME]['metadata']['uid'],
                'enrollment_uid':self.core.maps[self.enrollment_name]['metadata']['uid'],'enrollment_sha256':h.digest(enrollment),
                'cleanup_uid':self.core.maps[self.cleanup_name]['metadata']['uid'],'cleanup_sha256':h.digest(cleanup)}}
        if fresh_profile:
            self.ledger={'version':1,'allocations':{}};self.set_ledger(self.ledger)
            self.core.maps.pop(self.enrollment_name);self.core.maps.pop(self.cleanup_name)
            self.review['stopped']={'kind':'never-enrolled','ledger_uid':self.core.maps[LEDGER_NAME]['metadata']['uid'],'attempt':None}
        self.review['original_course']=copy.deepcopy((await self.provider.courses())[0])
        self.review['target_ceiling']=copy.deepcopy(approval['ceiling'])
        self.freeze_calls = 0; self.fail_freeze_at = None
        async def freeze():
            self.freeze_calls += 1
            return {'version':1,'freeze_id':self.review['freeze_id'],
                'active':self.freeze_calls != self.fail_freeze_at,'sources':['cit','cps'],'writer_pods':[],
                'external_starts_excluded':True,'observed_at':datetime.now(timezone.utc).isoformat()}
        async def read_registration(source,workspace):
            self.calls.append('application-read '+source+':'+workspace)
            return self.store.workspace(source,workspace)
        self.context = {'service':self.service,'policy':self.policy,'operator_qualification':self.groups,
            'authority_backend':self.backend,'verify_external_freeze':freeze,'read_registration':read_registration}
        for member in self.members:
            self.store.put({'id':member,'person':member,'profiles':[name],'projects':['course'],
                'allowance':1,'expires':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},ServiceIdentity(self.source,self.source))
        return self
    async def close(self):
        await self.http.aclose(); self.provider.db.close()
    def set_ledger(self, ledger):
        self.core.maps[LEDGER_NAME]['data']['state.json'] = h.canonical(ledger)


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = await Fixture().setup(Path(self.tmp.name))
    async def asyncTearDown(self):
        await self.f.close(); self.tmp.cleanup()
    async def blocked(self):
        with self.assertRaises((ValueError,h.HandoverIncomplete)): await h.migrate(self.f.context,self.f.review)
        self.assertEqual((await self.f.service.get(self.f.workspace))['state'],'stopped')
    async def test_actual_application_and_http_handover_preserves_all_storage_and_audits(self):
        f = self.f; result = await h.migrate(f.context,f.review)
        self.assertEqual(result['state'],'handover-complete-stopped')
        self.assertFalse(result['freeze_release_performed']); self.assertFalse(result['start_performed'])
        saved = await f.service.get(f.workspace)
        self.assertEqual(saved,{**f.local,'profile':h.PROFILE})
        central = f.store.workspace('cps',f.workspace)
        self.assertEqual(central['storage'],f.old['storage'])
        self.assertEqual(central['profiles'],[h.PROFILE]); self.assertGreaterEqual(f.freeze_calls,5)
        self.assertIn('PUT workspaces',f.calls); self.assertIn('POST workspace-policy/preview',f.calls)
        self.assertIn('POST workspace-policy',f.calls); self.assertIn('owner-check',f.calls)
        audit = f.provider.audit()[-1]
        self.assertEqual(json.loads(audit['previous']),f.local)
        self.assertEqual(json.loads(audit['current']),saved)
        self.assertEqual(f.store.audit()[-1]['previous']['profiles'],[h.OLD_PROFILE])
    async def test_active_reservation_missing_grant_and_unresolved_hub_writer_block(self):
        f = self.f
        for case in ('generic','native','grant','hub'):
            with self.subTest(case=case):
                if case == 'generic':
                    f.reservations.acquire('cps:'+f.workspace,f.members,attempt=f.attempt)
                elif case == 'native':
                    ledger = copy.deepcopy(f.ledger); ledger['allocations']['a'*60]['state'] = 'enrolled'; f.set_ledger(ledger)
                elif case == 'grant':
                    f.store.put({'id':f.members[0],'person':f.members[0],'profiles':[],'projects':['course'],
                        'allowance':1,'expires':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},ServiceIdentity('cps','cps'))
                else: f.server = {'ready':True}
                await self.blocked()
                self.assertEqual(f.store.workspace('cps',f.workspace),f.old)
                if case == 'generic':
                    f.reservations.release('cps:'+f.workspace,shutdown_confirmed=True,attempt=f.attempt)
                elif case == 'native': f.set_ledger(f.ledger)
                elif case == 'grant':
                    f.store.put({'id':f.members[0],'person':f.members[0],'profiles':[h.PROFILE],'projects':['course'],
                        'allowance':1,'expires':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},ServiceIdentity('cps','cps'))
                else: f.server = None
    async def test_wrong_profile_approval_source_members_and_storage_block(self):
        f = self.f
        for case in ('profile','config','source','members','storage','administrator'):
            with self.subTest(case=case):
                old_review = copy.deepcopy(f.review); old_document = copy.deepcopy(f.old)
                if case == 'profile': f.review['new_profile'] = 'interactive-shared-20'
                elif case == 'config': f.review['qualification_config_sha256'] = 'sha256:'+'0'*64
                elif case == 'source': f.review['source'] = 'cit'
                elif case == 'members': f.review['members'] = f.members[:1]
                elif case == 'storage':
                    # The genuine normal store preserves storage. A fresh
                    # observer reporting changed storage must still block.
                    old_reader = f.context['read_registration']
                    async def reader(source,workspace):
                        value = await old_reader(source,workspace)
                        value['storage']['path'] = '/different'
                        return value
                    f.context['read_registration'] = reader
                else: f.admin = False
                await self.blocked()
                f.review = old_review
                if case == 'storage': f.context['read_registration'] = old_reader
                f.admin = True
    async def test_immutable_cleanup_ledger_and_pod_negatives_are_actual_gets(self):
        f = self.f
        cases = ('cleanup-uid','cleanup-attempt','mutable','enrollment-uid','enrollment-hash','ledger-uid',
            'foreign-attempt','competing','replacement-pod','missing-ledger','api-denied')
        for case in cases:
            with self.subTest(case=case):
                original_maps = copy.deepcopy(f.core.maps); original_pod = f.core.live_pod
                if case == 'cleanup-uid': f.core.maps[f.cleanup_name]['metadata']['uid'] = uid()
                elif case == 'cleanup-attempt':
                    receipt = json.loads(f.core.maps[f.cleanup_name]['data']['receipt.json']); receipt['attempt'] = uid()
                    f.core.maps[f.cleanup_name]['data']['receipt.json'] = h.canonical(receipt)
                elif case == 'mutable': f.core.maps[f.cleanup_name]['immutable'] = False
                elif case == 'enrollment-uid': f.core.maps[f.enrollment_name]['metadata']['uid'] = uid()
                elif case == 'enrollment-hash':
                    row = json.loads(f.core.maps[f.enrollment_name]['data']['enrollment.json']); row['actor'] = 'other'
                    f.core.maps[f.enrollment_name]['data']['enrollment.json'] = h.canonical(row)
                elif case == 'ledger-uid': f.core.maps[LEDGER_NAME]['metadata']['uid'] = uid()
                elif case == 'foreign-attempt':
                    ledger = copy.deepcopy(f.ledger); ledger['allocations']['a'*60]['attempt'] = uid(); f.set_ledger(ledger)
                elif case == 'competing':
                    ledger = copy.deepcopy(f.ledger); ledger['allocations']['b'*60] = {**ledger['allocations']['a'*60],'state':'enrolled'}; f.set_ledger(ledger)
                elif case == 'replacement-pod': f.core.live_pod = {'metadata':{'uid':uid()}}
                elif case == 'missing-ledger': del f.core.maps[LEDGER_NAME]
                else:
                    old_method = f.core.read_namespaced_config_map
                    def denied(*args,**kwargs): raise PermissionError('API unavailable')
                    f.core.read_namespaced_config_map = denied
                await self.blocked()
                self.assertEqual(f.store.workspace('cps',f.workspace),f.old)
                f.core.maps = original_maps; f.core.live_pod = original_pod
                if case == 'api-denied': f.core.read_namespaced_config_map = old_method
    def retirement(self):
        from cps_compute.native_gpu_controller import CapIdentity, RetiredCapEntry, RetiredInertCap
        f = self.f; intent = f.review['stopped']['intent']; parent = '/kubepods.slice/kubepods-pod'+intent['pod_uid'].replace('-','_')+'.slice'
        identity = CapIdentity(pod_uid=intent['pod_uid'],spec_sha256=intent['spec_sha256'],node_uid=intent['node_uid'],
            gpu_uuid=intent['gpu_uuid'],container_id='c'*64,host_pid=12000,pid_start_ticks=12345,boot_id=uid(),
            cgroup_relative=parent,cgroup_path='/sys/fs/cgroup'+parent,cgroup_device=27,cgroup_inode=1357569,driver_generation=uid())
        cap = 5120*1048576
        proof = RetiredInertCap(identity,identity.epoch,0,'sha256:'+'d'*64,
            RetiredCapEntry(1357569,1357569,1357569,True,True,True,cap,cap,0))
        return {'proof':proof.to_dict(),'enrollment_uid':f.review['stopped']['enrollment_uid'],
            'enrollment_sha256':f.review['stopped']['enrollment_sha256'],'journal_sha256':'sha256:'+'f'*64}
    async def test_typed_retired_inert_cleanup_preserves_provenance_without_claiming_unlimited(self):
        f = self.f; receipt = json.loads(f.core.maps[f.cleanup_name]['data']['receipt.json'])
        receipt['retirement'] = self.retirement()
        f.core.maps[f.cleanup_name]['data']['receipt.json'] = h.canonical(receipt)
        f.review['stopped']['cleanup_sha256'] = h.digest(receipt)
        result = await h.migrate(f.context,f.review)
        self.assertEqual(result['state'],'handover-complete-stopped')
        self.assertEqual(receipt['retirement']['proof']['entry']['hard'],5120*1048576)
    async def test_root_rehashed_invalid_retirement_still_fails_production_typed_validator(self):
        f = self.f; original = copy.deepcopy(f.core.maps[f.cleanup_name])
        original_sha = f.review['stopped']['cleanup_sha256']
        for case in ('used','unpinned','online','cap','enrollment-uid'):
            with self.subTest(case=case):
                receipt = json.loads(original['data']['receipt.json']); receipt['retirement'] = self.retirement()
                proof = receipt['retirement']['proof']
                if case == 'used': proof['entry']['used'] = 1
                elif case == 'unpinned': proof['entry']['pinned'] = False
                elif case == 'online': proof['entry']['offline'] = False
                elif case == 'cap': proof['entry']['hard'] = 10240*1048576
                else: receipt['retirement']['enrollment_uid'] = uid()
                f.core.maps[f.cleanup_name]['data']['receipt.json'] = h.canonical(receipt)
                f.review['stopped']['cleanup_sha256'] = h.digest(receipt)
                await self.blocked()
                self.assertEqual(f.store.workspace('cps',f.workspace),f.old)
        f.core.maps[f.cleanup_name] = original; f.review['stopped']['cleanup_sha256'] = original_sha
    async def test_freeze_loss_between_commits_and_local_write_failure_retain_stopped(self):
        f = self.f; f.fail_freeze_at = 3
        with self.assertRaises(h.HandoverIncomplete) as caught: await h.migrate(f.context,f.review)
        self.assertEqual(caught.exception.phase,'central-registration')
        self.assertEqual(f.store.workspace('cps',f.workspace)['profiles'],[h.PROFILE])
        self.assertEqual(await f.service.get(f.workspace),f.local)
        # No rollback, release, start or unfreeze was attempted; recovery remains Root reviewed.
        self.assertEqual(f.reservations.state('cps:'+f.workspace)['active'],False)
        self.assertTrue(all('release' not in call and 'start' not in call for call in f.calls))
    async def test_partial_local_commit_failure_reports_incomplete_even_if_written(self):
        f = self.f; original_put = f.provider.put
        async def lost_response(kind,record,*,actor):
            result = await original_put(kind,record,actor=actor)
            if kind == 'workspaces': raise TimeoutError('Commit response lost')
            return result
        f.provider.put = lost_response
        with self.assertRaises(h.HandoverIncomplete) as caught: await h.migrate(f.context,f.review)
        self.assertEqual(caught.exception.phase,'local-profile-commit')
        self.assertEqual((await f.service.get(f.workspace))['state'],'stopped')
        self.assertEqual((await f.service.get(f.workspace))['profile'],h.PROFILE)
        self.assertEqual(f.provider.audit()[-1]['outcome'],'failure')
    async def test_tamper_after_registration_blocks_local_commit(self):
        f = self.f; original_request = f.compute._request
        async def request(path,method='GET',payload=None):
            result = await original_request(path,method,payload)
            if path == 'workspaces' and method == 'PUT':
                f.core.maps[f.cleanup_name]['metadata']['uid'] = uid()
            return result
        f.compute._request = request
        with self.assertRaises(h.HandoverIncomplete): await h.migrate(f.context,f.review)
        self.assertEqual(await f.service.get(f.workspace),f.local)
    async def test_fresh_full_storage_validation_failure_never_writes_local(self):
        f = self.f; original_validate = f.compute.validate_workspace
        async def denied(*args,**kwargs):
            if kwargs.get('registration') is not None: raise ValueError('Fresh storage validation denied')
            return await original_validate(*args,**kwargs)
        f.compute.validate_workspace = denied
        with self.assertRaises(h.HandoverIncomplete) as caught: await h.migrate(f.context,f.review)
        self.assertEqual(caught.exception.phase,'fresh-storage-validation')
        self.assertEqual(f.store.workspace('cps',f.workspace)['profiles'],[h.PROFILE])
        self.assertEqual(await f.service.get(f.workspace),f.local)
    async def test_application_reader_and_normal_get_must_agree(self):
        f = self.f; original_request = f.compute._request
        async def request(path,method='GET',payload=None):
            result = await original_request(path,method,payload)
            if path == 'workspaces/'+f.workspace: result['storage']['pvc'] = 'other'
            return result
        f.compute._request = request
        with self.assertRaises(h.HandoverIncomplete): await h.migrate(f.context,f.review)
        self.assertEqual(await f.service.get(f.workspace),f.local)
    async def test_membership_and_freeze_changes_after_preview_block_put(self):
        f = self.f; old_validate = f.compute.validate_workspace
        async def validate(*args,**kwargs):
            result = await old_validate(*args,**kwargs)
            await f.provider.delete('memberships','m1',actor='admin')
            return result
        f.compute.validate_workspace = validate
        await self.blocked()
        self.assertEqual(f.store.workspace('cps',f.workspace),f.old)
    async def test_central_registration_lost_response_remains_frozen_stopped(self):
        f = self.f; original_request = f.compute._request
        async def request(path,method='GET',payload=None):
            result = await original_request(path,method,payload)
            if path == 'workspaces' and method == 'PUT': raise TimeoutError('Registration response lost')
            return result
        f.compute._request = request
        with self.assertRaises(h.HandoverIncomplete) as caught: await h.migrate(f.context,f.review)
        self.assertEqual(caught.exception.phase,'central-registration')
        self.assertEqual(f.store.workspace('cps',f.workspace)['profiles'],[h.PROFILE])
        self.assertEqual(await f.service.get(f.workspace),f.local)
    async def test_default_inert_never_imports_factory_or_reads_credentials(self):
        with patch.object(h,'private_bytes',side_effect=AssertionError('read')), patch.object(h,'verify_source_closure',side_effect=AssertionError('import')):
            output = io.StringIO()
            with redirect_stdout(output): self.assertEqual(h.main([]),0)
            self.assertEqual(json.loads(output.getvalue())['state'],'inert')


if __name__ == '__main__': unittest.main()


class TenGiBTest(unittest.IsolatedAsyncioTestCase):
    async def test_actual_service_preview_registration_and_course_commit_ten_gib(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=await Fixture().setup(Path(tmp),'cit')
            try:
                result=await h.migrate(f.context,f.review)
                self.assertEqual(result['profile'],h.PROFILES['cit'])
                self.assertEqual((await f.service.get(f.workspace))['course_ceiling']['gpuMemoryGiB'],10)
                self.assertEqual((await f.provider.courses())[0]['resource_ceiling']['gpuMemoryGiB'],10)
                self.assertEqual(f.store.workspace('cit',f.workspace)['ceiling']['gpuMemoryGiB'],10)
                self.assertEqual(f.store.workspace('cit',f.workspace)['storage'],f.old['storage'])
                self.assertTrue(any(row['kind']=='courses' and row['actor']=='admin' for row in f.provider.audit()))
                self.assertFalse(result['start_performed'])
            finally:await f.close()


class DedicatedTenGiBCourseTest(unittest.IsolatedAsyncioTestCase):
    async def test_unused_extra_course_group_denies_before_ceiling_or_registration_write(self):
        with tempfile.TemporaryDirectory() as directory:
            f=await Fixture().setup(Path(directory),'cit')
            try:
                await f.provider.put('groups',{'id':'unrelated-unused','course_id':'course','term_id':'term'},actor='admin')
                before_courses=await f.provider.courses()
                with self.assertRaises(h.HandoverIncomplete): await h.migrate(f.context,f.review)
                self.assertEqual(await f.provider.courses(),before_courses)
                self.assertEqual(f.store.workspace('cit',f.workspace),f.old)
                self.assertNotIn('PUT workspaces',f.calls)
            finally: await f.close()
