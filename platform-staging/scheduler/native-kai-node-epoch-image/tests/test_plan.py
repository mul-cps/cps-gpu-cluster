"""Offline prospective-object tests; these fixtures grant no live authority."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('plan',HERE.parent/'plan.py')
plan=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan)


def object_(kind,name,uid):
    return {'apiVersion':'apps/v1' if kind=='Deployment' else 'v1','kind':kind,
            'metadata':{'name':name,'namespace':'cps-native-system','uid':uid,'resourceVersion':'123'}}


def fixture():
    data={p.name:p.read_text() for p in (HERE.parent/'bundle').iterdir() if p.name!='native_operator_epoch.py'}
    data['node_agent.py']=(HERE/'original-node-agent.py').read_text()
    code=object_('ConfigMap','code','11111111-1111-4111-8111-111111111111');code.update(immutable=True,data=data)
    process={'kind':'Deployment','name':'cps-native-node-agent','namespace':'cps-native-system',
             'uid':'22222222-2222-4222-8222-222222222222','container':'node-agent',
             'image':'ghcr.io/mul-cps/cps-compute@'+plan.BASE_DIGEST,'service_account':'cps-native-node-agent'}
    bootstrap=object_('ConfigMap','bootstrap','33333333-3333-4333-8333-333333333333')
    bootstrap.update(immutable=True,data={'process.json':plan.encoded(process),'template.json':'{"kept":true}',
                                        'acknowledgment.json':'{"uid":"kept"}'})
    deployment=object_('Deployment',process['name'],process['uid'])
    mounts=[{'name':'code','mountPath':'/opt/native','readOnly':True},
            {'name':'config','mountPath':'/config/config.json','subPath':'config.json','readOnly':True},
            {'name':'bootstrap','mountPath':'/var/run/cps-native-approvals/process.json','subPath':'process.json','readOnly':True}]
    args=['--execute','--config','/config/config.json','--bundle','/opt/native']
    for flag in plan.APPROVAL_FLAGS:args += [flag,'/var/run/cps-native-approvals/'+flag[2:]+'.json']
    deployment['spec']={'replicas':1,'template':{'metadata':{'labels':{'app':'kept'}},'spec':{
        'serviceAccountName':process['service_account'],'containers':[{'name':'node-agent','image':process['image'],
        'command':['python3','/opt/native/node_agent.py'],'args':args,'volumeMounts':mounts}],
        'volumes':[{'name':'code','configMap':{'name':'code'}},{'name':'bootstrap','configMap':{'name':'bootstrap'}},
                   {'name':'config','configMap':{'name':'old-config'}}]}}}
    return deployment,code,bootstrap


def operator_fixture():
    d,c,b=fixture();v=plan.v2(d,c,b);d['spec']=v['after_spec'];d['metadata']['resourceVersion']='124'
    old=object_('ConfigMap','old-config','44444444-4444-4444-8444-444444444444')
    olddata={'pool':{'node_uid':'55555555-5555-4555-8555-555555555555'},'terminal_history':{'old':'never-discard'}}
    old.update(immutable=True,data={'config.json':plan.encoded(olddata)})
    config=dict(olddata,version=2,enabled=True,mode='operator-qualification',authority_namespace='cps-native-system',
        policy_hash='sha256:'+'a'*64,workspaces={'cit:native-group-a':{'profile':'interactive-native-qualification-10','cap_mib':10240}})
    nc=object_('ConfigMap','operator-config','66666666-6666-4666-8666-666666666666')
    nc.update(immutable=True,data={'config.json':plan.encoded(config)})
    target=object_('ConfigMap','cps-native-kai-epoch-node','77777777-7777-4777-8777-777777777777');target['data']={'epoch.json':'{}'}
    sa=object_('ServiceAccount','cps-native-node-agent','88888888-8888-4888-8888-888888888888')
    process=json.loads(v['create_bootstrap']['data']['process.json']);process['service_account_uid']=sa['metadata']['uid']
    cfg={'enabled':True,'version':1,'ttlSeconds':30,'process':process,
         'target':{k:target['metadata'][k] for k in ('namespace','name','uid')},
         'node_configuration':{**{k:nc['metadata'][k] for k in ('namespace','name','uid','resourceVersion')},
                               'data_sha256':'sha256:'+plan.digest(nc['data'])}}
    settings=object_('ConfigMap','operator-settings','99999999-9999-4999-8999-999999999999')
    settings.update(immutable=True,data={'settings.json':plan.encoded(cfg)})
    return dict(deployment=d,node_config=nc,settings=settings,target=target,service_account=sa,old_config=old)


class PlanTests(unittest.TestCase):
    def test_operator_creates_use_single_frozen_authority_and_retain_history(self):
        f=operator_fixture();old=f['old_config'];q=json.loads((HERE.parent.parent/'native-kai-v1-qualification/operator-qualification.json').read_text())
        data=json.loads(old['data']['config.json']);data.update(pool=q['node_pool'],enabled=True,authority_namespace='cps-native-system',version=2,mode='qualified-group')
        old['data']['config.json']=plan.encoded(data);r=plan.operator_creates(old,q)
        created=json.loads(r['create_node_config']['data']['config.json'])
        self.assertEqual(created['terminal_history'],data['terminal_history']);self.assertEqual(created['pool'],data['pool'])
        self.assertEqual(created['policy_hash'],q['policy_hash']);self.assertNotIn('uid',r['create_node_config']['metadata'])
        q['profile_caps']['interactive-native-qualification-10']=20480
        with self.assertRaises(ValueError):plan.operator_creates(old,q)

    def test_settings_proposal_uses_only_actual_readback_refs(self):
        f=operator_fixture();r=plan.operator_settings(f['deployment'],f['node_config'],f['target'],f['service_account'])
        self.assertEqual(json.loads(r['data']['settings.json']),json.loads(f['settings']['data']['settings.json']))
        f['node_config']['metadata'].pop('uid')
        with self.assertRaises(ValueError):plan.operator_settings(f['deployment'],f['node_config'],f['target'],f['service_account'])

    def test_paired_v2_exact_minimum_delta_and_no_input_mutation(self):
        d,c,b=fixture();before=copy.deepcopy([d,c,b]);r=plan.v2(d,c,b)
        self.assertEqual([d,c,b],before);pod=r['after_spec']['template']['spec'];container=pod['containers'][0]
        self.assertEqual(container['image'],plan.IMAGE);self.assertNotIn('code',[x['name'] for x in pod['volumes']])
        self.assertNotIn('/opt/native',[x['mountPath'] for x in container['volumeMounts']])
        self.assertEqual(container['args'],d['spec']['template']['spec']['containers'][0]['args'])
        self.assertEqual(r['create_bootstrap']['data']['template.json'],b['data']['template.json'])
        self.assertEqual(r['create_bootstrap']['data']['acknowledgment.json'],b['data']['acknowledgment.json'])
        self.assertEqual(json.loads(r['create_bootstrap']['data']['process.json'])['image'],plan.IMAGE)
        self.assertEqual(r['patch'][0]['value'],d['metadata']['uid']);self.assertEqual(r['patch'][1]['value'],'123')

    def test_v2_foreign_helper_pin_and_wrong_source_and_duplicate_mount_denied(self):
        for change in ('helper','process','projection'):
            with self.subTest(change=change):
                d,c,b=fixture()
                if change=='helper':c['data']['node_backend.py']+='\n# foreign\n'
                if change=='process':b['data']['process.json']=b['data']['process.json'].replace(plan.BASE_DIGEST,'sha256:'+'f'*64)
                if change=='projection':d['spec']['template']['spec']['containers'][0]['volumeMounts'].append({'name':'code','mountPath':'/other'})
                with self.assertRaises(ValueError):plan.v2(d,c,b)

    def test_inverse_requires_actual_current_rv_and_complete_post_spec(self):
        d,c,b=fixture();r=plan.v2(d,c,b);d['spec']=copy.deepcopy(r['after_spec']);d['metadata']['resourceVersion']='999'
        inverse=plan.inverse(d,r);self.assertEqual(inverse[1]['value'],'999');self.assertEqual(inverse[-1]['value'],r['before_spec'])
        d['spec']['replicas']=2
        with self.assertRaises(ValueError):plan.inverse(d,r)

    def test_operator_mutual_exclusion_and_private_materialization(self):
        f=operator_fixture();r=plan.operator(**f);pod=r['after_spec']['template']['spec'];c=pod['containers'][0]
        self.assertIn('--operator-epoch-config',c['args']);self.assertFalse(any(flag in c['args'] for flag in plan.APPROVAL_FLAGS))
        self.assertEqual(pod['initContainers'][0]['securityContext']['capabilities'],{'drop':['ALL']})
        self.assertNotIn('/operator-input',[x['mountPath'] for x in c['volumeMounts']])
        self.assertEqual({x['name'] for x in c['env']},{'CPS_NATIVE_OPERATOR_POD_NAME','CPS_NATIVE_OPERATOR_POD_UID','CPS_NATIVE_OPERATOR_POD_NAMESPACE'})
        self.assertIn('os.O_EXCL|os.O_NOFOLLOW,0o600',r['materialize_command'])

    def test_operator_actual_readbacks_epoch_history_and_scope_required(self):
        for change in ('target','rv','sa','history','pool','cap','scope','v2mask'):
            with self.subTest(change=change):
                f=operator_fixture()
                if change=='target':f['target']['metadata']['uid']='replaced'
                if change=='rv':f['node_config']['metadata']['resourceVersion']='999'
                if change=='sa':f['service_account']['metadata']['uid']='replaced'
                if change in ('history','pool','cap','scope'):
                    c=json.loads(f['node_config']['data']['config.json'])
                    if change=='history':c['terminal_history']={}
                    if change=='pool':c['pool']['node_uid']='replaced'
                    if change=='cap':c['workspaces']['cit:native-group-a']['cap_mib']=20480
                    if change=='scope':c['workspaces']['cps:native-group-b']=c['workspaces']['cit:native-group-a']
                    f['node_config']['data']['config.json']=plan.encoded(c)
                if change=='v2mask':f['deployment']['spec']['template']['spec']['containers'][0]['volumeMounts'].append({'name':'code','mountPath':'/opt/native'})
                with self.assertRaises(ValueError):plan.operator(**f)

    def test_post_create_rbac_remains_exact_names_and_foreign_controller_denied(self):
        f=operator_fixture();d=f['deployment'];rs=object_('ReplicaSet','new-rs','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
        rs['metadata']['ownerReferences']=[{'kind':'Deployment','uid':d['metadata']['uid'],'controller':True}]
        rs['spec']={'template':copy.deepcopy(d['spec']['template'])}
        pod=object_('Pod','new-pod','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
        pod['metadata']['ownerReferences']=[{'kind':'ReplicaSet','uid':rs['metadata']['uid'],'controller':True}]
        pod['spec']=copy.deepcopy(d['spec']['template']['spec'])
        role=object_('Role','cps-native-approval-node','cccccccc-cccc-4ccc-8ccc-cccccccccccc')
        role['rules']=[{'apiGroups':[g],'resources':[resource],'resourceNames':[name],'verbs':['get']}
          for g,resource,name in [('', 'pods','old-pod'),('apps','replicasets','old-rs')]]
        role['rules'].append({'apiGroups':[''],'resources':['configmaps'],'resourceNames':['cps-native-approval-ack-node'],'verbs':['patch']})
        r=plan.process_rbac(d,role,pod,rs,operator_mode=True)
        self.assertEqual(r['after_rules'][0]['resourceNames'],['new-pod']);self.assertEqual(r['after_rules'][1]['resourceNames'],['new-rs'])
        self.assertEqual(r['after_rules'][2]['resourceNames'],['cps-native-kai-epoch-node'])
        self.assertEqual(r['after_rules'][3]['resourceNames'],['cps-native-node-agent'])
        self.assertTrue(all(rule['resourceNames'] for rule in r['after_rules']))
        pod['metadata']['ownerReferences'][0]['uid']='foreign'
        with self.assertRaises(ValueError):plan.process_rbac(d,role,pod,rs)


if __name__=='__main__':unittest.main()
