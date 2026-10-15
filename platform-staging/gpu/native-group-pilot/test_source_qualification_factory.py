"""Only temporary CPU data and fake authenticated Core responses; no live calls."""
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import source_qualification_factory as f
import source_qualification_reader as reader

HANDOVER=Path(__file__).parent
sys.path.insert(0,str(HANDOVER))
from test_source_qualification_handover import Fixture
os.environ.setdefault('JUPYTERHUB_API_TOKEN','synthetic-cpu-fixture')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def uid(): return str(uuid.uuid4())


class Api:
    def __init__(self): self.pods={};self.deployments={};self.configmaps={};self.policies=[]
    def read_namespaced_pod(self,name,namespace,**kwargs): return copy.deepcopy(self.pods[(namespace,name)])
    def list_namespaced_pod(self,namespace,label_selector='',**kwargs):
        labels=dict(x.split('=',1) for x in label_selector.split(',') if x)
        return {'apiVersion':'v1','kind':'PodList','items':[copy.deepcopy(p) for (ns,_),p in self.pods.items()
            if ns==namespace and all(p['metadata'].get('labels',{}).get(k)==v for k,v in labels.items())]}
    def read_namespaced_deployment(self,name,namespace,**kwargs): return copy.deepcopy(self.deployments[(namespace,name)])
    def read_namespaced_config_map(self,name,namespace,**kwargs): return copy.deepcopy(self.configmaps[(namespace,name)])
    def list_namespaced_network_policy(self,namespace,**kwargs):
        return {'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicyList','items':[copy.deepcopy(p) for p in self.policies if p['metadata']['namespace']==namespace]}


class Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.fixture=await Fixture().setup(self.root); q=self.fixture
        self.api=Api(); freeze_id=uid(); operator_uid=uid()
        def pod(ns,name,pid,labels,volumes=None):
            p={'apiVersion':'v1','kind':'Pod','metadata':{'namespace':ns,'name':name,'uid':pid,'labels':labels},
                'spec':{'containers':[{'name':'main','image':'registry.invalid/fixture@sha256:'+'a'*64}], 'volumes':volumes or []},
                'status':{'containerStatuses':[{'name':'main','imageID':'fixture@sha256:'+'a'*64,'state':{'running':{'startedAt':'2026-10-09T10:00:00Z'}}}]}}
            self.api.pods[(ns,name)]=p; return p
        operator=pod('cps-compute','cps-native-handover-20261009-cps',operator_uid,{'cps.compute/profile-handover-operator':freeze_id})
        operator['spec'].update(serviceAccountName='cps-native-handover-operator',securityContext={'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True,'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}})
        operator['spec']['containers'][0].update(name='operator',securityContext={'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}})
        admins=[]; hubs=[]
        for source,ns in [('cps','jupyterhub'),('cit','cit-jhub')]:
            admin={'source':source,'namespace':'cps-compute','name':source+'-admin','uid':uid(),'selector':{'app':source+'-admin'}}
            self.api.deployments[('cps-compute',source+'-admin')]={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':'cps-compute','name':source+'-admin','uid':admin['uid']},
                'spec':{'replicas':0,'selector':{'matchLabels':admin['selector']}}}; admins.append(admin)
            old=copy.deepcopy(q.policy.catalog); old['version']='synthetic-old'
            from cps_compute.policy import Policy
            old_policy=Policy(old)
            cm={'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{'namespace':ns,'name':'installed-old','uid':uid()},
                'data':{'policy.json':f.canonical(old),'settings.json':'{"enabled":true}'}}
            self.api.configmaps[(ns,'installed-old')]=cm
            p=pod(ns,'hub',uid(),{'app':'hub'},[{'name':'native','configMap':{'name':'installed-old'}}])
            hubs.append({'source':source,'namespace':ns,'pod':'hub','pod_uid':p['metadata']['uid'],'spec_sha256':f.checksum(p['spec']),
                'image_id':p['status']['containerStatuses'][0]['imageID'],'container':'main','configmap':'installed-old','configmap_uid':cm['metadata']['uid'],
                'configmap_data_sha256':f.checksum(cm['data']),'config_volume':'native','policy_key':'policy.json','old_policy_hash':old_policy.hash,
                'hook_source_sha256':'b'*64})
        gateway=pod('gateway','gateway',uid(),{'app':'gateway'})
        freeze={'mode':'source-writers-old-policy','freeze_id':freeze_id,'operator':{'namespace':'cps-compute','name':'cps-native-handover-20261009-cps','uid':operator_uid,
            'spec_sha256':f.checksum(operator['spec'])},'admins':admins,'targets':[],'hubs':hubs,'exclusion_evidence':{'path':str(self.root/'exclusion.json'),'sha256':''}}
        self.evidence={'version':1,'protocol':'root-operator-source-writer-start-exclusion/v1','freeze_id':freeze_id,'operator_uid':operator_uid,
            'hub_pod_uids':[x['pod_uid'] for x in hubs],'hub_old_policy_hashes':{x['source']:x['old_policy_hash'] for x in hubs},
            'gateway_new_policy_hash':q.policy.hash,'hook_source_sha256':{x['source']:x['hook_source_sha256'] for x in hubs},
            'no_alternate_group_start_path':True,'source_service_token_custody':'root-exclusive-during-external-freeze',
            'passed':True,'observed_at':datetime.now(timezone.utc).isoformat()}
        policy=self.root/'policy.json'; policy.write_text(f.canonical(q.policy.catalog))
        groups=self.root/'groups.json';groups.write_bytes(q.groups.document)
        from e2x_course_hub.cps.bootstrap import ensure_initial_config
        server=self.root/'server.yml'; ensure_initial_config(server)
        cfg=self.root/'console.py'
        cfg.write_text('\n'.join(['c=get_config()',"c.CourseServiceApp.console_owner='cps'",'c.CourseServiceApp.database_path='+repr(str(self.root/'console.sqlite')),
            'c.CourseServiceApp.server_config_file='+repr(str(server)),"c.CourseServiceApp.api_url='https://hub.invalid/api'",
            "c.CourseServiceApp.compute_policy_url='https://fixture.invalid'","c.CourseServiceApp.compute_policy_token='synthetic-cpu-fixture'",
            "c.CourseServiceApp.course_providers={'local':{'enabled':True},'moodle':{'enabled':False}}"] ))
        cfg.chmod(0o600)
        self.metadata={'version':1,'enabled':True,'source':'cps','workspace':'native-group-b',
            'handover':{'path':str(HANDOVER/'source_qualification_handover.py'),'sha256':f.HANDOVER_SHA},
            'console':{'config_path':str(cfg),'config_sha256':sha(cfg),'database_path':str(self.root/'console.sqlite'),
                'server_config_path':str(server),'hub_api_url':'https://hub.invalid/api','compute_policy_url':'https://fixture.invalid'},
            'gateway':{'namespace':'gateway','pod':'gateway','pod_uid':gateway['metadata']['uid'],'pod_spec_sha256':f.checksum(gateway['spec']),
                'container':'main','image_id':gateway['status']['containerStatuses'][0]['imageID'],'python_path':'/usr/local/bin/python',
                'reader_path':str(Path(reader.__file__)),'reader_sha256':sha(reader.__file__),'request':{}},
            'policy':{'path':str(policy),'sha256':sha(policy)},'qualification_config':{'path':str(groups),'sha256':sha(groups)},
            'kubernetes':{'kubeconfig':'/ROOT/actual','context':'actual','kubectl_path':'/usr/bin/kubectl','kubectl_sha256':'c'*64},'freeze':freeze}
        self.update_evidence()
    def update_evidence(self):
        path=Path(self.metadata['freeze']['exclusion_evidence']['path']);path.write_text(f.canonical(self.evidence)); path.chmod(0o600)
        self.metadata['freeze']['exclusion_evidence']['sha256']=sha(path)
    def cpu_protected(self,path,digest):
        raw=Path(path).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),digest); return raw
    async def asyncTearDown(self):
        for app in f.CONTEXTS: app.tornado_settings['course_provider'].db.close()
        f.CONTEXTS.clear();await self.fixture.close();self.tmp.cleanup()
    def verifier(self):
        return f.FreezeVerifier(self.metadata,self.api,self.api,self.api,self.fixture.backend,self.fixture.policy.hash)
    async def test_source_writer_old_policy_exact_fresh_core_exclusion(self):
        with patch.object(f,'protected',self.cpu_protected): result=await self.verifier()()
        self.assertIs(result['active'],True);self.assertEqual(result['sources'],['cit','cps'])
    async def test_writer_uid_pod_config_policy_and_custody_tampering_blocks(self):
        cases=('replicas','admin-uid','writer-pod','hub-uid','hub-spec','cm-uid','cm-mutable','equal-policy','evidence','custody','stale')
        original_api=copy.deepcopy(self.api.__dict__); original_metadata=copy.deepcopy(self.metadata); original_evidence=copy.deepcopy(self.evidence)
        for case in cases:
            with self.subTest(case=case):
                if case=='replicas':self.api.deployments[('cps-compute','cps-admin')]['spec']['replicas']=1
                elif case=='admin-uid':self.api.deployments[('cps-compute','cit-admin')]['metadata']['uid']=uid()
                elif case=='writer-pod':self.api.pods[('cps-compute','old-admin')]={'metadata':{'namespace':'cps-compute','uid':uid(),'labels':{'app':'cps-admin'}}}
                elif case=='hub-uid':self.api.pods[('jupyterhub','hub')]['metadata']['uid']=uid()
                elif case=='hub-spec':self.api.pods[('cit-jhub','hub')]['spec']['containers'][0]['image']='other'
                elif case=='cm-uid':self.api.configmaps[('jupyterhub','installed-old')]['metadata']['uid']=uid()
                elif case=='cm-mutable':self.api.configmaps[('cit-jhub','installed-old')]['immutable']=False
                elif case=='equal-policy':self.metadata['freeze']['hubs'][0]['old_policy_hash']=self.fixture.policy.hash
                elif case=='evidence':self.evidence['no_alternate_group_start_path']=False;self.update_evidence()
                elif case=='custody':self.evidence['source_service_token_custody']='unknown';self.update_evidence()
                else:self.evidence['observed_at']=(datetime.now(timezone.utc)-timedelta(minutes=11)).isoformat();self.update_evidence()
                with patch.object(f,'protected',self.cpu_protected), self.assertRaises(ValueError):await self.verifier()()
            self.api.__dict__=copy.deepcopy(original_api);self.metadata=copy.deepcopy(original_metadata);self.evidence=copy.deepcopy(original_evidence);self.update_evidence()
    async def test_genuine_configured_app_only_local_provider_no_runtime_jobs(self):
        original_fstat=os.fstat
        def root_stat(fd):
            info=original_fstat(fd)
            return SimpleNamespace(**{key:getattr(info,key) for key in dir(info) if key.startswith('st_')}, **{}) if info.st_uid==10001 else SimpleNamespace(**{
                **{key:getattr(info,key) for key in dir(info) if key.startswith('st_')},'st_uid':10001})
        with patch.object(f,'protected',self.cpu_protected), patch('os.fstat',root_stat), patch('cps_compute.runtime.create_runtime',side_effect=AssertionError('job bootstrap')):
            context=await f.build_from_metadata(self.metadata,self.api,self.api,self.api)
        from e2x_course_hub.cps.workspaces import WorkspaceService
        from e2x_course_hub.cps.providers import LocalCourseProvider
        self.assertIs(type(context['service']),WorkspaceService);self.assertIs(type(context['service'].provider),LocalCourseProvider)
        self.assertIs(context['service'],f.CONTEXTS[-1].tornado_settings['workspace_service'])
        self.assertIs(context['service'].compute,f.CONTEXTS[-1].tornado_settings['compute_policy'])
    async def test_moodle_is_rejected_before_provider_initialization(self):
        cfg=Path(self.metadata['console']['config_path']);cfg.write_text(cfg.read_text()+"\nc.CourseServiceApp.course_providers={'local':{'enabled':True},'moodle':{'enabled':True}}\n")
        self.metadata['console']['config_sha256']=sha(cfg)
        with patch.object(f,'protected',self.cpu_protected),patch('e2x_course_hub.cps.providers.configure_provider',side_effect=AssertionError('constructor')),self.assertRaises(ValueError):
            await f.build_from_metadata(self.metadata,self.api,self.api,self.api)
    async def test_unarmed_factory_reads_no_paths_credentials_or_kubernetes(self):
        with patch.dict(os.environ,{},clear=True),patch.object(f,'protected',side_effect=AssertionError('read')),self.assertRaises(ValueError):await f.build_context()
    async def test_callback_or_wrong_source_metadata_cannot_pass_through(self):
        for change in (lambda x:x.update(read_registration=lambda:None),lambda x:x.update(source='cit'),lambda x:x['freeze'].update(verify=lambda:True)):
            value=copy.deepcopy(self.metadata);change(value)
            with self.assertRaises(ValueError):f.validate_metadata(value)


    async def test_admin_namespace_is_shared_compute_while_hubs_remain_source_owned(self):
        self.assertEqual({a['namespace'] for a in self.metadata['freeze']['admins']}, {'cps-compute'})
        self.assertEqual({a['source']:a['namespace'] for a in self.metadata['freeze']['hubs']}, {'cps':'jupyterhub','cit':'cit-jhub'})
        self.assertIs(f.validate_metadata(self.metadata), self.metadata)
        with patch.object(f,'protected',self.cpu_protected):
            self.assertIs((await self.verifier()())['active'], True)
        for source, wrong in [('cps','jupyterhub'),('cit','cit-jhub')]:
            value=copy.deepcopy(self.metadata)
            next(a for a in value['freeze']['admins'] if a['source']==source)['namespace']=wrong
            with self.subTest(source=source), self.assertRaises(ValueError): f.validate_metadata(value)
        for source in ('cps','cit'):
            value=copy.deepcopy(self.metadata)
            next(a for a in value['freeze']['hubs'] if a['source']==source)['namespace']='cps-compute'
            with self.subTest(hub=source), self.assertRaises(ValueError): f.validate_metadata(value)



    async def test_full_planned_disabled_moodle_factory_without_initialization(self):
        full={'local':{'enabled':True},'moodle':{'enabled':False,'baseUrl':None,'authSecretRef':None,'syncInterval':'10m','readOnly':True}}
        self.assertTrue(f.local_only_configuration(full))
        self.assertTrue(f.local_only_configuration({'local':{'enabled':True},'moodle':{'enabled':False}}))
        cfg=Path(self.metadata['console']['config_path'])
        cfg.write_text(cfg.read_text()+'\nc.CourseServiceApp.course_providers='+repr(full)+'\n')
        self.metadata['console']['config_sha256']=sha(cfg)
        import e2x_course_hub.cps.providers as providers
        original_fstat=os.fstat
        def root_stat(fd):
            info=original_fstat(fd)
            return SimpleNamespace(**{**{key:getattr(info,key) for key in dir(info) if key.startswith('st_')},'st_uid':10001})
        with patch.object(f,'protected',self.cpu_protected), patch('os.fstat',root_stat), patch.object(providers.MoodleCourseProvider,'__init__',side_effect=AssertionError('Moodle must not initialize')):
            context=await f.build_from_metadata(self.metadata,self.api,self.api,self.api)
        self.assertEqual(context['service'].provider.console,'cps')
        for patchmap in ({'enabled':True},{'baseUrl':'https://moodle.invalid'},{'authSecretRef':'secret'},{'unknown':False},{'syncInterval':'1m'},{'readOnly':False},{'enabled':0}):
            value=copy.deepcopy(full);value['moodle'].update(patchmap)
            with self.subTest(patchmap=patchmap):self.assertFalse(f.local_only_configuration(value))
        for value in ({**full,'extra':{}},{**full,'local':{'enabled':1}},{**full,'local':{'enabled':True,'unknown':False}}):
            self.assertFalse(f.local_only_configuration(value))


class ReaderTests(unittest.TestCase):
    def test_actual_configured_store_reader_is_readonly_and_preserves_normal_fields(self):
        from cps_compute.internal import ControlStore,ServiceIdentity
        from cps_compute.reservations import Reservations
        import cps_compute.internal as internal
        import cps_compute.runtime as runtime
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'control.sqlite';store=ControlStore(db);r=Reservations(root/'reservations.sqlite')
            expected={'workspace':'native-group-b','owner':'neutral','server':'rtc','members':['p'],'principal':'workspace:cps:native-group-b',
                'profiles':['interactive-native-pilot-5'],'policy_hash':'old','storage':{'path':'/unchanged','state':'active'}}
            store.put_workspace(expected,ServiceIdentity('cps','cps'),r)
            cfg=root/'runtime.json';cfg.write_text(json.dumps({'state_directory':str(root)}))
            info=db.stat();request={'source':'cps','workspace':'native-group-b','config_path':str(cfg),'config_sha256':sha(cfg),
                'internal_sha256':sha(internal.__file__),'runtime_sha256':sha(runtime.__file__),'database_path':str(db),
                'database_device':info.st_dev,'database_inode':info.st_ino,'database_uid':info.st_uid}
            before=sha(db)
            with patch.object(reader,'projected_config_bytes',reader.file_bytes),patch.dict(os.environ,{'CPS_COMPUTE_CONFIG':str(cfg)}):self.assertEqual(reader.read_registration(request),expected)
            self.assertEqual(sha(db),before)
            for field,value in [('source','cit'),('database_inode',info.st_ino+1),('config_sha256','0'*64),('database_uid',True)]:
                changed={**request,field:value}
                with patch.object(reader,'projected_config_bytes',reader.file_bytes),patch.dict(os.environ,{'CPS_COMPUTE_CONFIG':str(cfg)}),self.assertRaises(ValueError):reader.read_registration(changed)
            self.assertEqual(sha(db),before)
    def test_missing_actual_schema_cannot_initialize_or_create_database(self):
        import sqlite3
        import cps_compute.internal as internal
        import cps_compute.runtime as runtime
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'control.sqlite';connection=sqlite3.connect(db);connection.execute('CREATE TABLE existing (id INTEGER)');connection.close()
            cfg=root/'runtime.json';cfg.write_text(json.dumps({'state_directory':str(root)}));info=db.stat()
            request={'source':'cps','workspace':'native-group-b','config_path':str(cfg),'config_sha256':sha(cfg),'internal_sha256':sha(internal.__file__),
                'runtime_sha256':sha(runtime.__file__),'database_path':str(db),'database_device':info.st_dev,'database_inode':info.st_ino,'database_uid':info.st_uid}
            before=sha(db)
            with patch.object(reader,'projected_config_bytes',reader.file_bytes),patch.dict(os.environ,{'CPS_COMPUTE_CONFIG':str(cfg)}),self.assertRaises(sqlite3.OperationalError):reader.read_registration(request)
            self.assertEqual(sha(db),before)


if __name__=='__main__':unittest.main()
