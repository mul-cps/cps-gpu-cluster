"""Offline generated collector checks; retained lifetimes are CPU fixtures only."""
import copy
import ast
import io
import json
from pathlib import Path
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import prepare_singleuser_baseline20 as p


CROSS = Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012')


class SingleuserBaseline20Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CROSS / 'harness20-actual-v4/measurements/vmm-cit-to-cps/final-postflight.json').exists():
            raise unittest.SkipTest('Private retained actual20 fixture is intentionally unavailable')
        manifest = json.loads((CROSS / 'profile20-actual-manifest-v3/manifest.json').read_bytes())
        cls.binding = json.loads(Path(manifest['binding']['path']).read_bytes())
        cls.observer = (CROSS / 'harness20-actual-v4/vmm-owner-exit/host_owner_observer.py').read_bytes()
        after = json.loads((CROSS / 'harness20-actual-v4/measurements/vmm-cit-to-cps/final-postflight.json').read_bytes())
        cls.request = {k: after[k] for k in ('host', 'pods')}

    def collector(self):
        raw = p.render(self.binding, self.observer)
        module = types.ModuleType('generated_baseline20')
        exec(compile(raw, 'generated-baseline20', 'exec'), module.__dict__)
        return module

    def test_generated_collector_accepts_actual_five_twenty_closed_fixture(self):
        module = self.collector()
        pairs = module.validate_request(self.request, module.helper())
        self.assertEqual([pod['cap_mib'] for _, pod in pairs], [5120, 20480])
        with patch.object(module, 'capture', side_effect=AssertionError('host capture called')), redirect_stdout(io.StringIO()) as output:
            module.main([])
        self.assertEqual(json.loads(output.getvalue()), {'state': 'inert', 'proc_reads': False, 'gpu_calls': False})

    def test_generated_collector_rejects_changed_cap_policy_uid_and_charged_baseline(self):
        module = self.collector()
        for mutate in (
            lambda value: value['host']['targets'][1]['inventory_row'].__setitem__('hard', 10737418240),
            lambda value: value['host']['targets'][1]['inventory_row'].__setitem__('used', 1),
            lambda value: value['host']['targets'][1]['intent'].__setitem__('policy_hash', 'sha256:' + '0' * 64),
            lambda value: value['host']['targets'][1].__setitem__('pod_uid', value['host']['targets'][0]['pod_uid']),
        ):
            value = copy.deepcopy(self.request)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                module.validate_request(value, module.helper())

    def test_observer_protocol_and_binding_scope_are_pinned(self):
        with self.assertRaises(ValueError):
            p.render(self.binding, self.observer + b'\n# changed\n')
        binding = copy.deepcopy(self.binding)
        binding['targets'][1]['cap_mib'] = 10240
        with self.assertRaises(ValueError):
            p.render(binding, self.observer)
        binding = copy.deepcopy(self.binding)
        binding['policy_hash'] = 'sha256:' + '0' * 64
        with self.assertRaises(ValueError):
            p.render(binding, self.observer)

    def test_frozen_collector_is_unchanged(self):
        self.assertEqual(p.sha(p.TEMPLATE.read_bytes()), p.TEMPLATE_SHA)

    def test_original_capture_rejects_twenty_and_generated_host_logic_is_unchanged(self):
        original = p.TEMPLATE.read_bytes()
        module = types.ModuleType('original_baseline')
        exec(compile(original, 'original-baseline', 'exec'), module.__dict__)
        with self.assertRaises(ValueError):
            module.validate_request(self.request, module.helper())
        rendered = p.render(self.binding, self.observer)
        for name in ('helper', 'sealed', 'capture', 'main'):
            def source(raw):
                tree = ast.parse(raw)
                return ast.get_source_segment(raw.decode(), next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == name))
            self.assertEqual(source(original), source(rendered), name)

    def test_preparer_default_has_no_capture_or_packet_reads(self):
        with patch.object(p, 'render', side_effect=AssertionError('render called')), redirect_stdout(io.StringIO()) as output:
            p.main([])
        self.assertEqual(json.loads(output.getvalue()), {'state': 'inert', 'api_calls': False,
                                                        'gpu_calls': False, 'host_reads': False})


if __name__ == '__main__':
    unittest.main()
