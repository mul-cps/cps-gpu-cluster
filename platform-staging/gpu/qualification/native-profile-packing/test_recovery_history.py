"""CPU-only future recovery fixtures made from the preserved actual failed capture.

The synthetic terminal/audit/cleanup/marker below are NEVER execution evidence.
"""
import copy
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

HERE = Path(__file__).parent
CAPTURE = Path('/home/bjoern/.local/state/cps-platform-completion-20261011/restart-session-20261011T190822Z/recovery-current-capture-20261011T1954')
NODE = Path('/home/bjoern/git/cps-gpu-cluster-worktrees/native-cleared-offline-recovery-20261011/platform-staging/gpu/native-group-pilot')
POD = '8066366f-6e7e-42ea-83b2-86a58e9c3bad'
BINDING = '16d264e00ee6778319a8961f9da510147c3bebc925e674bf95880689cd25'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()

def body_sha(value):
    return sha(canonical(value).encode())

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result

def future_fixture():
    from cps_compute import native_gpu_controller as models
    host_raw = (CAPTURE / 'host-records.json').read_bytes()
    assert sha(host_raw) == 'sha256:0076ef26a0198b422879a23262da90b7e8d667ff29254f72f0b124ae7ac136b3'
    host = json.loads(host_raw)
    records = [dict(pod_uid=name[:-5], journal_sha256=row['rawSha256'], record=row['value'])
               for name, row in host['directories']['journal']['records'].items()]
    original = next(row['record'] for row in records if row['pod_uid'] == POD)
    inventory = json.loads((CAPTURE / 'physical-inventory.json').read_text())['inventory']
    enrollment = json.loads((CAPTURE / 'enrollment.json').read_text())
    writers = {}
    for number, name in enumerate(('cps-admin', 'cit-admin', 'compute-gateway'), 1):
        writers[name] = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
            'metadata': {'namespace': 'cps-compute', 'name': name,
                'uid': '00000000-0000-4000-8000-' + str(number).zfill(12),
                'generation': 1}, 'spec': {'replicas': 0,
                'selector': {'matchLabels': {'app': name}}},
            'status': {'observedGeneration': 1}}
    operation = '00000000-0000-4000-8000-000000000999'
    plan = {'version': 1, 'protocol': 'cleared-offline-recovery-plan/v1',
        'operation_id': operation, 'node_config_sha256': 'sha256:' + 'a' * 64,
        'original': original, 'original_raw_sha256': sha((canonical(original) + '\n').encode()),
        'inventory': inventory, 'enrollment': enrollment,
        'ledger': json.loads((CAPTURE / 'ledger.json').read_text()),
        'journal_sha256s': {row['pod_uid']: body_sha(row['record']) for row in records},
        'physical_pods': [row['pod_uid'] for row in records if row['record']['state'] != 'cleaned'],
        'writers': writers}
    review = {'version': 1, 'operation_id': operation, 'plan_sha256': body_sha(plan),
        'issued_at': '2026-10-11T19:54:00Z', 'expires_at': '2026-10-11T20:00:00Z',
        'approved': True, 'exclusive_operator_custody': True,
        'no_alternate_writer_or_release': True, 'normal_stop_passed': False,
        'production_qualified': False,
        'credential': {'namespace': 'cps-native-system',
            'service_account': 'cps-native-cleared-offline-recovery',
            'service_account_uid': '00000000-0000-4000-8000-000000000996',
            'pod_name': 'cpu-only-credential', 'pod_uid': '00000000-0000-4000-8000-000000000995',
            'pod_spec_sha256': 'sha256:' + 'b' * 64, 'api_server': 'https://cpu.invalid:6443',
            'audience': 'cpu-only', 'token_sha256': 'sha256:' + 'c' * 64,
            'ca_sha256': 'sha256:' + 'd' * 64}}
    e = json.loads(enrollment['data']['enrollment.json'])
    proof = models.validate_cleared_offline_inventory(inventory, models.CapRecord.from_dict(original),
        binding_id=BINDING, attempt=e['attempt'], enrollment_uid=enrollment['metadata']['uid'],
        enrollment_sha256=body_sha(e), journal_raw=(canonical(original) + '\n').encode(),
        operation_id=operation, plan_sha256=body_sha(plan), review_sha256=body_sha(review))
    terminal = {**original, 'state': 'recovered-cleared-offline-cap', 'recovery': proof.to_dict()}
    terminal_row = dict(pod_uid=POD, journal_sha256=sha((canonical(terminal) + '\n').encode()), record=terminal)
    records = [terminal_row if row['pod_uid'] == POD else row for row in records]
    audit_body = {'version': 1, 'binding_id': BINDING, 'attempt': e['attempt'],
        'proof': proof.to_dict(), 'enrollment_uid': enrollment['metadata']['uid'],
        'enrollment_sha256': body_sha(e), 'journal_sha256': body_sha(terminal)}
    def cm(prefix, key, value, uid):
        return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'namespace': 'cps-native-system', 'name': prefix + BINDING[:40],
                'uid': uid, 'labels': {'cps.compute/native-binding': BINDING}},
            'data': {key: canonical(value)}}
    audit = cm('cps-native-recovery-', 'recovery.json', audit_body,
               '00000000-0000-4000-8000-000000000997')
    receipt = {'version': 1, 'binding_id': BINDING, 'attempt': e['attempt'],
        'intent': e['intent'], 'cleanup_confirmed': True,
        'recovery': {'proof': proof.to_dict(), 'enrollment_uid': enrollment['metadata']['uid'],
            'enrollment_sha256': body_sha(e), 'journal_sha256': body_sha(terminal),
            'audit_uid': audit['metadata']['uid'], 'audit_sha256': body_sha(audit_body)}}
    cleanup = cm('cps-native-cleanup-', 'receipt.json', receipt,
                 '00000000-0000-4000-8000-000000000998')
    marker = {'enrollment_uid': enrollment['metadata']['uid'],
        'receipt_uid': cleanup['metadata']['uid'], 'receipt': receipt}
    pool = {'node': original['intent']['node'], **asdict(proof.epoch)}
    history = {'version': 2, 'protocol': 'native-packing-terminal-history/v2', **pool,
        'controller_sha256': '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880',
        'records': records,
        'recovery': {'original_raw': canonical(original) + '\n', 'plan': plan, 'review': review,
                     'enrollment': enrollment, 'audit': audit, 'cleanup': cleanup, 'marker': marker,
                     'protected_raw_sha256': {k: sha((canonical(v) + '\n').encode()) for k, v in
                         [('plan', plan), ('review', review), ('marker', marker)]}}}
    binding = {'pool': pool, 'targets': []}
    return history, binding, inventory

class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CAPTURE / 'host-records.json').exists():
            raise unittest.SkipTest('Actual protected Oct11 CPU replay inputs unavailable')
        cls.agent = module('reviewed_node_history_test', NODE / 'node_agent.py')
        cls.codec = module('reviewed_recovery_history_test', NODE / 'cleared_offline_recovery.py')
        path = HERE / 'recovery_history.py'
        if path.exists():
            cls.reader = module('recovery_history', path)
        else:
            old = module('old_history_reader', HERE / 'prepare_harness.py')
            cls.reader = SimpleNamespace(validate_history=lambda value, binding, **_: old.validate_retired(value, binding))

    def validate(self, history, binding):
        return self.reader.validate_history(history, binding, agent=self.agent, recovery_codec=self.codec)

    def test_actual_original_mixed_history_accepts_distinct_cpu_recovery(self):
        history, binding, _ = future_fixture()
        try:
            result = self.validate(history, binding)
        except ValueError as exc:
            self.fail('The authenticated historical exception has no reader: ' + str(exc))
        self.assertEqual(len(result['finite']), 11)
        self.assertEqual(len(result['cleaned']), 5)
        self.assertEqual(result['recovered']['pod_uid'], POD)
        self.assertFalse(result['normal_stop_passed'])

    def test_missing_mutable_swapped_or_owned_authority_denied(self):
        for key in ('enrollment', 'audit', 'cleanup'):
            for change in ('mutable', 'uid', 'owner', 'missing', 'body'):
                history, binding, _ = future_fixture()
                cm = history['recovery'][key]
                if change == 'mutable': cm['immutable'] = False
                elif change == 'uid': cm['metadata']['uid'] = '00000000-0000-4000-8000-000000000001'
                elif change == 'owner': cm['metadata']['ownerReferences'] = [{}]
                elif change == 'missing': history['recovery'][key] = None
                else: cm['data'][next(iter(cm['data']))] = '{}'
                with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                    self.validate(history, binding)

    def test_original_16_journals_and_archive_cannot_be_rehashed_away(self):
        for change in ('finite', 'cleaned', 'missing', 'extra-recovery', 'archive', 'marker'):
            history, binding, _ = future_fixture()
            if change in ('finite', 'cleaned'):
                state = 'retired-inert-cap' if change == 'finite' else 'cleaned'
                row = next(row for row in history['records'] if row['record']['state'] == state)
                row['record']['seal_id'] = '00000000-0000-4000-8000-000000000001'
                row['journal_sha256'] = sha((canonical(row['record']) + '\n').encode())
            elif change == 'missing': history['records'].pop()
            elif change == 'extra-recovery': history['records'].append(copy.deepcopy(next(row for row in history['records'] if row['pod_uid'] == POD)))
            elif change == 'archive': history['recovery']['original_raw'] += '\n'
            else: history['recovery']['marker']['receipt_uid'] = '00000000-0000-4000-8000-000000000001'
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate(history, binding)

    def test_recovery_can_never_be_a_current_target(self):
        history, binding, _ = future_fixture(); binding['targets'] = [{'pod_uid': POD}]
        with self.assertRaises(ValueError): self.validate(history, binding)

    def test_plan_review_original_cap_identity_and_scope_mutations_denied(self):
        for key in ('approved', 'normal_stop_passed', 'production_qualified', 'operation_id', 'plan_sha256'):
            history, binding, _ = future_fixture()
            history['recovery']['review'][key] = False if key == 'approved' else True
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(history, binding)

    def test_current_inventory_may_add_active_new_lifetimes(self):
        history, binding, inventory = future_fixture()
        self.validate(history, binding)
        inventory = copy.deepcopy(inventory)
        inventory['entries'].append({'cgroup_id': 1999999, 'kernfs_id': 1999999, 'inode': 1999999,
            'offline': False, 'pinned': True, 'default_hierarchy': True,
            'soft': 5120 * 1048576, 'hard': 5120 * 1048576, 'used': 1048576})
        self.assertEqual(self.reader.validate_physical(history, inventory, active_inodes={1999999}), 12)

    def test_current_recovery_row_drift_or_unbound_inventory_denied(self):
        for key, value in [('used', 1), ('offline', False), ('pinned', False), ('soft', 1), ('hard', 5120 * 1048576), ('inode', 42)]:
            history, binding, inventory = future_fixture()
            target = next(row for row in inventory['entries'] if row['inode'] == 1390814)
            target[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.reader.validate_physical(history, inventory)

    def observe(self, history, inventory, *, corrupt=None):
        from cps_compute import native_gpu_controller as models, native_gpu_control as control
        root = '/run/cps-native-gpu/'; closure = history['recovery']
        proof = next(row['record']['recovery'] for row in history['records'] if row['pod_uid'] == POD)
        files = {root + 'journal/' + row['pod_uid'] + '.json': (canonical(row['record']) + '\n').encode()
                 for row in history['records']}
        files[root + 'journal/recovery-originals/' + POD + '.' + proof['operation_id'] + '.json'] = closure['original_raw'].encode()
        for name in ('plan', 'review'):
            files[root + 'operator/cleared-offline-recovery/' + proof['operation_id'] + '/' + name + '.json'] = (canonical(closure[name]) + '\n').encode()
        files[root + 'published-cleanup/' + POD + '.json'] = (canonical(closure['marker']) + '\n').encode()
        if corrupt: files[next(path for path in files if corrupt in path)] += b'\n'
        return self.reader.observe_history(history, inventory,
            binding={'pool': {k: history[k] for k in ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')}, 'targets': []},
            agent=self.agent, recovery_codec=self.codec, models=models,
            cleanup_validator=control.validate_cleanup_record, audit_body=control.recovery_audit_body,
            baseline=self.reader.baseline_pins(), read=lambda path: files[path],
            absent=lambda path: None, retired_mount=lambda identity: None)

    def test_observer_reads_all17_and_authenticated_durable_files(self):
        history, binding, inventory = future_fixture()
        observed = self.observe(history, inventory)
        self.assertEqual(len(observed), 12)
        self.reader.validate_observed(history, observed)
        self.assertEqual(len([row for row in observed if 'retirement' in row]), 11)
        self.assertEqual(len([row for row in observed if 'recovery' in row]), 1)

    def test_observer_denies_changed_protected_archive_plan_marker_or_journal(self):
        for path in ('recovery-originals/', '/plan.json', 'published-cleanup/', 'journal/1850'):
            history, binding, inventory = future_fixture()
            with self.subTest(path=path), self.assertRaises(ValueError): self.observe(history, inventory, corrupt=path)

    def test_local_assembler_requires_real_terminal_and_protected_complete_history(self):
        import assemble_recovery_history as assembler
        history,binding,_=future_fixture()
        host=json.loads((CAPTURE/'host-records.json').read_bytes())
        terminal=next(row for row in history['records']if row['pod_uid']==POD)
        host['directories']['journal']['records'][POD+'.json'].update(value=terminal['record'],rawSha256=terminal['journal_sha256'])
        closure=history['recovery']
        sources=SourceLoaderTests().sources()
        def run():
            return assembler.assemble(host,closure['original_raw'].encode(),(canonical(closure['plan'])+'\n').encode(),
                (canonical(closure['review'])+'\n').encode(),(canonical(closure['marker'])+'\n').encode(),
                closure['enrollment'],closure['audit'],closure['cleanup'],sources)
        result=run();self.validate(result,binding)
        host['directories']['journal']['records'][POD+'.json']['mode']=0o644
        with self.assertRaisesRegex(ValueError,'Root0600'):run()
        host['directories']['journal']['records'][POD+'.json']['mode']=0o600
        host['directories']['journal']['records'][POD+'.json']['value']=closure['plan']['original']
        with self.assertRaises(ValueError):run()

    def test_unchanged_stop_inspector_accepts_new_finite_pair_with_historical_exception(self):
        old = module('test_prepare_harness_history', HERE / 'test_prepare_harness.py')
        old.StopTests.setUpClass(); case = old.StopTests()
        args = case.fixture()
        history, binding, inventory = future_fixture()
        prior = self.observe(history, inventory)
        args[1]['host']['retired_caps'] = copy.deepcopy(prior)
        args[4]['retired_caps'] = copy.deepcopy(prior) + args[4]['retired_caps'][1:]
        result = case.stop.validate(*args)
        self.assertEqual(len(result['terminal_lifetimes']), 2)
        self.assertEqual(result['state'], 'stop-witnesses-consistent-awaiting-Root-review')

class SourceLoaderTests(unittest.TestCase):
    def sources(self):
        import recovery_history as reader
        from cps_compute import native_gpu_controller as model, native_gpu_control as control
        paths = {'model': Path(model.__file__), 'control': Path(control.__file__),
            'agent': NODE / 'node_agent.py', 'recovery': NODE / 'cleared_offline_recovery.py',
            'reader': HERE / 'recovery_history.py', 'baseline': HERE / 'recovery-baseline-journal-pins.json'}
        return {key: {'raw': path.read_bytes(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for key, path in paths.items()}

    def test_exact_loader_executes_genuine_pure_codecs(self):
        import recovery_source_loader as loader
        history, binding, _ = future_fixture()
        loaded = loader.load_sources(self.sources())
        checked = loader.validate(loaded, history, binding)
        self.assertEqual(len(checked['finite']), 11)

    def test_changed_codec_bytes_and_wrong_node_closure_fail(self):
        import recovery_source_loader as loader
        for key in ('model', 'control', 'agent', 'recovery', 'reader', 'baseline'):
            sources = self.sources(); sources[key]['raw'] += b'\n'
            with self.subTest(key=key), self.assertRaises(ValueError): loader.load_sources(sources)

    def test_rendered_preflight_inert_and_preserves_current_finite_stop_code(self):
        import prepare_recovery_harness as prepare
        old = module('test_prepare_harness_render_history', HERE / 'test_prepare_harness.py')
        history, _, _ = future_fixture()
        original_root = Path('/home/bjoern/.local/state/cps-group-native-20261009/group-probes')
        original = {name: (original_root / name).read_bytes() for name in prepare.p.SOURCE_PINS}
        out = prepare.render_sources(original, old.binding(), history, self.sources())
        self.assertEqual(out['inspect_stop.py'], (HERE / 'inspect_stop.py').read_bytes())
        scope = {'__name__': 'prepared_only', '__file__': '/private/run_group_acceptance.py'}
        exec(compile(out['run_group_acceptance.py'], 'generated-v2-history', 'exec'), scope)
        self.assertEqual(scope['CONTROLLER_SHA'], '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880')
        loaded = scope['_validate_history'](history, scope['BOUND_CONFIG']['targets'])
        self.assertEqual(len(loaded.baseline), 17)

    def test_generated_host_executes_protected_durable_callback_and_rejects_drift(self):
        """Execute the full generated HOST; only host I/O and health are CPU doubles."""
        import ast, io, os, socket
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import prepare_recovery_harness as prepare
        old=module('test_prepare_host_execution',HERE/'test_prepare_harness.py')
        history,_,inventory=future_fixture()
        root=Path('/home/bjoern/.local/state/cps-group-native-20261009/group-probes')
        out=prepare.render_sources({name:(root/name).read_bytes()for name in prepare.p.SOURCE_PINS},old.binding(),history,self.sources())
        host_node=next(n for n in ast.parse(out['run_group_acceptance.py']).body if isinstance(n,ast.Assign)and any(isinstance(x,ast.Name)and x.id=='HOST_SOURCE'for x in n.targets))
        tree=ast.parse(ast.literal_eval(host_node.value))
        # These are the original protected-host transport boundary definitions.
        # All generated history/epoch/inventory/closure code executes unchanged.
        for node in tree.body:
            if isinstance(node,ast.FunctionDef)and node.name in ('read','absent','retired_mount'):
                arguments={'read':'path,mode,private','absent':'path','retired_mount':'identity'}[node.name]
                node.body=ast.parse('return _cpu_'+node.name+'('+arguments+')').body
        ast.fix_missing_locations(tree)
        closure=history['recovery'];operation=closure['review']['operation_id'];prefix='/run/cps-native-gpu/'
        files={prefix+'journal/'+row['pod_uid']+'.json':(canonical(row['record'])+'\n').encode()for row in history['records']}
        files[prefix+'journal/recovery-originals/'+POD+'.'+operation+'.json']=closure['original_raw'].encode()
        files[prefix+'published-cleanup/'+POD+'.json']=(canonical(closure['marker'])+'\n').encode()
        for key in ('plan','review'):files[prefix+'operator/cleared-offline-recovery/'+operation+'/'+key+'.json']=(canonical(closure[key])+'\n').encode()
        health=b"MODULE_BUILDS={'nvidia':{'elf_sha256':'core'},'nvidia_uvm':{'elf_sha256':'uvm'}}\ndef validate_native_driver_health(*a,**kw):return "+repr(history['driver_generation']).encode()+b'\n'
        files[prefix+'driver-inputs-optional-stack/native_gpu_health.py']=health
        files['/proc/driver/nvidia/gpus/0000:06:10.0/cps_native_caps']=canonical(inventory).encode()
        request={k:history[k]for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')}
        request.update(targets=[],terminal_history=history,core_sha256='core',uvm_sha256='uvm',health_sha256=hashlib.sha256(health).hexdigest())
        reads=[]
        def read(path,mode,private):
            reads.append(str(path));self.assertEqual(mode,0o400 if 'driver-inputs' in str(path) or str(path).startswith('/proc/') else 0o600)
            return files[str(path)]
        def mount(identity):self.assertEqual(identity.cgroup_device,29)
        def absent(path):self.assertNotIn(str(path),files)
        def execute():
            with patch.object(sys,'argv',['cpu',json.dumps(request)]),patch.object(os,'geteuid',return_value=0),patch.object(socket,'gethostname',return_value=history['node']),patch.object(Path,'read_text',return_value=history['boot_id']),redirect_stdout(io.StringIO())as output:
                exec(compile(tree,'generated-host-cpu-execution','exec'),{'__name__':'cpu_observer','_cpu_read':read,'_cpu_absent':absent,'_cpu_retired_mount':mount})
            return json.loads(output.getvalue())
        result=execute()
        self.assertEqual(len(result['retired_caps']),12)
        self.assertEqual(reads.count(prefix+'published-cleanup/'+POD+'.json'),2)
        key='activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py'
        tree=ast.parse(prepare.historical_host_source((root/key).read_bytes(),self.sources()))
        for node in tree.body:
            if isinstance(node,ast.FunctionDef)and node.name in ('read','absent','retired_mount'):
                arguments={'read':'path,mode,private','absent':'path','retired_mount':'identity'}[node.name]
                node.body=ast.parse('return _cpu_'+node.name+'('+arguments+')').body
        ast.fix_missing_locations(tree)
        self.assertEqual(execute()['retired_caps'],result['retired_caps'])
        files[prefix+'operator/cleared-offline-recovery/'+operation+'/review.json']+=b'\n'
        with self.assertRaisesRegex(ValueError,'Protected archived'):execute()

if __name__ == '__main__': unittest.main()
