#!/usr/bin/env python3
"""Explicit, default-inert recovery of the one reviewed cleared offline CPS cap.

This is a distinct operator exception. It neither resets a cap nor certifies
normal Stop, finite retirement, hardware qualification or production readiness.
"""
from __future__ import annotations
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import ssl
import sys
from urllib.parse import quote
import urllib.request
from urllib.parse import urlsplit

POD = '8066366f-6e7e-42ea-83b2-86a58e9c3bad'
BINDING = '16d264e00ee6778319a8961f9da510147c3bebc925e674bf95880689cd25'
ATTEMPT = 'cbdbd6be-c340-4e2b-9a6a-71230258a367'
SEAL = '5e8060c6-a3f8-4023-bf1c-bad3870a6dc1'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GENERATION = 'b10498fc-9153-4394-875a-ea7cfb498625'
RECOVERED = 'recovered-cleared-offline-cap'
WRITERS = ('cps-admin', 'cit-admin', 'compute-gateway')
STABLE = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
          'st_size', 'st_mtime_ns', 'st_ctime_ns')


def require(condition, message):
    if not condition: raise ValueError(message)


def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()


def directory(path, uid=0):
    value = Path(path).lstat()
    require(stat.S_ISDIR(value.st_mode) and value.st_uid == uid
            and stat.S_IMODE(value.st_mode) == 0o700, 'Private owned0700 directory required')


def protected(path, uid=0):
    path = Path(path)
    directory(path.parent, uid)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == uid
                and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                and before.st_size <= 2097152, 'Protected owned0600 single-link regular input required')
        raw = b''
        while len(raw) <= 2097152:
            piece = os.read(fd, min(65536, 2097153 - len(raw)))
            if not piece: break
            raw += piece
        after = os.fstat(fd)
        current = path.lstat()
        require(len(raw) <= 2097152 and all(getattr(before, k) == getattr(after, k)
                == getattr(current, k) for k in STABLE), 'Stable protected input required')
        return raw
    finally: os.close(fd)


def preserve(path, raw, uid=0):
    """Exclusive durable private evidence; identical retries never overwrite."""
    path = Path(path)
    directory(path.parent, uid)
    try: fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        require(protected(path, uid) == raw, 'Conflicting operation evidence refused')
        return
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent)
        finally: os.close(parent)
    except BaseException:
        # Retain the exclusively created bytes for explicit inspection on failure.
        raise


def operation_directory(state, operation, agent, uid=0, *, create=False):
    require(agent.canonical_uuid(operation), 'Exact recovery operation UUID required')
    result = Path(state)
    for name in ('operator', 'cleared-offline-recovery', operation):
        result /= name
        if create: result.mkdir(mode=0o700, exist_ok=True)
        directory(result, uid)
    return result


def instant(value):
    require(isinstance(value, str) and value.endswith('Z'), 'UTC recovery review timestamp required')
    result = datetime.fromisoformat(value[:-1] + '+00:00')
    require(result.utcoffset().total_seconds() == 0, 'UTC recovery review required')
    return result


def validate_review(agent, review, plan, *, now=None, fresh=True):
    agent.closed(review, {'version', 'operation_id', 'plan_sha256', 'issued_at', 'expires_at',
        'approved', 'exclusive_operator_custody', 'no_alternate_writer_or_release',
        'normal_stop_passed', 'production_qualified', 'credential'}, 'Closed explicit operator review required')
    require(type(review['version']) is int and review['version'] == 1
        and review['operation_id'] == plan['operation_id']
        and review['plan_sha256'] == agent.canonical_sha256(plan)
        and all(review[k] is True for k in ('approved', 'exclusive_operator_custody',
            'no_alternate_writer_or_release'))
        and review['normal_stop_passed'] is False and review['production_qualified'] is False,
        'Explicit exception review cannot qualify normal Stop or production')
    issued, expires = instant(review['issued_at']), instant(review['expires_at'])
    validate_credential(agent,review['credential'],plan)
    require(0 < (expires - issued).total_seconds() <= 600, 'Review exclusion is at most ten minutes')
    if fresh:
        now = datetime.now(timezone.utc) if now is None else now
        require(issued <= now < expires, 'Fresh operator custody review required')


def validate_credential(agent,value,plan):
    agent.closed(value,{'namespace','service_account','service_account_uid','pod_name','pod_uid',
        'pod_spec_sha256','api_server','audience','token_sha256','ca_sha256'},
        'Closed exact transient service-account credential binding required')
    require(value['namespace'] == plan['enrollment']['metadata']['namespace']
        and value['service_account'] == 'cps-native-cleared-offline-recovery'
        and all(agent.canonical_uuid(value[k]) for k in ('service_account_uid','pod_uid'))
        and agent.token(value['pod_name']) and agent.token(value['audience'])
        and all(isinstance(value[k],str) and len(value[k]) == 71 and value[k].startswith('sha256:')
            for k in ('pod_spec_sha256','token_sha256','ca_sha256')),
        'Exact reviewed scoped SA and bound credential Pod required')
    endpoint=urlsplit(value['api_server'])
    require(endpoint.scheme == 'https' and endpoint.hostname and endpoint.port
        and endpoint.path == '' and not endpoint.query and not endpoint.fragment and not endpoint.username
        and not endpoint.password, 'Explicit pinned TLS Kubernetes endpoint required')


def token_claims(agent,raw,credential,review):
    require(digest(raw) == credential['token_sha256'], 'Protected transient token raw pin mismatch')
    text=raw.decode().strip(); parts=text.split('.')
    require(len(parts) == 3 and all(parts), 'Pod-bound service-account JWT required')
    header,payload=(agent.parse(base64.urlsafe_b64decode(x+'='*((-len(x))%4))) for x in parts[:2])
    require(header.get('alg') == 'RS256' and payload.get('sub') == 'system:serviceaccount:'
        +credential['namespace']+':'+credential['service_account']
        and payload.get('aud') == [credential['audience']]
        and type(payload.get('iat')) is int and type(payload.get('nbf')) is int and type(payload.get('exp')) is int
        and payload['nbf'] <= datetime.now(timezone.utc).timestamp() < payload['exp']
        and payload['iat'] <= datetime.now(timezone.utc).timestamp()
        and payload['exp'] - payload['iat'] <= 3600
        and payload['exp'] >= instant(review['expires_at']).timestamp(),
        'Current bounded exact scoped SA token audience/lifetime required')
    bound=payload.get('kubernetes.io',{})
    require(bound.get('namespace') == credential['namespace']
        and bound.get('serviceaccount',{}).get('name') == credential['service_account']
        and bound.get('serviceaccount',{}).get('uid') == credential['service_account_uid']
        and bound.get('pod',{}).get('name') == credential['pod_name']
        and bound.get('pod',{}).get('uid') == credential['pod_uid'],
        'Actual reviewed Pod-bound service-account token claims required')
    return text


def credential_fence(agent,kube,credential):
    ns=quote(credential['namespace'],safe='')
    sa=kube.call('GET','/api/v1/namespaces/'+ns+'/serviceaccounts/'+credential['service_account'])
    require(isinstance(sa,dict) and sa.get('apiVersion') == 'v1' and sa.get('kind') == 'ServiceAccount'
        and sa.get('metadata',{}).get('namespace') == credential['namespace']
        and sa['metadata'].get('name') == credential['service_account']
        and sa['metadata'].get('uid') == credential['service_account_uid']
        and not sa['metadata'].get('deletionTimestamp'), 'Actual transient SA identity must remain current')
    pod=kube.call('GET','/api/v1/namespaces/'+ns+'/pods/'+quote(credential['pod_name'],safe=''))
    require(isinstance(pod,dict) and pod.get('apiVersion') == 'v1' and pod.get('kind') == 'Pod'
        and pod.get('metadata',{}).get('namespace') == credential['namespace']
        and pod['metadata'].get('name') == credential['pod_name'] and pod['metadata'].get('uid') == credential['pod_uid']
        and not pod['metadata'].get('deletionTimestamp') and pod.get('spec',{}).get('serviceAccountName') == credential['service_account']
        and agent.canonical_sha256(pod['spec']) == credential['pod_spec_sha256'],
        'Actual bound credential Pod UID/fullspec must remain current')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        raise ValueError('Pinned Kubernetes endpoint redirects refused')


def authority_api(agent,qualification,directory_path,credential,review):
    token_raw=protected(Path(directory_path)/'token'); ca_raw=protected(Path(directory_path)/'ca.crt')
    require(digest(ca_raw) == credential['ca_sha256'], 'Protected Kubernetes TLS CA raw pin mismatch')
    token=token_claims(agent,token_raw,credential,review)
    # Construct the existing scoped adapter from verified bytes, avoiding its
    # ambient endpoint and projected/default credential constructor entirely.
    api_type=agent.api_class(qualification)
    api=api_type.__new__(api_type)
    api.base=credential['api_server']; api.token=token
    api.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cadata=ca_raw.decode())))
    observed=api.call('POST','/apis/authentication.k8s.io/v1/selfsubjectreviews',
        {'apiVersion':'authentication.k8s.io/v1','kind':'SelfSubjectReview'})
    user=observed.get('status',{}).get('userInfo',{})
    require(observed.get('apiVersion') == 'authentication.k8s.io/v1' and observed.get('kind') == 'SelfSubjectReview'
        and user.get('username') == 'system:serviceaccount:'+credential['namespace']+':'+credential['service_account']
        and set(user.get('groups',[])) == {'system:authenticated','system:serviceaccounts',
            'system:serviceaccounts:'+credential['namespace']},
        'Actual Kubernetes authentication must verify the scoped SA; decoded JWT alone is insufficient')
    credential_fence(agent,api,credential)
    return api


def validate_plan(agent, models, plan, config=None):
    agent.closed(plan, {'version', 'protocol', 'operation_id', 'node_config_sha256', 'original',
        'original_raw_sha256', 'inventory', 'enrollment', 'ledger', 'journal_sha256s', 'physical_pods', 'writers'},
        'Closed captured recovery plan required')
    require(type(plan['version']) is int and plan['version'] == 1
        and plan['protocol'] == 'cleared-offline-recovery-plan/v1'
        and agent.canonical_uuid(plan['operation_id']), 'Versioned distinct recovery plan required')
    original = models.CapRecord.from_dict(plan['original'])
    i = original.identity
    require(original.intent.pod_uid == POD and original.intent.namespace == 'jupyterhub'
        and original.intent.node == 'k3s-wk-gpu2' and original.intent.cap_mib == 5120
        and i.cgroup_inode == 1390814 and i.cgroup_device == 29
        and i.boot_id == BOOT and i.driver_generation == GENERATION and original.seal_id == SEAL
        and original.state == 'cleanup-prepared' and original.readback == original.limit
        and original.retirement is None and original.recovery is None,
        'Only the captured sealed CPS cleanup-prepared finite transaction is eligible')
    raw = (agent.canonical_json(original.to_dict()) + '\n').encode()
    require(plan['original_raw_sha256'] == digest(raw), 'Exact failed journal raw bytes required')
    if config is not None:
        require(plan['node_config_sha256'] == agent.canonical_sha256(config), 'Actual node configuration changed')
        envelope = agent.validate_enrollment(plan['enrollment'], config, models)
    else:
        cm = plan['enrollment']; body = agent.parse(cm['data']['enrollment.json'])
        require(cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
            and cm.get('immutable') is True and agent.canonical_uuid(cm['metadata'].get('uid')),
            'Original immutable enrollment required')
        envelope = {'authority_namespace':cm['metadata']['namespace'], 'configmap_name':cm['metadata']['name'],
            'configmap_uid':cm['metadata']['uid'], 'enrollment':body}
    e = envelope['enrollment']
    require(e['binding_id'] == BINDING and e['attempt'] == ATTEMPT and e['source'] == 'cps'
        and e['intent'] == original.intent.to_dict(), 'Original immutable binding/attempt/intent required')
    ids = plan['journal_sha256s']
    require(isinstance(ids, dict) and len(ids) == 17 and POD in ids
        and all(agent.canonical_uuid(k) and isinstance(v, str) and len(v) == 71
            and v.startswith('sha256:') for k, v in ids.items())
        and ids[POD] == agent.canonical_sha256(original.to_dict()),
        'All seventeen exact original protected journal pins required')
    physical = plan['physical_pods']
    require(isinstance(physical,list) and len(physical) == 12 and len(set(physical)) == 12
        and POD in physical and set(physical).issubset(ids), 'Exact twelve current-epoch physical lifetimes required')
    require(len(plan['inventory'].get('entries', [])) == 12, 'Complete original twelve-entry map required')
    ledger = agent.abort_ledger(plan['ledger'], envelope['authority_namespace'])
    rows = ledger['allocations']
    require(len(rows) == 23 and BINDING in rows and rows[BINDING]['state'] == 'releasing'
        and all(v['state'] == 'released' for k,v in rows.items() if k != BINDING)
        and rows[BINDING]['intent'] == original.intent.to_dict() and rows[BINDING]['attempt'] == ATTEMPT
        and rows[BINDING]['cap_mib'] == 5120 and all(rows[BINDING].get(k) == v for k,v in e.items()),
        'Captured ledger must retain the single exact original releasing enrollment')
    require(set(plan['writers']) == set(WRITERS), 'All three writer Deployment captures required')
    for name in WRITERS: writer_zero(agent, plan['writers'][name], name)
    return original, envelope


def make_proof(agent, models, plan, review):
    original, envelope = validate_plan(agent, models, plan)
    return models.validate_cleared_offline_inventory(plan['inventory'], original,
        binding_id=BINDING, attempt=ATTEMPT, enrollment_uid=envelope['configmap_uid'],
        enrollment_sha256=agent.canonical_sha256(envelope['enrollment']),
        journal_raw=(agent.canonical_json(original.to_dict()) + '\n').encode(),
        operation_id=plan['operation_id'], plan_sha256=agent.canonical_sha256(plan),
        review_sha256=agent.canonical_sha256(review))


def plan_from_captures(agent, models, config, host, inventory, enrollment, ledger, writers, operation):
    """Offline assembly only; every input is a Root capture, never passed evidence."""
    require(host.get('bootId') == BOOT and host.get('driverGeneration') == GENERATION
        and host.get('healthPassed') is True, 'Captured original healthy host epoch required')
    section = host['directories']['journal']
    require(section['ownerUid'] == 0 and section['mode'] == 0o700, 'Captured protected journal directory required')
    entries = section['records']
    require(isinstance(entries,dict) and len(entries) == 17, 'All seventeen captured journals required')
    records, physical = {}, []
    for filename, entry in entries.items():
        require(entry['uid'] == 0 and entry['mode'] == 0o600 and entry['nlink'] == 1,
            'Captured private root0600 single-link journal required')
        record = models.CapRecord.from_dict(entry['value'])
        require(filename == record.intent.pod_uid + '.json', 'Captured original journal filename/UID required')
        raw = (agent.canonical_json(record.to_dict())+'\n').encode()
        require(entry['rawSha256'] in (digest(raw),digest(raw)[7:]), 'Captured exact writer raw journal checksum required')
        records[record.intent.pod_uid] = record
        if record.identity.boot_id == BOOT and record.identity.driver_generation == GENERATION:
            physical.append(record.intent.pod_uid)
    original = records[POD]
    plan = {'version':1,'protocol':'cleared-offline-recovery-plan/v1','operation_id':operation,
        'node_config_sha256':agent.canonical_sha256(config),'original':original.to_dict(),
        'original_raw_sha256':digest((agent.canonical_json(original.to_dict())+'\n').encode()),
        'inventory':inventory,'enrollment':enrollment,'ledger':ledger,
        'journal_sha256s':{uid:agent.canonical_sha256(r.to_dict()) for uid,r in records.items()},
        'physical_pods':sorted(physical),'writers':writers}
    validate_plan(agent,models,plan,config)
    return plan


def writer_zero(agent, value, name):
    require(isinstance(value, dict) and value.get('apiVersion') == 'apps/v1'
        and value.get('kind') == 'Deployment', 'Actual writer Deployment required')
    meta, spec, status = value.get('metadata', {}), value.get('spec', {}), value.get('status', {})
    require(meta.get('namespace') == 'cps-compute' and meta.get('name') == name
        and agent.canonical_uuid(meta.get('uid')) and not meta.get('deletionTimestamp')
        and type(meta.get('generation')) is int and meta['generation'] > 0
        and spec.get('replicas') == 0 and type(spec.get('replicas')) is int
        and type(status.get('observedGeneration')) is int
        and status['observedGeneration'] >= meta['generation']
        and all(type(status.get(k, 0)) is int and status.get(k, 0) == 0
            for k in ('replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas', 'unavailableReplicas')),
        'Current-generation zero writer Deployment required')
    selector = spec.get('selector', {})
    require(set(selector) == {'matchLabels'} and isinstance(selector['matchLabels'], dict)
        and selector['matchLabels'] and all(isinstance(k,str) and isinstance(v,str)
            for k,v in selector['matchLabels'].items()), 'Exact simple writer Pod selector required')


def control_plane(agent, kube, plan, envelope, config, models):
    for name in WRITERS:
        expected = plan['writers'][name]
        actual = kube.call('GET', '/apis/apps/v1/namespaces/cps-compute/deployments/' + name)
        writer_zero(agent, actual, name)
        require(all(actual['metadata'][k] == expected['metadata'][k] for k in ('uid','generation'))
            and actual['spec'] == expected['spec'], 'Writer identity/spec changed during exclusion')
        selector = ','.join(k + '=' + v for k,v in sorted(expected['spec']['selector']['matchLabels'].items()))
        pods = kube.call('GET', '/api/v1/namespaces/cps-compute/pods?labelSelector=' + quote(selector,safe=''))
        require(isinstance(pods,dict) and pods.get('apiVersion') == 'v1' and pods.get('kind') == 'PodList'
            and isinstance(pods.get('metadata'),dict) and not pods['metadata'].get('continue')
            and agent.token(pods['metadata'].get('resourceVersion'))
            and type(pods['metadata'].get('remainingItemCount',0)) is int
            and pods['metadata'].get('remainingItemCount',0) == 0 and pods.get('items') == [],
            'Complete actual writer Pod absence required')
    cm = kube.configmap(envelope['authority_namespace'], 'cps-native-gpu-allocations')
    expected = plan['ledger']
    require(agent.abort_ledger(cm,envelope['authority_namespace']) == agent.abort_ledger(expected,envelope['authority_namespace'])
        and all(cm['metadata'].get(k) == expected['metadata'][k] for k in ('uid','resourceVersion')),
        'Exact ledger UID/RV/full preimage must remain unchanged')
    actual = kube.configmap(envelope['authority_namespace'], envelope['configmap_name'])
    expected = plan['enrollment']
    require(actual is not None and actual.get('immutable') is True
        and actual.get('apiVersion') == 'v1' and actual.get('kind') == 'ConfigMap'
        and actual.get('metadata',{}).get('uid') == envelope['configmap_uid']
        and not actual['metadata'].get('deletionTimestamp') and not actual['metadata'].get('ownerReferences')
        and actual.get('data') == expected['data'] and not actual.get('binaryData'),
        'Exact immutable original enrollment must remain unchanged')
    require(agent.validate_enrollment(actual,config,models) == envelope,
        'Actual full immutable enrollment metadata/body changed')


def audit_object(agent, envelope, record):
    proof = record.recovery
    require(record.state == RECOVERED and proof is not None
        and record.intent.to_dict() == envelope['enrollment']['intent']
        and proof.binding_id == envelope['enrollment']['binding_id'] and proof.attempt == envelope['enrollment']['attempt']
        and proof.enrollment_uid == envelope['configmap_uid']
        and proof.enrollment_sha256 == agent.canonical_sha256(envelope['enrollment']),
        'Exact recovered terminal and immutable enrollment required')
    body = {'version':1, 'binding_id':proof.binding_id, 'attempt':proof.attempt,
        'proof':proof.to_dict(), 'enrollment_uid':proof.enrollment_uid,
        'enrollment_sha256':proof.enrollment_sha256, 'journal_sha256':agent.canonical_sha256(record.to_dict())}
    return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
        'metadata':{'namespace':envelope['authority_namespace'],
            'name':'cps-native-recovery-' + proof.binding_id[:40], 'labels':{agent.LABEL:proof.binding_id}},
        'data':{'recovery.json':agent.canonical_json(body)}}


def recovery_extension(agent, envelope, record, audit):
    expected = audit_object(agent,envelope,record)
    agent.validate_cleanup(audit,expected)
    require(not audit['metadata'].get('ownerReferences'), 'Recovery audit must have independent immutable custody')
    return {'proof':record.recovery.to_dict(), 'enrollment_uid':envelope['configmap_uid'],
        'enrollment_sha256':agent.canonical_sha256(envelope['enrollment']),
        'journal_sha256':agent.canonical_sha256(record.to_dict()), 'audit_uid':audit['metadata']['uid'],
        'audit_sha256':agent.canonical_sha256(agent.parse(expected['data']['recovery.json']))}


def published_provenance(agent, models, state, envelope, record, audit, *, uid=0):
    """Historical verification uses durable evidence, never a future physical map."""
    recovery_extension(agent,envelope,record,audit)
    proof = record.recovery
    root = operation_directory(state,proof.operation_id,agent,uid)
    plan, review = (agent.parse(protected(root / name,uid)) for name in ('plan.json','review.json'))
    validate_plan(agent,models,plan)
    validate_review(agent,review,plan,fresh=False)
    require(make_proof(agent,models,plan,review) == proof, 'Protected approved recovery provenance changed')
    journal = models.PrivateJournal(Path(state) / 'journal')
    require(journal.read_recovery_original(proof) == (agent.canonical_json(proof.original.to_dict())+'\n').encode()
        and journal.read(record.intent.pod_uid) == record, 'Exact archived original and recovered terminal required')


def lock(path, uid=0):
    directory(Path(path).parent,uid)
    fd = os.open(path,os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        lock_identity(path,fd,uid)
        fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd); raise


def lock_identity(path,fd,uid=0):
    value,current = os.fstat(fd),Path(path).lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_uid == uid and value.st_nlink == 1
        and stat.S_IMODE(value.st_mode) == 0o600 and (value.st_dev,value.st_ino) == (current.st_dev,current.st_ino),
        'Unchanged private lock fd/path identity required')
    return value.st_dev,value.st_ino


def journal_lock_identity(path,uid=0):
    """Probe the SDK-held lock without reacquiring it on another descriptor."""
    fd = os.open(path,os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        identity = lock_identity(path,fd,uid)
        try: fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return identity
        raise ValueError('SDK journal writer lock must already be held')
    finally: os.close(fd)


def backend_class(adapter):
    class RecoveryBackend(adapter.QualificationNodeBackend):
        def configure_recovery(self,agent,kube,journal,store,plan,review,proof,config):
            self.agent,self.kube,self.journal,self.store = agent,kube,journal,store
            self.plan,self.review,self.proof,self.config = plan,review,proof,config
            self.original,self.envelope = validate_plan(agent,self.m,plan,config)
            self.held = None
            return self

        def pid_absent(self,identity):
            try: raw = (self.proc / str(identity.host_pid) / 'stat').read_text()
            except FileNotFoundError: return
            require(len(raw) <= 16384 and ')' in raw, 'Complete original PID lifetime observation required')
            tail = raw.rsplit(')',1)[1].split()
            require(len(tail) >= 20 and tail[19].isdigit(), 'Typed actual PID start ticks required')
            require(int(tail[19]) != identity.pid_start_ticks, 'Original host PID lifetime must remain absent')

        def locks_unchanged(self):
            require(self.held is not None, 'All recovery lock domains must remain held')
            journal_id,fds,identities = self.held
            require(journal_lock_identity(self.state / 'journal/.writer.lock',self.uid) == journal_id,
                'Original journal lock inode changed')
            for path,fd in fds:
                require(lock_identity(path,fd,self.uid) == identities[str(path)], 'Recovery lock inode changed')
                fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)

        def fresh(self,proof):
            self.locks_unchanged()
            validate_review(self.agent,self.review,self.plan)
            credential_fence(self.agent,self.kube,self.review['credential'])
            require(proof == self.proof, 'Only the exact approved recovery operation may execute')
            control_plane(self.agent,self.kube,self.plan,self.envelope,self.config,self.m)
            records = self.journal.records()
            require({r.intent.pod_uid for r in records} == set(self.plan['journal_sha256s']),
                'All seventeen original journal identities must remain present')
            for record in records:
                if record.intent.pod_uid == POD:
                    require(record == self.original or (record.state == RECOVERED and record.recovery == proof
                        and record.intent == self.original.intent and record.identity == self.original.identity
                        and record.seal_id == self.original.seal_id and record.readback == self.original.readback),
                        'Original/recovered same-operation journal required')
                else:
                    require(self.agent.canonical_sha256(record.to_dict()) == self.plan['journal_sha256s'][record.intent.pod_uid],
                        'Original peer journal changed')
                if record.intent.pod_uid not in self.plan['physical_pods']:
                    require(record.state in ('cleaned','retired-inert-cap'), 'Historical journals must remain terminal')
                    continue
                intent,group = self._current(record.identity,absent=True)
                require(group is None and self.get_pod(intent) is None, 'All original Pod/cgroup paths must remain absent')
                self._retired_mount(record.identity)
                self.pid_absent(record.identity)
                require(self.read_gate(record.identity) is None, 'Every original native gate must remain absent')
            physical = [r for r in records if r.intent.pod_uid in self.plan['physical_pods']]
            require(len({r.identity.cgroup_inode for r in physical}) == 12
                and {r.identity.cgroup_inode for r in physical} == {row['inode'] for row in self.plan['inventory']['entries']},
                'Complete physical map must match all original tracked journal identities')
            require(not self.gpu_clients(proof.identity.gpu_uuid), 'No GPU client may remain during operator exception')
            inventory = self._inventory(proof.identity)
            require(inventory == self.plan['inventory'], 'Complete original physical inventory changed')
            for record in physical:
                if record.intent.pod_uid == POD: continue
                require(record.state == 'retired-inert-cap' and record.retirement is not None,
                    'Every other physical lifetime must retain its original finite retirement proof')
                peer = self.m.validate_retired_inventory(inventory,record.identity,record.limit)
                require(peer.entry == record.retirement.entry and peer.gpu_id == record.retirement.gpu_id,
                    'Every physical peer must retain its exact original finite cap entry')
            result = self.m.validate_cleared_offline_inventory(inventory,self.original,
                binding_id=BINDING,attempt=ATTEMPT,enrollment_uid=proof.enrollment_uid,
                enrollment_sha256=proof.enrollment_sha256,
                journal_raw=(self.agent.canonical_json(self.original.to_dict())+'\n').encode(),
                operation_id=proof.operation_id,plan_sha256=proof.plan_sha256,review_sha256=proof.review_sha256)
            require(result == proof, 'Fresh complete physical proof must equal approved exception')
            # Recheck every original lifetime and authority after the inventory read.
            for record in physical:
                intent,group = self._current(record.identity,absent=True)
                require(group is None and self.get_pod(intent) is None, 'Original Pod/cgroup absence changed across read')
                self._retired_mount(record.identity); self.pid_absent(record.identity)
                require(self.read_gate(record.identity) is None, 'Original gate returned during recovery')
            control_plane(self.agent,self.kube,self.plan,self.envelope,self.config,self.m)
            self.locks_unchanged()
            return result

        @contextmanager
        def recovery_fence(self,proof):
            require(self.held is None, 'Nested recovery fence refused')
            journal_id = journal_lock_identity(self.state / 'journal/.writer.lock',self.uid)
            fds = []
            try:
                for path in (self.state / 'authority/.driver-loader.lock', self.state / 'operator/.teardown.lock'):
                    fds.append((path,lock(path,self.uid)))
                self.held = (journal_id,fds,{str(path):lock_identity(path,fd,self.uid) for path,fd in fds})
                self.fresh(proof)
                yield
                self.fresh(proof)
                record = self.journal.read(POD)
                require(record.state == RECOVERED and record.recovery == proof, 'Exact distinct terminal required before publication')
                # All three locks remain held throughout immutable API publication.
                audit = self.agent.publish_cleanup(self.kube,audit_object(self.agent,self.envelope,record))
                self.fresh(proof)
                receipt = self.agent.cleanup_object(self.envelope,record,audit=audit)
                cleanup = self.agent.publish_cleanup(self.kube,receipt)
                self.fresh(proof)
                self.store.mark_cleanup_published(POD,self.envelope,cleanup,record,audit=audit)
            finally:
                self.held = None
                for _,fd in reversed(fds): os.close(fd)

        def cleared_offline_recovery(self,identity,original,proof):
            require(identity == self.original.identity and original == self.original, 'Exact failed original transaction required')
            return self.fresh(proof)
    return RecoveryBackend


def execute(agent,config,bundle,state,kube,driver,plan_raw,review_raw,*,crictl,cri_socket):
    adapter,qualification,modules = bundle
    models = modules['models']
    plan,review = agent.parse(plan_raw),agent.parse(review_raw)
    original,envelope = validate_plan(agent,models,plan,config)
    validate_review(agent,review,plan)
    proof = make_proof(agent,models,plan,review)
    journal = models.PrivateJournal(Path(state) / 'journal')
    current = journal.read(POD)
    if current == original:
        require(protected(journal.path(POD)) == (agent.canonical_json(original.to_dict())+'\n').encode(),
            'Actual failed raw journal must match exact approved archive preimage')
    else:
        require(current is not None and current.state == RECOVERED and current.recovery == proof,
            'Only an identical partial recovery operation may resume')
        journal.read_recovery_original(proof)
    store = agent.EnrollmentStore(state,models)
    require(store.backend.private_read(Path(state)/'enrollments'/ (POD+'.json')) == envelope,
        'Original protected immutable enrollment mirror required')
    require(store.backend.private_read(Path(state)/'intents'/ (POD+'.json')) == original.intent.to_dict(),
        'Original protected intent mirror required')
    root = operation_directory(state,proof.operation_id,agent,create=True)
    preserve(root/'plan.json',plan_raw); preserve(root/'review.json',review_raw)
    records = journal.records()
    backend = backend_class(adapter)(models,modules['manual'],intents=[r.intent for r in records],driver=driver,
        get_pod=kube.pod,get_node=kube.node,get_cri=qualification.cri_reader(crictl,cri_socket),delete_pod=kube.delete,
        gpu_clients=qualification.gpu_clients,
        health=lambda:qualification.health(driver,modules['health'],authority_directory=str(Path(state)/'authority')),
        state_root=state).configure_recovery(agent,kube,journal,store,plan,review,proof,config)
    record = models.NativeCapController(backend,journal,enabled=True).recover_cleared_offline(
        original.intent,proof,operator_approved=True)
    audit = kube.configmap(envelope['authority_namespace'],'cps-native-recovery-'+BINDING[:40])
    cleanup = kube.configmap(envelope['authority_namespace'],'cps-native-cleanup-'+BINDING[:40])
    require(store.cleanup_published(POD,envelope,record,cleanup,audit=audit), 'Durable distinct recovery completion required')
    return {'state':'operator-cleared-offline-recovery-published','operation_id':proof.operation_id,
        'pod_uid':POD,'normal_stop_passed':False,'production_qualified':False,'ledger_release_performed':False}


def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    for key in ('plan','review','config','node-agent','bundle','state-root','service-account'):
        parser.add_argument('--'+key,type=Path)
    for key in ('self-sha256','node-agent-sha256','plan-sha256','review-sha256'):
        parser.add_argument('--'+key)
    parser.add_argument('--crictl',type=Path,default=Path('/host/var/lib/rancher/k3s/data/current/bin/crictl'))
    parser.add_argument('--cri-socket',default='unix:///host/run/k3s/containerd/containerd.sock')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,
            'normal_stop_passed':False,'production_qualified':False})); return
    require(os.geteuid() == 0 and all(getattr(args,key) is not None for key in
        ('plan','review','config','node_agent','bundle','state_root','service_account','self_sha256',
            'node_agent_sha256','plan_sha256','review_sha256')), 'Explicit Root protected inputs and pins required')
    require(digest(protected(Path(__file__))) == 'sha256:'+args.self_sha256, 'Operator helper raw pin mismatch')
    agent_raw = protected(args.node_agent)
    require(digest(agent_raw) == 'sha256:'+args.node_agent_sha256,'Node agent raw pin mismatch')
    spec = importlib.util.spec_from_loader('_cleared_offline_node_agent',loader=None)
    agent = importlib.util.module_from_spec(spec); agent.__file__ = str(args.node_agent)
    sys.modules[spec.name] = agent; exec(compile(agent_raw,str(args.node_agent),'exec'),agent.__dict__)
    plan_raw,review_raw = protected(args.plan),protected(args.review)
    require(digest(plan_raw) == 'sha256:'+args.plan_sha256 and digest(review_raw) == 'sha256:'+args.review_sha256,
        'Actual protected plan/review raw pins required')
    config = agent.read_config(args.config); require(config['enabled'],'Root node authority configuration must be enabled')
    bundle = agent.load_bundle(args.bundle)
    plan,review = agent.parse(plan_raw),agent.parse(review_raw)
    validate_plan(agent,bundle[2]['models'],plan,config); validate_review(agent,review,plan)
    make_proof(agent,bundle[2]['models'],plan,review)
    kube = authority_api(agent,bundle[1],args.service_account,review['credential'],review)
    driver = bundle[2]['manual'].Nvml()
    try:
        result = execute(agent,config,bundle,args.state_root,kube,driver,plan_raw,review_raw,
            crictl=args.crictl,cri_socket=args.cri_socket)
        print(json.dumps(result,sort_keys=True))
    finally: driver.close()


def main(argv=None):
    try: return _main(argv)
    except Exception as error:
        # No token, raw capture, role, response body or private SQL goes to logs.
        print(json.dumps({'state':'failed-no-completion-claim','error_type':type(error).__name__,
            'normal_stop_passed':False,'production_qualified':False}),file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__': main()
