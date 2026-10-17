"""CPU image adoption plans; synthetic credentials and no API/readiness proof."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import uuid

from cps_compute.immutable_configmap import ImmutableConfigMapRef
from cps_compute.native_group_revision import ApprovalRevision
from cps_compute.native_node.config import NodeConfiguration
from test_native_node_config import node_fixture, ref

SPEC = importlib.util.spec_from_file_location('current_group_image_adoption', Path(__file__).with_name('image_adoption.py'))
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def encoded(value):
    return base64.b64encode(canonical(value).encode()).decode()


def fixture():
    policy, node, core, maps = node_fixture()
    loaded = NodeConfiguration.load(core, ref(node), policy)
    config = json.loads(node['data']['config.json'])
    namespace = node['metadata']['namespace']
    counter = iter(range(1000, 2000))
    def actual(kind, name, data=None, **extra):
        value = {'apiVersion': 'rbac.authorization.k8s.io/v1' if kind == 'Role' else 'v1', 'kind': kind, 'metadata': {'namespace': namespace, 'name': name,
            'uid': str(uuid.UUID(int=next(counter))), 'resourceVersion': '9'}, **extra}
        if data is not None: value['data'] = data
        return value
    objects = {'configmap/'+v['metadata']['namespace']+'/'+v['metadata']['name']: copy.deepcopy(v)
               for v in maps.values()}
    def add(value):
        meta=value['metadata']; objects[value['kind'].lower()+'/'+meta['namespace']+'/'+meta['name']] = value
        return value
    declarations = config['component_declarations']
    old = {'gateway': 'ghcr.io/mul-cps/cps-compute@sha256:'+'1'*64,
           'hub:cps': 'ghcr.io/mul-cps/cps-compute@sha256:'+'2'*64,
           'hub:cit': 'ghcr.io/mul-cps/cps-compute@sha256:'+'2'*64,
           'node': 'ghcr.io/mul-cps/cps-native-node@sha256:'+'3'*64}
    docs={}
    for component, declaration in declarations.items():
        declaration['image'] = old[component]
        declaration['service_account'] = 'sa-' + component.replace(':', '-')
        declaration['container'] = 'node-agent' if component=='node' else 'gateway' if component=='gateway' else 'hub'
        add({'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':namespace,
            'name':declaration['service_account'],'uid':declaration['service_account_uid'],'resourceVersion':'2'}})
        doc=actual('ConfigMap','approval-'+component.replace(':','-'),copy.deepcopy(maps['approval']['data']),immutable=True)
        docs[component]=add(doc)
    config['approval_ref']=ApprovalRevision.from_configmap(docs['node'],policy,loaded.deployment).reference
    index=copy.deepcopy(maps['terminal-index']); index['data']['index.json']=canonical({'version':2,'total_records':1})
    add(index); config['terminal_index_ref']=ref(index).to_dict()
    node=copy.deepcopy(node); node['data']['config.json']=canonical(config); add(node)
    processes={c:{k:v for k,v in d.items()if k!='service_account_uid'}for c,d in declarations.items()}
    pool=loaded.deployment.node_pool
    epoch={k:pool[k]for k in ('node_uid','boot_id','driver_generation','gpu_uuid')}
    settings={'enabled':True,'acknowledgments':copy.deepcopy(config['acknowledgment_targets']),
              'processes':processes,'driver_epoch':epoch,'ttlSeconds':30}
    runtime={'policy_hash':policy.hash,'nativeGroupApprovals':settings,
             'nativeGpuGroups':json.loads(maps['deployment']['data']['deployment.json']),
             'storage':{'kept':'unchanged'},'hubs':{'kept':'unchanged'},'database_marker':'synthetic-only'}
    runtime_secret=add(actual('Secret','runtime',{'runtime.json':encoded(runtime),
        'other.key':base64.b64encode(b'synthetic-only-not-a-credential').decode()},type='Opaque'))
    policy_cm=add(actual('ConfigMap','policy',{'catalog.json':canonical(policy.catalog)}))
    seed_body={'version':1,'node_process':copy.deepcopy(processes['node']),
               'node_acknowledgment':copy.deepcopy(settings['acknowledgments']['node']),
               'database':'synthetic-only','qualification_json':'/inputs/qualification.json'}
    seed=add(actual('Secret','capture-seed',{'config.json':encoded(seed_body),
        'export.token':base64.b64encode(b'synthetic-only-not-a-token').decode(),
        'qualification.json':encoded({'retained':'exact'})},immutable=True,type='Opaque'))
    bootstrap=add(actual('ConfigMap','bootstrap',{'config-ref.json':canonical(ref(node).to_dict()),
        'policy.json':canonical(policy.catalog),'release':'true'}))
    ledger=add(actual('ConfigMap','cps-native-gpu-allocations',{'state.json':canonical({'version':1,
        'allocations':{'one':{'state':'released','audit':'retained'},'two':{'state':'released','audit':'retained2'}}})}))
    deployments={}
    for component,declaration in declarations.items():
        volumes=[{'name':'cps-native-approval-document','configMap':{'name':docs[component]['metadata']['name']}},
                 {'name':'untouched','hostPath':{'path':'/retained'}}]
        containers=[{'name':declaration['container'],'image':old[component],
            'command':['python','-m','cps_compute.native_node.service']if component=='node'else['preserved-command'],
            'env':[{'name':'PRESERVED','value':'exact'}],'volumeMounts':[{'name':'untouched','mountPath':'/retained'}]}]
        initializers=[]
        if component!='node':
            publisher={'version':1,'component':component,'process':copy.deepcopy(processes[component]),
                       'acknowledgment':copy.deepcopy(settings['acknowledgments'][component]),'driver_epoch':epoch,
                       'ttlSeconds':30 if component=='gateway' else 45}
            pub=add(actual('ConfigMap','publisher-'+component.replace(':','-'),{'publisher.json':canonical(publisher)},immutable=True))
            volumes.append({'name':'cps-native-approval-publisher','configMap':{'name':pub['metadata']['name']}})
            reference=ApprovalRevision.from_configmap(docs[component],policy,loaded.deployment).reference
            refcm=add(actual('ConfigMap','reference-'+component.replace(':','-'),{'reference.json':canonical(reference)},immutable=True))
            volumes.append({'name':'cps-native-approval-reference','configMap':{'name':refcm['metadata']['name']}})
        if component=='gateway':
            containers.append({'name':'approval-capture','image':old[component],'command':['retained-capture']})
            initializers.append({'name':'capture-private-inputs','image':old[component],'command':['retained-input-copy']})
            volumes.extend([{'name':'config','secret':{'secretName':runtime_secret['metadata']['name']}},
                            {'name':'policy','configMap':{'name':policy_cm['metadata']['name']}},
                            {'name':'capture-seed','secret':{'secretName':seed['metadata']['name']}}])
        if component=='node':
            volumes.append({'name':'packaged-bootstrap-input','configMap':{'name':bootstrap['metadata']['name']}})
            initializers.append({'name':'packaged-bootstrap','image':old[component],'command':['retained-bootstrap'],
                                 'env':[{'name':'NODE_IMAGE','value':old[component]},{'name':'PRESERVED','value':'exact'}]})
        dep={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':namespace,'name':declaration['name'],
             'uid':declaration['uid'],'resourceVersion':'8'},'spec':{'replicas':1,'strategy':{'type':'Recreate'},
             'selector':{'matchLabels':{'app':component.replace(':','-')}},'template':{
              'metadata':{'labels':{'app':component.replace(':','-')},'annotations':{'preserved':'exact'}},
              'spec':{'serviceAccountName':declaration['service_account'],'containers':containers,
                      'initContainers':initializers,'volumes':volumes}}}}
        deployments[component]=dep;add(dep)
        role='cps-native-approval-gateway'if component=='gateway'else'cps-native-approval-node'if component=='node'else'cps-native-approval-hub-'+component.split(':')[1]
        add(actual('Role',role,rules=[{'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],
              'resourceNames':['old-approved-name', node['metadata']['name'] if component=='node' else pub['metadata']['name']]},
              {'apiGroups':[''],'resources':['pods'],'verbs':['get']}] + ([{'apiGroups':[''],'resources':['configmaps'],
              'verbs':['get'],'resourceNames':['other-static-config']}] if component.startswith('hub:') else [])))
    snapshot={'version':1,'captured_at':'2026-10-17T00:00:00+00:00','objects':objects,'deployments':deployments}
    images={c:('ghcr.io/mul-cps/cps-native-node'if c=='node'else'ghcr.io/mul-cps/cps-compute')+'@sha256:'+v*64
            for c,v in zip(declarations,('a','b','c','d'))}
    return snapshot,images,config['approval_ref']['revision']


class ImageAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot,self.images,self.revision=fixture()
    def plan(self,snapshot=None,images=None):
        value=self.snapshot if snapshot is None else snapshot
        return h.render(value,self.images if images is None else images,
                        expected_snapshot_sha256=h.sha(value),expected_revision=self.revision)
    def object(self,label):
        return self.snapshot['objects'][label]
    def test_all_four_images_are_coordinated_without_mutating_input(self):
        before=copy.deepcopy(self.snapshot);plan=self.plan()
        self.assertEqual(self.snapshot,before)
        self.assertFalse(plan['live_applied']);self.assertFalse(plan['hardware_qualified'])
        node=json.loads(plan['creates']['node-config']['data']['config.json'])
        for component in self.images:
            self.assertEqual(node['component_declarations'][component]['image'],self.images[component])
        runtime_patch=plan['patches']['gateway.runtime-secret']['patch']
        new_runtime=json.loads(base64.b64decode(runtime_patch[-1]['value']['runtime.json']))
        self.assertEqual({c:v['image']for c,v in new_runtime['nativeGroupApprovals']['processes'].items()},self.images)
        old_runtime=json.loads(base64.b64decode(h.secret_volume(self.snapshot,'gateway','config')['data']['runtime.json']))
        for c in self.images:
            new_runtime['nativeGroupApprovals']['processes'][c]['image']=old_runtime['nativeGroupApprovals']['processes'][c]['image']
        self.assertEqual(new_runtime,old_runtime)
        old_node_ref=json.loads(h.volume(self.snapshot,'node','packaged-bootstrap-input')['data']['config-ref.json'])
        old_node=json.loads(self.snapshot['objects']['configmap/'+old_node_ref['namespace']+'/'+old_node_ref['name']]['data']['config.json'])
        for c in self.images:node['component_declarations'][c]['image']=old_node['component_declarations'][c]['image']
        self.assertEqual(node,old_node)
        self.assertNotIn('node.deployment',plan['patches'])
        self.assertEqual(plan['preservation']['released_ledger_entries'],2)
        self.assertEqual(plan['preservation']['archived_terminal_records'],1)
    def test_publishers_and_capture_secret_only_change_process_images(self):
        plan=self.plan()
        for component in ('gateway','hub:cps','hub:cit'):
            old=h.volume(self.snapshot,component,'cps-native-approval-publisher')
            new=plan['creates'][component+'.publisher'];body=json.loads(old['data']['publisher.json'])
            body['process']['image']=self.images[component]
            self.assertEqual(new['data'],{'publisher.json':canonical(body)})
        seed=plan['creates']['gateway.capture-seed'];old=h.secret_volume(self.snapshot,'gateway','capture-seed')
        expected=copy.deepcopy(old['data']);body=json.loads(base64.b64decode(expected['config.json']))
        body['node_process']['image']=self.images['node'];expected['config.json']=encoded(body)
        self.assertEqual(seed['data'],expected);self.assertTrue(seed['immutable'])
        self.assertNotEqual(seed['metadata']['name'],old['metadata']['name'])
        self.assertFalse(any(p['target']['name']==old['metadata']['name']for p in plan['patches'].values()))
    def test_each_patch_has_exact_identity_resource_version_and_preimage(self):
        for record in self.plan()['patches'].values():
            p=record['patch'];self.assertEqual([x['op']for x in p],['test','test','test','replace'])
            self.assertEqual([x['path']for x in p[:2]],['/metadata/uid','/metadata/resourceVersion'])
            self.assertEqual(p[2]['path'],p[3]['path'])
            self.assertEqual(set(record['target']),{'kind','namespace','name'})
    def test_roles_add_only_named_configmap_gets(self):
        plan=self.plan()
        for name,p in plan['patches'].items():
            if not name.endswith('.role'):continue
            old,new=p['patch'][2]['value'],p['patch'][3]['value']
            self.assertEqual(old[1:],new[1:])
            self.assertEqual({k:v for k,v in old[0].items()if k!='resourceNames'},
                             {k:v for k,v in new[0].items()if k!='resourceNames'})
            self.assertTrue(set(old[0]['resourceNames'])<=set(new[0]['resourceNames']))
    def test_bind_uses_actual_immutable_uid_rv_hash_and_preserves_packaged_command(self):
        plan=self.plan();actual=copy.deepcopy(plan['creates']['node-config'])
        actual['metadata'].update(uid=str(uuid.UUID(int=9999)),resourceVersion='88')
        result=h.bind_node(self.snapshot,plan,actual)
        bootstrap=result['creates']['node.bootstrap'];reference=json.loads(bootstrap['data']['config-ref.json'])
        self.assertEqual(reference['uid'],actual['metadata']['uid']);self.assertEqual(reference['resourceVersion'],'88')
        self.assertEqual(reference['data_sha256'],h.sha(actual['data']))
        self.assertEqual(bootstrap['data']['release'],'false')
        old=h.volume(self.snapshot,'node','packaged-bootstrap-input')
        self.assertEqual(bootstrap['data']['policy.json'],old['data']['policy.json'])
        desired=result['patches']['node.deployment']['patch'][-1]['value'];old_spec=self.snapshot['deployments']['node']['spec']
        expected=copy.deepcopy(old_spec)
        for row in expected['template']['spec']['containers']+expected['template']['spec']['initContainers']:row['image']=self.images['node']
        next(e for e in expected['template']['spec']['initContainers'][0]['env']if e['name']=='NODE_IMAGE')['value']=self.images['node']
        next(v for v in expected['template']['spec']['volumes']if v['name']=='packaged-bootstrap-input')['configMap']['name']=bootstrap['metadata']['name']
        self.assertEqual(desired,expected)
    def test_unchanged_gateway_reuses_actual_immutable_publisher(self):
        images=copy.deepcopy(self.images)
        images['gateway']=self.snapshot['deployments']['gateway']['spec']['template']['spec']['containers'][0]['image']
        plan=self.plan(images=images)
        old=h.volume(self.snapshot,'gateway','cps-native-approval-publisher')
        self.assertEqual(plan['reuses']['gateway.publisher'],old)
        self.assertNotIn('gateway.publisher',plan['creates'])
        actual=copy.deepcopy(plan['creates']['node-config']);actual['metadata'].update(uid=str(uuid.UUID(int=9999)),resourceVersion='88')
        stopped=copy.deepcopy(self.snapshot['deployments']['node']);stopped['spec']['replicas']=0;stopped['metadata']['resourceVersion']='99'
        bound=h.bind_node(self.snapshot,plan,actual,stopped=stopped)
        self.assertEqual(bound['patches']['node.deployment']['patch'][1]['value'],'99')
        self.assertEqual(bound['patches']['node.deployment']['patch'][2]['value'],stopped['spec'])
        stopped['spec']['template']['spec']['containers'][0]['env'].append({'name':'FOREIGN','value':'drift'})
        with self.assertRaises(ValueError):h.bind_node(self.snapshot,plan,actual,stopped=stopped)

    def test_explicit_operator_pins_and_closed_image_map_required(self):
        with self.assertRaises(ValueError):h.render(self.snapshot,self.images,expected_snapshot_sha256='sha256:'+'0'*64,expected_revision=self.revision)
        with self.assertRaises(ValueError):h.render(self.snapshot,self.images,expected_snapshot_sha256=h.sha(self.snapshot),expected_revision='sha256:'+'0'*64)
        for images in ({**self.images,'extra':self.images['node']},{k:v for k,v in self.images.items()if k!='node'},
                       {**self.images,'node':'ghcr.io/mul-cps/cps-native-node:latest'},
                       {**self.images,'node':self.images['gateway']}):
            with self.subTest(images=sorted(images)):
                with self.assertRaises(ValueError):self.plan(images=images)
    def test_cross_declaration_drift_fails_even_with_new_snapshot_pin(self):
        mutations=(
            lambda s:s['deployments']['node']['spec']['template']['spec']['containers'][0].update(image=self.images['node']),
            lambda s:s['deployments']['gateway']['metadata'].update(uid=str(uuid.UUID(int=999))),
            lambda s:s['deployments']['node']['spec']['template']['spec']['containers'][0].update(command=['sh']),
            lambda s:s['deployments']['node']['spec']['strategy'].update(type='RollingUpdate'),
            lambda s:s['deployments']['gateway']['spec']['template']['spec']['containers'][1].update(image=self.images['gateway']),
        )
        for i,mutate in enumerate(mutations):
            with self.subTest(i=i):
                value=copy.deepcopy(self.snapshot);mutate(value)
                # Keep the duplicated captured Deployment aligned to reach the
                # image/declaration checks, not merely the snapshot-copy guard.
                for dep in value['deployments'].values():value['objects']['deployment/'+dep['metadata']['namespace']+'/'+dep['metadata']['name']]=copy.deepcopy(dep)
                with self.assertRaises(ValueError):self.plan(value)
    def test_publisher_seed_and_active_ledger_drift_are_rejected(self):
        for fault in ('publisher','publisher-ttl','seed','ledger','role','bootstrap'):
            with self.subTest(fault=fault):
                value=copy.deepcopy(self.snapshot)
                if fault in ('publisher','publisher-ttl'):
                    cm=h.volume(value,'hub:cps','cps-native-approval-publisher');body=json.loads(cm['data']['publisher.json']);
                    if fault=='publisher':body['process']['image']=self.images['hub:cps']
                    else:body['ttlSeconds']=121
                    cm['data']['publisher.json']=canonical(body)
                elif fault=='seed':
                    obj=h.secret_volume(value,'gateway','capture-seed');body=json.loads(base64.b64decode(obj['data']['config.json']));body['node_process']['image']=self.images['node'];obj['data']['config.json']=encoded(body)
                elif fault=='ledger':
                    obj=next(o for o in value['objects'].values()if o['metadata']['name']=='cps-native-gpu-allocations');body=json.loads(obj['data']['state.json']);body['allocations']['one']['state']='enrolled';obj['data']['state.json']=canonical(body)
                elif fault=='role':
                    obj=next(o for o in value['objects'].values()if o['kind']=='Role'and o['metadata']['name']=='cps-native-approval-node');obj['rules'][0]['verbs']=['get','list']
                else:
                    obj=h.volume(value,'node','packaged-bootstrap-input');refbody=json.loads(obj['data']['config-ref.json']);refbody['data_sha256']='sha256:'+'0'*64;obj['data']['config-ref.json']=canonical(refbody)
                with self.assertRaises(ValueError):self.plan(value)
    def test_bootstrap_node_image_env_is_exact_and_advances_with_installed_image(self):
        for fault in ('missing','duplicate','foreign','valueFrom'):
            with self.subTest(fault=fault):
                value=copy.deepcopy(self.snapshot)
                init=value['deployments']['node']['spec']['template']['spec']['initContainers'][0]
                if fault=='missing':init['env']=[e for e in init['env']if e['name']!='NODE_IMAGE']
                elif fault=='duplicate':init['env'].append(copy.deepcopy(init['env'][0]))
                elif fault=='foreign':init['env'][0]['value']=self.images['node']
                else:init['env'][0]={'name':'NODE_IMAGE','valueFrom':{'fieldRef':{'fieldPath':'metadata.name'}}}
                dep=value['deployments']['node'];value['objects']['deployment/'+dep['metadata']['namespace']+'/'+dep['metadata']['name']]=copy.deepcopy(dep)
                with self.assertRaises(ValueError):self.plan(value)

    def test_content_addressed_collision_cannot_reuse_foreign_metadata_identity(self):
        plan=self.plan();value=copy.deepcopy(self.snapshot)
        obj=copy.deepcopy(plan['creates']['gateway.publisher']);target='configmap/'+obj['metadata']['namespace']+'/'+obj['metadata']['name']
        obj['metadata'].update(namespace='foreign',uid=str(uuid.UUID(int=9999)),resourceVersion='88')
        value['objects'][target]=obj
        with self.assertRaises(ValueError):self.plan(value)

    def test_bind_rejects_fabricated_or_changed_actual_config_and_tampered_plan(self):
        plan=self.plan();actual=copy.deepcopy(plan['creates']['node-config'])
        for fault in ('no-uid','mutable','wrong-name','changed-data','owner','tampered-plan'):
            with self.subTest(fault=fault):
                value=copy.deepcopy(actual);packet=copy.deepcopy(plan)
                value['metadata'].update(uid=str(uuid.UUID(int=9999)),resourceVersion='88')
                if fault=='no-uid':value['metadata'].pop('uid')
                elif fault=='mutable':value['immutable']=False
                elif fault=='wrong-name':value['metadata']['name']='foreign'
                elif fault=='changed-data':value['data']['config.json']='{}'
                elif fault=='owner':value['metadata']['ownerReferences']=[{'uid':'foreign'}]
                else:packet['images']['node']=self.images['gateway']
                with self.assertRaises(ValueError):h.bind_node(self.snapshot,packet,value)


if __name__=='__main__':unittest.main()
