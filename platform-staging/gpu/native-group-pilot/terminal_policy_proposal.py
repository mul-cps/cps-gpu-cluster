"""Pure full terminal authority mapping for a future policy hash.

This module makes no API, filesystem, device, driver, or application calls.
The proposal retains complete immutable maps and protected host records; a
count, timestamp, status flag, or digest alone cannot substitute for them.
"""
import copy
import hashlib
import json
import re
import node_agent as agent

RECOVERY_UID = '8066366f-6e7e-42ea-83b2-86a58e9c3bad'
RECOVERY_BINDING = '16d264e00ee6778319a8961f9da510147c3bebc925e674bf95880689cd25'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False)


def raw_sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def immutable(cm, namespace, name, binding, key):
    meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
    agent.require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
        and cm.get('immutable') is True and not cm.get('binaryData')
        and meta.get('namespace')==namespace and meta.get('name')==name
        and meta.get('labels')=={agent.LABEL:binding} and agent.canonical_uuid(meta.get('uid'))
        and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'),
        'Exact independently retained immutable terminal authority required')
    agent.closed(cm.get('data'),{key},'Single complete terminal authority payload required')
    return agent.parse(cm['data'][key])


def protected_records(directory):
    agent.closed(directory,{'ownerUid','mode','records'},'Complete protected authority directory required')
    agent.require(type(directory['ownerUid']) is int and directory['ownerUid']==0
        and type(directory['mode']) is int and directory['mode']==0o700
        and isinstance(directory['records'],dict),'Root-owned private authority directory required')
    records={}
    for name,row in directory['records'].items():
        agent.closed(row,{'uid','mode','nlink','rawSha256','value'},'Original full protected authority file required')
        agent.require(isinstance(name,str) and name.endswith('.json') and agent.canonical_uuid(name[:-5])
            and type(row['uid']) is int and row['uid']==0 and type(row['mode']) is int
            and row['mode'] in (0o400,0o600) and type(row['nlink']) is int and row['nlink']==1
            and isinstance(row['value'],dict) and isinstance(row['rawSha256'],str)
            and re.fullmatch('sha256:[0-9a-f]{64}',row['rawSha256']) is not None,
            'Original no-follow protected authority metadata required')
        records[name[:-5]]=row
    return records


def map_history(authority, ledger, previous_node):
    from cps_compute import native_gpu_controller as models
    from cps_compute.native_gpu_control import validate_cleanup_record,recovery_audit_body
    agent.closed(authority,{'authority_maps','host_snapshot'},'Full terminal authority captures required')
    agent.validate_config(previous_node)
    meta=ledger.get('metadata',{})
    agent.require(ledger.get('apiVersion')=='v1' and ledger.get('kind')=='ConfigMap'
        and meta.get('name')=='cps-native-gpu-allocations'
        and meta.get('namespace')==previous_node['authority_namespace']
        and agent.canonical_uuid(meta.get('uid')) and meta.get('resourceVersion'),
        'Actual full allocation ledger identity required')
    state=agent.parse(ledger.get('data',{}).get('state.json','{}'))
    agent.closed(state,{'version','allocations'},'Full closed allocation state required')
    agent.require(type(state['version']) is int and state['version']==1
        and isinstance(state['allocations'],dict) and len(state['allocations'])<=128,
        'Bounded complete allocation state required')
    maps=authority['authority_maps']
    agent.require(isinstance(maps,dict) and maps.get('apiVersion')=='v1'
        and maps.get('kind') in ('List','ConfigMapList') and isinstance(maps.get('items'),list)
        and isinstance(maps.get('metadata'),dict) and not maps['metadata'].get('continue'),
        'Complete unpaginated actual authority ConfigMap List required')
    by_name={}
    for original in maps['items']:
        cm=copy.deepcopy(original)
        agent.require(isinstance(cm,dict),'Actual ConfigMap List item required')
        if maps['kind']=='ConfigMapList':
            cm.setdefault('apiVersion','v1');cm.setdefault('kind','ConfigMap')
        info=cm.get('metadata',{})
        agent.require(cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
            and info.get('namespace')==meta['namespace'] and agent.canonical_uuid(info.get('uid'))
            and isinstance(info.get('name'),str) and info['name'] not in by_name,
            'Distinct original namespaced authority objects required')
        by_name[info['name']]=cm
    host=authority['host_snapshot'];directories=host.get('directories',{})
    agent.closed(directories,{'enrollments','intents','journal'},'All original protected authority directories required')
    contents={key:protected_records(value) for key,value in directories.items()}
    agent.require(host.get('node')==previous_node['pool']['node']
        and host.get('nodeUid')==previous_node['pool']['node_uid']
        and agent.canonical_uuid(host.get('bootId')) and agent.canonical_uuid(host.get('driverGeneration')),
        'Exact unchanged original node/driver epoch required')
    epoch=models.DriverEpoch(host['nodeUid'],host['bootId'],host['driverGeneration'],previous_node['pool']['gpu_uuid'])
    enrolled={}
    for binding,row in state['allocations'].items():
        agent.require(isinstance(row,dict) and row.get('binding_id')==binding and row.get('state')=='released',
            'Every complete previous allocation must remain released')
        if row.get('intent') is not None:
            intent=models.CapIntent(**row['intent'])
            agent.require(intent.pod_uid not in enrolled,'Distinct original allocation Pod UIDs required')
            enrolled[intent.pod_uid]=(binding,row,intent)
    agent.require(set(enrolled)==set(contents['enrollments'])==set(contents['intents']),
        'Full allocation/enrollment/intent sets must match exactly')
    agent.require({name for name in by_name if name.startswith('cps-native-enrollment-')}
        =={'cps-native-enrollment-'+binding[:40] for binding,_,_ in enrolled.values()},
        'No missing or invented immutable enrollment authority')
    result={};journal_uids=set()
    for uid,(binding,row,intent) in enrolled.items():
        name='cps-native-enrollment-'+binding[:40];cm=by_name.get(name)
        enrollment=immutable(cm,meta['namespace'],name,binding,'enrollment.json')
        envelope=contents['enrollments'][uid]['value']
        agent.require(envelope=={'authority_namespace':meta['namespace'],'configmap_name':name,
            'configmap_uid':cm['metadata']['uid'],'enrollment':enrollment}
            and all(row.get(k)==v for k,v in enrollment.items())
            and enrollment.get('intent')==intent.to_dict() and contents['intents'][uid]['value']==intent.to_dict(),
            'Complete original protected enrollment/intent/ledger changed')
        cleanup_name='cps-native-cleanup-'+binding[:40];abort_name='cps-native-abort-'+binding[:40]
        cleanup=by_name.get(cleanup_name);abort=by_name.get(abort_name)
        agent.require((cleanup is None)!=(abort is None),'Exactly one original terminal completion required')
        journal_digest=None
        if abort is not None:
            agent.require(uid not in contents['journal'],'Pre-gate abort cannot acquire a native journal')
            completed=immutable(abort,meta['namespace'],abort_name,binding,'abort.json')
            original_epoch=models.DriverEpoch(**completed['node_epoch'])
            agent.require(uid in previous_node.get('terminal_history',{}) or original_epoch==epoch,
                'A new abort mapping needs the current unchanged driver epoch')
            agent.validate_abort(abort,envelope,ledger,original_epoch,models)
            kind='pre-gate-abort';completion=abort
        else:
            agent.require(uid in contents['journal'],'Complete original terminal journal required')
            protected=contents['journal'][uid];body=protected['value'];record=models.CapRecord.from_dict(body)
            agent.require(record.to_dict()==body and record.intent==intent
                and record.state in ('cleaned','retired-inert-cap','recovered-cleared-offline-cap')
                and protected['rawSha256']==raw_sha((canonical(body)+'\n').encode()),
                'Exact typed original protected terminal journal required')
            completed=immutable(cleanup,meta['namespace'],cleanup_name,binding,'receipt.json')
            expected={'version':1,'binding_id':binding,'attempt':enrollment['attempt'],
                'intent':intent.to_dict(),'cleanup_confirmed':True}
            validate_cleanup_record(completed,expected)
            journal_digest=agent.canonical_sha256(body)
            if record.state=='retired-inert-cap':
                agent.require(record.identity.epoch==epoch, 'Original finite retirement must match the unchanged physical epoch')
                proof=completed.get('retirement',{})
                agent.require(proof=={'proof':record.retirement.to_dict(),'enrollment_uid':cm['metadata']['uid'],
                    'enrollment_sha256':agent.canonical_sha256(enrollment),'journal_sha256':journal_digest},
                    'Finite retirement must retain its exact full journal and immutable enrollment')
            elif record.state=='recovered-cleared-offline-cap':
                agent.require(uid==RECOVERY_UID and binding==RECOVERY_BINDING,
                    'Only the original distinct recovery exception may survive a policy change')
                proof=completed.get('recovery',{})
                audit_name='cps-native-recovery-'+binding[:40];audit=by_name.get(audit_name)
                audit_body=immutable(audit,meta['namespace'],audit_name,binding,'recovery.json')
                agent.require(proof.get('proof')==record.recovery.to_dict()
                    and proof.get('enrollment_uid')==cm['metadata']['uid']
                    and proof.get('enrollment_sha256')==agent.canonical_sha256(enrollment)
                    and proof.get('journal_sha256')==journal_digest
                    and proof.get('audit_uid')==audit['metadata']['uid']
                    and proof.get('audit_sha256')==agent.canonical_sha256(audit_body)
                    and audit_body==recovery_audit_body(completed),
                    'Original recovery journal/proof/audit/cleanup must remain distinct and complete')
            else:
                agent.require(completed==expected,'Cleaned historical journal must use exact original plain cleanup')
            journal_uids.add(uid);kind='cleanup';completion=cleanup
        entry={'binding_id':binding,'policy_hash':enrollment['policy_hash'],'profile':enrollment['profile'],
            'enrollment_uid':cm['metadata']['uid'],'enrollment_sha256':agent.canonical_sha256(enrollment),
            'completion_kind':kind,'completion_uid':completion['metadata']['uid'],
            'completion_sha256':agent.canonical_sha256(completed),'ledger_uid':meta['uid'],
            'journal_sha256':journal_digest}
        previous=previous_node.get('terminal_history',{}).get(uid)
        if previous is not None:
            if 'cap_mib' in previous:entry['cap_mib']=intent.cap_mib
            if 'configuration_authority' in previous:
                reference=previous['configuration_authority']
                historical=agent.validate_historical_configuration(by_name.get(reference['name']),
                    reference,previous_node,previous)
                agent.require(agent.validate_enrollment(cm,historical,models)==envelope
                    and record.state=='retired-inert-cap' and record.retirement.entry.used==0,
                    'Historical configuration reference requires the exact finite released enrollment')
                entry['configuration_authority']=copy.deepcopy(reference)
            agent.require(previous==entry,'Every previous full terminal mapping must remain unchanged')
            result[uid]=copy.deepcopy(previous)
        else:result[uid]=dict(entry,cap_mib=intent.cap_mib)
    agent.require(set(contents['journal'])==journal_uids
        and set(previous_node.get('terminal_history',{}))<=set(result),
        'No omitted or invented journal or previous terminal authority')
    return result
