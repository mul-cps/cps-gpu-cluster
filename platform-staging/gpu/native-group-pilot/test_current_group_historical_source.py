"""Offline finite-history tests; no hardware or live API acceptance is claimed."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import current_group_historical_source as source
import historical_configuration_source as prior
import test_historical_configuration as historical_tests
from test_node_agent import POD,canonical_json


class CurrentHistoricalTest(historical_tests.HistoricalConfigurationTest):
    def setUp(self):
        super().setUp()
        self.fixture.enrollment['policy_hash']=source.QUALIFICATION_POLICY
        self.fixture.enrollment['intent']['policy_hash']=source.QUALIFICATION_POLICY
        namespace=dict(vars(self.agent))
        function=source.historical_validator_source(prior.definitions(Path(self.agent.__file__).read_text())['validate_historical_configuration'])
        exec(compile(function,'<reviewed-group-terminal-validator>','exec'),namespace)
        exec(compile(prior.definitions(Path(self.agent.__file__).read_text())['validate_authority_enrollments'],
            '<reviewed-terminal-reads>','exec'),namespace)
        self.agent=SimpleNamespace(**namespace)

    def values(self,root):
        values=super().values(root);config=values[0]
        config.update(mode='qualified-group',policy_hash=source.RESTORED_POLICY)
        config['workspaces']={'cps:native-group-b':{'profile':'interactive-shared-5','cap_mib':5120},
            'cit:native-group-a':{'profile':'interactive-shared-10','cap_mib':10240}}
        return values

    def test_current20_and_active_capacity_remain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=self.values(Path(tmp));config=values[0]
            config['terminal_history']={}
            with self.assertRaises(ValueError):self.dispatch(values)
            config['workspaces']['cit:native-group-a']={'profile':'interactive-shared-20','cap_mib':20480}
            with self.assertRaises(ValueError):self.agent.validate_config(config)

    def test_only_exact_reviewed_restored_and_historical_policies_allow_terminal_reference(self):
        for which in ('restored','historical'):
            with self.subTest(which=which),tempfile.TemporaryDirectory() as tmp:
                values=self.values(Path(tmp));config,cm=values[:2]
                if which=='restored':config['policy_hash']='sha256:'+'a'*64
                else:
                    old=self.agent.parse(cm['data']['config.json']);old['policy_hash']='sha256:'+'b'*64
                    cm['data']['config.json']=canonical_json(old)
                    entry=config['terminal_history'][POD];entry['policy_hash']=old['policy_hash']
                    entry['configuration_authority'].update(policy_hash=old['policy_hash'],
                        data_sha256=self.agent.canonical_sha256(cm['data']))
                with self.assertRaises(ValueError):self.dispatch(values)


class ActualSourceTest(unittest.TestCase):
    def test_actual_pinned_source_preserves_all_other_definitions_and_recovery(self):
        path=os.environ.get('CPS_CURRENT_NATIVE_AGENT_SOURCE')
        if not path:self.skipTest('Root supplies the safe actual34ce source capture, never credentials')
        original=Path(path).read_text();extension=Path(source.agent.__file__).read_text()
        updated=source.extend_source(original,extension)
        old=prior.definitions(original);new=prior.definitions(updated)
        self.assertEqual(set(new)-set(old),{'validate_configuration_reference','validate_historical_configuration'})
        self.assertTrue(all(new[k]==v for k,v in old.items() if k not in ('validate_config','validate_authority_enrollments')))
        self.assertIn("'recovered-cleared-offline-cap'",new['validate_authority_enrollments'])
        self.assertIn(source.RESTORED_POLICY,updated);self.assertIn(source.QUALIFICATION_POLICY,updated)
        self.assertNotEqual(hashlib.sha256(updated.encode()).hexdigest(),source.ORIGINAL_SHA256)
        with self.assertRaises(ValueError):source.extend_source(original+'\n',extension)
        with self.assertRaises(ValueError):source.extend_source(original,extension+'\n')


if __name__=='__main__':unittest.main()
