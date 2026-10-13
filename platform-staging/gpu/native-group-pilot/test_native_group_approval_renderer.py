"""Offline projection guards; fixtures are not live readiness evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from cps_compute.native_group_approvals import ApprovalSnapshot
from cps_compute.native_group_revision import ApprovalRevision, approval_envelope
from cps_compute.native_gpu_controller import DriverEpoch
from cps_compute.native_groups import NativeGroupDeployment, canonical_sha256
from test_native_group_packing import measured_fixture
import native_group_approval_renderer as r


NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
NAMESPACES = {'gateway':'cps-compute', 'hub:cps':'jupyterhub',
              'hub:cit':'cit-jhub', 'node':'cps-native-system'}


def uid(n):
    return '00000000-0000-4000-8000-' + f'{n:012d}'


def fixture():
    policy, config = measured_fixture((5, 10), budget=15360, slots=2)
    config['authorityNamespace'] = 'cps-native-system'
    qualification = NativeGroupDeployment.from_config(config, policy)
    registry = {'version':1, 'generation':1, 'deployment':copy.deepcopy(config)}
    raw = r.canonical(registry).encode()
    baselines = {}
    for index, (component, namespace) in enumerate(NAMESPACES.items(), 1):
        name = component.replace(':', '-')
        container = {'name':name, 'image':'ghcr.io/example/' + name + '@sha256:' + str(index)*64,
            'args':['--config', '/config/config.json'], 'env':[{'name':'PRESERVED', 'value':'kept'}],
            'volumeMounts':[{'name':'config', 'mountPath':'/config', 'readOnly':True}],
            'securityContext':{'allowPrivilegeEscalation':False}}
        spec = {'replicas':1, 'selector':{'matchLabels':{'app':name}},
            'template':{'metadata':{'labels':{'app':name}}, 'spec':{
                'serviceAccountName':name, 'containers':[container],
                'volumes':[{'name':'config', 'configMap':{'name':'untouched-static'}}]}}}
        deployment = {'apiVersion':'apps/v1', 'kind':'Deployment',
            'metadata':{'namespace':namespace, 'name':name, 'uid':uid(index), 'resourceVersion':'4'},
            'spec':spec}
        baselines[component] = {'deployment':deployment, 'container':name,
            'previous_document':None, 'previous_reference':None}
    return policy, qualification, registry, raw, baselines


def request(f):
    policy, qualification, registry, raw, baselines = f
    return dict(source_raw=raw, source_sha256='sha256:'+hashlib.sha256(raw).hexdigest(),
        trusted_revision=canonical_sha256(registry), policy=policy, qualification=qualification,
        baselines=baselines, captured_at=NOW, now=NOW)


def actual_documents(plan):
    result = copy.deepcopy(plan['documents'])
    for index, cm in enumerate(result.values(), 10):
        cm['metadata'].update(uid=uid(index), resourceVersion='8')
    return result


def readiness_fixture(f, projection, documents):
    policy, qualification, _, _, baselines = f
    pool = qualification._config()['node_pool']
    epoch = DriverEpoch(pool['node_uid'], pool['boot_id'], pool['driver_generation'], pool['gpu_uuid'])
    deployments, replicasets, pods, processes, acks = {}, {}, {}, {}, {}
    for index, component in enumerate(NAMESPACES, 20):
        baseline = baselines[component]
        deployment = copy.deepcopy(baseline['deployment'])
        deployment['spec'] = copy.deepcopy(projection['patches'][component][-1]['value'])
        deployment['metadata'].update(resourceVersion='20', generation=2)
        deployment['status'] = {'observedGeneration':2, 'updatedReplicas':1, 'readyReplicas':1}
        rs = {'apiVersion':'apps/v1', 'kind':'ReplicaSet',
            'metadata':{'namespace':NAMESPACES[component], 'name':'rs-'+str(index), 'uid':uid(index),
                'resourceVersion':'1', 'ownerReferences':[{'apiVersion':'apps/v1','kind':'Deployment', 'name':deployment['metadata']['name'],
                    'uid':deployment['metadata']['uid'], 'controller':True}]},
            'spec':{'template':copy.deepcopy(deployment['spec']['template'])}}
        pod = {'apiVersion':'v1', 'kind':'Pod',
            'metadata':{'namespace':NAMESPACES[component], 'name':'pod-'+str(index), 'uid':uid(index+10),
                'resourceVersion':'1', 'labels':copy.deepcopy(deployment['spec']['template']['metadata']['labels']),
                'ownerReferences':[{'apiVersion':'apps/v1','kind':'ReplicaSet', 'name':rs['metadata']['name'],
                    'uid':rs['metadata']['uid'], 'controller':True}]},
            'spec':copy.deepcopy(deployment['spec']['template']['spec']),
            'status':{'phase':'Running', 'conditions':[{'type':'Ready', 'status':'True'}],
                'containerStatuses':[{'name':baseline['container'], 'ready':True,
                    'imageID':'docker-pullable://'+deployment['spec']['template']['spec']['containers'][0]['image']}]}}
        if component=='node':pod['spec']['nodeName']=pool['node']
        process = {'namespace':NAMESPACES[component], 'name':pod['metadata']['name'], 'uid':pod['metadata']['uid'],
            'container':baseline['container'], 'image':pod['spec']['containers'][0]['image'],
            'service_account':pod['spec']['serviceAccountName']}
        revision = ApprovalRevision.from_configmap(documents[component], policy, qualification)
        ack = {'version':1, 'component':component, 'revision':revision.reference['revision'],
            'policy_hash':policy.hash, 'document':revision.reference, 'process':process,
            'driver_epoch':epoch.__dict__, 'observed_at':NOW.isoformat()}
        deployments[component], replicasets[component], pods[component] = deployment, rs, pod
        processes[component], acks[component] = process, ack
    return dict(deployments=deployments, replicasets=replicasets, pods=pods,
        expected_processes=processes, acknowledgments=acks, driver_epoch=epoch, now=NOW)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture()
        self.args = request(self.f)

    def test_identical_document_initial_create_and_no_invented_identity(self):
        plan = r.document_intent(**self.args)
        self.assertEqual(len(plan['documents']), 4)
        self.assertEqual(len({cm['data']['approval.json'] for cm in plan['documents'].values()}), 1)
        for component, cm in plan['documents'].items():
            self.assertEqual(cm['metadata']['namespace'], NAMESPACES[component])
            self.assertNotIn('uid', cm['metadata'])
            self.assertTrue(cm['immutable'])
        self.assertFalse(plan['live_applied'])
        self.assertEqual(self.f[-1], self.args['baselines'])

    def test_source_raw_pin_scope_profile_members_and_storage_cannot_be_forged(self):
        for mutate in (
            lambda d: d['deployment']['node_pool'].update(memory_budget_mib=99999),
            lambda d: d['deployment']['workspaces']['cps:group-5'].update(profiles=['interactive-shared-20']),
            lambda d: d['deployment']['workspaces']['cps:group-5'].update(members=['forged']),
            lambda d: d['deployment']['workspaces']['cps:group-5']['storage'].update(path='/etc'),
            lambda d: d['deployment']['workspaces'].update({'other:group':d['deployment']['workspaces']['cps:group-5']}),
        ):
            registry = copy.deepcopy(self.f[2]); mutate(registry)
            with self.assertRaises(ValueError):
                r.document_intent(**dict(self.args, source_raw=r.canonical(registry).encode()))

    def test_valid_raw_pin_still_cannot_broaden_qualification(self):
        registry = copy.deepcopy(self.f[2]); registry['deployment']['node_pool']['headroom_mib'] = 0
        raw = r.canonical(registry).encode()
        with self.assertRaises(ValueError):
            r.document_intent(**dict(self.args, source_raw=raw,
                source_sha256='sha256:'+hashlib.sha256(raw).hexdigest(), trusted_revision=canonical_sha256(registry)))

    def test_freshness_and_actual_identity_required(self):
        for change in ({'captured_at':NOW-timedelta(seconds=121)}, {'captured_at':NOW+timedelta(seconds=1)}):
            with self.assertRaises(ValueError):r.document_intent(**dict(self.args, **change))
        for field in ('uid', 'resourceVersion'):
            bad=copy.deepcopy(self.args['baselines']); del bad['node']['deployment']['metadata'][field]
            with self.assertRaises(ValueError):r.document_intent(**dict(self.args, baselines=bad))

    def test_actual_readbacks_required_and_minimal_full_spec_cas(self):
        plan = r.document_intent(**self.args); docs = actual_documents(plan)
        output = r.projection_intent(**self.args, documents=docs)
        for component, baseline in self.f[-1].items():
            patch = output['patches'][component]
            self.assertEqual(patch[:3], [
                {'op':'test','path':'/metadata/uid','value':baseline['deployment']['metadata']['uid']},
                {'op':'test','path':'/metadata/resourceVersion','value':'4'},
                {'op':'test','path':'/spec','value':baseline['deployment']['spec']}])
            before=baseline['deployment']['spec']['template']['spec']; after=patch[-1]['value']['template']['spec']
            self.assertEqual(after['containers'][0]['image'], before['containers'][0]['image'])
            self.assertEqual(after['serviceAccountName'], before['serviceAccountName'])
            self.assertEqual(after['volumes'][0], before['volumes'][0])
            self.assertEqual(after['containers'][0]['securityContext'], before['containers'][0]['securityContext'])
            self.assertEqual(output['references'][component]['uid'], docs[component]['metadata']['uid'])
            self.assertEqual(output['references'][component]['data_sha256'], canonical_sha256(docs[component]['data']))
        self.assertEqual(output['references']['node']['namespace'], 'cps-native-system')
        with self.assertRaises(ValueError):r.projection_intent(**self.args, documents=plan['documents'])
        bad=copy.deepcopy(docs); bad['gateway']['data']['approval.json']+='\n'
        with self.assertRaises(ValueError):r.projection_intent(**self.args, documents=bad)

    def test_collision_and_node_arg_are_closed(self):
        plan=r.document_intent(**self.args); docs=actual_documents(plan)
        bad=copy.deepcopy(self.args['baselines'])
        bad['node']['deployment']['spec']['template']['spec']['containers'][0]['args']+=['--approval-reference=/forged']
        with self.assertRaises(ValueError):r.projection_intent(**dict(self.args, baselines=bad), documents=docs)
        bad=copy.deepcopy(self.args['baselines'])
        bad['gateway']['deployment']['spec']['template']['spec']['volumes'].append(
            {'name':'cps-native-approval-document', 'secret':{'secretName':'foreign'}})
        with self.assertRaises(ValueError):r.projection_intent(**dict(self.args, baselines=bad), documents=docs)

    def test_successive_revision_retains_all_prior_actual_document_refs(self):
        docs=actual_documents(r.document_intent(**self.args))
        projection=r.projection_intent(**self.args, documents=docs)
        baselines=copy.deepcopy(self.args['baselines'])
        for index, component in enumerate(NAMESPACES, 40):
            row=baselines[component]
            row['deployment']['spec']=projection['patches'][component][-1]['value']
            row['deployment']['metadata']['resourceVersion']='next'
            row['previous_document']=docs[component]
            row['previous_reference']=copy.deepcopy(projection['reference_maps'][component])
            row['previous_reference']['metadata'].update(uid=uid(index), resourceVersion='2')
        registry=copy.deepcopy(self.f[2]); registry['generation']=2
        registry['deployment']['workspaces']={}
        raw=r.canonical(registry).encode()
        args=dict(self.args, baselines=baselines, source_raw=raw,
            source_sha256='sha256:'+hashlib.sha256(raw).hexdigest(), trusted_revision=canonical_sha256(registry))
        plan=r.document_intent(**args)
        envelope=json.loads(plan['documents']['node']['data']['approval.json'])
        self.assertEqual(envelope['history'], [projection['references'][c] for c in r.COMPONENTS])
        result=r.projection_intent(**args, documents=actual_documents(plan))
        self.assertEqual(result['patches']['node'][-1]['value']['template']['spec']['containers'][0]['args'],
            ['--config','/config/config.json','--approval-reference',r.DIRECTORY+'/reference.json',
                '--approval-template',r.DIRECTORY+'/template.json','--approval-process',r.DIRECTORY+'/process.json'])
        with self.assertRaises(ValueError):r.document_intent(**dict(self.args, baselines=baselines))
        bad=copy.deepcopy(baselines); bad['gateway']['previous_document']=None; bad['gateway']['previous_reference']=None
        with self.assertRaises(ValueError):r.document_intent(**dict(args, baselines=bad))

    def test_real_replica_hash_and_actual_reference_inputs_checked(self):
        docs=actual_documents(r.document_intent(**self.args))
        projection=r.projection_intent(**self.args, documents=docs)
        ready=readiness_fixture(self.f, projection, docs)
        for component in NAMESPACES:
            rs=ready['replicasets'][component]
            rs['spec']['template']['metadata']['labels']['pod-template-hash']='5d7699686'
            rs['spec']['selector']=copy.deepcopy(ready['deployments'][component]['spec']['selector'])
            rs['spec']['selector']['matchLabels']['pod-template-hash']='5d7699686'
            ready['pods'][component]['metadata']['labels']['pod-template-hash']='5d7699686'
        self.assertTrue(r.readiness_intent(projection=projection, documents=docs,
            policy=self.f[0], qualification=self.f[1], **ready)['ready'])
        for mutate in (
            lambda d: d['pods']['node']['metadata']['labels'].update({'pod-template-hash':'different'}),
            lambda d: d['pods']['hub:cps']['spec']['volumes'][2]['configMap'].update(name='old-reference'),
            lambda d: d['pods']['gateway']['spec']['containers'][0]['env'][-1].update(value='node'),
            lambda d: d['pods']['node']['spec']['volumes'][3]['configMap'].update(name='foreign-bootstrap'),
        ):
            bad=copy.deepcopy(ready); mutate(bad)
            with self.assertRaises(ValueError):r.readiness_intent(projection=projection, documents=docs,
                policy=self.f[0], qualification=self.f[1], **bad)

    def test_node_qualified_template_and_fixed_process_bootstrap_are_explicit(self):
        docs=actual_documents(r.document_intent(**self.args))
        result=r.projection_intent(**self.args, documents=docs)
        self.assertEqual(set(result['bootstrap_maps']), {'node'})
        bootstrap=result['bootstrap_maps']['node']
        self.assertEqual(json.loads(bootstrap['data']['template.json']), self.f[1]._config())
        self.assertEqual(json.loads(bootstrap['data']['process.json']), {
            'namespace':'cps-native-system', 'kind':'Deployment', 'name':'node', 'uid':uid(4), 'container':'node',
            'image':self.f[-1]['node']['deployment']['spec']['template']['spec']['containers'][0]['image'],
            'service_account':'node'})
        pod=result['patches']['node'][-1]['value']['template']['spec']
        volume=next(v for v in pod['volumes'] if v['name']==r.BOOTSTRAP_VOLUME)
        self.assertEqual(volume['configMap']['defaultMode'], 0o400)
        self.assertEqual({m['subPath'] for m in pod['containers'][0]['volumeMounts'] if m['name']==r.BOOTSTRAP_VOLUME},
            {'template.json','process.json'})
        bad=copy.deepcopy(self.args['baselines'])
        bad['node']['deployment']['spec']['template']['spec']['containers'][0]['args']+=['--approval-template','/foreign']
        with self.assertRaises(ValueError):r.projection_intent(**dict(self.args, baselines=bad), documents=docs)

    def test_cli_inert_and_private_render_files(self):
        self.assertEqual(r.main([]), 0)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); request_file=root/'input.json'
            policy, qualification, registry, raw, baselines=self.f
            captured=datetime.now(timezone.utc).isoformat()
            request_file.write_text(r.canonical({'version':1, 'source_raw':raw.decode(),
                'source_sha256':self.args['source_sha256'], 'trusted_revision':self.args['trusted_revision'],
                'policy':policy.catalog, 'qualification':qualification._config(), 'baselines':baselines,
                'captured_at':captured, 'documents':None}))
            os.chmod(request_file, 0o600)
            self.assertEqual(r.main(['--render','--input',str(request_file),'--output',str(root/'output')]), 0)
            self.assertEqual((root/'output').stat().st_mode&0o777, 0o700)
            self.assertEqual((root/'output'/'intent.json').stat().st_mode&0o777, 0o600)
            os.chmod(request_file, 0o644)
            with self.assertRaises(ValueError):r.main(['--render','--input',str(request_file),'--output',str(root/'bad')])
    def test_actual_process_readiness_and_node_reference(self):
        docs=actual_documents(r.document_intent(**self.args))
        projection=r.projection_intent(**self.args, documents=docs)
        ready=readiness_fixture(self.f, projection, docs)
        result=r.readiness_intent(projection=projection, documents=docs,
            policy=self.f[0], qualification=self.f[1], **ready)
        self.assertTrue(result['ready'])
        self.assertEqual(result['enrollment_approval_reference'], projection['references']['node'])
        for mutate in (
            lambda d: d['acknowledgments']['node'].update(observed_at=(NOW-timedelta(seconds=31)).isoformat()),
            lambda d: d['pods']['gateway']['metadata']['ownerReferences'][0].update(uid=uid(999)),
            lambda d: d['deployments']['hub:cps']['spec']['template']['spec']['containers'][0].update(image='foreign'),
            lambda d: d['acknowledgments']['hub:cit'].update(document=projection['references']['hub:cps']),
            lambda d: d['expected_processes']['node'].update(uid=uid(998)),
            lambda d: d['deployments']['node']['status'].update(observedGeneration=1),
            lambda d: d['pods']['gateway']['spec']['containers'][0].update(command=['/forged']),
            lambda d: d['pods']['hub:cps']['spec']['containers'][0].update(securityContext={'privileged':True}),
        ):
            bad=copy.deepcopy(ready); mutate(bad)
            with self.assertRaises(ValueError):r.readiness_intent(projection=projection, documents=docs,
                policy=self.f[0], qualification=self.f[1], **bad)


def actual_acknowledgments():
    return {c:{'apiVersion':'v1', 'kind':'ConfigMap', 'metadata':{'namespace':ns,
        'name':'cps-native-approval-ack-'+c.replace(':','-'), 'uid':uid(i), 'resourceVersion':'1'},
        'data':{'ack.json':'{}'}} for i,(c,ns) in enumerate(NAMESPACES.items(),100)}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture(); self.args=request(self.f)
        self.docs=actual_documents(r.document_intent(**self.args))
        self.projection=r.projection_intent(**self.args, documents=self.docs)
        self.acks=actual_acknowledgments()
        pool=self.f[1]._config()['node_pool']
        self.epoch=DriverEpoch(pool['node_uid'],pool['boot_id'],pool['driver_generation'],pool['gpu_uuid'])

    def publisher(self, **changes):
        kwargs=dict(projection=self.projection, documents=self.docs,
            baselines=self.f[-1], acknowledgments=self.acks, policy=self.f[0],qualification=self.f[1],
            driver_epoch=self.epoch)
        kwargs.update(changes)
        return r.publisher_intent(**kwargs)

    def test_uid_pinned_bootstrap_preserves_static_spec_and_no_fake_readiness(self):
        result=self.publisher()
        self.assertFalse(result['process_readiness_verified'])
        self.assertEqual(set(result['bootstrap_maps']),set(r.COMPONENTS))
        for c in r.COMPONENTS:
            ref=result['acknowledgment_references'][c]
            self.assertEqual(ref,{k:self.acks[c]['metadata'][k] for k in ('namespace','name','uid')})
            self.assertEqual(result['process_declarations'][c]['uid'],self.f[-1][c]['deployment']['metadata']['uid'])
            self.assertEqual(set(result['process_declarations'][c]),{'namespace','kind','name','uid','container','image','service_account'})
            spec=result['patches'][c][-1]['value']['template']['spec']
            old=self.f[-1][c]['deployment']['spec']['template']['spec']
            self.assertEqual(spec['containers'][0]['image'],old['containers'][0]['image'])
            self.assertEqual(spec['volumes'][0],old['volumes'][0])
            self.assertEqual(result['patches'][c][:3],self.projection['patches'][c][:3])
            data=result['bootstrap_maps'][c]['data']
            if c=='node':
                self.assertEqual(json.loads(data['acknowledgment.json']),ref)
                self.assertEqual(json.loads(data['process.json']),result['process_declarations'][c])
                self.assertEqual(spec['containers'][0]['args'][-2:],['--approval-acknowledgment',r.DIRECTORY+'/acknowledgment.json'])
                volume=next(v for v in spec['volumes'] if v['name']==r.BOOTSTRAP_VOLUME)
                self.assertEqual(volume['configMap']['defaultMode'],0o400)
            else:
                bootstrap=json.loads(data['publisher.json'])
                self.assertEqual(bootstrap['acknowledgment'],ref)
                self.assertEqual(bootstrap['process'],result['process_declarations'][c])
                self.assertEqual(bootstrap['driver_epoch'],self.epoch.__dict__)
                self.assertIn({'name':'CPS_NATIVE_APPROVAL_PUBLISHER_PATH','value':r.DIRECTORY+'/publisher.json'},spec['containers'][0]['env'])

    def test_mutable_actual_ack_identity_epoch_and_scope_required(self):
        for mutate in (
            lambda d:d['node']['metadata'].pop('uid'),
            lambda d:d['node']['metadata'].update(namespace='foreign'),
            lambda d:d['gateway'].update(immutable=True),
            lambda d:d['hub:cit']['data'].update({'extra':'secret'}),
            lambda d:d['hub:cps']['metadata'].update(ownerReferences=[{'uid':uid(777)}]),
        ):
            acks=copy.deepcopy(self.acks); mutate(acks)
            with self.assertRaises(ValueError):self.publisher(acknowledgments=acks)
        with self.assertRaises(ValueError):self.publisher(driver_epoch=DriverEpoch(self.epoch.node_uid,self.epoch.boot_id,'foreign',self.epoch.gpu_uuid))
        for ttl in (True,14,121):
            with self.assertRaises(ValueError):self.publisher(ttl_seconds=ttl)

    def test_supplied_projection_cannot_smuggle_static_or_credential_changes(self):
        for mutate in (
            lambda s:s['template']['spec']['containers'][0].update(command=['/forged']),
            lambda s:s['template']['spec']['containers'][0]['env'][0].update(value='changed'),
            lambda s:s['template']['spec']['volumes'][0].update(secret={'secretName':'foreign'}),
            lambda s:s['template']['spec'].update(hostPID=True),
        ):
            projection=copy.deepcopy(self.projection)
            mutate(projection['expected_deployments']['gateway']['spec'])
            with self.assertRaises(ValueError):self.publisher(projection=projection)

    def test_named_access_contains_get_and_own_patch_only_no_predicted_pods(self):
        result=self.publisher(); intent=r.access_intent(projection=result)
        self.assertFalse(intent['live_applied'])
        for obj in intent['objects']:
            if obj['kind']!='Role':continue
            for rule in obj['rules']:
                self.assertTrue(rule['resourceNames'])
                self.assertNotIn('*',rule['resourceNames'])
                self.assertNotIn('pods',rule['resources'])
                self.assertNotIn('replicasets',rule['resources'])
                self.assertTrue(set(rule['verbs'])<={'get','patch'})
                if 'patch' in rule['verbs']:
                    role=obj['metadata']['name']
                    component=next(c for c in r.COMPONENTS if role==r.access_name(c))
                    self.assertEqual(rule['resourceNames'],[self.acks[component]['metadata']['name']])
        self.assertEqual(set(result['runtime_settings']['acknowledgments']),set(r.COMPONENTS))
        self.assertEqual(result['runtime_settings']['acknowledgments'],result['acknowledgment_references'])
        bad=copy.deepcopy(result);bad['acknowledgment_references']['node']['namespace']='foreign'
        with self.assertRaises(ValueError):r.access_intent(projection=bad)

    def test_process_access_uses_actual_owner_chain_and_guarded_role_rules(self):
        result=self.publisher(); observations=readiness_fixture(self.f,result,self.docs)
        for c in r.COMPONENTS:
            rs=observations['replicasets'][c]; pod=observations['pods'][c]
            rs['metadata']['ownerReferences'][0]['apiVersion']='apps/v1'
            pod['metadata']['ownerReferences'][0]['apiVersion']='apps/v1'
            pod['metadata']['labels']=copy.deepcopy(observations['deployments'][c]['spec']['template']['metadata']['labels'])
        initial=r.access_intent(projection=result)
        roles={}
        for i,obj in enumerate(initial['objects'],200):
            if obj['kind']=='Role':
                obj=copy.deepcopy(obj);obj['metadata'].update(uid=uid(i),resourceVersion='2')
                roles[obj['metadata']['namespace']+'/'+obj['metadata']['name']]=obj
        intent=r.process_access_intent(projection=result,deployments=observations['deployments'],
            replicasets=observations['replicasets'],pods=observations['pods'],roles=roles)
        self.assertFalse(intent['live_applied'])
        for patch in intent['patches'].values():
            self.assertEqual([p['path'] for p in patch[:3]],['/metadata/uid','/metadata/resourceVersion','/rules'])
            self.assertTrue(any(rule['resources']==['pods'] for rule in patch[-1]['value']))
        bad=copy.deepcopy(observations);bad['pods']['node']['metadata']['ownerReferences'][0]['uid']=uid(999)
        with self.assertRaises(ValueError):r.process_access_intent(projection=result,deployments=bad['deployments'],
            replicasets=bad['replicasets'],pods=bad['pods'],roles=roles)
        for mutate in (
            lambda d:d['pods']['node']['metadata']['ownerReferences'][0].update(name='unknown'),
            lambda d:d['pods']['gateway']['spec']['containers'][0].update(command=['/forged']),
            lambda d:d['replicasets']['hub:cps']['spec']['template']['spec']['containers'][0].update(args=['/old']),
        ):
            bad=copy.deepcopy(observations);mutate(bad)
            with self.assertRaises(ValueError):r.process_access_intent(projection=result,deployments=bad['deployments'],
                replicasets=bad['replicasets'],pods=bad['pods'],roles=roles)
        bad=copy.deepcopy(roles);next(iter(bad.values()))['rules'].append({'resources':['secrets'],'verbs':['get']})
        with self.assertRaises(ValueError):r.process_access_intent(projection=result,deployments=observations['deployments'],
            replicasets=observations['replicasets'],pods=observations['pods'],roles=bad)

    def test_private_cli_publisher_and_post_rollout_role_packets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.json';publisher=root/'publisher.json'
            source.write_text(r.canonical({'version':1,'source_raw':self.f[3].decode(),
                'source_sha256':self.args['source_sha256'],'trusted_revision':self.args['trusted_revision'],
                'policy':self.f[0].catalog,'qualification':self.f[1]._config(),'baselines':self.f[-1],
                'captured_at':datetime.now(timezone.utc).isoformat(),'documents':self.docs}))
            publisher.write_text(r.canonical({'version':1,'acknowledgments':self.acks,
                'driver_epoch':self.epoch.__dict__,'ttlSeconds':30}))
            os.chmod(source,0o600);os.chmod(publisher,0o600)
            self.assertEqual(r.main(['--render','--input',str(source),'--publisher-input',str(publisher),
                '--output',str(root/'publication')]),0)
            packet=json.loads((root/'publication'/'intent.json').read_text())
            self.assertEqual(packet['acknowledgment_references']['node']['uid'],self.acks['node']['metadata']['uid'])
            observed=readiness_fixture(self.f,packet,self.docs)
            roles={}
            for i,obj in enumerate(packet['initial_access']['objects'],200):
                if obj['kind']=='Role':
                    obj=copy.deepcopy(obj);obj['metadata'].update(uid=uid(i),resourceVersion='2')
                    roles[obj['metadata']['namespace']+'/'+obj['metadata']['name']]=obj
            path=root/'process.json';path.write_text(r.canonical({'version':1,'projection':packet,
                **{k:observed[k] for k in ('deployments','replicasets','pods')},'roles':roles}));os.chmod(path,0o600)
            self.assertEqual(r.main(['--render','--process-access','--input',str(path),'--output',str(root/'process')]),0)
            final=json.loads((root/'process'/'intent.json').read_text())
            self.assertEqual(len(final['patches']),7)
            self.assertFalse(final['process_readiness_verified'])


if __name__ == '__main__':unittest.main()
