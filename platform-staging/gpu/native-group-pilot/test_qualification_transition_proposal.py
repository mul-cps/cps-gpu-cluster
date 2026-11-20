"""Offline Source CRUD/inverse proposals with complete surrounding state."""
import copy
import base64
import json
from datetime import datetime,timezone
from test_qualification_proposal import inputs as proposal_inputs
import importlib
import unittest


class TransitionTest(unittest.TestCase):
    def setUp(self):self.helper=importlib.import_module('qualification_transition_proposal')

    def fixtures(self):
        full={};registrations={}
        for source,size,letter in (('cps',5,'b'),('cit',10,'a')):
            wid='native-group-'+letter
            people=self.helper.CIT_PEOPLE if source=='cit' else {'member-c':'8edde4a2-257c-42d7-9732-13f1e8742a33','member-d':'3237c91b-cef3-4f6f-960e-875b9e93c4be'}
            profile='interactive-native-qualification-'+str(size)
            ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':size}
            course={'id':'native-gpu-pilot-20261009','source':'local','external_id':None,
                'resource_ceiling':ceiling,'workspace_bindings':[{'group_id':'native-pilot-group-'+letter}]}
            workspace={'id':wid,'source':'local','external_id':None,'state':'stopped','profile':profile,
                'course_id':course['id'],'term_id':'qualification-20261009','group_id':'native-pilot-group-'+letter,
                'course_ceiling':ceiling,'hub_user':source+'nativegroup'+letter,'hub_server':'rtc',
                'namespace':'jupyterhub' if source=='cps' else 'cit-jhub','pod':'jupyter-'+source+'nativegroup'+letter+'--rtc',
                'archive_pending':False,'membership_removal_pending':False,'reconciliation_pending':False}
            records={'courses':[course],'workspaces':[workspace],'groups':[], 'terms':[], 'memberships':[{'group_id':'native-pilot-group-'+letter,'person_id':name,'canonical_person_id':person,'role':'student','source':'local'} for name,person in people.items()]}
            grants={person:[{'id':'native-pilot-'+source+'-'+name,'person':person,'source':source,
                'profiles':['interactive-cpu',profile],'projects':[],'allowance':1,
                'starts':'2026-10-09T00:00:00Z','expires':'2026-10-12T00:00:00Z','reason':'qualification'}] for name,person in people.items()}
            full[source]={'actor_model':{'name':'bjoern' if source=='cps' else 'akadmin','admin':True},
                'records':copy.deepcopy(records),'all_records':copy.deepcopy(records), 'grants':grants,
                'people':people,'aliases':{'email_links':{},'reviewed_account_aliases':{}},'servers':{wid:None}}
            registrations[source+':'+wid]={'workspace':wid,'principal':'workspace:'+source+':'+wid,
                'profiles':[profile],'members':sorted(people.values()),'ceiling':ceiling,'policy_hash':'sha256:'+'1'*64,
                'course_id':course['id'],'term_id':workspace['term_id'], 'owner':workspace['hub_user'],
                'namespace':workspace['namespace'],'pod':workspace['pod'],'group_id':workspace['group_id'],
                'storage':{'state':'active','claim':'unchanged-claim','mount':'/workspace'}}
        return full,registrations

    def test_exact_source20_plan_is_disabled_and_inverse_restores_full_original(self):
        args=self.fixtures();original=copy.deepcopy(args)
        result=self.helper.source_intent(*args,policy_hash='sha256:'+'2'*64)
        self.assertFalse(result['enabled']);self.assertFalse(result['hardware_qualified'])
        self.assertEqual(result['before'],original[0]);self.assertEqual(result['registrations_before'],original[1])
        self.assertEqual(result['after']['cps'],original[0]['cps'])
        self.assertEqual(result['after']['cit']['aliases'],original[0]['cit']['aliases'])
        grants=[g for rows in result['after']['cit']['grants'].values() for g in rows]
        self.assertEqual({tuple(g['profiles']) for g in grants},{('interactive-cpu','interactive-native-qualification-20')})
        self.assertTrue(all(g['expires']=='2026-10-12T00:00:00Z' and g['allowance']==1 for g in grants))
        self.assertEqual(result['after']['cit']['records']['courses'][0]['resource_ceiling']['gpuMemoryGiB'],20)
        self.assertEqual(result['inverse']['before'],result['after'])
        self.assertEqual(result['inverse']['after'],result['before'])
        self.assertEqual(result['inverse']['registrations_after'],original[1])
        self.assertEqual(result['registrations_after']['cit:native-group-a']['storage'],original[1]['cit:native-group-a']['storage'])
        self.assertEqual(len(result['operations']),6)
        self.assertTrue(all(op['audit_required'] for op in result['operations']))
        self.assertEqual(args,original)

    def test_wrong_source_grant_active_workspace_storage_or_unrelated_ceiling_denies(self):
        for fault in ('grant','running','ceiling','storage','actor','duplicate-record','extra-workspace'):
            with self.subTest(fault=fault):
                full,regs=self.fixtures()
                if fault=='grant':next(iter(full['cit']['grants'].values()))[0]['source']='cps'
                elif fault=='running':full['cit']['records']['workspaces'][0]['state']='running'
                elif fault=='ceiling':full['cit']['records']['courses'][0]['resource_ceiling']['gpuMemoryGiB']=20
                elif fault=='storage':regs['cit:native-group-a']['storage']['state']='deleted'
                elif fault=='actor':full['cit']['actor_model']['admin']=False
                elif fault=='duplicate-record':full['cit']['all_records']['workspaces'][0]['profile']='other'
                else:full['cit']['all_records']['workspaces'].append({'id':'research-data','course_id':'native-gpu-pilot-20261009'})
                with self.assertRaises(ValueError):self.helper.source_intent(full,regs,policy_hash='sha256:'+'2'*64)


class ConfigurationTest(unittest.TestCase):
    def setUp(self):self.helper=importlib.import_module('qualification_transition_proposal')
    def fixtures(self):
        render=importlib.import_module('qualification_proposal').render
        now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc)
        args=list(proposal_inputs());old=render(*args,now=now)
        args[0]['catalog']=old['policy.json'];new=render(*args,now=now,preset='cps5-cit20')
        def cm(name,data):return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
            'metadata':{'name':name,'namespace':'cps-compute','uid':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','resourceVersion':'8'},'data':data}
        def deployment(name,config):return {'apiVersion':'apps/v1','kind':'Deployment','metadata':{
            'name':name,'namespace':'cps-compute','uid':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','resourceVersion':'9'},
            'spec':{'replicas':1,'template':{'metadata':{'annotations':{'old':'preserved'}},'spec':{
                'containers':[{'name':name,'image':'example@sha256:'+'a'*64,'env':[{'name':'keep','value':'yes'}]}],
                'volumes':[{'name':'config','configMap':{'name':config}},{'name':'keep','emptyDir':{}}]}}}}
        policy=cm('compute-policy',{'policy.json':json.dumps(old['policy.json']),'other':'unchanged'})
        runtime={'policy_hash':old['policy.json']['policyHash'],'nativeGpuQualification':old['operator-qualification.json'],
            'nativeGpuGroups':{'enabled':False},'nativeGpuPilot':{'enabled':False},'hubs':{'cps':{'identity':'unchanged'},'cit':{'identity':'unchanged'}}}
        secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'compute-runtime','namespace':'cps-compute',
            'uid':'cccccccc-cccc-4ccc-8ccc-cccccccccccc','resourceVersion':'10'},'data':{
            'runtime.json':base64.b64encode(json.dumps(runtime).encode()).decode(),'other':'dW5jaGFuZ2Vk'}}
        node=cm('old-node-config',{'config.json':json.dumps(old['node-config.json']),'other':'preserved'})
        baseline={'policy':policy,'runtime':secret,'node_config':node,'node_deployment':deployment('agent',node['metadata']['name']),
            'gateway_deployment':deployment('gateway','gateway-other')}
        for source,size in (('cps',5),('cit',10)):
            settings={'source':source,'qualificationDeployment':old['operator-qualification.json'],
                'profiles':['interactive-native-qualification-'+str(size)],'owners':['unchanged-owner'],'trust':'unchanged'}
            hub=cm('old-'+source,{'settings.json':json.dumps(settings),'policy.json':json.dumps(old['policy.json']),
                'ca.crt':'unchanged-ca','canonical-people.json':'unchanged-aliases'})
            baseline[source]={'config':hub,'deployment':deployment('hub',hub['metadata']['name'])}
        return new,baseline

    def test_coordinated_policy_runtime_and_hubs_preserve_images_trust_and_identities(self):
        proposal,baseline=self.fixtures();original=copy.deepcopy(baseline)
        result=self.helper.configuration_intent(proposal,baseline)
        self.assertFalse(result['enabled']);self.assertFalse(result['hardware_qualified'])
        self.assertEqual(result['full-runtime-after.json']['hubs'],result['full-runtime-before.json']['hubs'])
        self.assertEqual(result['runtime.patch.json'][-1]['value']['other'],baseline['runtime']['data']['other'])
        for source in ('cps','cit'):
            newcm=result['configurations'][source]
            self.assertTrue(newcm['immutable'])
            for key in ('ca.crt','canonical-people.json'):self.assertEqual(newcm['data'][key],baseline[source]['config']['data'][key])
            oldspec=baseline[source]['deployment']['spec'];new_spec=result['deployment_patches'][source][-1]['value']
            self.assertEqual(oldspec['template']['spec']['containers'],new_spec['template']['spec']['containers'])
        for patch in result['deployment_patches'].values():self.assertEqual([op['op'] for op in patch],['test','test','test','replace'])
        self.assertEqual(result['inverse']['original_deployment_specs']['node'],baseline['node_deployment']['spec'])
        self.assertEqual(baseline,original)

    def test_profile_mismatch_general_enablement_image_or_volume_drift_denies(self):
        for fault in ('profile','general','image','volume'):
            with self.subTest(fault=fault):
                proposal,baseline=self.fixtures()
                if fault=='profile':
                    data=baseline['cit']['config']['data'];settings=json.loads(data['settings.json']);settings['profiles']=['interactive-cpu'];data['settings.json']=json.dumps(settings)
                elif fault=='general':
                    data=baseline['runtime']['data'];runtime=json.loads(base64.b64decode(data['runtime.json']));runtime['nativeGpuGroups']['enabled']=True;data['runtime.json']=base64.b64encode(json.dumps(runtime).encode()).decode()
                elif fault=='image':proposal['operator-qualification.json']['workloadImage']='malicious@sha256:'+'d'*64
                else:baseline['node_deployment']['spec']['template']['spec']['volumes'][0]['configMap']['name']='another'
                with self.assertRaises(ValueError):self.helper.configuration_intent(proposal,baseline)
