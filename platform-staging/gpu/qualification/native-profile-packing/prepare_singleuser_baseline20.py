#!/usr/bin/env python3
"""Inert offline derivative of the reviewed read-only singleuser collector.

Only the closed 5/20 policy/caps and exact rendered two-lifetime observer change.
No host reads, Kubernetes calls, GPU operation or future UID assignment occurs.
"""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path

import prepare_harness as legacy
import prepare_current_operator20 as operator20

TEMPLATE = Path('/home/bjoern/.local/state/cps-platform-completion-20261011/singleuser-baseline-prepared-20261011/capture_singleuser.py')
TEMPLATE_SHA = '9489d9d64baae1599228ebbac78781442be267d1d8f9a24d7a6c9105215880b1'
OBSERVER = Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012/harness20-actual-v4/vmm-owner-exit/host_owner_observer.py')
OBSERVER_SHA = '39d1f821171f851880a364f7fcdaf0d77e26696674a71584d3250039c7c5fd63'
OPERATOR20_SHA = 'c660f74851df0500079aa705cfd47d74284655871bc32982192cddf3f85c6cde'
OLD_POLICY = 'sha256:02316f90f705f5550ab54d1d514ed48f73aa6a13324eea7d4aeaaef959af2fd5'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def assignment(raw, name, value):
    tree = ast.parse(raw)
    nodes = [node for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    legacy.require(len(nodes) == 1, 'One exact reviewed assignment required: ' + name)
    node = nodes[0]
    lines = raw.decode().splitlines(keepends=True)
    lines[node.lineno - 1:node.end_lineno] = [name + ' = ' + repr(value) + '\n']
    return ''.join(lines).encode()


def render(binding, observer_source):
    legacy.require(sha(Path(operator20.__file__).read_bytes()) == OPERATOR20_SHA,
                   'Exact reviewed current operator20 preparer required')
    h, _, protocol = operator20.loaders()
    h.validate_binding(binding)
    legacy.require(binding['policy_hash'] == operator20.POLICY_HASH,
                   'Exact current operator-only5/20 policy required')
    caps = {target['pod_uid']: target['cap_mib'] * 1048576 for target in binding['targets']}
    original = legacy.read_pinned(OBSERVER, OBSERVER_SHA, private=True)
    expected = assignment(original, 'CAP_BY_UID', caps)
    legacy.require(observer_source == expected, 'Exact existing observer protocol with only actual UID/cap binding required')
    raw = legacy.read_pinned(TEMPLATE, TEMPLATE_SHA, private=True)
    raw = assignment(raw, 'OBSERVER_SHA', sha(observer_source))
    raw = assignment(raw, 'OBSERVER_B64', base64.b64encode(observer_source).decode())
    text = protocol.replace(raw.decode(),
                            "10737418240:('cit','native-group-a','cit-jhub','jupyter-citnativegroupa--rtc')",
                            "21474836480:('cit','native-group-a','cit-jhub','jupyter-citnativegroupa--rtc')")
    text = protocol.replace(text, OLD_POLICY, binding['policy_hash'])
    result = text.encode()
    compile(result, 'current-operator20-singleuser-capture', 'exec')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    for key in ('binding', 'observer', 'output'):
        parser.add_argument('--' + key, type=Path)
    for key in ('binding-sha256', 'observer-sha256'):
        parser.add_argument('--' + key)
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'host_reads': False}))
        return
    legacy.require(all((args.binding, args.binding_sha256, args.observer,
                        args.observer_sha256, args.output)), 'Complete actual pinned preparation inputs required')
    binding = legacy.parse(legacy.read_pinned(args.binding, args.binding_sha256, private=True))
    observer = legacy.read_pinned(args.observer, args.observer_sha256, private=True)
    raw = render(binding, observer)
    import os
    import stat
    parent = args.output.parent.lstat()
    legacy.require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
                   and stat.S_IMODE(parent.st_mode) == 0o700, 'Owned private output parent required')
    args.output.mkdir(mode=0o700)
    legacy.write(args.output / 'capture_singleuser.py', raw)
    legacy.write(args.output / 'preparation-receipt.json', (legacy.canonical({
        'state': 'source-prepared-not-captured', 'api_calls': False, 'gpu_calls': False,
        'host_reads': False, 'hardware_qualification': False, 'collector_sha256': sha(raw),
        'original_collector_sha256': TEMPLATE_SHA, 'observer_sha256': sha(observer),
        'binding_sha256': args.binding_sha256, 'policy_hash': binding['policy_hash'],
    }) + '\n').encode())


if __name__ == '__main__':
    main()
