"""CPU-only scoped-window tests; fixtures never constitute live acceptance."""
import copy
import hashlib
import importlib.util
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
PRIVATE = Path('/home/bjoern/.local/state/cps-platform-completion-20261011')
SESSION = PRIVATE / 'packing-session-20261011T173917Z'
CHAIN = PRIVATE / 'fixture-renewal-prepared/qualified-19utc-actual-chain-173917-prepared'
WINDOW = PRIVATE / 'fixture-renewal-prepared/bounded-window-20261011-prepared'

def load_module():
    path = HERE / 'qualified_restart_window.py'
    if not path.exists(): return None
    spec = importlib.util.spec_from_file_location('qualified_window', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def fixture(source):
    usernames = ['cpsgpumembera','cpsgpumemberb','cpsgpumemberc','cpsgpumemberd'] if source=='cps' else ['citgpumembera','citgpumemberb']
    ms = [{'id':'native-pilot-'+u,'person_id':u,'canonical_person_id':'cpu-'+u,'expires':'2026-10-11T11:27:43.168759+00:00','starts':'2026-10-09T11:27:43.168759+00:00'}for u in usernames]
    records = {'courses':[{'id':'native-gpu-pilot-20261009','resource_ceiling':{'gpuMemoryGiB':5 if source=='cps' else 10}}], 'terms':[], 'groups':[], 'memberships':ms, 'workspaces':[{'id':'native-group-b'if source=='cps'else'native-group-a','state':'stopped','profile':'interactive-native-qualification-5'if source=='cps'else'interactive-native-qualification-10','course_ceiling':{'gpuMemoryGiB':5 if source=='cps'else 10}}]}
    grants = {'cpu-'+u:[{'id':'native-pilot-'+source+'-'+u,'person':'cpu-'+u,'source':source,'expires':ms[0]['expires'],'profiles':['interactive-cpu','interactive-native-qualification-5'if source=='cps'else'interactive-native-qualification-10'],'allowance':1}]for u in usernames}
    return {'records':records,'people':{u:'cpu-'+u for u in usernames},'grants':grants,'servers':{'native-group-b'if source=='cps'else'native-group-a':None},'all_records':copy.deepcopy(records)|{'other':[{'id':'keep','body':'unchanged'}]},'aliases':{'reviewed_account_aliases':[{'username':u,'canonical_person_id':'cpu-'+u}for u in usernames]},'actor_model':{'name':'bjoern'if source=='cps'else'akadmin','admin':True}}

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.m = load_module(); self.assertIsNotNone(self.m, 'Bounded four-fixture qualified window implementation missing')
        self.now = datetime(2026,10,11,19,0,tzinfo=timezone.utc); self.expiry = '2026-10-11T19:45:00+00:00'

    def test_changes_only_selected_two_memberships_and_two_grants_per_source(self):
        for source in ('cps','cit'):
            before=fixture(source); after=self.m.changed(source,before,self.expiry)
            for m in after['records']['memberships']:
                selected=m['person_id'] in self.m.SELECTED[source]
                self.assertEqual(m['expires'],self.expiry if selected else self.m.OLD_EXPIRY)
                mirror=next(x for x in after['all_records']['memberships']if x['id']==m['id']);self.assertEqual(m,mirror)
            for u,p in after['people'].items():self.assertEqual(after['grants'][p][0]['expires'],self.expiry if u in self.m.SELECTED[source]else self.m.OLD_EXPIRY)
            reverse=self.m.changed(source,after,self.m.OLD_EXPIRY);self.assertEqual(reverse,before);self.assertEqual(before,fixture(source))

    def test_positive_same_day_window_at_most_sixty_minutes(self):
        self.assertEqual(self.m.window(self.expiry,self.now).hour,19)
        self.m.window((self.now+timedelta(minutes=60)).isoformat(),self.now)
        for delta in [timedelta(0),timedelta(seconds=-1),timedelta(minutes=60,microseconds=1)]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):self.m.window((self.now+delta).isoformat(),self.now)

    def test_other_date_naive_and_non_utc_windows_reject(self):
        for value in ['2026-10-12T19:30:00+00:00','2026-10-11T19:30:00','2026-10-11T21:30:00+02:00']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.m.window(value,self.now)
        with self.assertRaises(ValueError):self.m.window('2026-10-12T00:00:00+00:00',datetime(2026,10,11,23,30,tzinfo=timezone.utc))

    def test_current_partial_selected_expiries_are_resumable(self):
        before=fixture('cps');current=self.m.changed('cps',before,self.expiry)
        current['records']['memberships'][-1]['expires']=self.m.OLD_EXPIRY;current['all_records']['memberships'][-1]['expires']=self.m.OLD_EXPIRY
        self.m.current_guard('cps',before,current,self.expiry)

    def test_unselected_expiry_extra_member_grant_alias_and_profile_drift_reject(self):
        mutations=[lambda x:x['records']['memberships'][0].__setitem__('expires',self.expiry),lambda x:x['records']['memberships'].append({'id':'extra'}),lambda x:next(iter(x['grants'].values())).append({'id':'extra'}),lambda x:x['aliases'].clear(),lambda x:x['records']['workspaces'][0].__setitem__('profile','interactive-native-qualification-20'),lambda x:x['records']['courses'][0]['resource_ceiling'].__setitem__('gpuMemoryGiB',20),lambda x:x['all_records']['other'][0].__setitem__('body','drift')]
        for mutate in mutations:
            current=self.m.changed('cps',fixture('cps'),self.expiry);mutate(current)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.m.current_guard('cps',fixture('cps'),current,self.expiry)

    def test_wrong_selected_expiry_rejects(self):
        current=self.m.changed('cit',fixture('cit'),self.expiry);current['records']['memberships'][0]['expires']='2026-10-11T20:00:00+00:00'
        with self.assertRaises(ValueError):self.m.current_guard('cit',fixture('cit'),current,self.expiry)

    def test_fresh_actual_admin_role_required_and_initial_model_normalized(self):
        current=self.m.changed('cit',fixture('cit'),self.expiry);current['actor_model']['last_activity']='changed'
        self.m.current_guard('cit',fixture('cit'),current,self.expiry)
        for k,v in [('admin',False),('name','unrelated')]:
            wrong=copy.deepcopy(current);wrong['actor_model'][k]=v
            with self.assertRaises(ValueError):self.m.current_guard('cit',fixture('cit'),wrong,self.expiry)

    def test_defaults_inert_before_any_helper_or_config_read(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        with patch.object(self.m,'load_frozen',side_effect=AssertionError('loaded')),redirect_stdout(io.StringIO())as out:self.m.main([])
        self.assertEqual(json.loads(out.getvalue())['state'],'inert')

@unittest.skipUnless((SESSION/'qualified-expiry-final/ledger-final.json').exists(),'Optional private actual baseline replay is not available')
class ActualBaselineTests(unittest.TestCase):
    def setUp(self):
        self.m=load_module();self.assertIsNotNone(self.m,'Bounded four-fixture qualified window implementation missing')
        self.q=self.m.load_frozen((WINDOW/'qualified_expiry.py').read_bytes(),(WINDOW/'renew_fixtures.py').read_bytes())
        self.ledger=json.loads((SESSION/'qualified-expiry-final/ledger-final.json').read_bytes());self.state=json.loads(self.ledger['data']['state.json'])

    def inputs(self,source):
        before=json.loads((SESSION/f'qualified-expiry-final/{source}/before-full.json').read_bytes());after=json.loads((SESSION/f'qualified-expiry-final/{source}/after-full.json').read_bytes());receipt=json.loads((SESSION/f'qualified-expiry-final/{source}/receipt.json').read_bytes())
        history={n:json.loads((CHAIN/source/(n.replace('_','-')+'.json')).read_bytes())for n in ['original','renewal_after','renewal_receipt','grant_before','grant_receipt','handover_receipt']};history['registration']=json.loads((CHAIN/'registration-pinned-v2'/source/'registration.json').read_bytes())
        return before,after,receipt,history

    def test_actual_completed_qualified_expired_baselines_accept(self):
        for source in ('cps','cit'):
            before,after,receipt,history=self.inputs(source);self.m.baseline_guard(source,before,after,receipt,history,self.state,self.q)

    def test_baseline_profile_receipt_expiry_and_history_mutations_reject(self):
        before,after,receipt,history=self.inputs('cit')
        for mutate in [lambda a,r:a['records']['workspaces'][0].__setitem__('profile','interactive-shared-5'),lambda a,r:a['records']['memberships'][0].__setitem__('expires','2026-10-11T19:00:00+00:00'),lambda a,r:r.__setitem__('state','incomplete'),lambda a,r:r.__setitem__('source','cps')]:
            a=copy.deepcopy(after);r=copy.deepcopy(receipt);mutate(a,r)
            with self.assertRaises(ValueError):self.m.baseline_guard('cit',before,a,r,history,self.state,self.q)

    def test_exact_original_twenty_one_and_no_active_claims(self):
        review={'ledger_uid':self.ledger['metadata']['uid'],'ledger_state_sha256':self.m.digest(self.state),'expected_allocation_count':21}
        self.m.ledger_guard(self.state,self.state,'renew',review,self.q)
        altered=copy.deepcopy(self.state);next(iter(altered['allocations'].values()))['state']='releasing';review['ledger_state_sha256']=self.m.digest(altered)
        with self.assertRaises(ValueError):self.m.ledger_guard(altered,self.state,'renew',review,self.q)
        altered=copy.deepcopy(self.state);next(iter(altered['allocations'].values()))['foreign']='drift';review['ledger_state_sha256']=self.m.digest(altered)
        with self.assertRaises(ValueError):self.m.ledger_guard(altered,self.state,'restore-expiry',review,self.q)

    def test_missing_old_record_and_unschematized_additional_record_reject(self):
        for mutate in [lambda s:s['allocations'].pop(next(iter(s['allocations']))),lambda s:s['allocations'].__setitem__('unknown',{'state':'released'})]:
            altered=copy.deepcopy(self.state);mutate(altered);review={'ledger_uid':self.ledger['metadata']['uid'],'ledger_state_sha256':self.m.digest(altered),'expected_allocation_count':len(altered['allocations'])}
            with self.assertRaises(ValueError):self.m.ledger_guard(altered,self.state,'restore-expiry',review,self.q)

class CycleRequestTests(unittest.TestCase):
    def setUp(self):
        self.m=load_module();self.now=datetime(2026,10,11,19,0,tzinfo=timezone.utc)
        self.review=review_fixture(self.m,'cit',self.now)
    def test_enabled_fresh_scoped_request_only(self):
        self.m.request_guard(self.review,self.now)
        for k,v in [('enabled',False),('source_writers_stopped',False),('fixture_starts_excluded',False),('source_token_custody','shared'),('actor','other'),('source','other'),('observed_at','2026-10-11T18:00:00+00:00'),('cycle_id','fake'),('operation','start')]:
            r=copy.deepcopy(self.review);r[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):self.m.request_guard(r,self.now)
    def test_capture_none_is_never_a_write_review(self):
        self.review['current_full_sha256']=None
        self.m.request_guard(self.review,self.now,capture=True)
        with self.assertRaises(ValueError):self.m.request_guard(self.review,self.now)
    def test_restore_requires_own_cycle_provenance(self):
        self.review['operation']='restore-expiry'
        with self.assertRaises(ValueError):self.m.request_guard(self.review,self.now)
        self.review['cycle_provenance_sha256']={k:'c'*64 for k in ('before_full','after_full','receipt')}
        self.m.request_guard(self.review,self.now)


def review_fixture(m,source,now):
    return {'version':1,'enabled':True,'operation':'renew','source':source,'actor':m.ACTORS[source],
            'cycle_id':'481d3da0-e5f3-4bcf-b8df-92b87353cabb','observed_at':now.isoformat(),
            'source_writers_stopped':True,'fixture_starts_excluded':True,'source_token_custody':'Root-exclusive',
            'runtime_review_sha256':'a'*64,'physical_retirement_review_sha256':'b'*64,
            'current_full_sha256':'c'*64,'renewed_expires':(now+timedelta(minutes=45)).isoformat(),
            'provenance_sha256':{k:'d'*64 for k in ('renewal_after','renewal_receipt','grant_before','grant_receipt','handover_receipt','registration')},
            'cycle_provenance_sha256':None}


@unittest.skipUnless((SESSION/'qualified-expiry-final/ledger-final.json').exists(),'Optional genuine API CPU fixtures require private baseline')
class GenuineCrudTests(unittest.IsolatedAsyncioTestCase):
    source='cit'
    async def asyncSetUp(self):
        import tempfile,types
        from e2x_course_hub.cps.providers import LocalCourseProvider
        from e2x_course_hub.cps.compute import ComputePolicyClient
        from e2x_course_hub.cps.workspaces import WorkspaceService,HubWorkspaceAdapter
        from e2x_course_hub.cps.audit import actor_context
        self.m=load_module();self.q=self.m.load_frozen((WINDOW/'qualified_expiry.py').read_bytes(),(WINDOW/'renew_fixtures.py').read_bytes())
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        actual=json.loads((SESSION/f'qualified-expiry-final/{self.source}/after-full.json').read_bytes())
        self.provider=LocalCourseProvider(self.path/'source.db',self.source);self.addCleanup(self.provider.db.close)
        await self.provider.link_identities([{'hub':self.source,'username':u,'person_id':p,'authority':'reviewed_account_alias','administrator_reviewed':True,'review_reason':'CPU fixture only'}for u,p in self.q.R.PEOPLE[self.source].items()],actor='CPU-fixture')
        for kind in ('courses','terms','assignments','groupings','projects'):
            for row in actual['all_records'][kind]:await self.provider.put(kind,row,actor='CPU-fixture')
        for row in actual['all_records']['groups']:await self.provider.put('groups',{**row,'members':[]},actor='CPU-fixture')
        for row in actual['all_records']['memberships']:await self.provider.put('memberships',row,actor='CPU-fixture')
        for kind in ('groups','workspaces'):
            for row in actual['all_records'][kind]:await self.provider.put(kind,row,actor='CPU-fixture')
        self.grants=copy.deepcopy(actual['grants']);self.calls=[];self.compute=ComputePolicyClient('https://compute-gateway.cps-compute.svc.cluster.local:8000','CPU-only',self.source)
        self.registration=json.loads((CHAIN/'registration-pinned-v2'/self.source/'registration.json').read_bytes())
        self.handover=json.loads((CHAIN/self.source/'handover-receipt.json').read_bytes());self.generic_active=False
        async def request(path,method='GET',payload=None):
            if path.startswith('workspaces/'):return copy.deepcopy(self.registration)
            if path.startswith('reservations/'):return {'workspace':path.split('/')[-1],'active':self.generic_active,'attempt':'CPU-only'if self.generic_active else None}
            if method=='GET':return copy.deepcopy(self.grants[path.split('/')[-1]])
            self.assertEqual(path,'grants');self.assertEqual(method,'PUT');self.assertEqual(actor_context.get(),self.m.ACTORS[self.source]);self.assertNotIn('source',payload)
            after={**payload,'source':self.source};self.grants[after['person']]=[after];self.calls.append(copy.deepcopy(after));return copy.deepcopy(after)
        self.compute._request=request;self.admin=True;self.running=False
        async def user(name):return {'name':name,'admin':self.admin if name==self.m.ACTORS[self.source]else False,'servers':{'rtc':{'pending':'spawn'}}if self.running and name.endswith('groupa')else{}}
        hub=HubWorkspaceAdapter(types.SimpleNamespace(api_url='http://hub.'+('cit-jhub'if self.source=='cit'else'jupyterhub')+'.svc.cluster.local:8081/hub/api',get_user=user))
        self.service=WorkspaceService(self.provider,self.compute,hub)
        self.settings={'course_provider':self.provider,'compute_policy':self.compute,'workspace_service':self.service}
        self.baseline=await self.q.R.capture(self.settings,self.source)
        self.now=datetime(2026,10,11,19,0,tzinfo=timezone.utc);self.review=review_fixture(self.m,self.source,self.now);self.review['current_full_sha256']=self.m.digest(self.baseline)
        policyfile=PRIVATE/'packing-fresh-20261011T161520Z/proposal/policy.json'
        modefile=policyfile.parent/'operator-qualification.json'
        from cps_compute.policy import Policy
        from cps_compute.native_qualification import NativeGroupQualification
        self.mode=NativeGroupQualification.from_config(json.loads(modefile.read_bytes()),Policy(json.loads(policyfile.read_bytes())))
        self.baseline_state=json.loads(json.loads((SESSION/'qualified-expiry-final/ledger-final.json').read_bytes())['data']['state.json'])
        self.native={'ledger_uid':self.q.R.BASE_LEDGER_UID,'ledger_resource_version':'CPU-only','ledger_state':self.baseline_state,'operator_uid':'481d3da0-e5f3-4bcf-b8df-92b87353cabb','gateway_uid':'481d3da0-e5f3-4bcf-b8df-92b87353cabb','node_uid':'481d3da0-e5f3-4bcf-b8df-92b87353cabb','hub_uids':['481d3da0-e5f3-4bcf-b8df-92b87353cabb']*2,'policy_hash':self.q.POLICY,'pod_absent':True}
    async def fence(self):return copy.deepcopy(self.native)
    async def register(self):return await self.q.genuine_registration(self.service,self.source,self.mode,self.handover)
    async def runop(self):
        out=self.path/('out'+str(len(list(self.path.iterdir()))));out.mkdir();self.last_out=out
        return await self.m.apply(self.settings,self.baseline,self.review,out,self.fence,self.register,self.q,clock=lambda:self.now)
    async def test_genuine_membership_and_grant_put_actor_audit_four_rows_only(self):
        from e2x_course_hub.cps.audit import actor_context
        audit=self.provider.audit();receipt=await self.runop();self.assertEqual(receipt['state'],'selected-qualified-expiry-renewed-read-back');self.assertFalse(receipt['workspace_started']);self.assertIsNone(actor_context.get())
        final=await self.q.R.capture(self.settings,self.source);self.assertEqual(final,self.m.changed(self.source,self.baseline,self.review['renewed_expires']));self.assertEqual(len(self.calls),2)
        self.assertEqual(self.provider.audit()[:len(audit)],audit);self.assertEqual([(x['actor'],x['kind'])for x in self.provider.audit()[len(audit):]],[(self.m.ACTORS[self.source],'memberships')]*2+[(self.m.ACTORS[self.source],'compute-grants')]*2)
        self.assertEqual(len(receipt['changes']),4)
    async def test_exact_cycle_can_restore_only_four_expiries_after_new_review(self):
        renewed=await self.runop();before=json.loads((self.last_out/'before-full.json').read_bytes());after=json.loads((self.last_out/'after-full.json').read_bytes())
        self.m.cycle_guard(self.source,self.baseline,before,after,renewed,self.review,self.baseline_state,self.registration,self.q)
        self.review.update(operation='restore-expiry',cycle_provenance_sha256={k:'e'*64 for k in ('before_full','after_full','receipt')},current_full_sha256=self.m.digest(after));self.now+=timedelta(hours=2);self.review['observed_at']=self.now.isoformat()
        receipt=await self.runop();self.assertEqual(receipt['state'],'selected-qualified-expiry-restored-read-back');self.assertEqual(await self.q.R.capture(self.settings,self.source),self.baseline);self.assertEqual(len(receipt['changes']),4)
    async def test_no_cycle_receipt_or_broadened_scope_is_accepted(self):
        receipt=await self.runop();before=json.loads((self.last_out/'before-full.json').read_bytes());after=json.loads((self.last_out/'after-full.json').read_bytes())
        for mutate in [lambda r:r.update(state='incomplete'),lambda r:r.update(source='other'),lambda r:r['changes'].pop(),lambda r:r.update(renewed_expires='2026-10-12T19:45:00+00:00'),lambda r:r.update(version=True)]:
            wrong=copy.deepcopy(receipt);mutate(wrong)
            with self.assertRaises(ValueError):self.m.cycle_guard(self.source,self.baseline,before,after,wrong,self.review,self.baseline_state,self.registration,self.q)
    async def test_cycle_inverse_rejects_detached_registration_and_original_ledger(self):
        receipt=await self.runop();before=json.loads((self.last_out/'before-full.json').read_bytes());after=json.loads((self.last_out/'after-full.json').read_bytes())
        for mutate in [lambda r:r.update(registration_sha256='sha256:'+'f'*64),lambda r:r['runtime_before'].update(pod_absent=False),lambda r:r['runtime_before']['ledger_state']['allocations'].pop(next(iter(r['runtime_before']['ledger_state']['allocations']))),lambda r:r['runtime_before'].update(ledger_uid='other')]:
            wrong=copy.deepcopy(receipt);mutate(wrong)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):self.m.cycle_guard(self.source,self.baseline,before,after,wrong,self.review,self.baseline_state,self.registration,self.q)
    async def test_stale_or_disabled_review_no_writes(self):
        for field,value in [('enabled',False),('observed_at','2026-10-11T18:00:00+00:00'),('current_full_sha256','f'*64),('renewed_expires','2026-10-11T20:00:01+00:00')]:
            old=self.review[field];self.review[field]=value
            with self.assertRaises(ValueError):await self.runop()
            self.review[field]=old;self.assertEqual(self.calls,[])
    async def test_registration_native_or_source_drift_preserves_incomplete_receipt(self):
        count=0
        async def drift():
            nonlocal count;count+=1
            return {**self.native,'ledger':str(count)}
        self.fence=drift
        with self.assertRaises(ValueError):await self.runop()
        self.assertEqual(self.calls,[]);self.assertEqual(json.loads((self.last_out/'receipt.json').read_bytes())['state'],'incomplete')
    async def test_pending_server_wrong_admin_or_generic_active_denies(self):
        for target in ('running','admin','generic_active'):
            self.running=target=='running';self.admin=target!='admin';self.generic_active=target=='generic_active'
            with self.assertRaises(ValueError):await self.runop()
            self.assertEqual(self.calls,[])
    async def test_partial_selected_rows_resume_with_fresh_review_without_other_writes(self):
        row=next(x for x in self.baseline['records']['memberships']if x['person_id']in self.m.SELECTED[self.source]);await self.provider.put('memberships',{**row,'expires':self.review['renewed_expires']},actor='CPU-fixture')
        self.review['current_full_sha256']=self.m.digest(await self.q.R.capture(self.settings,self.source));result=await self.runop();self.assertEqual(len(result['changes']),3);self.assertEqual(len(self.calls),2)

class GenuineCpsCrudTests(GenuineCrudTests):
    source='cps'


class RuntimeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def genuine_context(self, *, remove_new_records=False, change_new_record=False):
        """Real frozen792 reset/fence; only file-stat and transports are CPU doubles."""
        import types,base64
        from unittest.mock import patch
        from kubernetes import client,config
        m=load_module();q=m.load_frozen((WINDOW/'qualified_expiry.py').read_bytes(),(WINDOW/'renew_fixtures.py').read_bytes(),str(WINDOW/'qualified_expiry.py'))
        ns=q.build_context.__globals__;original_install=ns['install_base'];old_base=ns['R']
        index=json.loads((SESSION/'expiry-runtime-captures/index.json').read_bytes())
        objects={}
        for name,ref in index['objects'].items():
            raw=Path(ref['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),ref['sha256']);objects[name]=json.loads(raw)
        stage=json.loads((SESSION/'operator-stage/cit-stage-current.json').read_bytes())['files']
        policy=json.loads(base64.b64decode(stage['policy.json']['base64']));mode=json.loads(base64.b64decode(stage['operator-qualification.json']['base64']))
        runtime=json.loads((SESSION/'expiry-runtime-assembled/cit-runtime.json').read_bytes())
        baseline=json.loads(json.loads((SESSION/'qualified-expiry-final/ledger-final.json').read_bytes())['data']['state.json'])
        state=copy.deepcopy(baseline)
        if remove_new_records:state['allocations']={k:v for k,v in state['allocations'].items()if k in q.R.BASE_ALLOCATION_SHA256}
        if change_new_record:
            key=next(k for k in state['allocations']if k not in q.R.BASE_ALLOCATION_SHA256)
            self.assertIsNotNone(state['allocations'][key]['intent']);state['allocations'][key]['intent']=None
        self.assertEqual(len(state['allocations']),19 if remove_new_records else 21)
        objects['ledger']['data']['state.json']=m.canonical(state)
        runtime.update(ledger_state_sha256=m.digest(state),expected_allocation_count=len(state['allocations']))
        now=datetime.now(timezone.utc);review=review_fixture(m,'cit',now);review['current_full_sha256']=None
        retirement={'version':1,'state':'normal-close-and-physical-retirement-root-reviewed','source':'cit','observed_at':now.isoformat(),'policy_hash':q.POLICY,'ledger_uid':q.R.BASE_LEDGER_UID,'ledger_state_sha256':m.digest(state),'normal_close_receipt_sha256':'d'*64,'protected_retirement_capture_sha256':'e'*64,'all_native_released':True,'physical_retirement_verified':True}
        docs={'runtime':runtime,'retirement':retirement,'policy':policy,'mode':mode,'nodeconf':json.loads(objects['node_config_cm']['data']['config.json']),'closure':{}}
        # This sentinel marks the exact genuine loader boundary; no Source app is
        # constructed, and no credential or external transport is ever used.
        helper=b"import json\ndef decode(raw):return json.loads(raw)\ndef verify_source_closure(value):pass\ndef load_configured_service(*a,**kw):return type('CPUApp',(),{'tornado_settings':{'CPU_SOURCE_LOADER_BOUNDARY':True}})(),None\n"
        audit_path=PRIVATE/'native-packing-operator-prepared/old-hub-barrier-audit-prepared/audit_old_hub.py'
        audit_raw=audit_path.read_bytes();self.assertEqual(hashlib.sha256(audit_raw).hexdigest(),q.R.AUDIT_SHA)
        def protected(path,pin):
            if path==str(WINDOW/'qualified_expiry.py'):return (WINDOW/'qualified_expiry.py').read_bytes()
            if path=='renewal':return (WINDOW/'renew_fixtures.py').read_bytes()
            if path=='handover':return helper
            if path=='audit':return audit_raw
            return json.dumps(docs.get(path,{})).encode()
        def genuine_install(raw):
            original_install(raw)
            ns['R'].load.__globals__['protected']=protected
        pods={(o['metadata']['namespace'],o['metadata']['name']):o for name,o in objects.items()if name.endswith('_operator')or name.endswith('_hub')or name in ('node','gateway')}
        cms={(o['metadata']['namespace'],o['metadata']['name']):o for name,o in objects.items()if name.endswith('_cm')or name=='ledger'}
        deployments={(o['metadata']['namespace'],o['metadata']['name']):o for name,o in objects.items()if name in ('cps_admin','cit_admin')}
        loaded=[]
        class Core:
            def __init__(self):self_unused=loaded==['scoped'];require_loaded(self_unused)
            def read_namespaced_pod(self,name,namespace,**kw):
                if(namespace,name)not in pods:raise type('Absent',(Exception,),{'status':404})()
                return copy.deepcopy(pods[namespace,name])
            def read_namespaced_config_map(self,name,namespace,**kw):return copy.deepcopy(cms[namespace,name])
            def list_namespaced_pod(self,namespace,label_selector=None,**kw):return copy.deepcopy(objects['cps_admin_pods'if label_selector=='app=cps-admin'else'cit_admin_pods'])
        class Apps:
            def __init__(self):require_loaded(loaded==['scoped'])
            def read_namespaced_deployment(self,name,namespace,**kw):return copy.deepcopy(deployments[namespace,name])
        def require_loaded(ok):self.assertTrue(ok,'Scoped configuration must precede client construction')
        args=types.SimpleNamespace(source='cit',source_sha256='f'*64,renewal='renewal',handover='handover',audit_helper='audit',source_closure='closure',source_closure_sha256='f'*64,policy='policy',policy_sha256='f'*64,qualification_config='mode',qualification_config_sha256='f'*64,node_config='nodeconf',node_config_sha256='f'*64,physical_retirement_review='retirement',normal_close_receipt='close',protected_retirement_capture='physical',kubeconfig='scoped',kubeconfig_sha256='f'*64,runtime_review='runtime',config='app',config_sha256='f'*64,handover_receipt='handover-receipt',capture=True)
        with patch.dict(ns,{'protected':protected,'install_base':genuine_install}),patch.object(client,'CoreV1Api',Core),patch.object(client,'AppsV1Api',Apps),patch.object(config,'load_kube_config',lambda **kw:loaded.append(kw['config_file'])),patch.object(m,'ledger_guard',wraps=m.ledger_guard)as guard:
            if remove_new_records or change_new_record:
                with self.assertRaisesRegex(ValueError,'All actual native claims|original twenty-one'):await m.build_context(args,review,baseline,q,{'renewed_expires':'2026-10-11T19:00:00+00:00'})
            else:
                settings,fence,_=await m.build_context(args,review,baseline,q,{'renewed_expires':'2026-10-11T19:00:00+00:00'})
                self.assertEqual(settings,{'CPU_SOURCE_LOADER_BOUNDARY':True});first_calls=guard.call_count
                self.assertGreaterEqual(first_calls,1,'Added21 must run before Source boundary')
                returned=await fence();self.assertEqual(returned['ledger_state'],baseline)
                self.assertGreater(guard.call_count,first_calls,'Returned genuine fence must retain added21')
            self.assertIsNot(ns['R'],old_base,'Genuine initializer must actually reset its class')
            self.assertIs(q.R,ns['R'],'Exported class must track the genuine reset')
            self.assertGreaterEqual(guard.call_count,1,'Added21 guard must run before genuine Source loader')
    async def test_genuine_frozen_reset_enforces_added21_before_source_loader(self):
        await self.genuine_context(remove_new_records=True)
    async def test_genuine_frozen_reset_reaches_source_boundary_only_after_added21(self):
        await self.genuine_context()
    async def test_genuine_frozen_reset_rejects_one_changed_new_record_before_source(self):
        await self.genuine_context(change_new_record=True)
    async def test_fifo_input_rejects_promptly_without_open_block(self):
        import subprocess,tempfile,os,sys
        with tempfile.TemporaryDirectory()as d:
            fifo=Path(d)/'input';os.mkfifo(fifo)
            script="import importlib.util;spec=importlib.util.spec_from_file_location('m',"+repr(str(HERE/'qualified_restart_window.py'))+");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\ntry:m.protected("+repr(str(fifo))+",'a'*64)\nexcept ValueError:pass\nelse:raise AssertionError('FIFO accepted')"
            result=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=1)
            self.assertEqual(result.returncode,0,result.stderr.decode())
    async def test_default_inert_with_supplied_paths_still_opens_nothing(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        m=load_module()
        with patch.object(m,'load_frozen',side_effect=AssertionError('opened')),redirect_stdout(io.StringIO())as out:m.main(['--source','cit','--qualified-expiry','/must-not-open','--request','/must-not-open-request'])
        self.assertEqual(json.loads(out.getvalue())['state'],'inert')

if __name__=='__main__':unittest.main()
