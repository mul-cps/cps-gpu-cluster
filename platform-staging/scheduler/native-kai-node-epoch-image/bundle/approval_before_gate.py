"""Root-reviewed never-gated recovery for the controlled CPS group-b 5 GiB.

This pure publisher preserves all prior custody. It creates neither a native
journal nor a cleanup receipt and never releases member reservations. Actual
hardware observation and the continuously held writer fence belong to Root.
The legacy empty-journal qualification publisher remains unchanged.
"""
import base64
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import os
import select
import tempfile

import abort_before_gate as old
import native_approval_revision as approval

require,closed = old.require,old.closed
ENROLLMENT_KEYS = old.ENROLLMENT_KEYS | {'approval_ref'}
PROOF_BOOLEANS = ('journal_protected','target_journal_absent','gate_receipts_absent',
    'native_writers_quiesced','exclusive_lock','driver_healthy','approval_current','completed_history_verified')


def validate_proof(value,evidence):
    closed(value,('node_epoch','journal_device','journal_inode',*PROOF_BOOLEANS,*old.ZERO_PROOF,
        'approval_ref','retired_history_sha256','physical_rows_sha256'),'Closed approved live fence proof required')
    old.epoch(value['node_epoch'])
    for key in PROOF_BOOLEANS:require(value[key] is True,'Unproven '+key)
    for key in old.ZERO_PROOF:require(type(value[key]) is int and value[key]==0,'Nonzero or unproven '+key)
    for key in ('journal_device','journal_inode'):
        require(type(value[key]) is int and value[key]>0,'Original protected journal identity required')
    require(approval.reference(value['approval_ref'])==evidence['approval_ref'],'Current node approval reference changed')
    require(value['retired_history_sha256']==old.sha256(evidence['retired_journals'])
        and value['physical_rows_sha256']==old.sha256(evidence['physical_rows']),
        'Complete protected history/physical inventory changed')


def validate_history(evidence,models):
    journals,rows=evidence['retired_journals'],evidence['physical_rows']
    require(isinstance(journals,list) and 1<=len(journals)<=256
        and isinstance(rows,list) and 1<=len(rows)<=4096,'Complete bounded retained history and inventory required')
    entries={}
    for row in rows:
        closed(row,tuple(models.RetiredCapEntry.__dataclass_fields__),'Closed full physical row required')
        entry=models.RetiredCapEntry(**row)
        require(entry.inode not in entries,'Duplicate physical inode')
        entries[entry.inode]=entry
    uids=set();inodes=set()
    for item in journals:
        closed(item,('pod_uid','raw_base64','raw_sha256'),'Original protected raw journal pin required')
        require(old.valid_uuid(item['pod_uid']) and item['pod_uid'] not in uids
            and isinstance(item['raw_base64'],str) and len(item['raw_base64'])<=1048576,
            'Distinct bounded original journal identity required')
        try:raw=base64.b64decode(item['raw_base64'],validate=True)
        except (ValueError,TypeError) as exc:raise old.AbortError('Invalid protected raw journal') from exc
        require('sha256:'+hashlib.sha256(raw).hexdigest()==item['raw_sha256'],'Protected raw journal bytes changed')
        record=models.CapRecord.from_dict(old.parse(raw))
        require(record.intent.pod_uid==item['pod_uid'] and record.state in
            ('retired-inert-cap','recovered-cleared-offline-cap','cleaned'),'Only genuine completed prior journals may be retained')
        require(record.identity.node_uid==old.NODE_UID and record.identity.gpu_uuid==old.GPU,
            'Original physical history pool changed')
        require(record.identity.cgroup_inode not in inodes,'Duplicate original historical cgroup inode')
        if record.state=='cleaned':
            # Normal cleanup preserves the original finite seal readback. In
            # this bounded recovery path its original inode must be absent;
            # immutable completion is freshly checked by the held host fence.
            require(record.identity.cgroup_inode not in entries,'Cleaned original inode must be absent from full inventory')
        else:
            terminal=record.retirement if record.retirement is not None else record.recovery
            require(entries.get(record.identity.cgroup_inode)==terminal.entry,
                'Complete original retired physical entry required')
        uids.add(item['pod_uid']);inodes.add(record.identity.cgroup_inode)
    # Old cleared/unbound rows remain in the complete inventory. Unmatched
    # finite rows cannot disappear from the protected journal closure.
    require(all(inode in inodes or models.CapLimit(row.soft,row.hard).unlimited
        for inode,row in entries.items()),'Untracked finite physical row blocks recovery')
    return uids


def validate_evidence(evidence,expected,consumer,models):
    require(old.hash_value(expected) and old.sha256(evidence)==expected,'Reviewed approved evidence hash mismatch')
    closed(evidence,('version','qualification_only','authority_namespace','binding_id','attempt',
        'ledger_uid','allocation_sha256','ledger_custody_sha256','enrollment_uid','enrollment_sha256',
        'approval_ref','fence_command_sha256','proof','retired_journals','physical_rows','review'),
        'Closed approved recovery evidence required')
    require(type(evidence['version']) is int and evidence['version']==2
        and evidence['qualification_only'] is True and evidence['authority_namespace']==old.NAMESPACE,
        'Explicit controlled qualification recovery only')
    for key in ('ledger_uid','enrollment_uid'):require(old.valid_uuid(evidence[key]),'Actual API object UID required')
    for key in ('allocation_sha256','ledger_custody_sha256','enrollment_sha256','fence_command_sha256'):
        require(old.hash_value(evidence[key]),'Exact reviewed source/custody hash required')
    ref=approval.reference(evidence['approval_ref'])
    require(type(consumer) is approval.ApprovalConsumer and consumer.reference==ref
        and ref['namespace']==old.NAMESPACE,'Exact current node approval consumer required')
    require(isinstance(evidence['binding_id'],str) and len(evidence['binding_id'])==60
        and all(c in '0123456789abcdef' for c in evidence['binding_id'])
        and isinstance(evidence['attempt'],str) and 0<len(evidence['attempt'])<=128,'Exact reviewed binding/attempt required')
    review=evidence['review']
    closed(review,('operator','reason','gate_only_pod_sha256','controller_source_sha256',
        'node_agent_source_sha256','registration_failure_sha256','native_transaction_never_started'),
        'Explicit Root source/artifact review required')
    require(review['operator']=='root' and review['reason']=='approved-pod-failed-before-native-transaction'
        and review['native_transaction_never_started'] is True,'No unreviewed normal-production abort')
    for key in ('gate_only_pod_sha256','controller_source_sha256','node_agent_source_sha256','registration_failure_sha256'):
        require(old.hash_value(review[key]),'Exact reviewed failure/source artifact required')
    validate_proof(evidence['proof'],evidence)
    return validate_history(evidence,models)


def ledger_state(cm,evidence):
    meta=old.cm_metadata(cm,old.LEDGER)
    require(meta['uid']==evidence['ledger_uid'] and isinstance(meta.get('resourceVersion'),str)
        and meta['resourceVersion'],'Original actual ledger UID/RV required')
    closed(cm.get('data'),('state.json',),'Full native ledger data required')
    state=old.parse(cm['data']['state.json']);closed(state,('version','allocations'),'Exact full native ledger schema required')
    require(type(state['version']) is int and state['version']==1 and isinstance(state['allocations'],dict),
        'Versioned full native allocations required')
    record=state['allocations'].get(evidence['binding_id'])
    require(isinstance(record,dict) and ENROLLMENT_KEYS<=set(record)
        and record.get('state') in ('enrolling','enrolled','releasing','released'),
        'Existing registered intent and immutable enrollment required; reserved claims cannot be synthesized')
    closed(record,ENROLLMENT_KEYS|{'ceiling','group_id','state'}|
        ({'pre_gate_abort'} if 'pre_gate_abort' in record else set()),'Actual closed SDK allocation schema required')
    body={key:record[key] for key in ENROLLMENT_KEYS}
    require(record['binding_id']==evidence['binding_id'] and record['attempt']==evidence['attempt']
        and old.sha256({k:v for k,v in record.items() if k not in ('state','pre_gate_abort')})==evidence['allocation_sha256'],
        'Original full immutable allocation changed')
    normalized=copy.deepcopy(state);row=normalized['allocations'][evidence['binding_id']]
    row.pop('state');row.pop('pre_gate_abort',None)
    require(old.sha256(normalized)==evidence['ledger_custody_sha256']
        and all(isinstance(v,dict) and v.get('state')=='released'
            for bid,v in state['allocations'].items() if bid!=evidence['binding_id']),
        'Complete prior released allocation custody must remain exact')
    return state,record,body


def observe(backend,evidence,consumer,models):
    snapshot=backend.get_ledger();state,record,body=ledger_state(snapshot,evidence)
    require(body['source']=='cps' and body['workspace']=='native-group-b'
        and body['profile']=='interactive-shared-5' and body['cap_mib']==5120
        and body['approval_ref']==evidence['approval_ref'],'Only current approved controlled CPS5 scope may abort')
    cm=backend.get_enrollment(evidence['binding_id']);meta=old.cm_metadata(cm,'cps-native-enrollment-'+evidence['binding_id'][:40])
    require(meta['uid']==evidence['enrollment_uid'] and cm.get('immutable') is True
        and meta.get('labels')=={old.LABEL:evidence['binding_id']},'Original immutable enrollment UID/label required')
    closed(cm.get('data'),('enrollment.json',),'Full actual immutable enrollment required')
    require(cm['data']['enrollment.json']==approval.canonical(body) and approval.digest(body)==evidence['enrollment_sha256'],
        'Every original enrollment/ref byte must remain canonical and unchanged')
    doc=consumer.current();envelope=consumer._envelope(cm,models,doc,consumer.reference)
    require(envelope['enrollment']==body and body['intent']['pod_uid'] not in
        {item['pod_uid'] for item in evidence['retired_journals']},'Target never-gated UID must have no prior transaction')
    require(body['node']==old.NODE and body['node_uid']==old.NODE_UID and body['gpu_uuid']==old.GPU,
        'Only original controlled GPU2 physical pool supported')
    node=backend.get_node(body['node'])
    require(isinstance(node,dict) and node.get('metadata',{}).get('name')==old.NODE
        and node['metadata'].get('uid')==old.NODE_UID,'Actual Node UID changed')
    require(backend.get_pod(body['namespace'],body['name']) is None,'Existing or replacement Pod retains capacity')
    return snapshot,state,record,body


def verify_fence(fence,evidence):
    proof=fence.verify();validate_proof(proof,evidence)
    require(proof==evidence['proof'],'Changed live writer lock/epoch/current approval/history proof')


def execute_abort(backend,evidence,*,consumer,models,expected_evidence_sha256):
    validate_evidence(evidence,expected_evidence_sha256,consumer,models)
    with backend.fence(evidence) as fence:
        verify_fence(fence,evidence);_,_,_,enrollment=observe(backend,evidence,consumer,models)
        body=old.abort_body(evidence,enrollment)
        verify_fence(fence,evidence);observe(backend,evidence,consumer,models)
        existing=backend.get_abort(evidence['binding_id'])
        if existing is None:backend.create_abort(body);existing=backend.get_abort(evidence['binding_id'])
        proof=old.trusted_abort(existing,body)
        verify_fence(fence,evidence);snapshot,state,record,_=observe(backend,evidence,consumer,models)
        verify_fence(fence,evidence)
        require(old.trusted_abort(backend.get_abort(evidence['binding_id']),body)==proof,
            'Original actual immutable abort UID/body changed before CAS')
        if record['state']=='released':require(record.get('pre_gate_abort')==proof,'Exact actual abort UID required on retry')
        else:
            require('pre_gate_abort' not in record,'Partial released proof retains capacity')
            saved=copy.deepcopy(state);saved['allocations'][evidence['binding_id']].update(state='released',pre_gate_abort=proof)
            response=backend.compare_and_swap(snapshot,saved)
            actual,_,_=ledger_state(response,evidence)
            require(actual==saved,'Full guarded ledger CAS readback differs')
        verify_fence(fence,evidence);observe(backend,evidence,consumer,models)
        require(old.trusted_abort(backend.get_abort(evidence['binding_id']),body)==proof,
            'Original actual immutable abort UID/body changed after CAS')
        return dict(state='released',binding_id=evidence['binding_id'],attempt=evidence['attempt'],
            audit_sha256=expected_evidence_sha256,abort=proof,approval_ref=copy.deepcopy(evidence['approval_ref']))


class RootFence(old.RootFence):
    """Same live pinned Root RPC, with distinct full-retained-history proof."""
    def line(self,expected):
        deadline=datetime.now(timezone.utc).timestamp()+self.timeout
        while b'\n' not in self.buffer:
            remaining=deadline-datetime.now(timezone.utc).timestamp()
            require(remaining>0 and self.process.poll() is None,'Root fence exited or timed out')
            ready,_,_=select.select([self.process.stdout],[],[],remaining)
            require(ready,'Root fence response timed out')
            chunk=os.read(self.process.stdout.fileno(),4096)
            require(chunk and len(self.buffer)+len(chunk)<=65536,'Root fence EOF/oversized response')
            self.buffer+=chunk
        raw,self.buffer=self.buffer.split(b'\n',1);value=old.parse(raw)
        closed(value,('event','observed_at','proof'),'Closed live Root fence response required')
        require(value['event']==expected,'Unexpected Root fence event')
        try:
            stamp=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00'))
            age=(datetime.now(timezone.utc)-stamp).total_seconds()
            require(value['observed_at'].endswith('Z') and stamp.tzinfo is not None and -5<=age<=30,
                'Fresh UTC live Root fence response required')
        except (TypeError,AttributeError,ValueError) as exc:raise old.AbortError('Invalid Root fence timestamp') from exc
        validate_proof(value['proof'],self.evidence)
        require(value['proof']==self.evidence['proof'],'Actual Root proof changed')
        return value['proof']


class KubernetesBackend(old.KubernetesBackend):
    def fence(self,evidence):
        self.live_fence=RootFence(self.fence_command,evidence);return self.live_fence
    def compare_and_swap(self,snapshot,state):
        patch=[{'op':'test','path':'/metadata/uid','value':snapshot['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':snapshot['metadata']['resourceVersion']},
            {'op':'test','path':'/data','value':snapshot['data']},
            {'op':'replace','path':'/data','value':{'state.json':old.canonical(state)}}]
        with tempfile.NamedTemporaryFile(mode='w',prefix='approved-native-abort-cas-',encoding='utf8') as file:
            file.write(old.canonical(patch));file.flush()
            return self.call(['patch','configmap',old.LEDGER,'-n',old.NAMESPACE,'--type=json',
                '--patch-file',file.name,'-o','json'])


if __name__=='__main__':
    print(old.canonical({'state':'inert','api_calls':False,'device_calls':False,
        'requires':'explicit execute_abort API with reviewed actual consumer, models, evidence and pinned live Root fence'}))
