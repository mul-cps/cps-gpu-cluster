"""CPU-only complete terminal authority mapping across a policy change."""
import copy
import importlib
import json
import tempfile
from pathlib import Path
import unittest
from test_node_agent import TerminalHistoryTest as TerminalFixture, POD


class TerminalProposalTest(unittest.TestCase):
    def setUp(self):
        self.helper=importlib.import_module('terminal_policy_proposal')
        self.fixture=TerminalFixture('test_prior_cleaned_retired_and_abort_completion_survive_changed_policy')
        self.fixture.setUp()

    def fixture_values(self, root, *, abort=False, retired=False):
        config,_,_,_,maps,records,_=self.fixture.completed(root,abort=abort,retired=retired)
        authority={'apiVersion':'v1','kind':'ConfigMapList','metadata':{'resourceVersion':'12'},
            'items':[copy.deepcopy(cm) for cm in maps.values() if cm['metadata']['name']!='cps-native-gpu-allocations']}
        host={'version':1,'observerPodUid':'77777777-7777-4777-8777-777777777777',
            'node':config['pool']['node'],'nodeUid':config['pool']['node_uid'],
            'bootId':'209f8bc9-a478-48e4-925a-6e07ffa56f7a',
            'driverGeneration':'b10498fc-9153-4394-875a-ea7cfb498625',
            'healthSourceSha256':'sha256:'+'1'*64,'observedAt':'2026-10-12T04:00:00Z','directories':{}}
        if abort:
            proof=json.loads(next(cm for cm in authority['items'] if 'abort.json' in cm['data'])['data']['abort.json'])
            host['bootId']=proof['node_epoch']['boot_id'];host['driverGeneration']=proof['node_epoch']['driver_generation']
        elif retired:
            host['bootId']=records[POD].identity.epoch.boot_id;host['driverGeneration']=records[POD].identity.epoch.driver_generation
        for name in ('enrollments','intents','journal'):
            rows={}
            for path in sorted((root/name).glob('*.json')):
                value=json.loads(path.read_text())
                rows[path.name]={'uid':0,'mode':0o600,'nlink':1,
                    'rawSha256':self.helper.raw_sha(path.read_bytes()),'value':value}
            if name=='journal':
                rows={uid+'.json':{'uid':0,'mode':0o600,'nlink':1,
                    'rawSha256':self.helper.raw_sha((self.helper.canonical(record.to_dict())+'\n').encode()),
                    'value':record.to_dict()} for uid,record in records.items()}
            host['directories'][name]={'ownerUid':0,'mode':0o700,'records':rows}
        return {'authority_maps':authority,'host_snapshot':host},maps['cps-native-gpu-allocations'],config

    def test_cleaned_retired_and_aborted_history_survives_exactly(self):
        for kind in ('cleaned','retired','abort'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                args=self.fixture_values(Path(tmp),abort=kind=='abort',retired=kind=='retired')
                before=copy.deepcopy(args)
                result=self.helper.map_history(*args)
                self.assertEqual(result,args[2]['terminal_history'])
                self.assertEqual(args,before)

    def test_new_current_policy_retirement_is_added_with_original_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture_values(Path(tmp),retired=True)
            expected=copy.deepcopy(args[2]['terminal_history'][POD]);args[2]['terminal_history']={}
            result=self.helper.map_history(*args)
            self.assertEqual(result[POD],dict(expected,cap_mib=5120))
            self.assertEqual(result[POD]['policy_hash'],self.fixture.enrollment['policy_hash'])

    def test_missing_or_changed_full_authority_fails_closed(self):
        for fault in ('journal','enrollment','cleanup','old-map','ledger-live','recovery-invented','unprotected','pagination'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                args=list(self.fixture_values(Path(tmp),retired=True));doc,ledger,config=args
                if fault=='journal':doc['host_snapshot']['directories']['journal']['records'].clear()
                elif fault=='enrollment':doc['authority_maps']['items']=doc['authority_maps']['items'][1:]
                elif fault=='cleanup':doc['authority_maps']['items'][1]['data']['receipt.json']='{}'
                elif fault=='old-map':config['terminal_history'][POD]['journal_sha256']='sha256:'+'0'*64
                elif fault=='ledger-live':
                    state=json.loads(ledger['data']['state.json']);next(iter(state['allocations'].values()))['state']='enrolled'
                    ledger['data']['state.json']=json.dumps(state)
                elif fault=='recovery-invented':
                    row=doc['host_snapshot']['directories']['journal']['records'][POD+'.json']
                    row['value']['state']='recovered-cleared-offline-cap'
                elif fault=='unprotected':doc['host_snapshot']['directories']['journal']['ownerUid']=10001
                else:doc['authority_maps']['metadata']['continue']='next-page'
                with self.assertRaises(ValueError):self.helper.map_history(*args)


class HistoricalAbortEpochTest(TerminalProposalTest):
    def test_original_aborted_epoch_is_preserved_without_new_epoch_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            authority,ledger,node=self.fixture_values(Path(tmp),abort=True)
            authority['host_snapshot']['driverGeneration']='88888888-8888-4888-8888-888888888888'
            self.assertEqual(self.helper.map_history(authority,ledger,node),node['terminal_history'])
            node['terminal_history']={}
            with self.assertRaises(ValueError):self.helper.map_history(authority,ledger,node)
