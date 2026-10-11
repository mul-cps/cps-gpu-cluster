"""CPU-only measured qualification envelopes and retained v1 history."""
import copy
from dataclasses import replace
import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from test_node_agent import fixtures, TerminalHistoryTest, POD


def measured(config, profile='interactive-native-qualification-10', cap=10240):
    config = copy.deepcopy(config)
    config.update(version=2, mode='operator-qualification')
    config['pool'].update(total_memory_mib=40960, free_memory_mib=40470,
        headroom_mib=1024, memory_budget_mib=15360,
        boot_id='209f8bc9-a478-48e4-925a-6e07ffa56f7a',
        driver_generation='b10498fc-9153-4394-875a-ea7cfb498625')
    config['workspaces']={'cps:pilot': {'profile': profile, 'cap_mib': cap}}
    return config


class PackingTest(unittest.TestCase):
    def setUp(self):
        self.agent = importlib.import_module('node_agent')
        self.models = self.agent.load_models_from_snapshot()
        config, self.enrollment, self.cm = fixtures()
        self.config = measured(config)

    def test_exact_prospective_ten_gib_enrollment_keeps_immutable_intent(self):
        self.enrollment.update(profile='interactive-native-qualification-10', cap_mib=10240)
        self.enrollment['intent']['cap_mib']=10240
        self.cm['data']['enrollment.json']=json.dumps(self.enrollment)
        self.assertEqual(self.agent.validate_enrollment(self.cm,self.config,self.models)['enrollment'],self.enrollment)
        for value in (5120, 20480, True):
            bad=copy.deepcopy(self.cm);body=copy.deepcopy(self.enrollment)
            body['cap_mib']=body['intent']['cap_mib']=value;bad['data']['enrollment.json']=json.dumps(body)
            with self.assertRaises(ValueError):self.agent.validate_enrollment(bad,self.config,self.models)

    def test_measured_node_config_denies_memory_or_mode_drift(self):
        self.agent.validate_config(self.config)
        for key,value in [('memory_budget_mib',40960),('headroom_mib',0),('free_memory_mib',40961),
                          ('max_workspaces',True),('boot_id','0'*36)]:
            bad=copy.deepcopy(self.config);bad['pool'][key]=value
            with self.assertRaises(ValueError):self.agent.validate_config(bad)
        for mode in ('ordinary','qualification-passed',False):
            bad=copy.deepcopy(self.config);bad['mode']=mode
            with self.assertRaises(ValueError):self.agent.validate_config(bad)

    def test_pool_memory_counts_caps_until_physical_terminal_journal(self):
        five=self.models.CapIntent(**self.enrollment['intent'])
        ten=replace(five,pod_uid='22222222-2222-4222-8222-222222222222',cap_mib=10240)
        twenty=replace(five,pod_uid='33333333-3333-4333-8333-333333333333',cap_mib=20480)
        records={};journal=SimpleNamespace(read=lambda uid:records.get(uid))
        self.agent.validate_active_capacity(self.config,[five,ten],journal,set())
        with self.assertRaises(ValueError):self.agent.validate_active_capacity(self.config,[five,ten,twenty],journal,set())
        records[twenty.pod_uid]=SimpleNamespace(state='releasing')
        with self.assertRaises(ValueError):self.agent.validate_active_capacity(self.config,[five,ten,twenty],journal,set())
        records[twenty.pod_uid]=SimpleNamespace(state='retired-inert-cap')
        self.agent.validate_active_capacity(self.config,[five,ten,twenty],journal,set())

    def test_actual_epoch_must_equal_measured_pool_epoch(self):
        pool=self.config['pool'];epoch=self.models.DriverEpoch(pool['node_uid'],pool['boot_id'],pool['driver_generation'],pool['gpu_uuid'])
        self.agent.validate_pool_epoch(self.config,epoch)
        with self.assertRaises(ValueError):self.agent.validate_pool_epoch(self.config,replace(epoch,boot_id='44444444-4444-4444-8444-444444444444'))


class HistoryPackingTest(TerminalHistoryTest):
    def test_actual_old_closed_history_remains_terminal_under_measured_mode(self):
        for kind in ('cleaned','retired','abort'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                values=self.completed(Path(tmp),abort=kind=='abort',retired=kind=='retired')
                values[0].update(measured(values[0]))
                envelopes,terminal=self.dispatch(values)
                self.assertEqual(terminal,{POD})
                self.assertEqual(envelopes,[self.check()])
