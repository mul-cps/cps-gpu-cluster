"""CPU-only terminal configuration references never widen active capacity."""
import copy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import test_node_agent as fixture_module
from test_node_agent import POD, BINDING, canonical_json, canonical_digest


class HistoricalConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.EnrollmentTest()
        self.fixture.setUp()
        self.agent = self.fixture.agent
        self.models = self.fixture.models

    def values(self, root):
        _, record, _ = self.fixture.retired_cleanup_fixture()
        pool = dict(self.fixture.config['pool'], total_memory_mib=40960, free_memory_mib=40470,
            headroom_mib=1024, memory_budget_mib=15360, boot_id=record.identity.boot_id,
            driver_generation=record.identity.driver_generation)
        config = dict(version=2, enabled=True, mode='operator-qualification',
            authority_namespace='cps-native-authority', policy_hash='sha256:'+'e'*64, pool=pool,
            workspaces={'cps:native-group-b':{'profile':'interactive-native-qualification-5','cap_mib':5120},
                'cit:native-group-a':{'profile':'interactive-native-qualification-10','cap_mib':10240}})
        historical = copy.deepcopy(config)
        historical['policy_hash'] = self.fixture.enrollment['policy_hash']
        historical['pool']['memory_budget_mib'] = 25600
        historical['workspaces']['cit:native-group-a'] = {
            'profile':'interactive-native-qualification-20','cap_mib':20480}
        cm = {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
            'metadata':{'namespace':'cps-native-authority','name':'cps-native-node-qualification-test20',
                'uid':'77777777-7777-4777-8777-777777777777','resourceVersion':'12'},
            'data':{'config.json':canonical_json(historical)}}
        reference = {'namespace':cm['metadata']['namespace'],'name':cm['metadata']['name'],
            'uid':cm['metadata']['uid'],'data_sha256':canonical_digest(cm['data']),
            'policy_hash':historical['policy_hash']}
        enrollment = copy.deepcopy(self.fixture.enrollment)
        enrollment.update(source='cit', workspace='native-group-a', principal='workspace:cit:native-group-a',
            profile='interactive-native-qualification-20', namespace='cit-jhub',
            name='jupyter-native-group-a', cap_mib=20480)
        enrollment['intent'].update(namespace=enrollment['namespace'],name=enrollment['name'],cap_mib=20480)
        enrollment_cm = copy.deepcopy(self.fixture.cm)
        enrollment_cm['data']['enrollment.json'] = canonical_json(enrollment)
        envelope = self.agent.validate_enrollment(enrollment_cm, historical, self.models)
        store = self.agent.EnrollmentStore(root,self.models,trusted_uid=os.getuid())
        store.synchronize([envelope])
        limit = type(record.limit)(20480*1048576,20480*1048576)
        document = {'version':1,'backend':'misc-fallback','gpu_uuid':record.identity.gpu_uuid,'gpu_id':1,
            'entries':[dict(asdict(record.retirement.entry),soft=limit.soft,hard=limit.hard)]}
        retirement = self.models.validate_retired_inventory(document,record.identity,limit)
        record = replace(record,intent=self.models.CapIntent(**enrollment['intent']),readback=limit,retirement=retirement)
        cleanup = self.agent.cleanup_object(envelope,record)
        cleanup['metadata'].update(uid='66666666-6666-4666-8666-666666666666',resourceVersion='13')
        store.mark_cleanup_published(POD,envelope,cleanup,record)
        ledger = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'cps-native-gpu-allocations',
            'namespace':'cps-native-authority','uid':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','resourceVersion':'14'},
            'data':{'state.json':canonical_json({'version':1,'allocations':{BINDING:dict(enrollment,state='released')}})}}
        entry = {'binding_id':BINDING,'policy_hash':historical['policy_hash'],'profile':enrollment['profile'],
            'enrollment_uid':envelope['configmap_uid'],'enrollment_sha256':canonical_digest(enrollment),
            'completion_kind':'cleanup','completion_uid':cleanup['metadata']['uid'],
            'completion_sha256':canonical_digest(json.loads(cleanup['data']['receipt.json'])),
            'ledger_uid':ledger['metadata']['uid'],'journal_sha256':canonical_digest(record.to_dict()),
            'cap_mib':20480,'configuration_authority':reference}
        config['terminal_history'] = {POD:entry}
        maps = {item['metadata']['name']:item for item in (cm,enrollment_cm,cleanup,ledger)}
        calls=[]; records={POD:record}
        def get(ns,name):
            calls.append((ns,name))
            return copy.deepcopy(maps.get(name))
        kube=SimpleNamespace(configmap=get,pod=lambda intent:None)
        journal=SimpleNamespace(read=lambda uid:records.get(uid))
        return config,cm,enrollment_cm,store,journal,kube,maps,records,calls

    def dispatch(self, values):
        config,_,enrollment,store,journal,kube,*_=values
        return self.agent.validate_authority_enrollments([enrollment],config,self.models,store,journal,kube)

    def test_retired20_uses_actual_immutable25_pool_and_keeps_active15(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=self.values(Path(tmp));before=copy.deepcopy(values[0])
            with self.assertRaises(ValueError):self.agent.validate_enrollment(values[2],values[0],self.models)
            envelopes,terminal=self.dispatch(values)
            self.assertEqual(terminal,{POD});self.assertEqual(envelopes[0]['enrollment']['cap_mib'],20480)
            self.assertEqual(values[0],before)
            self.assertGreaterEqual(values[-1].count(('cps-native-authority',values[1]['metadata']['name'])),2)

    def test_reference_uid_data_pool_policy_epoch_and_shape_tampering_refuses(self):
        for fault in ('uid','data','budget','headroom','slots','policy','epoch','namespace','mutable','owner','field','same-policy'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                values=self.values(Path(tmp));config,cm,*_=values;entry=config['terminal_history'][POD]
                if fault=='uid':cm['metadata']['uid']=config['pool']['node_uid']
                elif fault=='data':cm['data']['extra']='forged'
                elif fault in ('budget','headroom','slots','policy','epoch'):
                    old=json.loads(cm['data']['config.json'])
                    if fault=='budget':old['pool']['memory_budget_mib']=20480
                    elif fault=='headroom':old['pool']['headroom_mib']=0
                    elif fault=='slots':old['pool']['max_workspaces']=3
                    elif fault=='epoch':old['pool']['boot_id']='88888888-8888-4888-8888-888888888888'
                    else:old['policy_hash']='sha256:'+'d'*64
                    cm['data']['config.json']=canonical_json(old)
                    entry['configuration_authority']['data_sha256']=canonical_digest(cm['data'])
                elif fault=='namespace':cm['metadata']['namespace']='jupyterhub'
                elif fault=='mutable':cm['immutable']=False
                elif fault=='owner':cm['metadata']['ownerReferences']=[{'uid':POD}]
                elif fault=='field':entry['configuration_authority']['ignore_live']=True
                else:entry['policy_hash']=config['policy_hash'];entry['configuration_authority']['policy_hash']=config['policy_hash']
                with self.assertRaises(ValueError):self.dispatch(values)

    def test_unreleased_or_nonterminal_nonzero_or_same_uid_cannot_use_historical_pool(self):
        for fault in ('released','journal','nonzero','pod','no-reference','late-config'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                values=self.values(Path(tmp));config,cm,_,_,journal,kube,maps,records,_=values
                if fault=='released':
                    ledger=maps['cps-native-gpu-allocations'];state=json.loads(ledger['data']['state.json'])
                    state['allocations'][BINDING]['state']='enrolled';ledger['data']['state.json']=canonical_json(state)
                elif fault=='journal':records[POD]=replace(records[POD],state='sealed',retirement=None)
                elif fault=='nonzero':
                    row=records[POD].to_dict();row['retirement']['entry']['used']=1
                    journal.read=lambda uid:self.models.CapRecord.from_dict(row)
                elif fault=='pod':kube.pod=lambda intent:{'apiVersion':'v1','kind':'Pod','metadata':{
                    'namespace':intent.namespace,'name':intent.name,'uid':POD}}
                elif fault=='no-reference':config['terminal_history'][POD].pop('configuration_authority')
                else:
                    old_get=kube.configmap;count=[0]
                    def get(ns,name):
                        value=old_get(ns,name)
                        if name==cm['metadata']['name']:
                            count[0]+=1
                            if count[0]>1:value['metadata']['uid']=POD
                        return value
                    kube.configmap=get
                with self.assertRaises((ValueError,self.models.ControllerError)):self.dispatch(values)

    def test_current20_and_active_capacity_remain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=self.values(Path(tmp));config=values[0]
            config['terminal_history']={}
            with self.assertRaises(ValueError):self.dispatch(values)
            config['workspaces']['cit:native-group-a']={'profile':'interactive-native-qualification-20','cap_mib':20480}
            with self.assertRaises(ValueError):self.agent.validate_config(config)
