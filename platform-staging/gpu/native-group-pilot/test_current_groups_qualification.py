"""Offline d48 source and released-custody replay; never fresh hardware evidence."""
import copy
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from test_qualification_proposal import inputs


class CurrentGroupQualificationTest(unittest.TestCase):
    def setUp(self):
        self.helper = importlib.import_module('qualification_proposal')

    def fixture(self, root):
        source = json.loads((Path(__file__).parent/'testdata/reviewed-d48-native-source.json').read_bytes())
        args = list(inputs()); body = args[0]; runtime = source['runtime']; group = runtime['nativeGpuGroups']
        custody=json.loads((Path(__file__).parent/'testdata/reviewed-current-released-custody.json').read_bytes())
        authority,ledger=custody['authority'],custody['ledger']
        body.update(catalog=source['catalog'], approvals=copy.deepcopy(group['workspaces']), ledger=ledger,
                    terminal_history={}, gate_image=group['gateImage'])
        body['node_config'] = dict(version=2, enabled=True, mode='qualified-group',
            authority_namespace=group['authorityNamespace'], policy_hash=runtime['policy_hash'],
            pool=copy.deepcopy(group['node_pool']), terminal_history={},
            workspaces={s:dict(profile=g['profiles'][0], cap_mib=g['ceiling']['gpuMemoryGiB']*1024)
                        for s,g in group['workspaces'].items()})
        body['terminal_history']=importlib.import_module('terminal_policy_proposal').map_history(authority,ledger,body['node_config'])
        hubs = {s:dict(source=s, groupDeployment=copy.deepcopy(group),
                       profiles=['interactive-cpu', 'interactive-shared-'+str(size)])
                for s,size in (('cps',5),('cit',10))}
        raw = json.dumps(runtime).encode(); hub_raw = json.dumps(hubs).encode()
        return args, authority, raw, hub_raw

    def run_proposal(self, fixture, **overrides):
        from cps_compute import native_gpu_controller as models
        args, authority, raw, hub_raw = fixture
        options = dict(now=datetime(2026,10,11,16,0,1,tzinfo=timezone.utc),
            terminal_authority=authority, source_runtime_raw=raw,
            source_runtime_sha256=self.helper.checksum(raw), source_hubs_raw=hub_raw,
            source_hubs_sha256=self.helper.checksum(hub_raw), source_controller_raw=Path(models.__file__).read_bytes())
        options.update(overrides)
        return self.helper.render_current_approved_groups(*args, **options)

    def test_real_source_produces_separate_disabled_twenty_handover(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(Path(tmp)); before = copy.deepcopy(fixture)
            result = self.run_proposal(fixture)
            self.assertEqual(fixture, before)
            mode = result['operator-qualification.json']
            self.assertEqual(mode['profile_caps'], {'interactive-native-qualification-5':5120,
                                                     'interactive-native-qualification-20':20480})
            self.assertFalse(result['acceptance.json']['hardware_qualified'])
            self.assertFalse(result['acceptance.json']['live_applied'])
            self.assertEqual(result['node-config.json']['terminal_history'], fixture[0][0]['terminal_history'])
            self.assertEqual(result['runtime-native-overlay.json']['nativeGpuGroups'], {'enabled':False})
            self.assertEqual(result['runtime-native-overlay.json']['nativeGpuPilot'], {'enabled':False})
            self.assertEqual(result['hub-native-overlays.json']['cit']['profiles'],
                             ['interactive-cpu','interactive-native-qualification-20'])
            self.assertEqual(result['hub-native-overlays.json']['cps']['profiles'],
                             ['interactive-cpu','interactive-native-qualification-5'])
            self.assertTrue(all(result['policy.json']['profiles'][p]['enabled'] is False for p in mode['profile_caps']))

    def test_foreign_general_twenty_hash_and_custody_sources_reject(self):
        for fault in ('foreign','general','twenty','hash','custody','image','pool','hub','policy','controller'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                fixture = list(self.fixture(Path(tmp))); args, authority, raw, hub_raw = fixture
                runtime = json.loads(raw); hubs = json.loads(hub_raw)
                if fault=='foreign':runtime['nativeGpuGroups']['workspaces']['other:group']=copy.deepcopy(next(iter(runtime['nativeGpuGroups']['workspaces'].values())))
                elif fault=='general':runtime['nativeGpuPilot']={'enabled':True}
                elif fault=='twenty':args[0]['catalog']['profiles']['interactive-shared-20']['enabled']=True
                elif fault=='custody':authority['host_snapshot']['directories']['journal']['records'].clear()
                elif fault=='image':runtime['nativeGpuGroups']['workloadImage']='foreign@sha256:'+'a'*64
                elif fault=='pool':runtime['nativeGpuGroups']['node_pool']['max_workspaces']=3
                elif fault=='hub':hubs['cit']['profiles'].append('interactive-shared-20')
                elif fault=='policy':runtime['policy_hash']='sha256:'+'a'*64
                fixture[2]=json.dumps(runtime).encode();fixture[3]=json.dumps(hubs).encode()
                kwargs={'source_runtime_sha256':'sha256:'+'0'*64} if fault=='hash' else {}
                if fault=='controller':kwargs['source_controller_raw']=b'old f40 controller source'
                with self.assertRaises(ValueError):self.run_proposal(fixture,**kwargs)

    def test_source_cannot_be_relabelled_as_legacy_qualification(self):
        legacy=importlib.import_module('qualification_transition_proposal')
        from test_qualification_transition_proposal import ConfigurationTest
        old=ConfigurationTest();old.setUp();proposal, baselines=old.fixtures()
        import base64
        actual=json.loads((Path(__file__).parent/'testdata/reviewed-d48-native-source.json').read_bytes())['runtime']
        baselines['runtime']['data']['runtime.json']=base64.b64encode(json.dumps(actual).encode()).decode()
        with self.assertRaises(ValueError):legacy.configuration_intent(proposal,baselines)


if __name__=='__main__':unittest.main()
