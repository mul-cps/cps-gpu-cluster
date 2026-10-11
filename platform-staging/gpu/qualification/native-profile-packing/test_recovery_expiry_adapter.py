"""CPU tests: historical recovery never becomes a new finite Stop proof."""
import copy
import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import test_recovery_history as fixture_module
future_fixture = fixture_module.future_fixture
HERE = fixture_module.HERE

class AdapterTests(unittest.TestCase):
    def setUp(self):
        import qualified_recovery_expiry_adapter as a
        import recovery_source_loader as loader
        self.a = a
        self.history, self.binding, _ = future_fixture()
        self.loaded = loader.load_sources(fixture_module.SourceLoaderTests().sources())

    def physical(self):
        from test_recovery_history import HistoryTests
        HistoryTests.setUpClass()
        observed = HistoryTests().observe(self.history, future_fixture()[2])
        now = datetime.now(timezone.utc).isoformat()
        runtime = {'source':'cit', 'ledger_uid':'00000000-0000-4000-8000-000000000002', 'ledger_state_sha256':'sha256:'+'a'*64}
        review = {'version':2,'state':'source-close-and-physical-inert-history-root-reviewed',
            'source':'cit','observed_at':now,'policy_hash':self.a.POLICY,
            'ledger_uid':runtime['ledger_uid'],'ledger_state_sha256':runtime['ledger_state_sha256'],
            'normal_close_receipt_sha256':'b'*64,'protected_retirement_capture_sha256':'c'*64,
            'history_raw_sha256':'d'*64,'all_native_released':True,'physical_inert_history_verified':True,
            'historical_recovery_uid':self.a.r.POD,'normal_stop_passed':False,'hardware_qualification':False}
        capture = {'kind':'native-group-host-observation','targets':[],
            **{k:self.history[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')}, 'retired_caps':observed}
        return runtime, review, capture

    def test_distinct_historical_review_accepts_without_normal_stop_claim(self):
        runtime, review, capture = self.physical()
        self.a.validate_physical_review(review, capture, self.history, runtime, 'cit', 'd'*64)

    def test_old_normal_review_or_false_authority_or_new_target_recovery_denied(self):
        for key,value in [('version',1),('normal_stop_passed',True),('all_native_released',False),('historical_recovery_uid','00000000-0000-4000-8000-000000000001'),('history_raw_sha256','e'*64),('physical_inert_history_verified',False)]:
            runtime, review, capture = self.physical();review[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.a.validate_physical_review(review,capture,self.history,runtime,'cit','d'*64)
        runtime, review, capture = self.physical();capture['targets']=[{'pod_uid':self.a.r.POD}]
        with self.assertRaises(ValueError):self.a.validate_physical_review(review,capture,self.history,runtime,'cit','d'*64)

    def test_observation_cannot_drop_any_of12_or_change_archive_class(self):
        for change in ('drop','finite','charge'):
            runtime,review,capture=self.physical()
            if change=='drop':capture['retired_caps'].pop()
            else:
                row=next(x for x in capture['retired_caps']if x['pod_uid']==self.a.r.POD)
                if change=='finite':row['retirement']=row.pop('recovery')
                else:row['inventory_row']['used']=1
            with self.subTest(change=change),self.assertRaises(ValueError):self.a.validate_physical_review(review,capture,self.history,runtime,'cit','d'*64)

    def test_default_inert_does_not_read_inputs_or_load_source(self):
        with redirect_stdout(io.StringIO())as out:self.assertEqual(self.a.main([]),0)
        self.assertFalse(json.loads(out.getvalue())['writes'])

    def test_genuine_frozen_context_is_adapted_and_frozen_bytes_remain_exact(self):
        import qualified_restart_window as window
        root=Path('/home/bjoern/.local/state/cps-platform-completion-20261011/qualified-restart-window-prepared-20261011/loader-reset-fixed-v2')
        raw=(root/'qualified_expiry.py').read_bytes()
        q=window.load_frozen(raw,(root/'renew_fixtures.py').read_bytes(),str(root/'qualified_expiry.py'))
        original=q.build_context.__globals__
        self.a.adapt_foundation(q,raw,self.history,self.loaded,'d'*64,'ghcr.io/mul-cps/cps-compute@sha256:'+'e'*64)
        self.assertIs(q.build_context.__globals__,original)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),window.QUALIFIED_SHA)
        self.assertEqual(original['NODE_SOURCE_SHA'],self.a.AGENT_SHA)
        nested=next(x for x in q.build_context.__code__.co_consts if getattr(x,'co_name',None)=='fence')
        self.assertIn('_recovery_actual_authorities',nested.co_names)

    def test_fifo_input_is_rejected_without_blocking(self):
        import os,tempfile
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'fifo';os.mkfifo(path)
            with self.assertRaisesRegex(ValueError,'regular'):self.a.protected(path,'a'*64)

class AuthorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_authority_gets_must_match_full_immutable_chain(self):
        import qualified_recovery_expiry_adapter as a
        history,_,_=future_fixture()
        values={(x['metadata']['name'],x['metadata']['namespace']):copy.deepcopy(x) for x in (history['recovery'][k]for k in ('enrollment','audit','cleanup'))}
        class Core:
            def read_namespaced_config_map(self,name,namespace):return copy.deepcopy(values[name,namespace])
        class Backend:
            core=Core()
            async def _call(self,fn,*args):return fn(*args)
            async def cleanup_receipt(self,binding):return copy.deepcopy(history['recovery']['marker']['receipt'])
        state=copy.deepcopy(history['recovery']['plan']['ledger']);state=json.loads(state['data']['state.json'])
        state['allocations'][a.r.BINDING]['state']='released'
        await a.actual_authorities(Backend(),history,state)
        for key,value in [('principal','workspace:cit:wrong'),('profile','interactive-native-qualification-10'),('actor','cit'),('members',[])]:
            altered=copy.deepcopy(state);altered['allocations'][a.r.BINDING][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact historical'):await a.actual_authorities(Backend(),history,altered)
        values[next(key for key in values if key[0].startswith('cps-native-recovery-'))]['metadata']['uid']='00000000-0000-4000-8000-000000000001'
        with self.assertRaises(ValueError):await a.actual_authorities(Backend(),history,state)

    async def genuine_context(self, *, changed_original21=False, changed_audit=False, releasing=False):
        """Execute genuine792+3c807 reset and every runtime fence before Source."""
        import base64
        from unittest.mock import patch
        from kubernetes import client,config
        import qualified_restart_window as window
        import qualified_recovery_expiry_adapter as adapter
        import test_qualified_restart_window as old
        import recovery_source_loader as loader
        history,_,inventory=future_fixture()
        qualified_raw=(old.WINDOW/'qualified_expiry.py').read_bytes()
        q=window.load_frozen(qualified_raw,(old.WINDOW/'renew_fixtures.py').read_bytes(),str(old.WINDOW/'qualified_expiry.py'))
        adapter.adapt_foundation(q,qualified_raw,history,loader.load_sources(fixture_module.SourceLoaderTests().sources()),'d'*64,'ghcr.io/mul-cps/cps-compute@sha256:'+'e'*64)
        ns=q.build_context.__globals__;original_install=ns['install_base'];discarded=ns['R']
        index=json.loads((old.SESSION/'expiry-runtime-captures/index.json').read_bytes())
        objects={name:json.loads(Path(ref['path']).read_bytes())for name,ref in index['objects'].items()}
        stage=json.loads((old.SESSION/'operator-stage/cit-stage-current.json').read_bytes())['files']
        policy=json.loads(base64.b64decode(stage['policy.json']['base64']));mode=json.loads(base64.b64decode(stage['operator-qualification.json']['base64']))
        runtime=json.loads((old.SESSION/'expiry-runtime-assembled/cit-runtime.json').read_bytes())
        baseline=json.loads(json.loads((old.SESSION/'qualified-expiry-final/ledger-final.json').read_bytes())['data']['state.json'])
        state=json.loads(history['recovery']['plan']['ledger']['data']['state.json'])
        state['allocations'][adapter.r.BINDING]['state']='releasing' if releasing else 'released'
        if changed_original21:
            key=next(iter(baseline['allocations']));state['allocations'][key]['actor']='changed'
        objects['ledger']['data']['state.json']=window.canonical(state)
        runtime.update(ledger_state_sha256=window.digest(state),expected_allocation_count=len(state['allocations']))
        runtime['gateway']['image_id']=ns['GATEWAY_IMAGE']
        for status in objects['gateway']['status']['containerStatuses']:
            if status['name']=='gateway':status['imageID']=ns['GATEWAY_IMAGE']
        objects['node_code_cm']['data']['node_agent.py']=(fixture_module.NODE/'node_agent.py').read_text()
        runtime['node']['code_data_sha256']=q.sha(objects['node_code_cm']['data'])
        for key in ('enrollment','audit','cleanup'):objects['recovery_'+key+'_cm']=copy.deepcopy(history['recovery'][key])
        if changed_audit:objects['recovery_audit_cm']['metadata']['uid']='00000000-0000-4000-8000-000000000001'
        now=datetime.now(timezone.utc);review=old.review_fixture(window,'cit',now)
        review.update(operation='restore-expiry',current_full_sha256=None,cycle_provenance_sha256={k:'f'*64 for k in ('before_full','after_full','receipt')})
        fixture_module.HistoryTests.setUpClass()
        physical={'kind':'native-group-host-observation','targets':[],**{k:history[k]for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')},'retired_caps':fixture_module.HistoryTests().observe(history,inventory)}
        retirement={'version':2,'state':'source-close-and-physical-inert-history-root-reviewed','source':'cit','observed_at':now.isoformat(),'policy_hash':q.POLICY,'ledger_uid':q.R.BASE_LEDGER_UID,'ledger_state_sha256':window.digest(state),'normal_close_receipt_sha256':'d'*64,'protected_retirement_capture_sha256':'e'*64,'history_raw_sha256':'d'*64,'all_native_released':True,'physical_inert_history_verified':True,'historical_recovery_uid':adapter.r.POD,'normal_stop_passed':False,'hardware_qualification':False}
        docs={'runtime':runtime,'retirement':retirement,'physical':physical,'policy':policy,'mode':mode,'nodeconf':json.loads(objects['node_config_cm']['data']['config.json']),'closure':{}}
        source_loads=[]
        helper=b"import json\ndef decode(raw):return json.loads(raw)\ndef verify_source_closure(value):pass\ndef load_configured_service(*a,**kw):\n SOURCE_LOADS.append(True)\n return type('CPUApp',(),{'tornado_settings':{'boundary':True}})(),None\n"
        # Provide a sentinel through builtins only inside the CPU Source boundary.
        import builtins
        audit_raw=(old.PRIVATE/'native-packing-operator-prepared/old-hub-barrier-audit-prepared/audit_old_hub.py').read_bytes()
        def protected(path,pin):
            if path==str(old.WINDOW/'qualified_expiry.py'):return qualified_raw
            if path=='renewal':return (old.WINDOW/'renew_fixtures.py').read_bytes()
            if path=='handover':return helper
            if path=='audit':return audit_raw
            return json.dumps(docs.get(path,{})).encode()
        def genuine_install(raw):
            original_install(raw);ns['R'].load.__globals__['protected']=protected
        pods={(x['metadata']['namespace'],x['metadata']['name']):x for name,x in objects.items()if name.endswith('_operator')or name.endswith('_hub')or name in ('node','gateway')}
        cms={(x['metadata']['namespace'],x['metadata']['name']):x for name,x in objects.items()if name.endswith('_cm')or name=='ledger'}
        deployments={(x['metadata']['namespace'],x['metadata']['name']):x for name,x in objects.items()if name in ('cps_admin','cit_admin')}
        configured=[];gets=[]
        class Core:
            def __init__(self):self_unused=configured==['scoped'];self_outer.assertTrue(self_unused)
            def read_namespaced_pod(self,name,namespace,**kw):
                if(namespace,name)not in pods:raise type('Absent',(Exception,),{'status':404})()
                return copy.deepcopy(pods[namespace,name])
            def read_namespaced_config_map(self,name,namespace,**kw):gets.append(name);return copy.deepcopy(cms[namespace,name])
            def list_namespaced_pod(self,namespace,label_selector=None,**kw):return copy.deepcopy(objects['cps_admin_pods'if label_selector=='app=cps-admin'else'cit_admin_pods'])
        class Apps:
            def __init__(self):self_outer.assertEqual(configured,['scoped'])
            def read_namespaced_deployment(self,name,namespace,**kw):return copy.deepcopy(deployments[namespace,name])
        self_outer=self
        args=SimpleNamespace(source='cit',source_sha256='f'*64,renewal='renewal',handover='handover',audit_helper='audit',source_closure='closure',source_closure_sha256='f'*64,policy='policy',policy_sha256='f'*64,qualification_config='mode',qualification_config_sha256='f'*64,node_config='nodeconf',node_config_sha256='f'*64,physical_retirement_review='retirement',normal_close_receipt='close',protected_retirement_capture='physical',kubeconfig='scoped',kubeconfig_sha256='f'*64,runtime_review='runtime',config='app',config_sha256='f'*64,handover_receipt='handover-receipt',capture=True)
        with patch.dict(ns,{'protected':protected,'install_base':genuine_install}),patch.object(client,'CoreV1Api',Core),patch.object(client,'AppsV1Api',Apps),patch.object(config,'load_kube_config',lambda **kw:configured.append(kw['config_file'])),patch.object(builtins,'SOURCE_LOADS',source_loads,create=True):
            if changed_original21 or changed_audit or releasing:
                with self.assertRaises(ValueError):await window.build_context(args,review,baseline,q,{'renewed_expires':'2026-10-11T19:00:00+00:00'})
                self.assertEqual(source_loads,[])
            else:
                settings,fence,_=await window.build_context(args,review,baseline,q,{'renewed_expires':'2026-10-11T19:00:00+00:00'})
                self.assertEqual(settings,{'boundary':True});self.assertEqual(source_loads,[True])
                expected=history['recovery']['audit']['metadata']['name'];before=gets.count(expected)
                self.assertGreater(before,0);await fence();self.assertGreater(gets.count(expected),before)
            self.assertIsNot(q.R,discarded);self.assertIs(q.R,ns['R'])

    async def test_genuine_context_authenticates_recovery_before_source_and_each_fence(self):await self.genuine_context()
    async def test_genuine_context_rejects_changed_original21_before_source(self):await self.genuine_context(changed_original21=True)
    async def test_genuine_context_rejects_changed_actual_audit_before_source(self):await self.genuine_context(changed_audit=True)
    async def test_genuine_context_rejects_unreleased_historical_allocation_before_source(self):await self.genuine_context(releasing=True)

if __name__=='__main__':unittest.main()
