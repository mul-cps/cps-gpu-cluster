#!/usr/bin/env python3
"""Read-only first guard matrix collector; no cap, Pod, module or file mutation live."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
NAMESPACE = 'cps-r615-uvm-guard-20261008'
PRIVATE = Path('/home/bjoern/.local/state/cps-gpu2-r615-canary-20261008/uvm-guard-fixture')
EXPECTED = {'uvm-guard-main': '567b84be-5bd3-48bf-9ee1-0633a6676acd',
            'uvm-guard-peer': '1f02616c-6d0e-4cfd-ae34-a8bb31ee5f39'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read(*arguments):
    return subprocess.check_output(['kubectl', '-n', NAMESPACE, *arguments], text=True)


def coverage(start, finish, ticks):
    before = [tick for tick in ticks if tick['parent']['observed_ns'] <= start]
    after = [tick for tick in ticks if tick['parent']['observed_ns'] >= finish]
    assert before and after, 'Phase must have peer ticks on both boundaries'
    left, right = before[-1], after[0]
    window = [tick for tick in ticks if left['parent']['observed_ns'] <= tick['parent']['observed_ns']
              <= right['parent']['observed_ns']]
    gaps = [b['parent']['observed_ns'] - a['parent']['observed_ns'] for a, b in zip(window, window[1:])]
    assert window and gaps and max(gaps) <= 1_000_000_000
    assert all(tick['tick']['cuda_result'] == 0 for tick in window)
    assert start - left['parent']['observed_ns'] <= 1_000_000_000
    assert right['parent']['observed_ns'] - finish <= 1_000_000_000
    return {'startedNs': start, 'finishedNs': finish, 'coveringPeerTicks': len(window),
            'firstPeerNs': left['parent']['observed_ns'], 'lastPeerNs': right['parent']['observed_ns'],
            'maxGapNs': max(gaps), 'allCudaResultsZero': True}


if __name__ == '__main__':
    destination = HERE / 'uvm-first-matrix'
    destination.mkdir(exist_ok=False)
    pods, logs, caps, events = {}, {}, {}, {}
    configmaps = {}
    for name, expected_uid in EXPECTED.items():
        pod = json.loads(read('get', 'pod', name, '-o', 'json'))
        assert pod['metadata']['uid'] == expected_uid and pod['spec']['nodeName'] == 'k3s-wk-gpu2'
        assert pod['spec']['automountServiceAccountToken'] is False
        assert all('valueFrom' not in env or 'secretKeyRef' not in env['valueFrom']
                   for container in pod['spec']['containers'] for env in container.get('env', []))
        cap = json.loads((PRIVATE / (expected_uid + '-manual-cap-and-release.json')).read_text())
        assert cap['pod_uid'] == expected_uid and cap['cap_bytes'] == 512 * 1048576
        assert cap['spec_sha256'] == hashlib.sha256(canonical(pod['spec'])).hexdigest()
        assert cap['readback']['soft'] == cap['readback']['hard'] == cap['cap_bytes']
        raw = read('logs', name, '-c', 'main')
        records = [json.loads(line) for line in raw.splitlines()]
        (destination / (name + '.jsonl')).write_text(raw)
        logs[name] = records
        pods[name] = pod
        caps[name] = cap
        events[name] = json.loads(read('get', 'events', '--field-selector',
                                     'involvedObject.uid=' + expected_uid, '-o', 'json'))
        for volume in pod['spec']['volumes']:
            if 'configMap' in volume:
                cm_name = volume['configMap']['name']
                assert cm_name.startswith('r615-uvm-guard-')
                cm = json.loads(read('get', 'configmap', cm_name, '-o', 'json'))
                assert cm.get('immutable') is True
                actual = hashlib.sha256(canonical(cm['data'])).hexdigest()
                assert actual == cm['metadata']['annotations']['source.data.sha256']
                assert actual == pod['metadata']['annotations']['source.data.sha256']
                configmaps[cm_name] = cm
    physical = PRIVATE / 'physical-memory.jsonl'
    raw_physical = physical.read_text()
    physical_records = [json.loads(line) for line in raw_physical.splitlines()]
    assert all(set(record) == {'observed_ns', 'gpu_rows'} for record in physical_records)
    (destination / 'physical-memory.jsonl').write_text(raw_physical)
    for filename, value in [('pods.json', pods), ('caps.json', caps), ('events.json', events),
                            ('configmaps.json', configmaps)]:
        (destination / filename).write_text(json.dumps(value, indent=2) + '\n')
    main, peer = logs['uvm-guard-main'], logs['uvm-guard-peer']
    assert len(main) == 5, 'Preserve the exact original five matrix records'
    ticks = [record for record in peer if record.get('kind') == 'independent-guard-peer-heartbeat']
    assert peer[-1]['status'] == 'peer-completed'
    assert all(tick['tick']['cuda_result'] == 0 for tick in ticks)
    phases = [record for record in main if 'started_ns' in record]
    phase_coverage = [{'mode': record['mode'], 'launch': record['launch'], 'status': record['status'],
                       **coverage(record['started_ns'], record['finished_ns'], ticks)} for record in phases]
    assert physical_records[0]['observed_ns'] <= min(record['started_ns'] for record in phases)
    assert physical_records[-1]['observed_ns'] >= max(record['finished_ns'] for record in phases)
    physical_values = {}
    for record in physical_records:
        for row in record['gpu_rows']:
            gpu, memory, utilization = [item.strip() for item in row.split(',')]
            values = physical_values.setdefault(gpu, {'minMemoryMiB': int(memory), 'maxMemoryMiB': int(memory),
                                                      'maxUtilizationPercent': int(utilization)})
            values['minMemoryMiB'] = min(values['minMemoryMiB'], int(memory))
            values['maxMemoryMiB'] = max(values['maxMemoryMiB'], int(memory))
            values['maxUtilizationPercent'] = max(values['maxUtilizationPercent'], int(utilization))
    report = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'First trusted global UVM-guard matrix; exact original fixtures',
              'mainLogRecords': len(main), 'peerLogRecords': len(peer), 'peerHeartbeatTicks': len(ticks),
              'peerAllTicksCudaZero': True, 'peerDurationNs': ticks[-1]['parent']['observed_ns'] - ticks[0]['parent']['observed_ns'],
              'phaseCoverage': phase_coverage, 'physicalSamples': len(physical_records),
              'physicalMemory': physical_values,
              'rawSequencePassed': main[0]['raw_sequence_passed'],
              'managedFreshAndForkDenied': all(record['managed_allocation_denied'] for record in main[:3]),
              'torch512Status': main[3]['status'], 'torch512ErrorType': main[3]['error_type'],
              'matrixExitCodes': main[4]['results'], 'torchQualified': False, 'tenantIsolationQualified': False,
              'artifactSHA256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(destination.iterdir())}}
    (destination / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('peerHeartbeatTicks', 'peerAllTicksCudaZero',
                     'rawSequencePassed', 'managedFreshAndForkDenied', 'torch512Status', 'torchQualified')}))
