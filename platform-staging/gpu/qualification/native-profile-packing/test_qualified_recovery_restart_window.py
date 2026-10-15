"""CPU-only recovery-aware expiry cycle; no fixture is live qualification."""
import copy
import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import qualified_restart_window as old
import qualified_recovery_expiry_adapter as inverse
import test_qualified_restart_window as old_tests
from test_qualified_restart_window import fixture
import test_recovery_history as history_tests

HERE = Path(__file__).parent


def module():
    path = HERE / 'qualified_recovery_restart_window.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('recovery_restart_test', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def ledger():
    history, _, _ = history_tests.future_fixture()
    result = copy.deepcopy(history['recovery']['plan']['ledger'])
    state = json.loads(result['data']['state.json'])
    state['allocations'][inverse.r.BINDING]['state'] = 'released'
    result['data']['state.json'] = old.canonical(state)
    return result


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertIsNotNone(self.m, 'Recovery-aware forward renewal bridge is missing')
        self.ledger = ledger()
        self.state = json.loads(self.ledger['data']['state.json'])

    def test_released23_preimage_accepts_exact_history_and_rejects_growth(self):
        self.m.current_ledger(self.ledger, self.state)
        for change in ('active', 'body', 'missing', 'growth', 'uid', 'rv'):
            altered = copy.deepcopy(self.ledger)
            state = copy.deepcopy(self.state)
            key = next(iter(state['allocations']))
            if change == 'active': state['allocations'][key]['state'] = 'releasing'
            if change == 'body': state['allocations'][key]['principal'] = 'foreign'
            if change == 'missing': state['allocations'].pop(key)
            if change == 'growth': state['allocations']['f' * 60] = state['allocations'][key]
            if change == 'uid': altered['metadata']['uid'] = 'foreign'
            if change == 'rv': altered['metadata']['resourceVersion'] = 'changed'
            altered['data']['state.json'] = old.canonical(state)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.m.current_ledger(altered, self.state, expected=self.ledger)

    def test_complete_source_baseline_preserves_every_nonexpiry_leaf(self):
        before = fixture('cps')
        self.m.expired_baseline('cps', before, before)
        def leaves(value, path=()):
            if isinstance(value, dict):
                for key, item in value.items(): yield from leaves(item, path + (key,))
            elif isinstance(value, list):
                for key, item in enumerate(value): yield from leaves(item, path + (key,))
            else: yield path
        for path in leaves(before):
            if path[0] == 'actor_model': continue
            mutated = copy.deepcopy(before)
            row = mutated
            for key in path[:-1]: row = row[key]
            row[path[-1]] = 'changed'
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.m.expired_baseline('cps', before, mutated)

    def test_wrong_source_admin_profile_storage_alias_and_active_server_reject(self):
        for source in ('cps', 'cit'):
            original = fixture(source)
            for mutate in (lambda x: x['actor_model'].update(admin=False),
                           lambda x: x['actor_model'].update(name='foreign'),
                           lambda x: x['records']['workspaces'][0].update(profile='interactive-cpu'),
                           lambda x: x['records']['workspaces'][0].update(storage={'pvc': 'foreign'}),
                           lambda x: x['aliases'].clear(),
                           lambda x: x['servers'].update(foreign={'ready': True})):
                changed = copy.deepcopy(original); mutate(changed)
                with self.subTest(source=source), self.assertRaises(ValueError):
                    self.m.expired_baseline(source, original, changed)
        with self.assertRaises(ValueError): self.m.expired_baseline('foreign', fixture('cps'), fixture('cps'))

    def test_fresh_physical_review_retains_distinct17_12_exception(self):
        import test_recovery_expiry_adapter as tests
        setup = tests.AdapterTests(); setup.setUp()
        runtime, review, physical = setup.physical()
        self.m.physical_review(review, physical, setup.history, runtime, 'cit', 'd' * 64)
        for key, value in (('observed_at', (datetime.now(timezone.utc)-timedelta(seconds=601)).isoformat()),
                           ('normal_stop_passed', True), ('hardware_qualification', True),
                           ('historical_recovery_uid', 'foreign')):
            changed = copy.deepcopy(review); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.m.physical_review(changed, physical, setup.history, runtime, 'cit', 'd' * 64)
        changed = copy.deepcopy(physical); changed['retired_caps'].pop()
        with self.assertRaises(ValueError): self.m.physical_review(review, changed, setup.history, runtime, 'cit', 'd' * 64)

    def test_default_inert_opens_no_external_inputs(self):
        with patch.object(self.m, 'protected', side_effect=AssertionError('opened')), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.m.main(['--history', '/missing']), 0)
        self.assertEqual(json.loads(out.getvalue())['state'], 'inert')

    def test_actual_inverse_before_after_receipt_must_bind_complete_expired_baseline(self):
        self.assertTrue(hasattr(self.m, 'inverse_baseline'), 'Actual inverse baseline validator is missing')
        source = 'cit'; baseline = fixture(source); before = old.changed(source, baseline, '2026-10-11T19:40:00+00:00')
        native = {'operator_uid':'cpu','gateway_uid':'cpu','hub_uids':['cpu','cpu'], 'node_uid':'cpu',
                  'policy_hash':inverse.POLICY,'ledger_uid':self.ledger['metadata']['uid'],
                  'ledger_resource_version':self.ledger['metadata']['resourceVersion'],'ledger_state':self.state,'pod_absent':True}
        receipt = {'version':1,'state':'selected-qualified-expiry-restored-read-back','operation':'restore-expiry',
            'source':source,'actor':'akadmin','cycle_id':'00000000-0000-4000-8000-000000000001',
            'renewed_at':'2026-10-11T22:00:00+00:00','renewed_expires':'2026-10-11T19:40:00+00:00',
            'changes':old.changes(before,baseline),'qualification':False,'workspace_started':False,
            'profiles_and_ceiling_preserved':True,'before_full_sha256':old.digest(before),
            'after_full_sha256':old.digest(baseline),'runtime_before':native,'registration_sha256':'sha256:'+old.digest({'storage':'kept'})}
        self.m.inverse_baseline(source,baseline,before,baseline,receipt,self.state,{'storage':'kept'},self.ledger['metadata']['uid'])
        for mutate in (lambda x:x.update(source='cps'), lambda x:x.update(state='incomplete'),
                       lambda x:x.update(after_full_sha256='f'*64), lambda x:x['changes'].pop(),
                       lambda x:x['runtime_before'].update(pod_absent=False), lambda x:x.update(registration_sha256='sha256:'+'e'*64)):
            changed=copy.deepcopy(receipt);mutate(changed)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                self.m.inverse_baseline(source,baseline,before,baseline,changed,self.state,{'storage':'kept'},self.ledger['metadata']['uid'])

    def test_bridge_ledger_preserves_original21_and_uses23_for_forward(self):
        self.assertTrue(hasattr(self.m, 'ledger_guard'), 'Forward23 loader guard is missing')
        private=old_tests.SESSION/'qualified-expiry-final/ledger-final.json'
        original=json.loads(json.loads(private.read_bytes())['data']['state.json'])
        q=old.load_frozen((old_tests.WINDOW/'qualified_expiry.py').read_bytes(),(old_tests.WINDOW/'renew_fixtures.py').read_bytes())
        runtime={'ledger_uid':q.R.BASE_LEDGER_UID,'ledger_state_sha256':old.digest(self.state),'expected_allocation_count':23}
        bound=self.m.binding('cit',fixture('cit'),self.ledger,'d'*64)
        self.m.ledger_guard(old,bound,self.state,original,'renew',runtime,q)
        for key in self.state['allocations']:
            mutated=copy.deepcopy(self.state);mutated['allocations'][key]['principal']='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.m.ledger_guard(old,bound,mutated,original,'renew',runtime,q)


class SourceBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_genuine_reset_context_refreshes_extra_named_ledger_before_source_and_each_fence(self):
        m=module();self.assertIsNotNone(m)
        self.assertTrue(hasattr(m,'add_authority_preimage'), 'Actual pre-Source ledger wrapper is missing')
        import test_recovery_expiry_adapter as tests
        actual=json.loads((old_tests.SESSION/'expiry-runtime-captures/index.json').read_bytes())['objects']['ledger']['path']
        expected=json.loads(Path(actual).read_bytes());state=json.loads(ledger()['data']['state.json']);expected['data']['state.json']=old.canonical(state)
        bound=m.binding('cit',fixture('cit'),expected,'d'*64)
        original_adapt=inverse.adapt_foundation; original_ledger=old.ledger_guard;queries=[]
        original_current=m.current_ledger
        def adapt(*args,**kwargs):
            q=original_adapt(*args,**kwargs)
            m.add_authority_preimage(q,bound)
            return q
        def guarded(state,baseline,operation,review,q,**kw):
            return m.ledger_guard(old,bound,state,baseline,operation,review,q,original=original_ledger,**kw)
        test=tests.AuthorityTests('test_actual_authority_gets_must_match_full_immutable_chain')
        def observed(*args,**kwargs):
            queries.append('ledger');return original_current(*args,**kwargs)
        with patch.object(inverse,'adapt_foundation',adapt),patch.object(old,'ledger_guard',guarded),patch.object(m,'current_ledger',observed):
            await test.genuine_context()
        self.assertGreaterEqual(len(queries),2)


class CliTests(unittest.TestCase):
    def test_protected_forward_bridge_reaches_frozen_guard_without_source_or_api(self):
        m=module();self.assertIsNotNone(m)
        history,_,_=history_tests.future_fixture()
        raw=lambda v:old.canonical(v).encode()
        sha=lambda v:__import__('hashlib').sha256(v).hexdigest()
        files={'history':raw(history),'after':raw(fixture('cit')),'before':raw(fixture('cit')),
               'receipt':raw({'pending':'not reached until complete frozen CLI supplied'}),'ledger':raw(ledger())}
        source=Path(m.__file__); files[str(source)]=source.read_bytes()
        for value in (old,inverse,inverse.r,inverse.loader,inverse.prepare,inverse.prepare.p):files[str(Path(value.__file__))]=Path(value.__file__).read_bytes()
        review={'version':1,'enabled':True,'operation':'renew','source':'cit','gateway_image':'ghcr.io/mul-cps/cps-compute@sha256:'+'e'*64,
            'history_raw_sha256':sha(files['history']),'adapter_sha256':sha(files[str(source)]),
            'reader_sha256':sha(files[str(Path(inverse.r.__file__))]),'loader_sha256':sha(files[str(Path(inverse.loader.__file__))]),
            'node_source_sha256':inverse.ACTIVE_AGENT_SHA,'historical_node_source_sha256':inverse.HISTORICAL_AGENT_SHA,
            'recovery_source_sha256':inverse.RECOVERY_SHA,'window_source_sha256':inverse.WINDOW_SHA,'inverse_source_sha256':m.INVERSE_SHA,
            'baseline_after_raw_sha256':sha(files['after']),'baseline_before_raw_sha256':sha(files['before']),
            'baseline_inverse_receipt_raw_sha256':sha(files['receipt']),'baseline_ledger_raw_sha256':sha(files['ledger']),
            'baseline_full_sha256':old.digest(fixture('cit')),'baseline_state_sha256':old.digest(json.loads(ledger()['data']['state.json']))}
        files['review']=raw(review)
        argv=['--execute','--bridge-sha256',sha(files[str(source)]),'--bridge-review','review','--bridge-review-sha256',sha(files['review']),
            '--history','history','--history-sha256',sha(files['history']),'--window-source',str(Path(old.__file__)),
            '--post-inverse-before','before','--post-inverse-before-sha256',sha(files['before']),
            '--post-inverse-after','after','--post-inverse-after-sha256',sha(files['after']),
            '--post-inverse-receipt','receipt','--post-inverse-receipt-sha256',sha(files['receipt']),
            '--current-baseline-ledger','ledger','--current-baseline-ledger-sha256',sha(files['ledger']),
            '--model-source','model','--control-source','control','--node-source','historical','--recovery-source','helper']
        def protected(path,pin):
            result=files[str(path)]
            if sha(result)!=pin:raise ValueError('pinned import drift')
            return result
        with patch.object(m.os,'geteuid',return_value=10001),patch.object(m,'protected',protected),patch.object(inverse.prepare,'bundle',return_value=history_tests.SourceLoaderTests().sources()),patch.object(m,'verify_sdk',create=True):
            with self.assertRaisesRegex(ValueError,'complete actual protected inputs'):m.main(argv)
            files['imported-drift']=b'foreign imported foundation'
            with patch.object(old,'__file__','imported-drift'),self.assertRaisesRegex(ValueError,'pinned import drift'):
                m.main(argv)
            for field,value in (('source','foreign'),('operation','start'),('window_source_sha256','f'*64),('baseline_state_sha256','f'*64),('node_source_sha256',inverse.HISTORICAL_AGENT_SHA)):
                changed=copy.deepcopy(review);changed[field]=value;files['review']=raw(changed)
                bad=list(argv);bad[bad.index('--bridge-review-sha256')+1]=sha(files['review'])
                with self.subTest(field=field),self.assertRaises(ValueError):m.main(bad)



class CrudTests(unittest.IsolatedAsyncioTestCase):
    source = 'cit'

    async def asyncSetUp(self):
        await old_tests.GenuineCrudTests.asyncSetUp(self)
        self.bridge = module()
        self.assertIsNotNone(self.bridge, 'Recovery-aware forward renewal bridge is missing')
        self.fresh_ledger = ledger()
        self.state = json.loads(self.fresh_ledger['data']['state.json'])
        self.native['ledger_state'] = self.state
        self.native['ledger_resource_version'] = self.fresh_ledger['metadata']['resourceVersion']
        self.binding = self.bridge.binding(self.source, self.baseline, self.fresh_ledger, 'd' * 64)

    async def fence(self): return copy.deepcopy(self.native)
    async def register(self): return await old_tests.GenuineCrudTests.register(self)

    async def runop(self):
        out = self.path / ('bridge' + str(len(list(self.path.iterdir())))); out.mkdir(); self.last_out = out
        return await self.bridge.apply(self.m, self.binding, self.settings, self.review, out, self.fence, self.register, self.q, clock=lambda: self.now)

    async def test_genuine_four_field_crud_and_actor_audit_preserve_every_other_field(self):
        from e2x_course_hub.cps.audit import actor_context
        audit = self.provider.audit()
        receipt = await self.runop()
        self.assertEqual(receipt['version'], 2)
        self.assertEqual(receipt['state'], 'recovery-history-selected-expiry-renewed-read-back')
        self.assertEqual(receipt['baseline_ledger_state_sha256'], old.digest(self.state))
        self.assertEqual(receipt['history_raw_sha256'], 'd' * 64)
        self.assertIsNone(actor_context.get())
        self.assertEqual(len(receipt['changes']), 4)
        self.assertEqual(await self.q.R.capture(self.settings, self.source), old.changed(self.source, self.baseline, self.review['renewed_expires']))
        self.assertEqual([(x['actor'], x['kind']) for x in self.provider.audit()[len(audit):]],
                         [(old.ACTORS[self.source], 'memberships')] * 2 + [(old.ACTORS[self.source], 'compute-grants')] * 2)

    async def test_own_cycle_inverse_accepts23_and_restores_only_own_expiry_fields(self):
        receipt = await self.runop(); before = json.loads((self.last_out/'before-full.json').read_bytes()); after = json.loads((self.last_out/'after-full.json').read_bytes())
        self.bridge.cycle_guard(self.m, self.binding, before, after, receipt, self.review, self.registration)
        self.review.update(operation='restore-expiry', current_full_sha256=old.digest(after), cycle_provenance_sha256={k: 'e'*64 for k in ('before_full','after_full','receipt')})
        self.now += timedelta(hours=2); self.review['observed_at'] = self.now.isoformat()
        restored = await self.runop()
        self.assertEqual(restored['state'], 'recovery-history-selected-expiry-restored-read-back')
        self.assertEqual(await self.q.R.capture(self.settings, self.source), self.baseline)

    async def test_old_foreign_incomplete_changed_cycle_cannot_authorize_inverse(self):
        receipt = await self.runop(); before = json.loads((self.last_out/'before-full.json').read_bytes()); after = json.loads((self.last_out/'after-full.json').read_bytes())
        for mutate in (lambda x: x.update(version=1), lambda x: x.update(source='foreign'),
                       lambda x: x.update(state='incomplete'), lambda x: x.update(cycle_id='foreign'),
                       lambda x: x.update(history_raw_sha256='e'*64), lambda x: x['changes'].pop(),
                       lambda x: x['runtime_before'].update(ledger_state=self.baseline_state),
                       lambda x: x.update(registration_sha256='sha256:'+'f'*64)):
            changed = copy.deepcopy(receipt); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.bridge.cycle_guard(self.m, self.binding, before, after, changed, self.review, self.registration)

    async def test_overlong_window_stale_review_and_active_native_deny_before_crud(self):
        for field, value in (('renewed_expires',(self.now+timedelta(seconds=3601)).isoformat()),
                             ('observed_at',(self.now-timedelta(seconds=601)).isoformat())):
            prior = self.review[field]; self.review[field] = value
            with self.assertRaises(ValueError): await self.runop()
            self.review[field] = prior; self.assertEqual(self.calls, [])
        key = next(iter(self.native['ledger_state']['allocations']))
        self.native['ledger_state']['allocations'][key]['state'] = 'releasing'
        with self.assertRaises(ValueError): await self.runop()
        self.assertEqual(self.calls, [])

    async def test_real_partial_write_failure_needs_fresh_full_review_and_resumes(self):
        request = self.compute._request
        async def fail(path, method='GET', payload=None):
            if method == 'PUT': raise ConnectionError('CPU transport failure')
            return await request(path, method, payload)
        self.compute._request = fail
        with self.assertRaises(ConnectionError): await self.runop()
        self.assertEqual(json.loads((self.last_out/'receipt.json').read_bytes())['state'], 'incomplete')
        self.assertEqual(self.calls, [])
        self.compute._request = request
        with self.assertRaises(ValueError): await self.runop()
        self.review['current_full_sha256'] = old.digest(await self.q.R.capture(self.settings,self.source))
        receipt = await self.runop()
        self.assertEqual(len(receipt['changes']), 2)
        self.assertEqual(len(self.calls), 2)


class CpsCrudTests(CrudTests):
    source = 'cps'
