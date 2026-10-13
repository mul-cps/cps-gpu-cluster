"""Offline delivery/restart tests; fake API objects are not live evidence."""
import copy
import fcntl
import hashlib
from datetime import timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest

import native_group_approval_renderer as r
from test_native_group_approval_renderer import NOW, readiness_fixture, uid
from test_native_group_approval_rollover import installed_fixture

if importlib.util.find_spec('native_group_approval_delivery'):
    import native_group_approval_delivery as d
else:
    d = None


class MemoryAPI:
    """CAS-capable API substitute; inject a process crash after a real mutation."""
    def __init__(self, fixture):
        self.initial, self.prior, self.old, self.kwargs, roles = fixture
        self.objects = {}
        self.mutations = []
        self.crash_at = None
        self.current = None
        for group in (self.old['deployments'], self.old['replicasets'], self.old['pods'],
                      roles, self.kwargs['previous_bootstrap_maps'], self.initial.acks):
            for obj in group.values():
                self.put(obj)
        for row in self.kwargs['baselines'].values():
            self.put(row['previous_document']); self.put(row['previous_reference'])

    def put(self, obj):
        meta = obj['metadata']
        self.objects[obj['kind'], meta['namespace'], meta['name']] = copy.deepcopy(obj)

    def get(self, kind, namespace, name, missing=False):
        obj = self.objects.get((kind, namespace, name))
        if obj is None and not missing:
            raise RuntimeError('not found')
        return copy.deepcopy(obj)

    def mutated(self, kind, namespace, name):
        self.mutations.append((kind, namespace, name))
        if len(self.mutations) == self.crash_at:
            raise RuntimeError('injected crash after API success')

    def create(self, obj):
        obj = copy.deepcopy(obj); meta = obj['metadata']
        if self.get(obj['kind'], meta['namespace'], meta['name'], True) is not None:
            raise RuntimeError('AlreadyExists')
        meta.update(uid=uid(1000 + len(self.objects)), resourceVersion='1')
        self.put(obj); self.mutated(obj['kind'], meta['namespace'], meta['name'])

    def patch(self, kind, namespace, name, patch):
        obj = self.get(kind, namespace, name)
        for op in patch:
            parts = op['path'].strip('/').split('/'); parent = obj
            for part in parts[:-1]:
                parent = parent[part]
            if op['op'] == 'test':
                if parent[parts[-1]] != op['value']:
                    raise RuntimeError('CAS conflict')
            elif op['op'] == 'replace':
                parent[parts[-1]] = copy.deepcopy(op['value'])
            else:
                raise AssertionError('Only renderer tests/replace permitted')
        obj['metadata']['resourceVersion'] = str(int(obj['metadata']['resourceVersion']) + 1)
        self.put(obj); self.mutated(kind, namespace, name)

    def processes(self, projection):
        if self.current is None:
            return {key:copy.deepcopy(self.old[key]) for key in ('deployments','replicasets','pods')}
        records = {key:copy.deepcopy(self.current[key]) for key in ('deployments','replicasets','pods')}
        records['deployments'] = {c:self.get('Deployment', p['namespace'], p['name'])
            for c,p in projection['process_declarations'].items()}
        return records

    def launch(self, projection, pending=False, acknowledge=True):
        documents = {c:self.get('ConfigMap', x['namespace'], x['name']) for c,x in projection['references'].items()}
        current = readiness_fixture(self.initial.f, projection, documents)
        for index, c in enumerate(r.COMPONENTS, 2000):
            pod, rs = current['pods'][c], current['replicasets'][c]
            pod['metadata'].update(name='new-pod-' + str(index), uid=uid(index))
            rs['metadata'].update(name='new-rs-' + str(index), uid=uid(index + 100))
            pod['metadata']['ownerReferences'][0].update(name=rs['metadata']['name'], uid=rs['metadata']['uid'])
            current['expected_processes'][c].update(name=pod['metadata']['name'], uid=pod['metadata']['uid'])
            current['acknowledgments'][c]['process'] = copy.deepcopy(current['expected_processes'][c])
            current['deployments'][c]['metadata']['resourceVersion'] = self.get('Deployment',
                rs['metadata']['namespace'], projection['process_declarations'][c]['name'])['metadata']['resourceVersion']
            if pending:
                pod['status'] = {'phase':'Pending', 'conditions':[{'type':'Ready','status':'False'}]}
            for key in ('deployments','replicasets','pods'):
                self.put(current[key][c])
            if acknowledge:
                ref = projection['acknowledgment_references'][c]
                ack = self.get('ConfigMap', ref['namespace'], ref['name'])
                ack['data']['ack.json'] = r.canonical(current['acknowledgments'][c])
                self.put(ack)
        self.current = current


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(d, 'Executable approval delivery module is required')
        self.fixture = installed_fixture(); self.api = MemoryAPI(self.fixture)
        initial, prior, old, kwargs, _ = self.fixture
        self.config = {'version':1, 'policy':initial.f[0].catalog,
            'qualification':initial.f[1]._config(), 'previous_publication':prior,
            'previous_publication_sha256':r.canonical_sha256(prior),
            'baselines':kwargs['baselines'], 'ttlSeconds':30}
        self.capture = {'version':1, 'source_raw':kwargs['source_raw'].decode(),
            'source_sha256':kwargs['source_sha256'], 'trusted_revision':kwargs['trusted_revision'],
            'captured_at':NOW.isoformat()}
        self.epoch = initial.epoch.__dict__
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'delivery'

    def controller(self):
        return d.Delivery(self.config, self.path, self.api, lambda:copy.deepcopy(self.capture), lambda:NOW,
            epoch_reader=lambda:self.epoch)

    def test_rollover_waits_for_actual_new_processes_and_fresh_all_four_acks(self):
        result = self.controller().tick()
        self.assertFalse(result['ready']); self.assertEqual(result['phase'], 'processes')
        publication = r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.assertEqual(len(self.api.mutations), 19)  # 8 CMs, 7 Roles, 4 Deployments
        self.api.launch(publication, pending=True, acknowledge=False)
        result = self.controller().tick()
        self.assertFalse(result['ready']); self.assertEqual(result['phase'], 'acknowledgments')
        for role in [obj for obj in self.api.objects.values() if obj['kind']=='Role']:
            for rule in role['rules']:
                self.assertIn('resourceNames', rule)
                if rule['resources'] == ['pods']:
                    self.assertTrue(rule['resourceNames'][0].startswith('new-pod-'))
        self.api.launch(publication)
        result = self.controller().tick()
        self.assertTrue(result['ready']); self.assertEqual(result['revision'], self.capture['trusted_revision'])
        count = len(self.api.mutations)
        self.assertTrue(self.controller().tick()['ready'])
        self.assertEqual(len(self.api.mutations), count)
        # Idle is freshly checked, not a cached readiness receipt.
        self.api.current['pods']['node']['status']['phase'] = 'Pending'
        self.assertFalse(self.controller().tick()['ready'])

    def test_restart_at_each_partial_mutation_keeps_exact_targets_and_custody(self):
        for crash_at in (1, 4, 8, 9, 12, 16, 19):
            with self.subTest(crash_at=crash_at), tempfile.TemporaryDirectory() as temp:
                api = MemoryAPI(self.fixture); api.crash_at = crash_at
                path = Path(temp)/'journal'
                controller = d.Delivery(self.config,path,api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch)
                with self.assertRaisesRegex(RuntimeError,'injected crash'):
                    controller.tick()
                api.crash_at = None
                self.assertEqual(d.Delivery(self.config,path,api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch).tick()['phase'], 'processes')
                self.assertEqual(len(api.mutations), 19)
                state = r.parse((path/'state.json').read_bytes())
                publication = state['transition']['publication']; api.launch(publication)
                self.assertTrue(d.Delivery(self.config,path,api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch).tick()['ready'])
                self.assertEqual(publication['runtime_settings'], self.fixture[1]['runtime_settings'])
                self.assertEqual(len(r.parse(publication['documents']['node']['data']['approval.json'])['history']),4)
                self.assertEqual((path/'state.json').stat().st_mode & 0o777, 0o600)

    def test_foreign_mutations_replacement_uid_or_immutable_collision_fail_closed(self):
        for mutation in ('rules','uid','document'):
            with self.subTest(mutation=mutation):
                api = MemoryAPI(self.fixture); api.crash_at = 8
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp)/'journal'; ctl=d.Delivery(self.config,path,api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch)
                    with self.assertRaises(RuntimeError): ctl.tick()
                    api.crash_at = None
                    state = r.parse((path/'state.json').read_bytes())
                    if mutation == 'document':
                        cm = state['transition']['documents']['node']; key=('ConfigMap',cm['metadata']['namespace'],cm['metadata']['name'])
                        api.objects[key]['data']['approval.json'] = '{}'
                    else:
                        role = next(obj for obj in api.objects.values() if obj['kind']=='Role')
                        if mutation=='uid': role['metadata']['uid']=uid(9999)
                        else: role['rules'].append({'apiGroups':[''],'resources':['secrets'],'verbs':['get']})
                    with self.assertRaises(ValueError): d.Delivery(self.config,path,api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch).tick()
                    self.assertEqual(len(api.mutations),8)

    def test_invalid_or_stale_trusted_export_has_no_mutations(self):
        for key,value in (('source_sha256','sha256:'+'0'*64),
                          ('captured_at',(NOW-timedelta(seconds=121)).isoformat()),
                          ('driver_epoch',self.epoch)):
            with self.subTest(key=key):
                capture={**self.capture,key:value}
                with self.assertRaises(ValueError):
                    d.Delivery(self.config,self.path,self.api,lambda:capture,lambda:NOW,epoch_reader=lambda:self.epoch).tick()
                self.assertEqual(self.api.mutations,[])

    def test_superseded_pending_revision_advances_without_old_loaded_acks_after_restart(self):
        self.controller().tick()
        state = r.parse((self.path/'state.json').read_bytes())
        second = state['transition']['publication']
        # Processes are real structurally matched Pending Pods; no head2 ack is published.
        self.api.launch(second,pending=True,acknowledge=False)
        registry = r.parse(self.capture['source_raw']); registry['generation'] += 1
        raw = r.canonical(registry)
        self.capture.update(source_raw=raw,source_sha256='sha256:'+hashlib.sha256(raw.encode()).hexdigest(),
            trusted_revision=r.canonical_sha256(registry))
        result = self.controller().tick()
        self.assertEqual(result['phase'],'source-advanced'); self.assertFalse(result['ready'])
        state = r.parse((self.path/'state.json').read_bytes())
        self.assertIsNone(state['transition']); self.assertEqual(state['publication']['revision'],second['revision'])
        # A new instance must plan head3 from the actual applied head2 baseline.
        result = self.controller().tick()
        self.assertEqual(result['phase'],'processes'); self.assertFalse(result['ready'])
        third = r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.assertEqual(third['revision'],self.capture['trusted_revision'])
        self.assertEqual(len(r.parse(third['documents']['node']['data']['approval.json'])['history']),8)
        self.api.launch(third)
        self.assertTrue(self.controller().tick()['ready'])

    def test_qualified_epoch_must_come_from_independent_observation(self):
        with self.assertRaises(ValueError):
            d.Delivery(self.config,self.path,self.api,lambda:self.capture,lambda:NOW,
                epoch_reader=lambda:{**self.epoch,'boot_id':'foreign'}).tick()
        self.assertEqual(self.api.mutations,[])

    def test_bound_prior_reference_uid_replacement_denied_in_seed_and_completed_journal(self):
        for completed in (False,True):
            with self.subTest(completed=completed), tempfile.TemporaryDirectory() as temp:
                api=MemoryAPI(self.fixture); path=Path(temp)/'journal'; capture=copy.deepcopy(self.capture)
                controller=lambda:d.Delivery(self.config,path,api,lambda:capture,lambda:NOW,epoch_reader=lambda:self.epoch)
                if completed:
                    controller().tick()
                    publication=r.parse((path/'state.json').read_bytes())['transition']['publication']
                    api.launch(publication); self.assertTrue(controller().tick()['ready'])
                    state=r.parse((path/'state.json').read_bytes()); ref=state['baselines']['node']['previous_reference']
                    registry=r.parse(capture['source_raw']); registry['generation']+=1; raw=r.canonical(registry)
                    capture.update(source_raw=raw,source_sha256='sha256:'+hashlib.sha256(raw.encode()).hexdigest(),
                        trusted_revision=r.canonical_sha256(registry))
                else:
                    ref=self.config['baselines']['node']['previous_reference']
                actual=api.objects['ConfigMap',ref['metadata']['namespace'],ref['metadata']['name']]
                actual['metadata']['uid']=uid(9090)
                count=len(api.mutations)
                with self.assertRaises(ValueError): controller().tick()
                self.assertEqual(len(api.mutations),count)

    def test_completed_current_head_pending_pod_turnover_rebinds_without_fabricated_ack(self):
        self.controller().tick()
        publication=r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.api.launch(publication); self.assertTrue(self.controller().tick()['ready'])
        for index,c in enumerate(r.COMPONENTS):
            pod=self.api.current['pods'][c]
            rs=self.api.current['replicasets'][c]
            rs['metadata'].update(name=rs['metadata']['name']+'-restart',uid=uid(6100+index))
            pod['metadata'].update(name=pod['metadata']['name']+'-restart',uid=uid(6000+index))
            pod['metadata']['ownerReferences'][0].update(name=rs['metadata']['name'],uid=rs['metadata']['uid'])
            pod['status']={'phase':'Pending','conditions':[{'type':'Ready','status':'False'}]}
        acks={c:self.api.get('ConfigMap',ref['namespace'],ref['name']) for c,ref in publication['acknowledgment_references'].items()}
        count=len(self.api.mutations)
        self.assertFalse(self.controller().tick()['ready'])
        self.assertEqual(len(self.api.mutations),count+7)
        for obj in self.api.objects.values():
            if obj['kind']=='Role':
                for rule in obj['rules']:
                    if rule['resources'] in (['pods'],['replicasets']): self.assertTrue(rule['resourceNames'][0].endswith('-restart'))
        for c,ref in publication['acknowledgment_references'].items():
            self.assertEqual(self.api.get('ConfigMap',ref['namespace'],ref['name']),acks[c])
        # Real fresh replacement receipts restore readiness, without another Source revision.
        for c,ref in publication['acknowledgment_references'].items():
            pod=self.api.current['pods'][c]; pod['status']=copy.deepcopy(self.fixture[2]['pods'][c]['status'])
            ack=self.api.get('ConfigMap',ref['namespace'],ref['name']); proof=r.parse(ack['data']['ack.json'])
            proof['process'].update(name=pod['metadata']['name'],uid=pod['metadata']['uid'])
            ack['data']['ack.json']=r.canonical(proof); self.api.put(ack)
        self.assertTrue(self.controller().tick()['ready'])

    def test_idle_rebinding_restart_partial_roles_and_replaced_role_uid_fail_closed(self):
        self.controller().tick()
        publication=r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.api.launch(publication); self.assertTrue(self.controller().tick()['ready'])
        for c in r.COMPONENTS:
            self.api.current['pods'][c]['metadata']['name']+='-restarted'
            self.api.current['pods'][c]['metadata']['uid']=uid(7000+r.COMPONENTS.index(c))
        self.api.crash_at=len(self.api.mutations)+3
        with self.assertRaises(RuntimeError): self.controller().tick()
        self.api.crash_at=None
        self.assertFalse(self.controller().tick()['ready'])
        count=len(self.api.mutations)
        role=next(obj for obj in self.api.objects.values() if obj['kind']=='Role')
        role['metadata']['uid']=uid(9900)
        with self.assertRaises(ValueError): self.controller().tick()
        self.assertEqual(len(self.api.mutations),count)

    def test_current_head_foreign_process_template_or_role_rules_fail_before_rebinding(self):
        self.controller().tick()
        publication=r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.api.launch(publication); self.assertTrue(self.controller().tick()['ready'])
        count=len(self.api.mutations)
        self.api.current['pods']['node']['spec']['containers'][0]['command']=['/foreign']
        with self.assertRaises(ValueError): self.controller().tick()
        self.assertEqual(len(self.api.mutations),count)
        self.api.current['pods']['node']['spec']['containers'][0].pop('command')
        role=next(obj for obj in self.api.objects.values() if obj['kind']=='Role')
        role['rules'].append({'apiGroups':[''],'resources':['secrets'],'verbs':['get']})
        with self.assertRaises(ValueError): self.controller().tick()
        self.assertEqual(len(self.api.mutations),count)

    def test_exclusive_journal_lock_and_changed_seed_prevent_mutations(self):
        self.path.mkdir(mode=0o700)
        with (self.path/'lock').open('w') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.controller().tick()
        self.assertEqual(self.api.mutations,[])
        self.controller().tick(); count=len(self.api.mutations)
        config={**self.config,'ttlSeconds':31}
        with self.assertRaisesRegex(ValueError,'different reviewed seed'):
            d.Delivery(config,self.path,self.api,lambda:self.capture,lambda:NOW,epoch_reader=lambda:self.epoch).tick()
        self.assertEqual(len(self.api.mutations),count)

    def test_resource_version_churn_is_rebased_under_uid_and_full_value_guards(self):
        self.api.crash_at=8
        with self.assertRaises(RuntimeError): self.controller().tick()
        self.api.crash_at=None
        for obj in self.api.objects.values():
            if obj['kind'] in ('Role','Deployment'): obj['metadata']['resourceVersion']='90'
        self.assertEqual(self.controller().tick()['phase'],'processes')
        self.assertEqual(len(self.api.mutations),19)

    def test_pending_process_replacement_rebinds_only_actual_named_get_permissions(self):
        self.controller().tick()
        publication=r.parse((self.path/'state.json').read_bytes())['transition']['publication']
        self.api.launch(publication,pending=True,acknowledge=False)
        self.assertFalse(self.controller().tick()['ready'])
        for c in r.COMPONENTS:
            pod=self.api.current['pods'][c]
            pod['metadata'].update(name=pod['metadata']['name']+'-replacement',uid=uid(5000+r.COMPONENTS.index(c)))
        result=self.controller().tick()
        self.assertFalse(result['ready'])
        for obj in self.api.objects.values():
            if obj['kind']=='Role':
                for rule in obj['rules']:
                    if rule['resources']==['pods']:
                        self.assertTrue(rule['resourceNames'][0].endswith('-replacement'))

    def test_actual_kubectl_and_capture_subprocess_interfaces_are_scoped(self):
        # Real subprocess boundary with a controlled executable, no cluster.
        script=Path(self.temp.name)/'command.py'
        script.write_text('#!/usr/bin/env python3\nimport json,sys\n'
            'print(json.dumps({"argv":sys.argv[1:],"body":sys.stdin.read()}))\n')
        script.chmod(0o700)
        api=d.Kubectl('reviewed-context',str(script))
        result=api.patch('Role','cit-jhub','approval-reader',[])
        self.assertEqual(result['argv'],['--context','reviewed-context','--request-timeout=20s',
            'patch','Role','approval-reader','-n','cit-jhub','--type=json','-p','[]','-o','json'])
        result=api.create({'apiVersion':'v1','kind':'ConfigMap','immutable':True,
            'metadata':{'namespace':'jupyterhub','name':'new-document'},'data':{'approval.json':'{}'}})
        self.assertEqual(result['argv'][3:9],['create','-n','jupyterhub','-f','-','-o'])
        self.assertEqual(r.parse(result['body'])['metadata']['name'],'new-document')
        with self.assertRaises(ValueError): api.patch('Secret','cps-compute','foreign',[])
        with self.assertRaises(ValueError): api.create({'kind':'ConfigMap','immutable':False})
        capture_script=Path(self.temp.name)/'capture.py'
        capture_script.write_text('#!/usr/bin/env python3\nprint('+repr(r.canonical(self.capture))+')\n')
        capture_script.chmod(0o700)
        self.assertEqual(d.CommandCapture([str(capture_script)])(),self.capture)

    def test_runtime_template_is_disabled_and_has_only_named_mutation_targets(self):
        import native_group_approval_delivery_runtime as runtime
        objects=runtime.render(self.config,image='ghcr.io/example/delivery@sha256:'+'a'*64,
            config_secret='operator-delivery-input',journal_pvc='operator-delivery-journal',context='reviewed-context')
        deployment=next(o for o in objects if o['kind']=='Deployment')
        self.assertEqual(deployment['spec']['replicas'],0)
        roles=[o for o in objects if o['kind']=='Role']
        self.assertEqual(len(roles),4)
        targets={}
        for role in roles:
            for rule in role['rules']:
                self.assertNotIn('*',rule['verbs'])
                self.assertNotIn('secrets',rule['resources'])
                if 'patch' in rule['verbs']:
                    self.assertIn('resourceNames',rule)
                    self.assertIn(rule['resources'],[['deployments'],['roles']])
                    targets[role['metadata']['namespace'],tuple(rule['resources'])]=rule['resourceNames']
                if 'create' in rule['verbs']: self.assertEqual(rule['resources'],['configmaps'])
        self.assertEqual(sum(len(names) for (ns,resource),names in targets.items() if resource==('deployments',)),4)
        self.assertEqual(sum(len(names) for (ns,resource),names in targets.items() if resource==('roles',)),7)
        policy=next(o for o in objects if o['kind']=='ValidatingAdmissionPolicy')
        self.assertEqual(policy['spec']['failurePolicy'],'Fail')
        self.assertEqual(policy['spec']['matchConstraints']['resourceRules'][0]['operations'],['CREATE'])


if __name__ == '__main__': unittest.main()
