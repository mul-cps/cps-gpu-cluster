"""Offline generated collector checks; retained lifetimes are CPU fixtures only."""
import copy
import ast
import io
import json
import hashlib
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
        def functions(raw):
            return {node.name: ast.get_source_segment(raw.decode(), node)
                    for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)}
        before, after = functions(original), functions(rendered)
        self.assertEqual(set(before), set(after))
        self.assertEqual({name for name in before if before[name] != after[name]},
                         {'validate_request', 'main'})
        for name, expected in before.items():
            if name == 'validate_request':
                expected = expected.replace("10737418240:('cit','native-group-a','cit-jhub','jupyter-citnativegroupa--rtc')",
                                            "21474836480:('cit','native-group-a','cit-jhub','jupyter-citnativegroupa--rtc')")
                expected = expected.replace(p.OLD_POLICY, self.binding['policy_hash'])
            elif name == 'main':
                expected = expected.replace('0<len(a.request.encode())<=65536',
                                            '0<len(a.request.encode())<=131072')
            self.assertEqual(expected, after[name], name)

    def test_complete_actual_restart_archive_input_bound_and_raw_pin(self):
        after_path = CROSS / 'harness20-restart-actual-v1/measurements/same-parent-vmm/after.json'
        if not after_path.exists():
            self.skipTest('Private complete actual restart archive is intentionally unavailable')
        binding = json.loads((CROSS / 'profile20-restart-actual-manifest-v1/actual-binding.json').read_bytes())
        observer = (CROSS / 'harness20-restart-actual-v1/vmm-owner-exit/host_owner_observer.py').read_bytes()
        raw = p.render(binding, observer)
        module = types.ModuleType('generated_restart_baseline20')
        exec(compile(raw, 'generated-restart-baseline20', 'exec'), module.__dict__)
        after = json.loads(after_path.read_bytes())
        request = {k: after[k] for k in ('host', 'pods')}
        text = json.dumps(request, sort_keys=True, separators=(',', ':'), allow_nan=False)
        self.assertGreater(len(text.encode()), 65536)
        self.assertLess(len(text.encode()), 131072)
        self.assertEqual(len(text.encode()), 72428)
        pin = hashlib.sha256(text.encode()).hexdigest()

        def cpu_capture(value, helper):
            self.assertEqual(value, request)
            self.assertEqual(value['host']['retired_caps'], request['host']['retired_caps'])
            module.validate_request(value, helper)
            return {'state': 'cpu-test-not-captured'}

        with patch.object(module.os, 'geteuid', return_value=0), patch.dict(module.os.environ, {}, clear=True), \
                patch.object(module, 'capture', side_effect=cpu_capture) as capture, redirect_stdout(io.StringIO()):
            module.main(['--capture', '--request', text, '--request-sha256', pin])
            capture.assert_called_once()
        for changed, supplied_pin in ((text + ' ', pin),
                                     (text + ' ' * (131073 - len(text.encode())), None)):
            with self.subTest(length=len(changed.encode())), patch.object(module.os, 'geteuid', return_value=0), \
                    patch.dict(module.os.environ, {}, clear=True), \
                    patch.object(module, 'capture', side_effect=AssertionError('host capture called')):
                with self.assertRaises(ValueError):
                    module.main(['--capture', '--request', changed, '--request-sha256',
                                 supplied_pin or hashlib.sha256(changed.encode()).hexdigest()])

    def test_preparer_default_has_no_capture_or_packet_reads(self):
        with patch.object(p, 'render', side_effect=AssertionError('render called')), redirect_stdout(io.StringIO()) as output:
            p.main([])
        self.assertEqual(json.loads(output.getvalue()), {'state': 'inert', 'api_calls': False,
                                                        'gpu_calls': False, 'host_reads': False})


if __name__ == '__main__':
    unittest.main()
