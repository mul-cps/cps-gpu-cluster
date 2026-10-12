#!/usr/bin/env python3
"""Explicit offline repeat preparation retaining full same-policy custody.

The existing operator20 validator/protocols are reused. Only runtime history
projection and the exact deployed node-agent validator dependency differ.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

import prepare_harness as legacy
import prepare_current_operator20 as original

ORIGINAL_SHA = 'c660f74851df0500079aa705cfd47d74284655871bc32982192cddf3f85c6cde'
AGENT_SHA = '3bae6d53e4ce42a54b6dcd372839ef5f7286084212c5930d1deeb93da8d6c688'


def runtime_history(history, policy_hash):
    """Project runtime authority; keep the full validated archive unchanged."""
    legacy.require(type(history) is dict and policy_hash == original.POLICY_HASH,
                   'Exact mapped current operator20 history/policy required')
    legacy.require(all(type(row) is dict and type(row.get('policy_hash')) is str
                       for row in history.values()), 'Typed full history required')
    return {uid: copy.deepcopy(row) for uid, row in history.items()
            if row['policy_hash'] != policy_hash}


def validator(agent_input):
    _, _, protocol = original.loaders()
    legacy.require(type(agent_input) is dict and set(agent_input) == {'path', 'sha256'}
                   and agent_input['sha256'] == AGENT_SHA, 'Exact deployed3bae node-agent source pin required')
    agent_raw = protocol.input_read(agent_input)
    pilot = original.HERE.parents[1] / 'native-group-pilot'
    if str(pilot) not in sys.path:
        sys.path.insert(0, str(pilot))
    agent = original.module('repeat_actual_node_agent', agent_raw, Path(agent_input['path']))
    legacy.require(agent.SOURCE_PINS['native_gpu_controller.py'] ==
                   '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880',
                   'Actual unchanged current630 controller dependency required')
    raw = legacy.read_pinned(Path(original.__file__), ORIGINAL_SHA)
    code = protocol.replace(raw.decode(), '    import node_agent as agent', '    agent = REPEAT_AGENT')
    marker = '    terminal=module("operator20_terminal_mapper",legacy.read_pinned(TERMINAL_SOURCE,TERMINAL_SHA),TERMINAL_SOURCE)'
    code = protocol.replace(code, marker, marker + '\n    terminal.agent = REPEAT_AGENT')
    code = protocol.replace(code, "node['terminal_history']==history",
                            "node['terminal_history']==RUNTIME_HISTORY(history,policy.hash)")
    # Runtime omits already-terminal same-policy entries. Replay their full
    # captured authority against the previous configuration, never that runtime
    # projection; the full `==history` custody guard remains unchanged.
    code = protocol.replace(code,
        "terminal.map_history({'authority_maps':old_authority,'host_snapshot':projected},before,node)==history",
        "terminal.map_history({'authority_maps':old_authority,'host_snapshot':projected},before,baseline['previous_node'])==history")
    code = protocol.replace(code, "'terminal_history_count':len(history)",
                            "'terminal_history_count':len(history),'runtime_terminal_history_count':len(node['terminal_history'])")
    result = original.module('repeat_operator20_validator', code.encode(), Path(original.__file__))
    result.REPEAT_AGENT = agent
    result.RUNTIME_HISTORY = runtime_history
    validate = result.validate_inputs

    def validate_inputs(*args):
        binding, context, cleared = validate(*args)
        context['preparation_mode'] = 'current-normal-lifecycle-operator20-repeat'
        context['source_dependency_pins']['deployed_node_agent'] = AGENT_SHA
        context['source_dependency_pins']['original_operator20_adapter'] = ORIGINAL_SHA
        context['same_policy_terminal_custody_retained'] = True
        return binding, context, cleared

    result.validate_inputs = validate_inputs
    return result


def prepare(manifest_path, manifest_sha, source_root, output, **native_inputs):
    _, _, protocol = original.loaders()
    wrapper = protocol.input_json({'path': str(manifest_path), 'sha256': manifest_sha})
    legacy.require(type(wrapper) is dict and set(wrapper) == {'version', 'state', 'operator_manifest', 'source_node_agent'}
                   and type(wrapper['version']) is int and wrapper['version'] == 1
                   and wrapper['state'] == 'Root-reviewed-current-operator20-repeat-plan',
                   'Closed explicit current operator20 repeat plan required')
    ref = wrapper['operator_manifest']
    # Existing input reader independently checks the closed private path/raw pin.
    protocol.input_json(ref)
    q = validator(wrapper['source_node_agent'])
    return q.prepare(Path(ref['path']), ref['sha256'], source_root, output, **native_inputs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    for name in ('manifest', 'source-root', 'output', 'native-binary', 'native-build'):
        parser.add_argument('--' + name, type=Path)
    for name in ('manifest-sha256', 'native-binary-sha256', 'native-build-sha256'):
        parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'hardware_qualification': False}))
        return
    legacy.require(all((args.manifest, args.manifest_sha256, args.source_root, args.output,
                        args.native_binary, args.native_binary_sha256, args.native_build, args.native_build_sha256)),
                   'Complete actual pinned repeat preparation inputs required')
    result = prepare(args.manifest, args.manifest_sha256, args.source_root, args.output,
                     native_binary_path=args.native_binary, native_binary_sha=args.native_binary_sha256,
                     native_build_path=args.native_build, native_build_sha=args.native_build_sha256)
    print(json.dumps({'state': result['state'], 'api_calls': False, 'gpu_calls': False,
                      'hardware_qualification': False, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
