"""Synthetic offline proposal inputs; never a hardware or Source approval."""
import copy
import importlib
import json
import unittest
import sys
from pathlib import Path
import cps_compute
sys.path.insert(0,str(Path(cps_compute.__file__).resolve().parents[2]/'tests'))
from datetime import datetime, timezone
from test_node_agent import fixtures
from test_native_groups import fixture as group_fixture


def inputs():
    policy, group=group_fixture()
    approval=copy.deepcopy(group['workspaces']['cps:group-a'])
    cit=copy.deepcopy(approval);cit.update(namespace='cit-jhub',principal='workspace:cit:native-group-a',
        owner='neutral-cit',pod='jupyter-neutral-cit',group_id='cit-group',members=['cit-person'])
    cit['storage']['namespace']='cit-jhub'
    approval.update(principal='workspace:cps:native-group-b',group_id='cps-group')
    node,_,_=fixtures();node.update(enabled=False,policy_hash=policy.hash,workspaces={},terminal_history={})
    ledger={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-gpu-allocations',
        'namespace':'cps-native-authority','uid':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','resourceVersion':'19'},
        'data':{'state.json':json.dumps({'version':1,'allocations':{}})}}
    observation={'nvmlDriverVersion':'615.71.09','observerPodUid':'44444444-4444-4444-8444-444444444444',
        'gpus':[{'uuid':group['node_pool']['gpu_uuid'],'migCurrent':0,'migPending':0,
            'memoryTotalBytes':42949672960,'memoryFreeBytes':42436526080,'memoryUsedBytes':513146880}]}
    health={'bootId':'209f8bc9-a478-48e4-925a-6e07ffa56f7a','driverGeneration':'b10498fc-9153-4394-875a-ea7cfb498625',
        'driverVersion':'615.71.09','healthPassed':True,'sourceSha256':group['evidence']['health_sha256']}
    return {'version':1,'catalog':policy.catalog,'approvals':{'cps:native-group-b':approval,'cit:native-group-a':cit},
        'node_config':node,'ledger':ledger,'terminal_history':{},'observed_at':'2026-10-11T16:00:00Z',
        'gate_image':group['gateImage'],'never_enrolled_evidence':None},json.dumps(observation).encode(),json.dumps(health).encode()


class ProposalTest(unittest.TestCase):
    def setUp(self):self.helper=importlib.import_module('qualification_proposal')
    def render(self,args):return self.helper.render(*args,now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc))
    def test_default_entrypoint_is_inert(self):
        self.assertEqual(self.helper.main([]),0)
    def test_exact_five_ten_proposal_is_disabled_for_humans_and_charges15360(self):
        result=self.render(inputs())
        mode=result['operator-qualification.json'];policy=result['policy.json']
        self.assertEqual(set(mode['profile_caps'].values()),{5120,10240})
        self.assertEqual(mode['node_pool']['memory_budget_mib'],15360)
        self.assertEqual(mode['node_pool']['free_memory_mib'],40470)
        self.assertTrue(all(policy['profiles'][p]['enabled'] is False for p in mode['profile_caps']))
        self.assertNotIn('gates',mode)
        self.assertEqual(result['node-config.json']['version'],2)
        self.assertEqual(result['acceptance.json']['hardware_qualified'],False)
    def test_stale_memory_mig_or_unreleased_history_denies(self):
        for change in ('stale','mig','live','history'):
            args=list(inputs());body=json.loads(args[1])
            if change=='stale':args[0]['observed_at']='2026-10-11T14:00:00Z'
            elif change=='mig':body['gpus'][0]['migCurrent']=1;args[1]=json.dumps(body).encode()
            else:
                record={'state':'enrolled' if change=='live' else 'released'}
                args[0]['ledger']['data']['state.json']=json.dumps({'version':1,'allocations':{'a'*60:record}})
            with self.assertRaises(ValueError):self.render(args)


class NeverEnrolledTest(unittest.TestCase):
    def test_none_intent_is_not_a_pod_uid_or_terminal_history(self):
        helper=importlib.import_module('qualification_proposal')
        value,observation,health=inputs()
        record={'version':1,'binding_id':'a'*60,'state':'released','intent':None,
            'source':'cps','workspace':'native-group-b','namespace':'jupyterhub','name':'jupyter-neutral',
            'policy_hash':'sha256:'+'b'*64,'profile':'interactive-native-pilot-5'}
        allocations={'a'*60:record}
        with self.assertRaises(ValueError):
            helper.validate_never_enrolled(None,allocations,{},value['ledger']['metadata'],
                value['node_config']['pool'],json.loads(health),json.loads(observation),
                now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc))

    def evidence(self):
        value,observation,health=inputs()
        health=json.loads(health);observation=json.loads(observation)
        meta=value['ledger']['metadata'];pool=value['node_config']['pool']
        record={'version':1,'binding_id':'a'*60,'state':'released','intent':None,
            'source':'cps','workspace':'native-group-b','namespace':'jupyterhub','name':'jupyter-neutral',
            'policy_hash':'sha256:'+'b'*64,'profile':'interactive-native-pilot-5'}
        snapshot={'version':1,'observerPodUid':observation['observerPodUid'],'node':pool['node'],
            'nodeUid':pool['node_uid'],'bootId':health['bootId'],'driverGeneration':health['driverGeneration'],
            'healthSourceSha256':health['sourceSha256'],'observedAt':'2026-10-11T16:00:00Z',
            'directories':{name:{'ownerUid':0,'mode':0o700,'records':{}} for name in ('enrollments','intents','journal')}}
        maps={'apiVersion':'v1','kind':'List','metadata':{'resourceVersion':''},'items':[]}
        evidence={'authority_maps':maps,'host_snapshot':snapshot,
            'pods':[{'namespace':record['namespace'],'name':record['name'],'status':404}]}
        return evidence,{'a'*60:record},{},meta,pool,health,observation

    def test_exact_absence_supports_released_never_enrolled_without_fabrication(self):
        helper=importlib.import_module('qualification_proposal')
        self.assertEqual(helper.validate_never_enrolled(*self.evidence(),
            now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc)),['a'*60])

    def test_missing_pod_incomplete_or_unprotected_host_changed_epoch_and_late_enrollment_deny(self):
        helper=importlib.import_module('qualification_proposal')
        for change in ('pod','host','epoch','extra','late','stale','protected-extra'):
            args=list(self.evidence());e=args[0]
            if change=='pod':e['pods'][0]['status']=200
            elif change=='host':e['host_snapshot']['directories']['intents']['ownerUid']=10001
            elif change=='epoch':e['host_snapshot']['driverGeneration']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
            elif change=='extra':e['authority_maps']['metadata']['continue']='more'
            elif change=='stale':e['host_snapshot']['observedAt']='2026-10-11T15:00:00Z'
            elif change=='protected-extra':e['host_snapshot']['directories']['intents']['records']['dddddddd-dddd-4ddd-8ddd-dddddddddddd.json']={'uid':0,'mode':0o600,'nlink':1,'rawSha256':'sha256:'+'c'*64,'value':{}}
            else:e['authority_maps']['items']=[{'apiVersion':'v1','kind':'ConfigMap','metadata':{
                'namespace':'cps-native-authority','name':'cps-native-enrollment-'+('a'*40),
                'uid':'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'}}]
            with self.subTest(change=change),self.assertRaises(ValueError):
                helper.validate_never_enrolled(*args,now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc))
