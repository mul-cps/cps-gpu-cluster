#!/usr/bin/env python3
"""Prepare a bounded legacy or measured five/twenty lifecycle agent; no deployment or authority creation.

The generated runner uses installed, exact SDK768 modules. It retains the old
enrollment/Pod/device/cleanup/publication validators, adds native completed
cleanup evidence, and partitions the COMPLETE physical inventory before backend
actions. Prior QA states are observed only through the reviewed original-journal
retirement verifier. This is a qualification-only operator tool, never a Source
qualification or an ordinary NodeConfiguration bootstrap.
"""
import argparse
import ast
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
LEGACY_SHA = '7492eab2fb5c807a043c580a75ac4a65619df1c206f7a880cbdefcbd7bbc4385'
PRODUCER_SHA = '8e712182fac65d8e67dc1f783a6b082ec61e4a1ce333b1c60b74201e73d23546'
COHORT = '3b217fe8-5750-4ead-954a-09286afd7d3f'  # Verifier code only; never adopts this state.
SDK_COMMIT = '76800510088bfdf92cc928f22eaae7934916e8a0'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
PINS = {
    '__init__.py': 'ffb033e72c0aca7026cd83c20c167b1f1272f2901f83cc40d81faefbba262df3',
    'native_node/__init__.py': '386a54b7bb48e6d3d03625429dde084c25b4266fc92faf3f0e0ad641116771b9',
    'native_node/backend.py': '23a5cc22701d058499f8f818d0a6e34595110d4eb334150852df6dc853a85a73',
    'native_node/identity.py': '9864e8df1406cce46bdc847e2d85619e7ca1d9723811e731ea93844f0c838dfd',
    'native_node/nvml.py': '0bedb1ea0a6301a2298da30d318dae2519ac0e05e0d35d05b7b5f2136a0d221c',
    'native_node/transport.py': '51c301067def92dbced90f5e1e7cba0e694850df88ed6d64189fbcc8a54743ba',
    'native_node/cdi.py': '41f82ef8ec3c4d5bf7011abc1436b52e4cf1329d16059def77a193b7baeac8af',
    'native_gpu_health.py': 'fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8',
    'native_gpu_controller.py': 'd677b3756965dc0f3a3042728ac41687b5cd085e052e235909cd41263573645a',
}
_OWNED_MODULES = {}


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def installed_sources(root):
    """Read and authenticate the complete import closure BEFORE executing code."""
    root = Path(root)
    raw = {name: (root / name).read_bytes() for name in PINS}
    require(all(sha(raw[name]) == pin for name, pin in PINS.items()),
            'Exact complete installed SDK768 module bytes required')
    return raw


def installed_modules(root=None):
    if root is None:
        dist = importlib.metadata.distribution('cps-compute')
        require(dist.version == '0.1.0', 'Exact installed SDK distribution required')
        root = Path(dist.locate_file('cps_compute'))
    root = Path(root)
    raw = installed_sources(root)
    # Neither package initializer has a role in the host adapter. All executable
    # native modules below come from the authenticated installed distribution.
    for name, directory in (('cps_compute', root), ('cps_compute.native_node', root / 'native_node')):
        if name in sys.modules:
            require(_OWNED_MODULES.get(name) is sys.modules[name],
                    'Preexisting unowned SDK module denied')
        else:
            package = types.ModuleType(name)
            package.__path__ = [str(directory)]
            sys.modules[name] = package
            _OWNED_MODULES[name] = package
    modules = {}
    for name in ('native_node/backend.py', 'native_node/identity.py', 'native_node/nvml.py',
                 'native_node/transport.py', 'native_node/cdi.py', 'native_gpu_health.py',
                 'native_gpu_controller.py'):
        key = 'cps_compute.' + name[:-3].replace('/', '.')
        existing = sys.modules.get(key)
        if existing is not None:
            require(_OWNED_MODULES.get(key) == (existing, PINS[name])
                    and Path(existing.__file__).resolve() == (root / name).resolve(),
                    'Preexisting unowned SDK module denied')
            module = existing
        else:
            module = types.ModuleType(key)
            module.__package__ = key.rpartition('.')[0]
            module.__file__ = str(root / name)
            sys.modules[key] = module
            exec(compile(raw[name], module.__file__, 'exec'), module.__dict__)
            _OWNED_MODULES[key] = (module, PINS[name])
        modules[name] = module
    return modules


def partition_inventory(value, caps, retired, unprogrammed):
    """Exact per-inode active caps; original retired rows are never normalized."""
    require(type(caps) is dict and len(caps) <= 2
            and all(type(inode) is int and inode > 0 and cap == 5120 * 1048576
                    and type(cap) is int for inode, cap in caps.items())
            and type(retired) is dict and not caps.keys() & retired.keys()
            and type(unprogrammed) is set and unprogrammed <= caps.keys(),
            'Exact two5 parent map and disjoint original retirements required')
    require(type(value) is dict and set(value) == {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}
            and type(value['version']) is int and value['version'] == 1
            and value['backend'] == 'misc-fallback' and value['gpu_uuid'] == GPU
            and type(value['gpu_id']) is int and 0 <= value['gpu_id'] < 2**32
            and type(value['entries']) is list and len(value['entries']) <= 256,
            'Complete selected physical GPU inventory required')
    seen = set(); live_used = 0; live_hard = 0
    for row in value['entries']:
        require(type(row) is dict and set(row) == {'cgroup_id', 'kernfs_id', 'inode', 'offline',
                'pinned', 'default_hierarchy', 'soft', 'hard', 'used'}
                and all(type(row[k]) is int and 0 <= row[k] < 2**64
                        for k in ('cgroup_id', 'kernfs_id', 'inode', 'soft', 'hard', 'used'))
                and all(type(row[k]) is bool for k in ('offline', 'pinned', 'default_hierarchy')),
                'Closed typed physical inventory row required')
        inode = row['inode']
        require(inode > 0 and row['cgroup_id'] == row['kernfs_id'] == inode
                and inode not in seen and row['pinned'] and row['default_hierarchy'],
                'Unique pinned default-hierarchy parent required')
        seen.add(inode)
        if inode in retired:
            require(row == retired[inode] and row['offline'] is True and row['used'] == 0,
                    'Fresh original retired row changed')
            continue
        cap = caps.get(inode)
        require(cap is not None and row['offline'] is False, 'Unrelated or offline current parent denied')
        if (row['soft'], row['hard']) == (0, (1 << 64) - 1):
            require(inode in unprogrammed and row['used'] == 0,
                    'Only an independently blocked virgin parent may be unprogrammed')
        else:
            require(row['soft'] == row['hard'] == cap and row['used'] <= cap,
                    'Exact actual per-Pod cap/charge required')
            live_hard += row['hard']; live_used += row['used']
    require(retired.keys() <= seen and live_hard <= 10240 * 1048576
            and live_used <= 10240 * 1048576, 'Complete original retirement set and fixed10GiB budget required')


def _exec(name, raw):
    module = types.ModuleType(name)
    module.__file__ = name + '.py'
    sys.modules[name] = module
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def adapt(legacy_raw, retirement_raw, wait_raw, *, root=None):
    """Construct definitions only. No API, NVML, journal constructor or writes."""
    modules = installed_modules(root)
    back = modules['native_node/backend.py']; models = modules['native_gpu_controller.py']
    tr = modules['native_node/transport.py']; ident = modules['native_node/identity.py']
    nvml = modules['native_node/nvml.py']; health = modules['native_gpu_health.py']
    cdi = modules['native_node/cdi.py']
    # Only the two terminal dispatch tests change in historical executable code.
    text = legacy_raw.decode()
    old = "record.state in ('cleaned', 'retired-inert-cap')"
    require(text.count(old) == 2, 'Exact historical terminal dispatch preimages required')
    # The cleanup validator is retained for its original states; the wrapper below
    # owns the new state. Alter only run's dispatch, not its old proof validator.
    start = text.index('def run(')
    text = text[:start] + text[start:].replace(old, "record.state in ('cleaned', 'retired-inert-cap', 'cleanup-offline-unlimited')", 1)
    old = "record.state in ('cleaned', 'retired-inert-cap', 'recovered-cleared-offline-cap')"
    require(text.count(old) == 2, 'Exact historical tombstone preimages required')
    start = text.index('class EnrollmentStore:'); end = text.index('\ndef abort_ledger(', start)
    store_text = text[start:end]
    require(store_text.count(old) == 1, 'Exact protected tombstone dispatch required')
    text = text[:start] + store_text.replace(old, "record.state in ('cleaned', 'retired-inert-cap', 'recovered-cleared-offline-cap', 'cleanup-offline-unlimited')") + text[end:]
    agent = _exec('_plain_lifecycle_original', text.encode())
    retirement = _exec('_plain_lifecycle_retirement', retirement_raw)
    # Reuse the authenticated original per-record proof loop without pretending a
    # filtered journal is complete. InventoryGuard reads the WHOLE current journal
    # and validates every record/intent before invoking this same proof loop.
    tree = ast.parse(retirement_raw)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'verify_retirements')
    loop = next(n for n in function.body if isinstance(n, ast.For))
    proof_text = 'def current_terminal(backend, record):\n    rows = {}\n    records = [record]\n' + '\n'.join('    ' + s for s in ast.unparse(loop).splitlines()) + '\n    return rows\n'
    exec(compile(proof_text, '<original-current-terminal-proof>', 'exec'), retirement.__dict__)
    wait = types.SimpleNamespace(require=back.require, hashlib=hashlib, json=json, GATE=back.GATE)
    exec(compile(wait_raw, '<original-awaiting-first-gate>', 'exec'), wait.__dict__)
    qualification = types.SimpleNamespace(**{name: getattr(tr, name) for name in
        ('Kubernetes', 'cri_reader', 'gpu_clients', 'health')}, awaiting_first_gate=wait.awaiting_first_gate)
    manual = types.SimpleNamespace(discover=ident.discover, safe_path=ident.safe_path, Nvml=nvml.Nvml)
    agent._installed_backend = back
    agent._installed_models = models
    agent.load_models_from_snapshot = lambda: models
    base_store = agent.EnrollmentStore

    class EnrollmentStore(base_store):
        def __init__(self, state, current_models, trusted_uid=0):
            require(current_models is models, 'Exact installed SDK types required')
            self.state, self.models, self.uid = Path(state), models, trusted_uid
            self.backend = back
            back.private_directory(self.state, self.uid)
            for name in ('intents', 'enrollments', 'authority', 'receipts', 'bootstrap', 'published-cleanup', 'pre-gate-aborts'):
                path = self.state / name
                path.mkdir(mode=0o700, exist_ok=True)
                back.private_directory(path, self.uid)
    agent.EnrollmentStore = EnrollmentStore
    original_object = agent.cleanup_object
    original_receipt = agent.cleanup_receipt

    def cleanup_object(envelope, record=None, *, audit=None):
        result = original_object(envelope, record, audit=audit)
        if record is not None and record.state == 'cleanup-offline-unlimited':
            require(type(record) is models.CapRecord and type(record.cleanup_offline) is models.CleanupOfflineUnlimited
                    and record.intent.to_dict() == envelope['enrollment']['intent'],
                    'Exact original typed completed cleanup journal required')
            receipt = agent.parse(result['data']['receipt.json'])
            receipt['cleanup_offline'] = {'proof': record.cleanup_offline.to_dict(),
                'enrollment_uid': envelope['configmap_uid'],
                'enrollment_sha256': agent.canonical_sha256(envelope['enrollment']),
                'journal_sha256': agent.canonical_sha256(record.to_dict())}
            result['data']['receipt.json'] = json.dumps(receipt, sort_keys=True, separators=(',', ':'))
        return result

    def cleanup_receipt(envelope, record, backend, pod, current_models):
        require(current_models is models, 'Exact installed SDK cleanup types required')
        if record.state != 'cleanup-offline-unlimited':
            return original_receipt(envelope, record, backend, pod, models)
        require(type(record) is models.CapRecord and record.intent.to_dict() == envelope['enrollment']['intent']
                and pod is None, 'Exact completed journal and actual Pod absence required')
        # Initial cleanup was completed by the native controller. Publication
        # retries revalidate that exact terminal/absence, without requiring an
        # unrelated peer to have no CUDA clients. Never run SET here.
        raw = clone_backend(agent, backend, [record.intent], backend.state)
        retirement.current_terminal(raw, record)
        return cleanup_object(envelope, record)

    agent.cleanup_object = cleanup_object
    agent.cleanup_receipt = cleanup_receipt
    agent._retirement = retirement
    agent._qualification = qualification
    agent._manual = manual
    agent._modules = modules
    return agent


def clone_backend(agent, source, intents, state):
    return agent._installed_backend.QualificationNodeBackend(agent._installed_models, agent._manual,
        intents=intents, driver=source.driver, get_pod=source.get_pod, get_node=source.get_node,
        get_cri=source.get_cri, delete_pod=source.delete_pod, gpu_clients=source.gpu_clients,
        health=source.health, proc_root=source.proc, cgroup_root=source.cg,
        state_root=Path(state), trusted_uid=source.uid, gate_name=source.gate_name)


def original_uid_absence(actual, intent, agent):
    if actual is None: return None
    require(type(actual) is dict and actual.get('apiVersion') == 'v1' and actual.get('kind') == 'Pod',
            'Authenticated actual Pod response required')
    metadata = actual.get('metadata')
    require(type(metadata) is dict and metadata.get('namespace') == intent.namespace
            and metadata.get('name') == intent.name and agent.canonical_uuid(metadata.get('uid'))
            and metadata['uid'] != '00000000-0000-0000-0000-000000000000'
            and metadata['uid'] != intent.pod_uid, 'Exact original Pod UID must remain absent')
    return metadata['uid']


def validate_lifecycle_scope(config, c):
    """Additional bounded scope, after the original closed config validator."""
    require(config['enabled'] and config['authority_namespace'] not in
            ('cps-native-system', 'cps-native-runtime', c.NS)
            and len(config['workspaces']) == 2, 'Separate two-workspace lifecycle scope required')
    pool = config['pool']
    identity = {'node': c.NODE, 'node_uid': c.NODE_UID, 'gpu_uuid': c.GPU, 'max_workspaces': 2}
    if config['version'] == 1:
        require('terminal_history' not in config and pool == identity
                and all(v == {'profile': 'interactive-native-pilot-5'}
                    for v in config['workspaces'].values()), 'Exact legacy two5 scope required')
        return
    require(config['version'] == 2 and config['mode'] == 'operator-qualification'
            and all(pool.get(k) == v for k, v in identity.items())
            and pool['boot_id'] == c.BOOT and pool['driver_generation'] == c.GENERATION
            and pool['memory_budget_mib'] == 25600,
            'Exact measured operator pool and current epoch required')
    expected = {('interactive-native-qualification-5', 5120),
                ('interactive-native-qualification-20', 20480)}
    require({(v['profile'], v['cap_mib']) for v in config['workspaces'].values()} == expected,
            'Exact measured five/twenty pair required')


def enrollment_configuration(agent, config, envelope):
    """Recover old validation scope from explicit pins, never from names alone.

    The original agent separately verifies completion, ledger and private journal
    pins before accepting history. This helper preserves that same old scope in
    the fresh physical-inventory checks and published-cleanup readback.
    """
    body = envelope['enrollment']
    entry = config.get('terminal_history', {}).get(body['intent']['pod_uid'])
    if entry is None:
        return config
    require('cap_mib' not in entry and 'configuration_authority' not in entry
            and entry['profile'] == body['profile'] == 'interactive-native-pilot-5'
            and body['intent']['cap_mib'] == 5120
            and entry['binding_id'] == body['binding_id']
            and entry['policy_hash'] == body['policy_hash'] != config['policy_hash']
            and entry['enrollment_uid'] == envelope['configmap_uid']
            and entry['enrollment_sha256'] == agent.canonical_sha256(body),
            'Exact original legacy five-GiB terminal enrollment pins required')
    return {'version': 1, 'enabled': config['enabled'],
            'authority_namespace': config['authority_namespace'],
            'policy_hash': entry['policy_hash'],
            'pool': {k: config['pool'][k] for k in ('node', 'node_uid', 'gpu_uuid', 'max_workspaces')},
            'workspaces': {body['source'] + ':' + body['workspace']: {'profile': entry['profile']}}}


class InventoryGuard:
    """Fresh proofs on each operation. No inventory/authority cache or bypass bit."""
    def __init__(self, agent, config, args, settings):
        self.agent, self.config, self.args = agent, deepcopy(config), args
        self.settings = deepcopy(settings)
        self.back = agent._installed_backend
        self.models = agent._installed_models
        self.c = agent._retirement
        require(type(settings) is dict and set(settings) == {'version', 'namespace_uid', 'cdi_runtime_pins', 'host_root'}
                and type(settings['version']) is int and settings['version'] == 1
                and agent.canonical_uuid(settings['namespace_uid'])
                and settings['host_root'] == '/host', 'Closed reviewed pilot runtime settings required')
        self.pins = agent._modules['native_node/cdi.py'].CDIRuntimePins.from_dict(settings['cdi_runtime_pins'])
        self.kube = None

    def raw_backend(self, source, intents, state):
        return clone_backend(self.agent, source, intents, state)

    def current_terminal(self, source, record):
        """UID-scoped absence ONLY behind exact prior published completion."""
        a = self.agent
        store = a.EnrollmentStore.__new__(a.EnrollmentStore)
        store.state, store.models, store.uid, store.backend = source.state, self.models, source.uid, self.back
        uid = record.intent.pod_uid
        envelope = self.back.private_read(source.state / 'enrollments' / (uid + '.json'), source.uid)
        require(type(envelope) is dict and envelope.get('enrollment', {}).get('intent') == record.intent.to_dict(),
                'Original protected terminal enrollment required')
        tombstone = self.back.private_read(source.state / 'published-cleanup' / (uid + '.json'), source.uid)
        raw = self.raw_backend(source, [record.intent], source.state)
        if tombstone is None:
            # Initial publication has no name-reuse exception.
            return self.c.current_terminal(raw, record)
        def published():
            actual = self.kube.configmap(self.config['authority_namespace'], envelope['configmap_name'])
            require(a.validate_enrollment(actual, enrollment_configuration(a, self.config, envelope), self.models) == envelope,
                    'Original immutable terminal enrollment changed')
            name = 'cps-native-cleanup-' + envelope['enrollment']['binding_id'][:40]
            cm = self.kube.configmap(self.config['authority_namespace'], name)
            require(store.cleanup_published(uid, envelope, record, cm),
                    'Exact prior published original cleanup proof required')
        published()
        before = original_uid_absence(source.get_pod(record.intent), record.intent, a)
        def only_original(intent):
            require(intent == record.intent, 'Original terminal-only reader scope required')
            original_uid_absence(source.get_pod(intent), intent, a)
            return None
        raw.get_pod = only_original
        rows = self.c.current_terminal(raw, record)
        require(original_uid_absence(source.get_pod(record.intent), record.intent, a) == before,
                'Replacement identity changed across original terminal proof')
        published()
        return rows

    def check(self, source):
        m, c = self.models, self.c
        require(self.kube is not None, 'Bound authenticated Kubernetes reader required')
        for namespace, uid in ((self.config['authority_namespace'], self.settings['namespace_uid']), (c.NS, c.NS_UID)):
            actual = self.kube.call('GET', '/api/v1/namespaces/' + namespace)
            require(type(actual) is dict and actual.get('metadata', {}).get('uid') == uid
                    and not actual['metadata'].get('deletionTimestamp'), 'Exact current/original namespace UID required')
        state = str(source.state)
        enrolled = list(source.intents.values())
        readers = []
        def make_backend(intents, root):
            backend = self.raw_backend(source, intents, root)
            readers.append(backend)
            return backend
        prior = c.retirement_inputs(self.args, m, self.back, make_backend, state)
        require(prior and readers, 'Explicit complete original prior-retirement descriptor required')
        journal = m.PrivateJournal.__new__(m.PrivateJournal)
        journal.directory = source.state / 'journal'
        records = journal.records()
        expected = {i.pod_uid: i for i in enrolled}
        for intent in enrolled:
            envelope = self.back.private_read(source.state / 'enrollments' / (intent.pod_uid + '.json'), source.uid)
            require(type(envelope) is dict and envelope.get('enrollment', {}).get('intent') == intent.to_dict(),
                    'Original cap enrollment mirror required')
            authority = enrollment_configuration(self.agent, self.config, envelope)
            body = envelope['enrollment']
            scope = authority['workspaces'].get(body['source'] + ':' + body['workspace'])
            require(scope is not None and scope['profile'] == body['profile']
                    and intent.policy_hash == authority['policy_hash']
                    and intent.cap_mib == (scope['cap_mib'] if authority['version'] == 2 else 5120),
                    'Exact original or measured configured enrollment cap required')
        require(len(expected) == len(enrolled)
                and all(expected.get(r.intent.pod_uid) == r.intent and r.recovery is None
                        and r.prepared_offline is None for r in records),
                'Complete original current journals and exact configured enrollments required')
        by_uid = {r.intent.pod_uid: r for r in records}
        raw = self.raw_backend(source, enrolled, state)
        caps = {}; unprogrammed = set(); terminal = {}
        for intent in enrolled:
            record = by_uid.get(intent.pod_uid)
            if record is not None and record.state in ('retired-inert-cap', 'cleanup-offline-unlimited'):
                rows = self.current_terminal(source, record)
                require(not terminal.keys() & rows.keys(), 'Current terminal parent alias denied')
                terminal.update(rows)
                continue
            if (record is not None and record.readback == record.limit
                    and raw.get_pod(intent) is None and raw._group(record.identity, absent=True) is None
                    and record.state not in ('cleanup-prepared', 'cleaned')):
                # Permit the actual controller to BEGIN cleanup of an applied
                # vanished parent. This is physical partition evidence only;
                # no terminal journal or release is inferred or manufactured.
                proof = raw.retired_inert_cap(record.identity, record.limit)
                terminal[record.identity.cgroup_inode] = asdict(proof.entry)
                continue
            if (record is not None and record.state in ('cleanup-prepared', 'cleaned')
                    and record.readback == record.limit):
                # This is still the native initial-cleanup proof, including its
                # no-client checks. Only an already published terminal uses the
                # UID-scoped reader above.
                proof = raw.cleanup_completion(record.identity, record)
                require(type(proof) in (m.CleanupOfflineUnlimited, m.RetiredInertCap),
                        'Exact native cleanup-completion proof required')
                terminal[record.identity.cgroup_inode] = asdict(proof.entry)
                continue
            if record is None:
                pod = raw.get_pod(intent)
                if pod is None or self.agent._qualification.awaiting_first_gate(pod, intent):
                    continue
                self.agent.validate_actual_pod(pod, {'intent': intent.to_dict()})
                self.agent.validate_device_identity_barrier(pod, intent)
                identity = raw.observe(intent).identity
            else:
                identity = record.identity
            require(identity.cgroup_inode not in caps, 'Current parent alias denied')
            caps[identity.cgroup_inode] = intent.cap_bytes
            if record is None or (record.state == 'prepared' and record.readback is None):
                unprogrammed.add(identity.cgroup_inode)
        require(not prior.keys() & terminal.keys(), 'Prior/current original parent alias denied')
        retired = {**prior, **terminal}
        reference = readers[0]
        old_journal = m.PrivateJournal.__new__(m.PrivateJournal)
        old_journal.directory = reference.state / 'journal'
        identity = old_journal.records()[0].identity
        partition_inventory(reference._inventory(identity), caps, retired, unprogrammed)
        require(c.retirement_inputs(self.args, m, self.back, make_backend, state) == prior,
                'Original retirement proofs changed across complete inventory')
        return prior

    def backend_type(self):
        guard = self
        class GuardedBackend(self.back.QualificationNodeBackend):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                guard.current_backend = self
            def quarantine(self, identity, reason):
                # Preserve the SDK's emergency UID-conditional stop even when
                # health/global inventory is why new authority was denied.
                # The original operation only revokes/stops; it never SETs caps.
                raw = guard.raw_backend(self, list(self.intents.values()), self.state)
                return raw.quarantine(identity, reason)
        for name in ('observe', 'check_owner', 'read_limit', 'read_limit_readonly', 'set_limit',
                     'check_cleanup', 'cleanup_completion', 'retired_inert_cap', 'prepared_offline_unlimited',
                     'read_gate', 'seal_gate', 'revoke_gate'):
            def action(instance, *args, _name=name, **kwargs):
                guard.check(instance)
                return getattr(super(GuardedBackend, instance), _name)(*args, **kwargs)
            setattr(GuardedBackend, name, action)
        return GuardedBackend


def run_agent(agent, args, settings):
    config = agent.read_config(args.config)
    agent.validate_config(config)
    c = agent._retirement
    validate_lifecycle_scope(config, c)
    require(str(args.state_root).startswith(c.ROOT + '/cohorts/')
            and str(args.state_root) == c.cohort_state(str(args.state_root)[len(c.ROOT + '/cohorts/'):-len('/state')]),
            'Explicit separate canonical QA cohort state required')
    guard = InventoryGuard(agent, config, args, settings)
    backend = types.SimpleNamespace(**{name: getattr(agent._installed_backend, name)
                                     for name in ('private_directory', 'private_read', 'private_write')},
                                    QualificationNodeBackend=guard.backend_type())
    cdi = types.SimpleNamespace(observe_current_cdi=lambda gpu: agent._modules['native_node/cdi.py'].observe_current_cdi(
        gpu, pins=guard.pins, host_root=settings['host_root']))
    bundle = (backend, agent._qualification, {'models': agent._installed_models, 'manual': agent._manual,
              'health': agent._modules['native_gpu_health.py'], 'cdi': cdi})
    agent.load_bundle = lambda _: bundle
    original_api = agent.api_class
    def api_class(qualification):
        base = original_api(qualification)
        class API(base):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                guard.kube = self
            def enrollments(self, namespace):
                actual = self.call('GET', '/api/v1/namespaces/' + namespace)
                require(actual is not None and actual.get('metadata', {}).get('uid') == settings['namespace_uid']
                        and not actual['metadata'].get('deletionTimestamp'), 'Exact pilot namespace UID required')
                return super().enrollments(namespace)
        return API
    agent.api_class = api_class
    original_publish = agent.publish_cleanup
    def publish_cleanup(*a, **kw):
        require(hasattr(guard, 'current_backend'), 'Current inventory owner required before publication')
        guard.check(guard.current_backend)
        return original_publish(*a, **kw)
    agent.publish_cleanup = publish_cleanup
    original_epoch = agent.abort_current_epoch
    def epoch(*a, **kw):
        actual = original_epoch(*a, **kw)
        require(actual.boot_id == c.BOOT and actual.driver_generation == c.GENERATION,
                'Exact independently qualified147 boot/generation required')
        return actual
    agent.abort_current_epoch = epoch
    original_run = agent.run
    def run(config, bundle, state, kube, driver, **kw):
        epoch(config, state, driver, agent._modules['native_gpu_health.py'], agent._installed_models)
        return original_run(config, bundle, state, kube, driver, **kw)
    agent.run = run
    argv = ['--execute', '--config', str(args.config), '--state-root', str(args.state_root),
            '--service-account', str(args.service_account), '--crictl', str(args.crictl),
            '--cri-socket', args.cri_socket, '--iterations', str(args.iterations), '--interval', str(args.interval)]
    return agent.main(argv)


def runtime_tools(crictl, host_root):
    """Resolve host tool projections before SDK loading or native GPU access."""
    host = Path(host_root)
    require(host.is_absolute() and '..' not in host.parts, 'Absolute canonical host root required')
    selected = Path(crictl)
    try:
        data = host / 'var/lib/rancher/k3s/data'
        if not selected.is_file() and selected == data / 'current/bin/crictl':
            target = (data / 'current').readlink()
            require(target.is_absolute() and target.parent == Path('/var/lib/rancher/k3s/data')
                    and len(target.name) == 64 and all(c in '0123456789abcdef' for c in target.name),
                    'Current k3s runtime tool link must select an immutable version')
            selected = host / target.relative_to('/') / 'bin/crictl'
        smi = host / 'run/nvidia/driver/usr/bin/nvidia-smi'
        for tool in (selected, smi):
            require(tool.is_file() and os.access(tool, os.X_OK)
                    and tool.resolve(strict=True).is_relative_to(host.resolve(strict=True)),
                    'Executable runtime tool inside the host projection required: ' + str(tool))
    except OSError as error:
        raise ValueError('Required host runtime tool unavailable') from error
    # Keep the crictl basename: k3s is a multicall executable.
    return {'crictl': str(selected), 'nvidia_smi_directory': str(smi.parent)}


def runtime_main(legacy_raw, retirement_raw, wait_raw, argv=None):
    p = argparse.ArgumentParser(description='Explicit operator-only plain two5 lifecycle qualification')
    p.add_argument('--execute', action='store_true')
    for name in ('config', 'state-root', 'service-account', 'crictl', 'runtime-settings', 'retirement'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--runtime-settings-sha256'); p.add_argument('--retirement-sha256')
    p.add_argument('--cri-socket', default='unix:///host/run/k3s/containerd/containerd.sock')
    p.add_argument('--iterations', type=int, default=60); p.add_argument('--interval', type=float, default=2)
    args = p.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'production_qualified': False}))
        return
    require(os.geteuid() == 0 and all(getattr(args, n) is not None for n in ('config', 'state_root',
            'service_account', 'crictl', 'runtime_settings', 'runtime_settings_sha256', 'retirement', 'retirement_sha256')),
            'Explicit Root reviewed settings, complete prior proofs and paths required')
    settings_raw = args.runtime_settings.read_bytes()
    require(sha(settings_raw) == args.runtime_settings_sha256, 'Reviewed runtime settings bytes changed')
    # Verify prior descriptor raw bytes before any dependency execution or access.
    prior_raw = args.retirement.read_bytes()
    require(len(prior_raw) <= 1048576 and sha(prior_raw) == args.retirement_sha256,
            'Reviewed complete prior-retirement descriptor bytes changed')
    settings = document(settings_raw)
    tools = runtime_tools(args.crictl, settings['host_root'])
    args.crictl = Path(tools['crictl'])
    os.environ['PATH'] = tools['nvidia_smi_directory'] + os.pathsep + os.environ.get('PATH', '')
    print(json.dumps({'state': 'runtime-tools-resolved', **tools}), flush=True)
    return run_agent(adapt(legacy_raw, retirement_raw, wait_raw), args, settings)


def _inputs():
    legacy = (HERE.parents[1] / 'native-group-pilot/node_agent.py').read_bytes()
    producer = (HERE / 'prepare_packaged_cleanup.py').read_bytes()
    require(sha(legacy) == LEGACY_SHA and sha(producer) == PRODUCER_SHA,
            'Exact reviewed original agent and retirement producer required before execution')
    module = types.ModuleType('_plain_retirement_producer'); module.__file__ = str(HERE / 'prepare_packaged_cleanup.py')
    exec(compile(producer, module.__file__, 'exec'), module.__dict__)
    generated = module.build_sources(COHORT)['controller.py']
    # The pure original wait recognizer has no loader/health/backend side effects.
    snapshot = document((HERE.parents[1] / 'native-group-pilot/source-snapshot.json').read_bytes())
    sources = snapshot['sources']
    legacy_module = _exec('_plain_agent_pin_reader', legacy)
    poll = sources['poll.py'].encode()
    require(sha(poll) == legacy_module.SOURCE_PINS['poll.py'], 'Original wait recognizer source changed')
    tree = ast.parse(poll)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'awaiting_first_gate')
    return legacy, generated, ast.unparse(function).encode()


def agent_for_tests(root):
    return adapt(*_inputs(), root=root)


def build_sources():
    legacy, retirement, wait = _inputs()
    current = Path(__file__).read_text()
    tree = ast.parse(current)
    names = {'require', 'sha', 'document', 'installed_sources', 'installed_modules', 'partition_inventory',
             '_exec', 'adapt', 'clone_backend', 'original_uid_absence', 'validate_lifecycle_scope', 'enrollment_configuration', 'InventoryGuard', 'run_agent', 'runtime_tools', 'runtime_main'}
    definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    prefix = '''#!/usr/bin/env python3
import argparse, ast, hashlib, importlib.metadata, json, os, sys, types
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
'''
    raw = (prefix + 'PINS=' + repr(PINS) + '\nGPU=' + repr(GPU) + '\n_OWNED_MODULES={}\n' +
           '\n\n'.join(ast.unparse(node) for node in definitions) +
           '\nif __name__ == "__main__":\n    runtime_main(' + repr(legacy) + ',' + repr(retirement) + ',' + repr(wait) + ')\n').encode()
    compile(raw, 'plain_node_agent.py', 'exec')
    return {'plain_node_agent.py': raw}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true'); p.add_argument('--output', type=Path)
    args = p.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False})); return
    require(args.output is not None, 'Exclusive offline output directory required')
    sources = build_sources()
    args.output.mkdir(mode=0o700)
    for name, raw in sources.items():
        fd = os.open(args.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(raw)
    print(json.dumps({'state': 'prepared', 'sdk_source': SDK_COMMIT, 'production_qualified': False,
                      'files': {name: sha(raw) for name, raw in sources.items()}}))


if __name__ == '__main__': main()
