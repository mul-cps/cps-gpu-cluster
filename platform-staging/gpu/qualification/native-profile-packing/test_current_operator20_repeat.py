"""Pure repeat projection/source closure; no hardware or lifecycle claims."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import prepare_current_operator20_repeat as repeat
import test_current_operator20 as original_tests

AGENT = Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012/profile20-restart-safe-source-v1/actual-node-agent-3bae.py')
ACTUAL = AGENT.parents[1] / 'profile20-restart-proposal-offline-v1'


class Repeat20Tests(unittest.TestCase):
    def actual_validator(self):
        if not AGENT.exists():
            self.skipTest('Private captured actual3bae source is intentionally unavailable')
        return repeat.validator({'path': str(AGENT), 'sha256': repeat.AGENT_SHA})

    def test_exact_actual_agent_and_existing_full_fixture_validation(self):
        q = self.actual_validator()
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _ = original_tests.Operator20Tests().complete_fixture(Path(tmp))
            h, c, p = q.loaders()
            _, context, _ = q.validate_inputs(manifest, h, c, p)
            self.assertEqual(context['preparation_mode'], 'current-normal-lifecycle-operator20-repeat')
            self.assertEqual(context['terminal_history_count'], context['runtime_terminal_history_count'])
            self.assertEqual(context['source_dependency_pins']['deployed_node_agent'], repeat.AGENT_SHA)
            self.assertIs(context['same_policy_terminal_custody_retained'], True)

    def test_full_history_is_not_relabelled_or_mutated_by_runtime_projection(self):
        # Deliberate CPU projection fixture, never supplied as captured authority.
        full = {'old': {'policy_hash': 'sha256:' + '1' * 64, 'source': 'cps'},
                'same': {'policy_hash': repeat.original.POLICY_HASH, 'source': 'cit'}}
        before = copy.deepcopy(full)
        runtime = repeat.runtime_history(full, repeat.original.POLICY_HASH)
        self.assertEqual(set(runtime), {'old'})
        self.assertEqual(full, before)
        runtime['old']['source'] = 'changed'
        self.assertEqual(full, before)
        with self.assertRaises(ValueError):
            repeat.runtime_history(full, 'sha256:' + '2' * 64)
        with self.assertRaises(ValueError):
            repeat.runtime_history({'lost': {}}, repeat.original.POLICY_HASH)

    def test_foreign_source_is_rejected_before_any_validator_runs(self):
        with self.assertRaises(ValueError):
            repeat.validator({'path': str(AGENT), 'sha256': '0' * 64})

    def test_actual_complete_archive_is_preserved_while_same_policy_runtime_projects(self):
        if not (ACTUAL / 'terminal-authority-snapshot.json').exists():
            self.skipTest('Private retained actual repeat proposal is intentionally unavailable')
        q = self.actual_validator()
        snapshot = json.loads((ACTUAL / 'terminal-authority-snapshot.json').read_bytes())
        node = json.loads((ACTUAL / 'node-config.json').read_bytes())
        raw = repeat.legacy.read_pinned(q.TERMINAL_SOURCE, q.TERMINAL_SHA)
        mapper = q.module('actual_repeat_terminal_mapper', raw, q.TERMINAL_SOURCE)
        mapper.agent = q.REPEAT_AGENT
        full = mapper.map_history({k: snapshot[k] for k in ('authority_maps', 'host_snapshot')},
                                  snapshot['ledger'], snapshot['previous_node'])
        unchanged = copy.deepcopy(full)
        self.assertEqual(len(full), 36)
        self.assertEqual(len(json.loads(snapshot['ledger']['data']['state.json'])['allocations']), 39)
        # This exact real captured projection failed the original full==runtime assumption.
        self.assertNotEqual(node['terminal_history'], full)
        self.assertEqual(node['terminal_history'], repeat.runtime_history(full, node['policy_hash']))
        self.assertEqual(len(node['terminal_history']), 34)
        q.REPEAT_AGENT.validate_config(node)
        self.assertEqual(full, unchanged)
        self.assertEqual(sum(row['policy_hash'] == node['policy_hash'] for row in full.values()), 2)
        lost = copy.deepcopy(snapshot['ledger'])
        state = json.loads(lost['data']['state.json'])
        bound = next(key for key, row in state['allocations'].items() if row.get('intent'))
        state['allocations'].pop(bound)
        lost['data']['state.json'] = json.dumps(state)
        with self.assertRaises(ValueError):
            mapper.map_history({k: snapshot[k] for k in ('authority_maps', 'host_snapshot')},
                               lost, snapshot['previous_node'])

    def test_default_is_inert_before_source_or_snapshot_reads(self):
        with patch.object(repeat, 'prepare', side_effect=AssertionError('prepare called')), redirect_stdout(io.StringIO()) as out:
            repeat.main([])
        self.assertEqual(json.loads(out.getvalue()), {'state': 'inert', 'api_calls': False,
                                                      'gpu_calls': False, 'hardware_qualification': False})


if __name__ == '__main__':
    unittest.main()
