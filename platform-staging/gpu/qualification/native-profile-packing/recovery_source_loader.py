"""Load only reviewed pure validators; no API clients or controller instances."""
import ast
import hashlib
import sys
from types import ModuleType, SimpleNamespace

import recovery_history as r

def load_sources(sources):
    r.closed(sources, {'model', 'control', 'agent', 'recovery', 'reader', 'baseline'})
    for key, value in sources.items():
        r.closed(value, {'raw', 'sha256'})
        r.require(type(value['raw']) is bytes and hashlib.sha256(value['raw']).hexdigest() == value['sha256'],
                  'Exact reviewed validator source bytes required: ' + key)
    r.require(sources['model']['sha256'] == r.MODEL_SHA and sources['control']['sha256'] == r.CONTROL_SHA
        and sources['baseline']['sha256'] == r.BASELINE_PIN
        and sources['agent']['sha256'] == '05a6ca95eaaaf79cdbbdffec8172c804676d982a4154a422188639cd6b24f09b'
        and sources['recovery']['sha256'] == '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b',
        'Exact SDK, node recovery and original journal closure required')
    def module(name, raw):
        name = name + '_' + hashlib.sha256(raw).hexdigest()[:16]
        result = ModuleType(name); result.__file__ = '/reviewed/' + name + '.py'
        sys.modules[name] = result
        exec(compile(raw, result.__file__, 'exec'), result.__dict__)
        return result
    models = module('historical_recovery_models', sources['model']['raw'])
    agent = module('historical_recovery_agent', sources['agent']['raw'])
    codec = module('historical_recovery_codec', sources['recovery']['raw'])
    r.require(agent.SOURCE_PINS['native_gpu_controller.py'] == r.MODEL_SHA
        and agent.RECOVERY_SOURCE_PIN == sources['recovery']['sha256'],
        'Final node and recovery validator closure required')
    reader = module('historical_recovery_reader', sources['reader']['raw'])
    # Exact function bodies from the pinned SDK. Importing its API module on the
    # host would need unrelated application packages; this extracts only codecs.
    import json, re, uuid
    from dataclasses import replace
    control = {'json': json, 're': re, 'uuid': uuid, 'hashlib': hashlib, 'replace': replace,
        'CapIntent': models.CapIntent, 'CapLimit': models.CapLimit,
        'ClearedOfflineRecovery': models.ClearedOfflineRecovery, 'RetiredInertCap': models.RetiredInertCap,
        'NativeAuthorityError': ValueError, 'NativeAuthorityConflict': ValueError}
    tree = ast.parse(sources['control']['raw'])
    names = {'_json', '_uid', '_sha', '_closed', 'validate_cleanup_record', 'recovery_audit_body'}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    r.require({node.name for node in functions} == names, 'Complete pinned cleanup codec definitions required')
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'pinned-sdk-cleanup-codecs', 'exec'), control)
    return SimpleNamespace(models=models, agent=agent, codec=codec, reader=reader,
        cleanup_validator=control['validate_cleanup_record'], audit_body=control['recovery_audit_body'],
        baseline=r.parse(sources['baseline']['raw'])['records'])

def validate(loaded, history, binding, *, allow_current=False):
    return loaded.reader.validate_history(history, binding, agent=loaded.agent, recovery_codec=loaded.codec,
        models=loaded.models, cleanup_validator=loaded.cleanup_validator, audit_body=loaded.audit_body,
        baseline=loaded.baseline, allow_current=allow_current)
