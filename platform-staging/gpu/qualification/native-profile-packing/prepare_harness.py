#!/usr/bin/env python3
"""Prepare pinned Oct9 probes for a controlled 5+10GiB experiment; never execute them."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

MIB = 1048576
NATIVE_C_SHA = '15119a459ad4611a001ee1e89fb97929efa693d8a1ec3136c1e7d0a9b7b45a86'
NATIVE_COMPILER_SHA = 'f6c5e80932fe1053efaca1155e6e777941aad7a716d4479d814df6e2e952a8aa'
CUDA_HEADER_SHA = '7a79d67ca888061b1dfbe4739b51ad64f85a2f3ad874947ce09b2c635b4c7072'
CPU_IMAGE = 'sha256:9720ec70a8a903914d26fd6a6aa3dec9eb11524ea4fac6f6ebc81827b8e18773'
CUDA_HEADER = Path('/tmp/cps-native-imports-headers/unpack/usr/local/cuda-13.4/targets/x86_64-linux/include/cuda.h')
SCOPES = [('cps', 'native-group-b', 'jupyterhub', 'jupyter-cpsnativegroupb--rtc', 5120),
          ('cit', 'native-group-a', 'cit-jhub', 'jupyter-citnativegroupa--rtc', 10240)]
SOURCE_PINS = {
    'group_probe.py': '02ce478a4543b3d971585add60c6314605a0f120eea3e8a6adb014c5ba527cbd',
    'run_group_acceptance.py': '91da523bc0a99cbb78f42f28dcc738d80710c03daed5b00ad1202c4196cd6d8c',
    'activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py': '9c4947f0ca3028073aa3997964c419f2bbb3f6721f1e1147d1ca0f8525e36b8e',
    'native-imports': '0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69',
    'imports/run_same_pod.py': '1fcb76aae4ab13e34cdc3e6071560abd2bbb90720ef4c7b4ea54cb8a2cb6593c',
    'imports/same_pod_imports.py': 'd8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c',
    'imports-cross-pod/run_cross_pod.py': 'ee8772c7caa0ba5eceaba18b4b8a3c7373ab35ac67b9426384513f1998570c87',
    'imports-cross-pod/ipc_endpoint.py': '0faa5fddc8db4e81b4cc49784cf6eb5933c1cb95366ea0218c9b367e6c2a9aad',
    'imports-cross-pod/ipc_host_pid.py': '0ec320a9ab119bd15bf104d98d43a321299d9ac78f5a3d64a64356b9e56ac570',
    'imports-cross-pod/kernel_witness_collector.py': 'd641b29b52e8f06af48a95ad3ab4841c488c097090473e51e4fe63717ff1588c',
    'imports-cross-pod/kernel_witness_validator.py': '8141665b34d61ce1293232ef79876b2acab19d3f20c70b945d32b46916da265a',
    'imports-cross-pod/kernel_witness_transport.py': '56a5983c0686154a3b34e694642846f6b6af7681203d1b256a3a379e2902a30a',
    'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py': '1f3ea6e31e876d088114859589cce5ce3f7d60834842b246ea55c1ae9fdef521',
    'vmm-cross-parent-sgid-fix/vmm_endpoint.py': '596d50a2083efc9442ce5f72e905fa19956f69a7b6a18f01f6904ca0a7eba4ad',
    'vmm-cross-parent-sgid-fix/vmm_bridge.py': '6e9b02c5ddfefac9b49330ab3423f07050d13252e7b0167f5e8c8da9d603f8aa',
    'vmm-cross-parent-sgid-fix/kernel_witness_collector.py': 'beab9579a163397089489bf974cd75cdd11a5f2d06c93aa26e9f7a9ae5d6cf64',
    'vmm-cross-parent-sgid-fix/kernel_witness_validator.py': 'c54badfd88f0e30f8b8948aa48e3c24f59027779cd59bcfb9413e032d417096e',
    'vmm-cross-parent-sgid-fix/kernel_witness_transport.py': '3d6b0a7b383d5cb05f20ca76479e78eff1ce9c1964441718138596dcbc6caaea',
    'vmm-owner-exit/run_owner_exit.py': '2ad7751b0c282bb6033e226ed199f24a57d2d7a5971e8f3cc0796ac7ca465d80',
    'vmm-owner-exit/owner_exit_probe.py': '622649c757afd433d4c8f48513eb923f33cf1fd3d08acf7c749137c246c1d6ff',
    'vmm-owner-exit/host_owner_observer.py': '3881ca93b3b5d321dbd07e42b2e4bd9e0c9cbd6bc1454ccc7bc57fc81b259a81',
    'mps/root-wrapper-prepared/run_mps.py': 'faddd67f25417c0861cf27f82bf213ac1601fcd772d51962431e92112881f9da',
    'mps/mps_probe.py': 'a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e',
    'managed/run_managed.py': '2d013735da034b437837fbb3335ae6d188774df3942c4d9363167c8894373862',
    'managed/managed_probe.py': 'a2ffe7b02ed783ec9247e5f9bd2b8f6472806cd7daaf82d530d219cf9dd2a2a9',
}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def validate_binding(value):
    return _validate_binding(value, 'interactive-native-qualification-')

def _validate_binding(value, profile_prefix):
    """Shared fixed pair/epoch checks; public entry points choose a closed mode."""
    require(isinstance(value, dict) and set(value) == {'version', 'state', 'policy_hash',
        'observer_uid', 'pool', 'pool_measurement', 'retired_capture', 'targets'}, 'Closed binding required')
    require(type(value['version']) is int and value['version'] == 1 and
        value['state'] == 'Root-reviewed-controlled-plan', 'Explicit controlled plan required')
    require(re.fullmatch('sha256:[a-f0-9]{64}', value['policy_hash'] or ''), 'Exact policy hash required')
    valid_uuid(value['observer_uid'])
    p = value['pool']
    require(isinstance(p, dict) and set(p) == {'node', 'node_uid', 'boot_id', 'gpu_uuid',
        'driver_generation', 'budget_mib', 'measured_free_bytes', 'headroom_bytes',
        'measurement_sha256'}, 'Closed measured pool required')
    expected = {'node': 'k3s-wk-gpu2', 'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
        'boot_id': '209f8bc9-a478-48e4-925a-6e07ffa56f7a',
        'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56',
        'driver_generation': 'b10498fc-9153-4394-875a-ea7cfb498625'}
    require(all(p[k] == v for k, v in expected.items()), 'Selected Oct9 healthy epoch required')
    require(all(type(p[k]) is int and 0 <= p[k] < 2**64 for k in
        ('budget_mib', 'measured_free_bytes', 'headroom_bytes')) and p['budget_mib'] == 15360
        and p['headroom_bytes'] > 0 and p['budget_mib'] * MIB <=
        p['measured_free_bytes'] - p['headroom_bytes'], 'Measured free minus headroom must cover15GiB')
    digest(p['measurement_sha256'])
    file_pin(value['pool_measurement'])
    require(value['pool_measurement']['sha256'] == p['measurement_sha256'], 'Exact measured source raw pin required')
    file_pin(value['retired_capture'])
    require(isinstance(value['targets'], list) and len(value['targets']) == 2, 'Exact pair required')
    seen = {value['observer_uid']}
    for t, (s, w, n, name, cap) in zip(value['targets'], SCOPES):
        require(isinstance(t, dict) and set(t) == {'source', 'workspace', 'namespace', 'name',
            'cap_mib', 'profile', 'pod_uid', 'spec_sha256', 'pod_capture'}, 'Closed actual target required')
        require((t['source'], t['workspace'], t['namespace'], t['name']) == (s, w, n, name)
            and type(t['cap_mib']) is int and t['cap_mib'] == cap
            and t['profile'] == profile_prefix + str(cap // 1024),
            'Only CPS B5 and CIT A10 operator scopes allowed')
        valid_uuid(t['pod_uid']); digest(t['spec_sha256']); file_pin(t['pod_capture'])
        require(t['pod_uid'] not in seen, 'Distinct actual lifetime UIDs required'); seen.add(t['pod_uid'])
    return value

def valid_uuid(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int,
            'Canonical nonzero UUID required')

def digest(value):
    require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'Raw SHA256 required')

def file_pin(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'} and
            isinstance(value['path'], str) and Path(value['path']).is_absolute(), 'Absolute raw input pin required')
    digest(value['sha256'])

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def replace(source, old, new, count=1):
    require(source.count(old) == count, 'Reviewed source adaptation span changed: ' + old[:60])
    return source.replace(old, new)

def definition(source, name):
    nodes = [n for n in ast.parse(source).body if getattr(n, 'name', None) == name]
    require(len(nodes) == 1, 'Exact source definition required: ' + name)
    n = nodes[0]
    return '\n'.join(source.splitlines()[n.lineno - 1:n.end_lineno]) + '\n'

def native_build_sources():
    base = Path(__file__).parent.parent / 'native-imports'
    original = read_pinned(base / 'native_imports.c', NATIVE_C_SHA)
    compiler = read_pinned(base / 'compile_probe.py', NATIVE_COMPILER_SHA)
    code = replace(original.decode(), 'else if(!strcmp(n,"5120"))cap_mib=5120;else return 2;',
        'else if(!strcmp(n,"5120"))cap_mib=5120;else if(!strcmp(n,"10240"))cap_mib=10240;else return 2;')
    return {'native_imports.c': code.encode(), 'compile_probe.py': compiler}

def cap_lookup(binding):
    caps = {t['pod_uid']: t['cap_mib'] * MIB for t in binding['targets']}
    return '\nCAP_BY_UID = ' + repr(caps) + '''
def expected_cap(pod_uid):
    require(type(pod_uid) is str and pod_uid in CAP_BY_UID, 'Exact bound CPS5/CIT10 lifetime required')
    return CAP_BY_UID[pod_uid]
def bind_cap(pod_uid):
    global CAP
    CAP = expected_cap(pod_uid)
    return CAP
def cap_row(row, pod_uid):
    cap = expected_cap(pod_uid)
    require(type(row) is dict and all(type(row.get(k)) is int for k in ('soft', 'hard', 'used'))
        and row['soft'] == row['hard'] == cap and 0 <= row['used'] <= cap
        and row.get('offline') is False and row.get('pinned') is True
        and row.get('default_hierarchy') is True, 'Exact active finite target-specific native cap required')
    return True
'''

def render_cap_sources(sources, binding):
    """Retain original exchange/process guards; adapt only closed lifetime caps."""
    lookup = cap_lookup(binding); result = {}
    for name in ('imports-cross-pod/ipc_endpoint.py', 'vmm-cross-parent-sgid-fix/vmm_endpoint.py',
                 'vmm-owner-exit/owner_exit_probe.py'):
        code = sources[name].decode()
        guard = "if __name__ == '__main__': main()" if name.endswith('ipc_endpoint.py') else "if __name__=='__main__':main()"
        code = replace(code, guard, lookup + '\n' + guard)
        if name.endswith('ipc_endpoint.py'):
            code = replace(code, "    p.add_argument('--wait-for-root', action='store_true')",
                "    p.add_argument('--wait-for-root', action='store_true')\n    p.add_argument('--expected-pod-uid')")
            code = replace(code, "    canonical_uuid(args.trial_id)",
                "    canonical_uuid(args.trial_id)\n    bind_cap(args.expected_pod_uid)")
        elif name.endswith('vmm_endpoint.py'):
            code = replace(code, '    global TRIAL,ROLE;TRIAL=args.trial_id;ROLE=args.role',
                '    global TRIAL,ROLE;TRIAL=args.trial_id;ROLE=args.role\n    bind_cap(args.expected_pod_uid)')
        else:
            code = replace(code, '    preflight(args);TRIAL,ROLE=args.trial_id,args.role;',
                '    preflight(args);bind_cap(args.expected_pod_uid);TRIAL,ROLE=args.trial_id,args.role;')
        result[name] = code.encode()
    for name in ('imports-cross-pod/ipc_host_pid.py', 'vmm-cross-parent-sgid-fix/vmm_bridge.py'):
        code = sources[name].decode()
        code = replace(code, "    relative = identity['cgroup_relative']",
            "    cap = expected_cap(identity['pod_uid'])\n    relative = identity['cgroup_relative']")
        code = replace(code, "actual['soft'] == actual['hard'] == 5368709120", "cap_row(actual, identity['pod_uid'])")
        code = replace(code, "actual['used'] <= 5368709120", "actual['used'] <= cap")
        if name.endswith('ipc_host_pid.py'):
            code = replace(code, "(b'--expect', b'deny')):",
                "(b'--expect', b'deny'), (b'--expected-pod-uid', identity['pod_uid'].encode())):")
        if name.endswith('vmm_bridge.py'):
            code = replace(code, "PODS=frozenset({'4010edf4-f407-409b-aa4c-de0615e8c05c','879a4589-faee-4569-bdb8-f2e7c154ef19'})",
                'PODS=frozenset(' + repr([t['pod_uid'] for t in binding['targets']]) + ')')
            suffix = binding['targets'][1]['pod_uid'].replace('-', '')[:12]
            code = code.replace('/run/cps-native-gpu/operator/vmm-cross-parent-sgid-fix',
                                '/run/cps-native-gpu/operator/vmm-profile-qualification-' + suffix)
        guard = "if __name__ == '__main__': main()" if name.endswith('ipc_host_pid.py') else "if __name__=='__main__':main()"
        code = replace(code, guard, lookup + '\n' + guard)
        result[name] = code.encode()
    name = 'vmm-owner-exit/host_owner_observer.py'; code = sources[name].decode()
    code = replace(code, "def inventory(raw,identity):", "def inventory(raw,identity):\n    cap=expected_cap(identity['pod_uid'])")
    code = replace(code, "row['soft']==row['hard']==CAP and row['used']<=CAP", "cap_row(row, identity['pod_uid']) and row['used']<=cap")
    code = replace(code, "    identity=request['identity'];path=identity['cgroup_relative']",
        "    identity=request['identity'];cap=expected_cap(identity['pod_uid']);path=identity['cgroup_relative']", count=2)
    code = replace(code, "0<=row['used']<=CAP if request['op']=='post-release' else BYTES<=row['used']<=CAP",
        "0<=row['used']<=cap if request['op']=='post-release' else BYTES<=row['used']<=cap")
    code = replace(code, "if __name__=='__main__':main()", lookup + "\nif __name__=='__main__':main()")
    result[name] = code.encode()
    return result

def render_sources(sources, binding, retired, *, native_binary=None):
    validate_binding(binding)
    return _render_validated_sources(sources, binding, retired, native_binary=native_binary)

def _render_validated_sources(sources, binding, retired, *, native_binary=None):
    require(set(sources) == set(SOURCE_PINS) and all(sha(sources[k]) == v
        for k, v in SOURCE_PINS.items()), 'Exact complete Oct9 source closure required')
    records = retired['records']; count = len(records)
    require(count <= 32, 'Bounded explicit retirement capture required')
    out = dict(sources)
    out.update(render_cap_sources(sources, binding))
    out.update(native_build_sources())
    if native_binary is not None: out['native-imports'] = native_binary
    helper = sources['imports/same_pod_imports.py'].decode()
    helper = replace(helper, 'CAP = 5368709120', 'CAP = 10737418240')
    helper = replace(helper, "'--cap-mib', '5120'", "'--cap-mib', '10240'")
    helper = replace(helper, SOURCE_PINS['native-imports'], sha(out['native-imports']))
    out['imports/same_pod_imports.py'] = helper.encode()
    # The old classifier, raw UUID path, watchdog, tensor touching and cleanup
    # remain unchanged. Both the direct oversized call and stepped exhaustion
    # must fail with a reviewed typed CUDA OOM; no successful over-cap touch.
    probe = sources['group_probe.py'].decode()
    probe = replace(probe, "    parser.add_argument('--duration',type=int,default=120)",
        "    parser.add_argument('--duration',type=int,default=120)\n    parser.add_argument('--cap-mib',type=int,choices=(5120,10240),default=5120)")
    probe = replace(probe, '    args=parser.parse_args()', '    args=parser.parse_args()\n    global CAP_MIB\n    CAP_MIB=args.cap_mib')
    probe = replace(probe, "        for step in range(1,CAP_MIB//STEP_MIB+2):", """        try:
            candidate=torch.empty((CAP_MIB+STEP_MIB)*MIB,dtype=torch.uint8,device='cuda')
        except Exception as error:
            proof=oom_proof(error,torch)
            if proof is None:raise
            result.update(oversized_denied=True,oversized_error=proof)
            mark('oversized-denial',{'attempted_total_tensor_mib':CAP_MIB+STEP_MIB,'typed_oom':proof})
        else:
            candidate=None;torch.cuda.empty_cache()
            raise RuntimeError('Oversized allocation unexpectedly succeeded; never touched')
        for step in range(1,CAP_MIB//STEP_MIB+2):""")
    probe = replace(probe, "1536 if args.case=='aggregate-oom' else 4096",
        "CAP_MIB-3584 if args.case=='aggregate-oom' else CAP_MIB-1024")
    probe = replace(probe, "            mark('after-step-touch',{'held_tensor_mib':len(held)*STEP_MIB})", """            mark('after-step-touch',{'held_tensor_mib':len(held)*STEP_MIB})
            if len(held)*STEP_MIB==minimum_held_mib:
                mark('held-native-observation-window',{'held_tensor_mib':len(held)*STEP_MIB,'hold_seconds':30})
                time.sleep(30)""")
    out['group_probe.py'] = probe.encode(); probe_sha = sha(out['group_probe.py'])

    # Use the later successful gate+identity preflight; graft only the bounded
    # stream/assessment runner from the original acceptance helper.
    original = sources['run_group_acceptance.py'].decode()
    pre = sources['activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py'].decode()
    pre = pre[:pre.index('def main(argv=None):')]
    pre += '\nimport threading\nPROBE_SHA = ' + repr(probe_sha) + '\n'
    sanitized = [{k: v for k, v in t.items() if k != 'pod_capture'} for t in binding['targets']]
    pre += 'BOUND_TARGETS = ' + repr(sanitized) + '\n'
    pre += 'BOUND_CONFIG = ' + repr({'observer_uid': binding['observer_uid'],
        'driver_generation': binding['pool']['driver_generation'], 'targets': [
        {k: t[k] for k in ('namespace', 'name', 'pod_uid')} for t in sanitized]}) + '\n'
    pre += 'BUDGET_BYTES = 16106127360\n'
    pre += "def target_binding(target):\n    found=[t for t in BOUND_TARGETS if all(t[k]==target[k] for k in ('namespace','name','pod_uid'))]\n    require(len(found)==1,'Exact Root-reviewed normal Source lifetime required')\n    return found[0]\n"
    pre = replace(pre, "TARGET_POLICY = 'sha256:78fb2d7ca42585a000e58b52c297d072a11dfbc466b19f50aa9d276d567a413f'",
        'TARGET_POLICY = ' + repr(binding['policy_hash']))
    whitelist = (canonical(retired) + '\n').encode()
    pre = replace(pre, "RETIRED_WHITELIST_SHA = '174f0e1b6e3c4491b6a3291e2e2f66b9bdbc0ed9a54d828b789e37de49f8b12f'",
        'RETIRED_WHITELIST_SHA = ' + repr(sha(whitelist)))
    pre = replace(pre, "len(approved)==6", 'len(approved)==' + str(count))
    pre = replace(pre, "len(value['records']) == 6", "len(value['records']) == " + str(count))
    # Only per-target finite limits change, including original retired caps.
    pre = replace(pre, "c['cap_bytes']", "intent['cap_mib']*1048576", count=5)
    pre = replace(pre, "record.limit.soft==record.limit.hard==intent['cap_mib']*1048576",
        "record.limit.soft==record.limit.hard==record.intent.cap_mib*1048576")
    pre = replace(pre, "require(set(rows)==bound,'Unbound/orphan native inventory entry blocks probes')",
        "require(set(rows)==bound,'Unbound/orphan native inventory entry blocks probes')\nrequire(sum(t['inventory_row']['hard'] for t in targets)<=c['budget_bytes'] and sum(t['inventory_row']['used'] for t in targets)<=c['budget_bytes'],'Aggregate admission/charge exceeds measured pool')")
    pre = replace(pre, 'def pod_snapshot(pod, target):', 'def pod_snapshot(pod, target):\n    bound = target_binding(target)')
    pre = replace(pre, "'--cap-mib': '5120'", "'--cap-mib': str(bound['cap_mib'])")
    pre = replace(pre, "'cap_mib': 5120, 'policy_hash': values['--policy-hash']", "'cap_mib': bound['cap_mib'], 'policy_hash': values['--policy-hash']")
    pre = replace(pre, "meta.get('annotations', {}).get('cps.compute/native-spec-sha256') == spec_sha",
        "meta.get('annotations', {}).get('cps.compute/native-spec-sha256') == spec_sha == bound['spec_sha256']")
    pre = replace(pre, "return {**target, 'intent': intent,", "return {**target, 'cap_mib': bound['cap_mib'], 'intent': intent,")
    pre = replace(pre, 'def preflight(config):', "def preflight(config):\n    require(config==BOUND_CONFIG,'Actual reviewed observer/epoch/two normal Source lifetimes required')")
    pre = replace(pre, "'cap_bytes': CAP, 'targets': targets,", "'cap_bytes': CAP, 'budget_bytes': BUDGET_BYTES, 'targets': targets,")
    pre = replace(pre, "row['soft']==row['hard']==CAP and row['used']<=CAP", "row['soft']==row['hard']==prior['intent']['cap_mib']*1048576 and row['used']<=row['hard']")
    for name in ('ProbeRun', 'assess', 'overlap', 'main'):
        pre += '\n' + definition(original, name)
    pre = replace(pre, "'--duration', str(duration), '--expected-device-uuid', GPU]",
        "'--duration', str(duration), '--expected-device-uuid', GPU, '--cap-mib', str(target_binding(target)['cap_mib'])]")
    pre = replace(pre, "(1536 if aggregate else 4096) <= held <= (2816 if aggregate else 5120)",
        "(6656 if aggregate else 9216) <= held <= (7936 if aggregate else 10240)")
    pre = replace(pre, "    typed = failure.get('over_error', {})", """    require(pr.get('cap_mib')==(10240 if aggregate else 5120) and failure.get('cap_mib')==10240
        and failure.get('oversized_denied') is True and failure.get('oversized_error')==failure.get('over_error')
        and failure.get('maximum_attempted_tensor_mib')==10496,'Exact10GiB oversized typed denial required')
    typed = failure.get('over_error', {})""")
    pre = replace(pre, "        oom_events = oom.complete()", """        oom.wait(lambda events:any(e.get('phase')=='held-native-observation-window' for e in events),35)
        held_observation=preflight(config);write_json(output/'held-native-observation.json',held_observation)
        compare_observations(before,held_observation)
        rows=held_observation['host']['targets']
        require(rows[1]['inventory_row']['used']>=(8704 if aggregate else 9216)*1048576
            and sum(t['inventory_row']['used'] for t in rows)<=BUDGET_BYTES,'Actual held charge/aggregate bounds required')
        oom_events = oom.complete()""")
    pre = replace(pre, "    result = assess(peer_events, oom_events, aggregate=aggregate)", """    compare_observations(before,after)
    require(all(t['inventory_row']['used']==0 for t in after['host']['targets']),'Actual final parent charge must be zero')
    result = assess(peer_events, oom_events, aggregate=aggregate)""")
    pre += "\nif __name__ == '__main__': main()\n"
    compile(pre, 'rendered-preflight', 'exec')
    out['run_group_acceptance.py'] = pre.encode()
    out.pop('activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py')
    out['retired-caps.json'] = whitelist
    # Extract literal host source without executing any preflight or API call.
    host_source = ast.literal_eval(next(n.value for n in ast.parse(pre).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HOST_SOURCE' for t in n.targets)))
    host_sha = sha(host_source.encode()); pre_sha = sha(out['run_group_acceptance.py'])
    for name in ['imports/run_same_pod.py', 'imports-cross-pod/run_cross_pod.py',
                 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py', 'vmm-owner-exit/run_owner_exit.py',
                 'mps/root-wrapper-prepared/run_mps.py']:
        code = sources[name].decode().replace(SOURCE_PINS['run_group_acceptance.py'], pre_sha)
        code = code.replace('463a9d907a5c33877c100dc79a25d4f6d7ed9d607c806b5742bfce0a51972ccd', host_sha)
        code = code.replace('b42230628ae39406b4a90ea6c311ce38202d6dcd565b769450938fedac70df5f', sha(whitelist))
        if name == 'imports/run_same_pod.py':
            code = code.replace(SOURCE_PINS['group_probe.py'], probe_sha)
            code = code.replace(SOURCE_PINS['imports/same_pod_imports.py'], sha(out['imports/same_pod_imports.py']))
            code = code.replace(SOURCE_PINS['native-imports'], sha(out['native-imports']))
            code = replace(code, "h=load_preflight();base=Path(__file__).parent",
                "require(args.side=='cit','This same-parent import experiment requires CIT10');h=load_preflight();base=Path(__file__).parent")
            code = replace(code, "len(after['host'].get('retired_caps',[]))==2", "len(after['host'].get('retired_caps',[]))==" + str(count))
        if name == 'imports-cross-pod/run_cross_pod.py':
            code = replace(code, "[*base, '--role', 'exporter']", "[*base, '--role', 'exporter', '--expected-pod-uid', exporter_target['pod_uid']]")
            code = replace(code, "Session(exporter_target, [*base, '--role', 'importer',",
                "Session(exporter_target, [*base, '--role', 'importer', '--expected-pod-uid', exporter_target['pod_uid'],")
            code = replace(code, "Session(importer_target, [*base, '--role', 'importer',",
                "Session(importer_target, [*base, '--role', 'importer', '--expected-pod-uid', importer_target['pod_uid'],")
        if name == 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py':
            code = replace(code, "CPS_UID='4010edf4-f407-409b-aa4c-de0615e8c05c'", 'CPS_UID=' + repr(sanitized[0]['pod_uid']))
            code = replace(code, "CIT_UID='879a4589-faee-4569-bdb8-f2e7c154ef19'", 'CIT_UID=' + repr(sanitized[1]['pod_uid']))
            suffix = binding['targets'][1]['pod_uid'].replace('-', '')[:12]
            code = code.replace('/run/cps-native-gpu/operator/vmm-cross-parent-sgid-fix',
                                '/run/cps-native-gpu/operator/vmm-profile-qualification-' + suffix)
        if name == 'vmm-owner-exit/run_owner_exit.py':
            code = replace(code, "    participants=post_release.get('participants');", "    cap=expected_cap(post_release['pod_uid'])\n    participants=post_release.get('participants');")
            code = replace(code, "row['soft']==row['hard']==5368709120", "row['soft']==row['hard']==cap")
            code = replace(code, "0<=row['used']<=5368709120", "0<=row['used']<=cap")
            code = replace(code, "BYTES<=prior['used']<=5368709120", "BYTES<=prior['used']<=cap")
            code = replace(code, "if __name__=='__main__':main()", cap_lookup(binding) + "\nif __name__=='__main__':main()")
        for changed, raw in out.items():
            if changed in SOURCE_PINS and changed != name and raw != sources[changed]:
                code = code.replace(SOURCE_PINS[changed], sha(raw))
        out[name] = code.encode()
    out['mps/run_mps.py'] = out.pop('mps/root-wrapper-prepared/run_mps.py')
    mps = sources['mps/mps_probe.py'].decode()
    mps = replace(mps, '1048576, 5120, 256, 5376', '1048576, 10240, 256, 10496')
    mps = replace(mps, 'held >= 4096', 'held >= 9216')
    mps = replace(mps, "require(type(mib) is int and mib in (64, STEP_MIB) and len(self.held) <= 20, 'Fixed bounded allocation required')",
        "require(type(mib) is int and len(self.held) <= 20 and (mib in (64, STEP_MIB) or (mib == MAX_ATTEMPT_MIB and touch is False and not self.held)), 'Fixed bounded allocation required')")
    mps = replace(mps, 'above5GiB', 'above10GiB')
    mps = replace(mps, "        for step in range(1, MAX_ATTEMPT_MIB // STEP_MIB + 1):", """        oversized=clients[0].request('allocate',mib=MAX_ATTEMPT_MIB,touch=False)
        require(type(oversized.get('cuda_result')) is int and oversized['cuda_result']==2,'Oversized10GiB allocation must deny with CUDA OOM')
        mark('oversized-denial',{'cuda_result':2,'attempted_mib':MAX_ATTEMPT_MIB})
        for step in range(1, MAX_ATTEMPT_MIB // STEP_MIB + 1):""")
    out['mps/mps_probe.py'] = mps.encode()
    wrapper = out['mps/run_mps.py'].decode().replace(SOURCE_PINS['mps/mps_probe.py'], sha(out['mps/mps_probe.py']))
    wrapper = replace(wrapper, "'cap_bytes': h.CAP, 'targets': before['pods'],", "'cap_bytes': h.CAP, 'budget_bytes': h.BUDGET_BYTES, 'targets': before['pods'],")
    wrapper = replace(wrapper, "4096 <= oom['held_mib'] <= 5120", "9216 <= oom['held_mib'] <= 10240")
    wrapper = replace(wrapper, "<= 5376", "<= 10496")
    wrapper = replace(wrapper, "completed.get('cap_mib') == 5120", "completed.get('cap_mib') == 10240")
    wrapper = replace(wrapper, "completed.get('max_attempted_mib') == 5376", "completed.get('max_attempted_mib') == 10496")
    wrapper = replace(wrapper, "default='cps'", "default='cit'")
    wrapper = replace(wrapper, "    registered = one(mps, 'phase', 'mps-registered')", """    oversized = one(mps, 'phase', 'oversized-denial')
    require(oversized.get('cuda_result')==2 and oversized.get('attempted_mib')==10496,'Exact oversized CUDA OOM required')
    registered = one(mps, 'phase', 'mps-registered')""")
    # This prepared MPS experiment is deliberately only the10GiB target.
    wrapper = replace(wrapper, "h = load_preflight()", "require(args.mps_hub=='cit','This controlled MPS probe requires the10GiB CIT target')\n    h = load_preflight()")
    out['mps/run_mps.py'] = wrapper.encode()
    out['run_kernel_controls.py'] = Path(__file__).with_name('run_kernel_controls.py').read_bytes()
    out['inspect_stop.py'] = Path(__file__).with_name('inspect_stop.py').read_bytes()
    out['run_retirement_witness.py'] = Path(__file__).with_name('run_retirement_witness.py').read_bytes()
    out['prepare_harness.py'] = Path(__file__).read_bytes()
    for name, raw in out.items():
        if name.endswith('.py'): compile(raw, name, 'exec')
    return out

def read_pinned(path, expected, *, private=False, allow_empty=False):
    digest(expected)
    if private:
        parent = path.parent.lstat()
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
                stat.S_IMODE(parent.st_mode) == 0o700, 'Private owned input parent required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                before.st_nlink == 1 and not before.st_mode & 0o022 and
                (not private or stat.S_IMODE(before.st_mode) == 0o600) and
                (0 <= before.st_size if allow_empty else 0 < before.st_size) and
                before.st_size <= 2097152, 'Stable owned bounded input required')
        raw = os.read(fd, 2097153); after = os.fstat(fd)
        require(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
            for k in ('st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns', 'st_size')) and
            sha(raw) == expected, 'Raw input pin changed')
        return raw
    finally:
        os.close(fd)

def validate_native_build(build, binary, binary_sha, binary_path):
    """Validate Root's actual offline CPU build; never create a build receipt."""
    fields = {'version', 'state', 'gpu_calls', 'hardwareQualified', 'imageId', 'observedAt',
        'sourceSha256', 'headerSha256', 'binarySha256', 'compileArgv', 'compileExitCode',
        'compileStdoutSha256', 'compileStderrSha256', 'cpuInertArgv', 'cpuInertExitCode',
        'cpuInertOutput', 'abiVersionInfoSha256'}
    require(type(build) is dict and set(build) == fields and type(build['version']) is int
        and build['version'] == 1 and build['state'] == 'cpu-compiled'
        and build['gpu_calls'] is False and build['hardwareQualified'] is False
        and build['imageId'] == CPU_IMAGE and build['headerSha256'] == CUDA_HEADER_SHA
        and build['sourceSha256'] == sha(native_build_sources()['native_imports.c'])
        and build['binarySha256'] == binary_sha == sha(binary) and binary.startswith(b'\x7fELF')
        and binary_sha != SOURCE_PINS['native-imports'], 'Exact actual new CPU build closure required')
    for key in ('sourceSha256', 'headerSha256', 'binarySha256', 'compileStdoutSha256',
                'compileStderrSha256', 'abiVersionInfoSha256'): digest(build[key])
    require(type(build['compileExitCode']) is int and build['compileExitCode'] == 0
        and type(build['cpuInertExitCode']) is int and build['cpuInertExitCode'] == 0
        and build['cpuInertOutput'] == {'state': 'inert', 'gpu_calls': False,
            'payload_mib': 64, 'production_qualified': False}, 'Actual successful inert CPU readback required')
    argv = build['compileArgv']
    require(type(argv) is list and len(argv) == 31 and all(type(a) is str for a in argv),
            'Exact bounded offline compile argv required')
    mount = argv[13]
    require(mount.endswith(':/source:ro'), 'Exact read-only source mount required')
    source_dir = Path(mount[:-len(':/source:ro')])
    require(source_dir.is_absolute() and str(source_dir) == os.path.normpath(str(source_dir)),
            'Absolute canonical source directory required')
    outdir = binary_path.parent
    expected = ['podman', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--security-opt=label=disable',
        '--userns=keep-id', '--tmpfs', '/tmp:rw,nodev,nosuid,size=64m',
        '-v', str(source_dir) + ':/source:ro', '-v', str(CUDA_HEADER.parent) + ':/headers:ro',
        '-v', str(outdir) + ':/out:rw', '--entrypoint', 'gcc', CPU_IMAGE,
        '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2', '-I/headers', '/source/native_imports.c',
        '-ldl', '-o', '/out/native-imports-10']
    require(argv == expected and binary_path.name == 'native-imports-10',
            'Only exact Root-approved offline no-device compiler recipe accepted')
    require(build['cpuInertArgv'] == ['podman', 'run', '--rm', '--pull=never', '--network=none',
        '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
        '--security-opt=label=disable', '--userns=keep-id', '-v', str(outdir) + ':/out:ro',
        '--entrypoint', '/out/native-imports-10', CPU_IMAGE], 'Exact offline inert execution recipe required')
    return {'source': {'path': str(source_dir / 'native_imports.c'), 'sha256': build['sourceSha256']},
        'header': {'path': str(CUDA_HEADER), 'sha256': build['headerSha256']},
        'stdout': {'path': str(outdir / 'compile.stdout'), 'sha256': build['compileStdoutSha256']},
        'stderr': {'path': str(outdir / 'compile.stderr'), 'sha256': build['compileStderrSha256']},
        'abi': {'path': str(outdir / 'abi-version-info.txt'), 'sha256': build['abiVersionInfoSha256']}}

def parse(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'Duplicate JSON field'); result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: require(False, 'Nonfinite JSON forbidden'))

def validate_retired(retired, binding, *, allow_current=False):
    return _validate_retired(retired, binding, allow_current=allow_current,
        controller_sha='f40ef40f71c9f1206f23fb7052fd69aafd103c0f03a24e6bf3987395dacfd179')

def _validate_retired(retired, binding, *, allow_current=False, controller_sha):
    from cps_compute import native_gpu_controller as controller
    require(sha(Path(controller.__file__).read_bytes()) == controller_sha,
        'Exact reviewed controller models required')
    require(isinstance(retired, dict) and set(retired) == {'version', 'node', 'node_uid', 'boot_id',
        'gpu_uuid', 'driver_generation', 'controller_sha256', 'records'} and type(retired['version']) is int
        and retired['version'] == 1 and retired['controller_sha256'] == controller_sha,
        'Closed original retirement capture required')
    require(all(retired[k] == binding['pool'][k] for k in
        ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')), 'Retirement epoch changed')
    require(isinstance(retired['records'], list) and 1 <= len(retired['records']) <= 32,
        'Actual explicit bounded retirement journals required')
    seen = set() if allow_current else {t['pod_uid'] for t in binding['targets']}
    inodes = set()
    for row in retired['records']:
        require(isinstance(row, dict) and set(row) == {'pod_uid', 'journal_sha256', 'record'}, 'Closed original journal required')
        valid_uuid(row['pod_uid'])
        require(re.fullmatch('sha256:[a-f0-9]{64}', row['journal_sha256'] or '') and row['pod_uid'] not in seen,
            'Distinct pinned original retirement required'); seen.add(row['pod_uid'])
        record = controller.CapRecord.from_dict(row['record'])
        require(record.state == 'retired-inert-cap' and record.intent.pod_uid == row['pod_uid']
            and record.intent.node == binding['pool']['node'] and record.intent.cap_mib in (5120, 10240)
            and record.identity.epoch == controller.DriverEpoch(binding['pool']['node_uid'],
                binding['pool']['boot_id'], binding['pool']['driver_generation'], binding['pool']['gpu_uuid'])
            and record.identity.cgroup_inode not in inodes, 'Original typed finite inert cap required')
        inodes.add(record.identity.cgroup_inode)
    if allow_current:
        require({t['pod_uid'] for t in binding['targets']} <= seen,
                'Both original controlled lifetimes must have actual retired journals')
    return retired

def write(path, raw):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())

def operator_argv(output, binding, out, host_sha):
    """A reviewable recipe only; this function cannot execute its argv."""
    from sys import executable
    cps, cit = binding['targets']
    common = ['--cps-pod-uid', cps['pod_uid'], '--cit-pod-uid', cit['pod_uid'],
              '--observer-pod-uid', binding['observer_uid']]
    epoch = ['--driver-generation', binding['pool']['driver_generation']]
    pins = {name: sha(raw) for name, raw in out.items()}
    commands = {}
    def add(key, name, argv):
        commands[key] = [executable, str(output / name), '--execute', *argv,
                         '--output', str(output / 'measurements' / key)]
    add('kernel-controls', 'run_kernel_controls.py', ['--source-sha256', pins['run_kernel_controls.py'],
        '--preflight-sha256', pins['run_group_acceptance.py'], '--managed-wrapper-sha256', pins['managed/run_managed.py'],
        '--probe-sha256', pins['managed/managed_probe.py']])
    add('cap-peer-aggregate', 'run_group_acceptance.py', [*common, *epoch,
        '--host-observer-source-sha256', host_sha])
    for mode in ('vmm-direct', 'ipc', 'vmm'):
        add('same-parent-' + mode, 'imports/run_same_pod.py', [*common, '--side', 'cit', '--mode', mode])
    for direction in ('cps-to-cit', 'cit-to-cps'):
        add('ipc-' + direction, 'imports-cross-pod/run_cross_pod.py', [*common, '--direction', direction,
            '--endpoint-source-sha256', pins['imports-cross-pod/ipc_endpoint.py'],
            '--host-pid-source-sha256', pins['imports-cross-pod/ipc_host_pid.py'], '--kernel-witness',
            '--wrapper-source-sha256', pins['imports-cross-pod/run_cross_pod.py'],
            *sum(([flag, pins['imports-cross-pod/' + file]] for flag, file in [
                ('--witness-collector-sha256', 'kernel_witness_collector.py'),
                ('--witness-validator-sha256', 'kernel_witness_validator.py'),
                ('--witness-transport-sha256', 'kernel_witness_transport.py')]), [])])
        add('vmm-' + direction, 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py',
            ['--observer-pod-uid', binding['observer_uid'], '--direction', direction,
             *sum(([flag, pins['vmm-cross-parent-sgid-fix/' + file]] for flag, file in [
                ('--wrapper-source-sha256', 'run_vmm_cross_parent.py'), ('--endpoint-source-sha256', 'vmm_endpoint.py'),
                ('--bridge-source-sha256', 'vmm_bridge.py'), ('--witness-collector-sha256', 'kernel_witness_collector.py'),
                ('--witness-validator-sha256', 'kernel_witness_validator.py'),
                ('--witness-transport-sha256', 'kernel_witness_transport.py')]), [])])
    add('mps-cit10', 'mps/run_mps.py', [*common, *epoch, '--mps-hub', 'cit',
        '--wrapper-source-sha256', pins['mps/run_mps.py']])
    return {'state': 'Root-review-and-execution-pending', 'api_calls': False, 'gpu_calls': False,
        'execution_authorized_by_preparer': False, 'commands': commands,
        'required_operator_preparation': ['Root creates owned700 measurements directory',
            'Root validates existing kernel witness collector/validator/transport and VMM bridge exact source pins',
            'Root supplies actual current singleuser-cohort baseline before creator-exit experiment'],
        'creator_exit_base_argv': [executable, str(output / 'vmm-owner-exit/run_owner_exit.py'), '--execute',
            *common, *epoch, '--source-sha256', pins['vmm-owner-exit/run_owner_exit.py'], '--side', 'cit'],
        'creator_exit_required_arguments': ['--singleuser-baseline', '--singleuser-baseline-sha256', '--output'],
        'after_stop_required_inputs': ['actual immutable enrollment/cleanup ConfigMaps for both targets',
            'actual released ledger and complete unpaginated PodList', 'actual complete updated protected retirement capture',
            'run_retirement_witness exact source/preflight/binding/updated-retired pins', 'inspect_stop actual raw input manifest'],
        'restart': 'Root normal Source Start; new actual binding with new UIDs/spec hashes and all prior retired records, then reprepare and run kernel-controls'}

def prepare(binding_path, binding_sha, source_root, output, *, native_binary_path=None,
            native_binary_sha=None, native_build_path=None, native_build_sha=None):
    binding = validate_binding(parse(read_pinned(binding_path, binding_sha, private=True)))
    return _prepare_validated_binding(binding, binding_sha, source_root, output,
        native_binary_path=native_binary_path, native_binary_sha=native_binary_sha,
        native_build_path=native_build_path, native_build_sha=native_build_sha)

def _prepare_validated_binding(binding, binding_sha, source_root, output, *, native_binary_path=None,
            native_binary_sha=None, native_build_path=None, native_build_sha=None, receipt_context=None,
            retirement_validator=None, source_renderer=None):
    measurement_pin = binding['pool_measurement']
    measured = parse(read_pinned(Path(measurement_pin['path']), measurement_pin['sha256'], private=True))
    require(measured.get('kind') == 'selected-device-nvml-memory-mig-observation' and
        all(measured.get(k) == binding['pool'][k] for k in ('node', 'boot_id', 'gpu_uuid'))
        and measured.get('mig_current') == measured.get('mig_pending') == 0
        and measured.get('read_only') is True and measured.get('nvml_header_sha256') ==
        'c9b494b7c8015b6ae7aca62b2ce98e6b13f3277a2bec80de528371e725d54012'
        and str(measured.get('driver_version', '')).startswith('615.')
        and type(measured.get('observed_at_ns')) is int and 0 <= time.time_ns() - measured['observed_at_ns'] <= 3600_000_000_000
        and all(type(measured.get(k)) is int and measured[k] >= 0 for k in ('total_bytes', 'free_bytes', 'used_bytes'))
        and measured['total_bytes'] > 0 and measured['total_bytes'] == measured['free_bytes'] + measured['used_bytes']
        and measured['free_bytes'] == binding['pool']['measured_free_bytes'],
        'Actual fresh selected-device NVML/MIG/free-memory capture required')
    retired_pin = binding['retired_capture']
    retired = (retirement_validator or validate_retired)(
        parse(read_pinned(Path(retired_pin['path']), retired_pin['sha256'], private=True)), binding)
    sources = {name: read_pinned(source_root / name, pin) for name, pin in SOURCE_PINS.items()}
    require(native_binary_path is not None and native_binary_sha and native_build_path is not None and native_build_sha,
            'Actual Ubuntu-compatible ten-cap binary and CPU build receipt pins required')
    native_binary = read_pinned(native_binary_path, native_binary_sha)
    build = parse(read_pinned(native_build_path, native_build_sha, private=True))
    build_inputs = validate_native_build(build, native_binary, native_binary_sha, native_binary_path)
    for key, pin in build_inputs.items():
        raw = read_pinned(Path(pin['path']), pin['sha256'], allow_empty=key in ('stdout', 'stderr'))
        if key == 'abi':
            versions = [tuple(map(int, v.split('.'))) for v in re.findall(r'GLIBC_([0-9.]+)', raw.decode())]
            require(versions and max(versions) <= (2, 39), 'Actual ELF ABI exceeds pinned Ubuntu notebook glibc')
    out = (source_renderer or render_sources)(sources, binding, retired, native_binary=native_binary)
    scope = {'__file__': str(output / 'run_group_acceptance.py'), '__name__': 'preparation_only'}
    exec(compile(out['run_group_acceptance.py'], 'pinned-pure-pod-validator', 'exec'), scope)
    for target in binding['targets']:
        pin = target['pod_capture']; pod = parse(read_pinned(Path(pin['path']), pin['sha256'], private=True))
        actual = scope['pod_snapshot'](pod, {k: target[k] for k in ('namespace', 'name', 'pod_uid')})
        require(actual['intent']['cap_mib'] == target['cap_mib'], 'Actual admitted target cap mismatch')
    parent = output.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
            stat.S_IMODE(parent.st_mode) == 0o700, 'Private owned output parent required')
    output.mkdir(mode=0o700)
    for name, raw in out.items(): write(output / name, raw)
    write(output / 'operator-argv.json', (canonical(operator_argv(output, binding, out, scope['HOST_SHA'])) + '\n').encode())
    receipt = {'state': 'prepared-awaiting-Root-controlled-execution', 'version': 1,
        'api_calls': False, 'gpu_calls': False, 'hardware_qualification': False, 'production_qualified': False,
        'binding_raw_sha256': binding_sha, 'policy_hash': binding['policy_hash'],
        'pool': binding['pool'], 'targets': [{k: v for k, v in t.items() if k != 'pod_capture'}
            for t in binding['targets']], 'actual_source_inputs': [binding['pool_measurement'], binding['retired_capture'],
                *(t['pod_capture'] for t in binding['targets'])],
        'original_sources': SOURCE_PINS, 'rendered_sources': {k: sha(v) for k, v in out.items()},
        'host_source_sha256': scope['HOST_SHA'], 'retired_count': len(retired['records']),
        'native_import_build': {'binary': {'path': str(native_binary_path), 'sha256': native_binary_sha},
            'receipt': {'path': str(native_build_path), 'sha256': native_build_sha},
            'original_c_sha256': NATIVE_C_SHA, 'rendered_c_sha256': build['sourceSha256'],
            'compiler_sha256': NATIVE_COMPILER_SHA, 'header_sha256': CUDA_HEADER_SHA,
            'actual_cpu_build_inputs': build_inputs,
            'runtime_compatibility': 'Root validates new ELF in approved Ubuntu notebook CPU environment'},
        'pending': ['Root actual normal Source Start provenance', 'all controlled hardware measurements',
                    'Root normal Stop/restart, immutable cleanup/released ledger and physical retirement witnesses',
                    'Root hardware review', 'maximum-profile overhead and production capacity qualification']}
    if receipt_context is not None:
        require(not set(receipt_context) & set(receipt), 'Preparation context cannot replace trusted receipt fields')
        receipt.update(receipt_context)
    write(output / 'preparation-receipt.json', (canonical(receipt) + '\n').encode())
    return receipt

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--emit-native-import-source', action='store_true')
    parser.add_argument('--binding', type=Path)
    parser.add_argument('--binding-sha256')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path)
    for field in ('native-import-binary', 'native-import-build-receipt'):
        parser.add_argument('--' + field, type=Path); parser.add_argument('--' + field + '-sha256')
    args = parser.parse_args(argv)
    if args.emit_native_import_source:
        require(args.output is not None, 'Fresh private build-source output required')
        parent = args.output.parent.lstat()
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
                'Private owned build-source parent required')
        args.output.mkdir(mode=0o700)
        for name, raw in native_build_sources().items(): write(args.output / name, raw)
        print(json.dumps({'state': 'native-import-source-prepared-not-built', 'gpu_calls': False, 'api_calls': False,
            'files': {name: sha(raw) for name, raw in native_build_sources().items()}, 'original_c_sha256': NATIVE_C_SHA,
            'header_sha256': CUDA_HEADER_SHA, 'hardware_qualification': False})); return
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'gpu_calls': False, 'api_calls': False,
                          'hardware_qualification': False, 'production_qualified': False}))
        return
    require(args.binding is not None and args.binding_sha256 and args.source_root is not None and
            args.output is not None, 'Actual pinned private binding, sources and fresh output required')
    receipt = prepare(args.binding, args.binding_sha256, args.source_root, args.output,
        native_binary_path=args.native_import_binary, native_binary_sha=args.native_import_binary_sha256,
        native_build_path=args.native_import_build_receipt, native_build_sha=args.native_import_build_receipt_sha256)
    print(json.dumps({'state': receipt['state'], 'api_calls': False, 'gpu_calls': False,
        'hardware_qualification': False, 'output': str(args.output)}))

if __name__ == '__main__':
    main()
