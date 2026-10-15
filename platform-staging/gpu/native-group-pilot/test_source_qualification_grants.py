import asyncio
import copy
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,AsyncMock

os.environ.setdefault('JUPYTERHUB_API_TOKEN','synthetic-cpu-only')
import source_qualification_grants as h
from e2x_course_hub.cps.providers import LocalCourseProvider
from e2x_course_hub.cps.compute import ComputePolicyClient
from e2x_course_hub.cps.workspaces import WorkspaceService,HubWorkspaceAdapter
from e2x_course_hub.api.hub_api import HubAPI
from cps_compute.internal import ControlStore,ServiceIdentity

class Tests(unittest.IsolatedAsyncioTestCase):
    async def setup_source(self,source):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=source
        self.provider=LocalCourseProvider(self.root/'courses.sqlite',source)
        self.client=ComputePolicyClient('https://compute-gateway.cps-compute.svc','synthetic-cpu-only',source)
        ns='jupyterhub' if source=='cps' else 'cit-jhub'
        hub=HubAPI(api_token='synthetic-cpu-only',api_url='http://hub.'+ns+'.svc/hub/api')
        self.users={w['hub_user']:{'name':w['hub_user'],'servers':{}} for w in h.workspaces(source)}
        hub.get_user=AsyncMock(side_effect=lambda name:copy.deepcopy(self.users[name]))
        self.service=WorkspaceService(self.provider,self.client,HubWorkspaceAdapter(hub))
        self.settings={'console_owner':source,'course_provider':self.provider,'compute_policy':self.client,'workspace_service':self.service,'api':SimpleNamespace(course_api=SimpleNamespace(hub_api=hub)),'service_prefix':'/services/'+source+'-admin'}
        self.store=ControlStore(self.root/'central.sqlite');self.calls=[]
        self.starts=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();self.expires=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        await self.provider.put('courses',{'id':h.COURSE,'resource_ceiling':h.CEILING,'workspace_bindings':[{k:w[k] for k in ('group_id','hub_user','hub_server','namespace','pod')} for w in h.workspaces(source)]},actor='operator:cpu-fixture')
        await self.provider.put('terms',{'id':h.TERM,'course_id':h.COURSE},actor='operator:cpu-fixture')
        for w in h.workspaces(source):
            names={u for u in h.PEOPLE[source] if u[-1] in (('a','b') if w['id'].endswith('a') else ('c','d'))}
            await self.provider.put('groups',{'id':w['group_id'],'course_id':h.COURSE,'term_id':h.TERM,'members':[]},actor='operator:cpu-fixture')
            for u in sorted(names):
                await self.provider.link_identities([{'hub':source,'username':u,'person_id':h.PEOPLE[source][u],'authority':'reviewed_account_alias','administrator_reviewed':True,'review_reason':'CPU-only fixture','verified':False}],actor='operator:cpu-fixture')
                await self.provider.put('memberships',{'id':'membership-'+u,'course_id':h.COURSE,'term_id':h.TERM,'group_id':w['group_id'],'person_id':u,'canonical_person_id':h.PEOPLE[source][u],'role':'student','starts':self.starts,'expires':self.expires},actor='operator:cpu-fixture')
            await self.provider.put('groups',{'id':w['group_id'],'course_id':h.COURSE,'term_id':h.TERM,'members':sorted(names)},actor='operator:cpu-fixture')
            await self.provider.put('workspaces',{**w,'course_id':h.COURSE,'term_id':h.TERM,'profile':h.OLD,'state':'stopped','course_ceiling':h.CEILING,'notice':'Preserve this notice'},actor='operator:cpu-fixture')
        for gid,person in h.expected_grants(source).items():
            self.store.put({'id':gid,'person':person,'profiles':['interactive-cpu',h.OLD,'batch-cpu'],'projects':['existing-research'],'allowance':1,'starts':self.starts,'expires':self.expires,'reason':'Keep original source reason'},ServiceIdentity(source,source))
            self.store.put({'id':'unrelated-'+gid,'person':person,'profiles':['batch-cpu'],'projects':['other-project'],'allowance':0,'expires':self.expires,'reason':'unrelated'},ServiceIdentity(source,source))
        async def request(path,method='GET',payload=None):
            self.calls.append((method,path,copy.deepcopy(payload)))
            if method=='GET':return [g for g in self.store.grants() if g['source']==source and g['person']==path.rsplit('/',1)[-1]]
            self.assertEqual((method,path),('PUT','grants'));return self.store.put(payload,ServiceIdentity(source,source))
        self.client._request=request
    async def asyncTearDown(self):
        if hasattr(self,'provider'):self.provider.db.close();self.tmp.cleanup()
    def review(self,before):return {'version':1,'source':before['source'],'actor':h.ACTOR,'before_sha256':h.digest(before),'writer_exclusion':{'passed':True,'observed_at':datetime.now(timezone.utc).isoformat(),'source_writers_stopped':True,'fixture_starts_excluded':True,'source_token_custody':'Root-exclusive','operator':h.ACTOR}}
    async def test_all_four_cps_existing_grants_and_unrelated_fields_preserved(self):
        await self.setup_source('cps');before=await h.capture(self.settings,'cps');after=await h.apply(self.settings,before,self.review(before),self.root)
        self.assertEqual(after['state'],'canonical-fixture-grants-updated-and-read-back');self.assertEqual(len(after['changes']),2)
        for change in after['changes']:
            self.assertEqual({k:v for k,v in change['before'].items() if k!='profiles'},{k:v for k,v in change['after'].items() if k!='profiles'})
            self.assertEqual(change['after']['profiles'],['interactive-cpu',h.NEW,'batch-cpu'])
        self.assertEqual(len([c for c in self.calls if c[0]=='PUT']),2)
        self.assertEqual(len(self.store.audit()),6)
        for gid,person in h.expected_grants('cps').items():self.assertTrue(any(g['id']=='unrelated-'+gid and g['profiles']==['batch-cpu'] for g in self.store.grants()))
    async def test_cit_uses_actual_own_source_not_cps_human(self):
        await self.setup_source('cit');before=await h.capture(self.settings,'cit');out=await h.apply(self.settings,before,self.review(before),self.root)
        self.assertEqual(len(out['changes']),2);self.assertTrue(all(g['source']=='cit' for g in self.store.grants()))
        self.assertTrue(all(a['actor']=='cit' for a in self.store.audit()))
        self.assertTrue(any(a['actor']==h.ACTOR for a in self.provider.audit()))
    async def test_unknown_missing_duplicate_and_foreign_fixture_grants_fail_no_put(self):
        await self.setup_source('cps');original=self.client._request
        for kind in ('missing','duplicate','foreign-source','foreign-person'):
            async def request(path,method='GET',payload=None):
                rows=await original(path,method,payload)
                if rows:
                    if kind=='missing':rows=[r for r in rows if not r['id'].startswith('native-pilot-')]
                    elif kind=='duplicate':rows+=copy.deepcopy(rows)
                    elif kind=='foreign-source':rows[0]['source']='cit'
                    else:rows[0]['person']='someone-else'
                return rows
            self.client._request=request
            with self.subTest(kind=kind),self.assertRaises(ValueError):await h.capture(self.settings,'cps')
        self.assertFalse(any(x[0]=='PUT' for x in self.calls))
    async def test_running_and_pending_actual_hub_server_block_even_local_stopped(self):
        await self.setup_source('cps')
        for state in ({'ready':True},{'pending':'spawn'},{'pending':'stop'}):
            self.users['cpsnativegroupa']['servers']={'rtc':state}
            with self.subTest(state=state),self.assertRaises(ValueError):await h.capture(self.settings,'cps')
        self.assertFalse(any(x[0]=='PUT' for x in self.calls))
    async def test_fresh_changed_original_blocks_all_puts(self):
        await self.setup_source('cps');before=await h.capture(self.settings,'cps')
        g=copy.deepcopy(self.store.grants()[0]);g.pop('source');g['reason']='Other current editor changed reason';self.store.put(g,ServiceIdentity('cps','cps'))
        with self.assertRaises(ValueError):await h.apply(self.settings,before,self.review(before),self.root)
        self.assertFalse(any(x[0]=='PUT' for x in self.calls))
    async def test_put_unauthorized_response_stays_incomplete_no_retry_or_rollback(self):
        await self.setup_source('cit');before=await h.capture(self.settings,'cit');original=self.client.put_grant
        async def changed(*args,**kwargs):
            result=await original(*args,**kwargs);result['person']='tampered';return result
        self.client.put_grant=changed
        with self.assertRaises(ValueError):await h.apply(self.settings,before,self.review(before),self.root)
        receipt=json.loads((self.root/'receipt.json').read_text());self.assertEqual(receipt['state'],'incomplete');self.assertIn('attempting',receipt);self.assertFalse(receipt['automatic_start'])
        self.assertEqual(len([x for x in self.calls if x[0]=='PUT']),1)
    async def test_stale_or_false_writer_exclusion_and_other_actor_review_fail_before_writes(self):
        await self.setup_source('cit');before=await h.capture(self.settings,'cit');r=self.review(before)
        for field,value in [('passed',False),('fixture_starts_excluded',False),('source_writers_stopped',False),('source_token_custody','unverified'),('observed_at',(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()),('operator','akadmin')]:
            bad=copy.deepcopy(r);bad['writer_exclusion'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):await h.apply(self.settings,before,bad,self.root)
        bad=copy.deepcopy(r);bad['actor']='bjoern'
        with self.assertRaises(ValueError):await h.apply(self.settings,before,bad,self.root)
        self.assertFalse(any(x[0]=='PUT' for x in self.calls))
    async def test_exact_replacement_rejects_arbitrary_person_source_id_and_permissions(self):
        await self.setup_source('cps');g=next(g for g in self.store.grants() if g['id'].startswith('native-pilot-'))
        for key,value in [('person','arbitrary'),('source','cit'),('id','other'),('allowance',2),('allowance',True),('profiles',[h.NEW]),('profiles',[h.OLD,h.OLD]),('profiles',[h.OLD,h.NEW]),('expires',(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())]:
            changed={**g,key:value}
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):h.replacement(changed,'cps')
        changed={**g,'new_resource':'1'}
        with self.assertRaises(ValueError):h.replacement(changed,'cps')
    def test_default_inert_imports_no_real_app_or_reads_or_network(self):
        with patch.object(h,'load_app',side_effect=AssertionError('constructor')),patch.object(h,'protected',side_effect=AssertionError('protected read')):self.assertEqual(h.main([]),0)
    def test_strict_disabled_moodle_planned_map_and_json_duplicate_keys(self):
        full={'local':{'enabled':True},'moodle':{'enabled':False,'baseUrl':None,'authSecretRef':None,'syncInterval':'10m','readOnly':True}}
        self.assertTrue(h.local_only_configuration(full))
        for key,value in [('enabled',True),('baseUrl','https://example.invalid'),('authSecretRef','secret'),('readOnly',1),('unknown',None)]:
            bad=copy.deepcopy(full);bad['moodle'][key]=value;self.assertFalse(h.local_only_configuration(bad))
        with self.assertRaises(ValueError):h.decode('{"a":1,"a":2}')
        with self.assertRaises(ValueError):h.decode('{"a":NaN}')

if __name__=='__main__':unittest.main()
