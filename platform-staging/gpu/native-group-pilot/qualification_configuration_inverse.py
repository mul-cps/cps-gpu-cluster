"""Pure disabled configuration inverse preserving full terminal GPU authority.

No application, transport, file or GPU calls are made. Root supplies complete
fresh captures and reviewed original bytes; Root owns staging and execution.
"""
import base64
import copy
import hashlib
import re
import node_agent as agent
import terminal_policy_proposal as terminal
import qualification_transition_proposal as transition
from historical_configuration_source import extend_source

IDENTITY = {'source','actor','workspace','principal','members','ceiling','group_id','profile',
    'policy_hash','namespace','name','node','node_uid','gpu_uuid','cap_mib'}
CHANGEABLE = {'profile','policy_hash','cap_mib','ceiling'}
PROVENANCE = {'adapter_sha256','before_full_sha256','after_full_sha256','receipt_sha256','review_sha256'}
PHYSICAL_PINS = {'core_sha256':'4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421',
    'uvm_sha256':'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61',
    'health_sha256':'52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67'}


def bare_sha(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) and value!='0'*64


def allocation_state(cm,node):
    from cps_compute.native_gpu_control import MeasuredNativeAuthority
    meta=transition.object_guard(cm,'ConfigMap')
    agent.require(cm.get('apiVersion')=='v1' and meta.get('namespace')==node['authority_namespace']
        and meta.get('name')=='cps-native-gpu-allocations','Actual full central allocation ledger required')
    agent.closed(cm.get('data'),{'state.json'},'Single complete allocation ledger required')
    state=agent.parse(cm['data']['state.json'])
    agent.closed(state,{'version','allocations'},'Closed full allocation state required')
    agent.require(type(state['version']) is int and state['version']==1
        and isinstance(state['allocations'],dict) and len(state['allocations'])<=64
        and all(row.get('state')=='released' for row in state['allocations'].values()),
        'Every full original and new allocation must be released')
    verifier=object.__new__(MeasuredNativeAuthority);verifier.pool=node['pool']
    verifier._validate_allocations(state['allocations'])
    return state['allocations']


def rows_by_uid(rows,description):
    agent.require(isinstance(rows,list),'Complete '+description+' list required')
    indexed={}
    for row in rows:
        agent.require(isinstance(row,dict) and agent.canonical_uuid(row.get('pod_uid'))
            and row['pod_uid'] not in indexed,'Distinct exact '+description+' Pod UIDs required')
        indexed[row['pod_uid']]=row
    return indexed


def history_records(capture,node):
    from cps_compute import native_gpu_controller as models
    history=capture['history'];host=capture['authority']['host_snapshot']
    agent.closed(history,{'version','protocol','node','node_uid','gpu_uuid','boot_id','driver_generation',
        'controller_sha256','records','recovery'},'Complete immutable terminal history required')
    agent.require(type(history['version']) is int and history['version']==2
        and all(history[k]==node['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')),
        'Full terminal history must belong to the same physical driver epoch')
    protected=terminal.protected_records(host['directories']['journal'])
    indexed=rows_by_uid(history['records'],'journal history')
    agent.require(set(indexed)==set(protected),'Full history and protected raw journal sets must agree')
    records={}
    for uid,row in indexed.items():
        agent.closed(row,{'pod_uid','journal_sha256','record'},'Full typed original history row required')
        record=models.CapRecord.from_dict(row['record'])
        agent.require(record.to_dict()==row['record'] and record.intent.pod_uid==uid
            and row['journal_sha256']==protected[uid]['rawSha256']
            and protected[uid]['value']==row['record']
            and protected[uid]['rawSha256']==terminal.raw_sha((terminal.canonical(row['record'])+'\n').encode()),
            'Full immutable history and original protected journal bytes must remain exact')
        records[uid]=record
    return indexed,records


def physical_records(capture,node,records):
    physical=capture['physical']
    agent.closed(physical,{'kind','node','node_uid','gpu_uuid','boot_id','driver_generation','observed_at_ns',
        'core_sha256','uvm_sha256','health_sha256','inventory_sha256','targets','retired_caps'},
        'Complete typed physical zero witness required')
    agent.require(physical['kind']=='native-group-host-observation'
        and all(physical[k]==node['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation'))
        and type(physical['observed_at_ns']) is int and physical['observed_at_ns']>0
        and physical['targets']==[], 'No active physical target may survive the configuration inverse')
    agent.require(all(bare_sha(physical[key]) and physical[key]==value for key,value in PHYSICAL_PINS.items())
        and isinstance(physical['inventory_sha256'],str)
        and re.fullmatch('sha256:[0-9a-f]{64}',physical['inventory_sha256'])
        and physical['inventory_sha256']!='sha256:'+'0'*64,
        'Original reviewed driver/core/health pins and a complete actual inventory digest required')
    indexed=rows_by_uid(physical['retired_caps'],'physical retirement')
    expected={uid for uid,record in records.items()
        if record.state in ('retired-inert-cap','recovered-cleared-offline-cap')}
    agent.require(set(indexed)==expected,'All finite and distinct recovered retirements require physical witness')
    for uid,row in indexed.items():
        record=records[uid];recovery=record.state=='recovered-cleared-offline-cap'
        key='recovery' if recovery else 'retirement';proof=record.to_dict()[key]
        agent.closed(row,{'pod_uid','identity','inventory_row','journal_sha256',key},
            'Full original physical terminal identity/proof required')
        agent.require(row['identity']==record.to_dict()['identity'] and row[key]==proof
            and row['inventory_row']==proof['entry'] and row['inventory_row']['used']==0
            and row['journal_sha256']==terminal.raw_sha((terminal.canonical(record.to_dict())+'\n').encode()),
            'Physical identity, finite limits and zero charge must match the complete terminal journal')
        if not recovery:
            cap=record.intent.cap_mib*1048576
            agent.require(row['inventory_row']['soft']==row['inventory_row']['hard']==cap
                and row['inventory_row']['offline'] is True and row['inventory_row']['pinned'] is True
                and row['inventory_row']['default_hierarchy'] is True,
                'Finite retired limits cannot be MAX, active, foreign or charged')
        else:
            agent.require(uid==terminal.RECOVERY_UID,'No new recovery exception may be inferred')
    return indexed


def validate_extension(captures,approval,original_node,current_node,baseline_history_raw):
    agent.closed(captures,{'baseline','current','binding'},'Full bounded baseline/current captures and binding required')
    baseline=captures['baseline'];current=captures['current'];binding=captures['binding']
    agent.closed(baseline,{'authority','ledger','history','physical'},'Complete original authority/history/physical required')
    agent.closed(current,{'authority','ledger','history','physical','pods'},'Complete fresh authority/history/physical/Pods required')
    agent.closed(approval,{'version','enabled','preset','policy_hash','baseline_ledger_state_sha256',
        'baseline_history_raw_sha256','binding_sha256','sources'},'Closed reviewed actual5/20 identity approval required')
    agent.require(type(approval['version']) is int and approval['version']==1 and approval['enabled'] is True
        and approval['preset']=='cps5-cit20' and approval['policy_hash']==current_node['policy_hash']
        and all(bare_sha(approval[k]) for k in ('baseline_ledger_state_sha256','baseline_history_raw_sha256','binding_sha256'))
        and hashlib.sha256(baseline['ledger']['data']['state.json'].encode()).hexdigest()==approval['baseline_ledger_state_sha256']
        and isinstance(baseline_history_raw,(str,bytes))
        and hashlib.sha256(baseline_history_raw.encode() if isinstance(baseline_history_raw,str) else baseline_history_raw).hexdigest()
            ==approval['baseline_history_raw_sha256']
        and agent.parse(baseline_history_raw)==baseline['history']
        and hashlib.sha256(agent.canonical_json(binding).encode()).hexdigest()==approval['binding_sha256'],
        'Reviewed full baseline raw bytes and exact actual binding required')
    oldrows=allocation_state(baseline['ledger'],original_node);newrows=allocation_state(current['ledger'],current_node)
    agent.require(baseline['ledger']['metadata']['uid']==current['ledger']['metadata']['uid']
        and set(oldrows)<=set(newrows) and all(newrows[key]==row for key,row in oldrows.items()),
        'Every original full ledger allocation must survive byte-equivalently')
    added={key:row for key,row in newrows.items() if key not in oldrows}
    agent.require(len(added)==2 and {row['source'] for row in added.values()}=={'cps','cit'},
        'Only the two new approved finite5/20 claims may extend the complete released ledger')
    agent.closed(approval['sources'],{'cps','cit'},'Both approved Source identities required')
    agent.closed(binding,{'version','state','policy_hash','observer_uid','pool','pool_measurement','retired_capture','targets'},
        'Closed actual controlled5/20 binding required')
    agent.require(type(binding['version']) is int and binding['version']==1
        and binding['state']=='Root-reviewed-controlled-plan' and binding['policy_hash']==current_node['policy_hash']
        and agent.canonical_uuid(binding['observer_uid']) and isinstance(binding['targets'],list)
        and len(binding['targets'])==2 and {t.get('source') for t in binding['targets']}=={'cps','cit'},
        'Exact bounded actual controlled pair required')
    expected_pool={'node','node_uid','gpu_uuid','boot_id','driver_generation','budget_mib','headroom_bytes',
        'measured_free_bytes','measurement_sha256'}
    agent.closed(binding['pool'],expected_pool,'Closed full actual measured pool binding required')
    agent.require(all(binding['pool'][k]==current_node['pool'][k]
            for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation'))
        and binding['pool']['budget_mib']==25600 and binding['pool']['headroom_bytes']==1073741824
        and type(binding['pool']['measured_free_bytes']) is int
        and binding['pool']['measured_free_bytes']>=26624*1048576,
        'Actual25GiB pair must retain its measured unsold1GiB headroom and driver epoch')
    old_uids={row['intent']['pod_uid'] for row in oldrows.values() if row['intent'] is not None}
    new_uids=set()
    for row in added.values():
        source=row['source'];size=5 if source=='cps' else 20;scope=transition.SCOPES[source]
        approved=approval['sources'][source]
        agent.closed(approved,{'identity','handover_provenance'},'Full Source identity and reviewed audited handover pins required')
        identity=approved['identity'];agent.closed(identity,IDENTITY,'Complete actual Source-owned identity required')
        agent.closed(approved['handover_provenance'],PROVENANCE,'All audited Source handover provenance required')
        agent.require(all(bare_sha(value) for value in approved['handover_provenance'].values()),
            'Actual audited Source handover provenance pins required')
        ceiling=identity['ceiling'];agent.closed(ceiling,{'cpu','memory','gpuMemoryGiB'},'Approved bounded Source ceiling required')
        agent.require(all(row[key]==value for key,value in identity.items() if key!='ceiling')
            and row['ceiling']==ceiling and ceiling=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':size}
            and identity['profile']=='interactive-native-qualification-'+str(size)
            and identity['cap_mib']==size*1024 and identity['workspace']==scope
            and identity['policy_hash']==current_node['policy_hash']
            and any(all(previous[key]==row[key] for key in IDENTITY-CHANGEABLE)
                for previous in oldrows.values()),
            'New pair must preserve exact original Source actor, canonical people, owner, workspace, group and Pod identity')
        target=next(t for t in binding['targets'] if t['source']==source)
        agent.closed(target,{'source','namespace','name','pod_uid','spec_sha256','workspace','profile','cap_mib','pod_capture'},
            'Full reviewed actual Pod binding required')
        intent=row['intent']
        agent.require(isinstance(intent,dict) and all(target[k]==row[k]
            for k in ('source','namespace','name','workspace','profile','cap_mib'))
            and intent['pod_uid']==target['pod_uid'] and intent['spec_sha256']==target['spec_sha256']
            and intent['pod_uid'] not in old_uids|new_uids,'Distinct exact new admitted Pod UID/spec and claim required')
        new_uids.add(intent['pod_uid'])
    olddirs=baseline['authority']['host_snapshot']['directories']
    newdirs=current['authority']['host_snapshot']['directories']
    agent.closed(olddirs,{'enrollments','intents','journal'},'All original protected directories required')
    agent.closed(newdirs,{'enrollments','intents','journal'},'All fresh protected directories required')
    for name,previous in olddirs.items():
        actual=newdirs[name]
        oldfiles=terminal.protected_records(previous);newfiles=terminal.protected_records(actual)
        agent.require(previous['ownerUid']==actual['ownerUid'] and previous['mode']==actual['mode']
            and set(newfiles)==set(oldfiles)|new_uids
            and all(newfiles[uid]==row for uid,row in oldfiles.items()),
            'Every original protected full file envelope and raw-byte pin must survive; only the exact new pair may grow')
        for uid in new_uids:
            row=newfiles[uid]
            agent.require(row['rawSha256']==terminal.raw_sha((terminal.canonical(row['value'])+'\n').encode()),
                'New protected mirrors require their complete original canonical raw bytes')
    oldmap=terminal.map_history(baseline['authority'],baseline['ledger'],original_node)
    fullmap=terminal.map_history(current['authority'],current['ledger'],current_node)
    agent.require(set(oldmap)|new_uids==set(fullmap)
        and all(fullmap[uid]==entry for uid,entry in oldmap.items()),'Full prior terminal authority may never be summarized or dropped')
    oldhistory,oldrecords=history_records(baseline,original_node);newhistory,newrecords=history_records(current,current_node)
    agent.require(set(oldhistory)|new_uids==set(newhistory)
        and all(newhistory[uid]==row for uid,row in oldhistory.items())
        and {k:v for k,v in baseline['history'].items() if k!='records'}
            =={k:v for k,v in current['history'].items() if k!='records'},
        'Complete immutable old journal history and distinct original recovery must remain unchanged')
    oldphysical=physical_records(baseline,original_node,oldrecords)
    newphysical=physical_records(current,current_node,newrecords)
    agent.require(all(baseline['physical'][key]==current['physical'][key] for key in PHYSICAL_PINS)
        and current['physical']['observed_at_ns']>=baseline['physical']['observed_at_ns'],
        'Physical witness must retain authenticated source pins and cannot predate the reviewed baseline')
    agent.require(set(oldphysical)|new_uids==set(newphysical)
        and all(newphysical[uid]==row for uid,row in oldphysical.items())
        and all(newrecords[uid].state=='retired-inert-cap' for uid in new_uids),
        'Both new claims require original finite zero-charge retirement, preserving all previous physical authority')
    pods=current['pods'];agent.require(pods.get('apiVersion')=='v1' and pods.get('kind')=='PodList'
        and isinstance(pods.get('items'),list) and isinstance(pods.get('metadata'),dict)
        and not pods['metadata'].get('continue'),'Complete unpaginated current PodList required')
    forbidden_names={(t['namespace'],t['name']) for t in binding['targets']}
    for pod in pods['items']:
        meta=pod.get('metadata',{})
        agent.require(agent.canonical_uuid(meta.get('uid')) and meta['uid'] not in new_uids
            and (meta.get('namespace'),meta.get('name')) not in forbidden_names,
            'Exact new Pod UIDs and replacement Pods using their workspace names must be absent')
    return fullmap,new_uids


def deployment_objects(configs):
    return {'node':configs['node_deployment'],'gateway':configs['gateway_deployment'],
        'cps':configs['cps']['deployment'],'cit':configs['cit']['deployment']}


def code_reference(spec):
    rows=[v for v in spec['template']['spec']['volumes'] if v.get('name')=='code' and 'configMap' in v]
    agent.require(len(rows)==1,'One exact existing node code ConfigMap volume required')
    return rows[0]['configMap']['name']


def validate_configuration_handover(originals,current,captures,node_agent_source):
    """Full actual handover and pinned one-key code diff, without side effects."""
    from cps_compute.policy import Policy
    fields={'policy','runtime','node_config','node_deployment','gateway_deployment','cps','cit'}
    agent.closed(originals,fields,'Full original configuration objects required')
    agent.closed(current,fields|{'node_code'},'Full fresh current objects and retained reviewed node code required')
    oldnode=agent.validate_config(agent.parse(originals['node_config']['data']['config.json']))
    node=agent.validate_config(agent.parse(current['node_config']['data']['config.json']))
    oldpolicy=Policy(agent.parse(originals['policy']['data']['policy.json']))
    newpolicy=Policy(agent.parse(current['policy']['data']['policy.json']))
    agent.require(oldpolicy.hash==oldnode['policy_hash'] and newpolicy.hash==node['policy_hash']
        and oldpolicy.hash!=newpolicy.hash and oldpolicy.catalog['gpuQualification']['qualified'] is False,
        'Original unqualified policy must be restored exactly')
    runtime=agent.parse(base64.b64decode(current['runtime']['data']['runtime.json'],validate=True))
    proposal={'policy.json':newpolicy.catalog,'operator-qualification.json':runtime['nativeGpuQualification'],
        'node-config.json':node}
    forward=transition.configuration_intent(proposal,originals)
    for key,expected in (('policy',forward['policy.patch.json'][-1]['value']),
                         ('runtime',forward['runtime.patch.json'][-1]['value'])):
        agent.require(current[key]['data']==expected,'Current full '+key+' differs from the reviewed coordinated5/20 handover')
        agent.require(all(current[key]['metadata'].get(k)==originals[key]['metadata'].get(k)
            for k in ('namespace','name','uid')),'Original policy/runtime API ownership must remain unchanged')
    for source in ('cps','cit'):
        agent.require(current[source]['config']['data']==forward['configurations'][source]['data'],
            'Current full Hub configuration changed beyond the explicit5/20 handover')
    agent.require(current['node_config']['data']==forward['configurations']['node']['data'],
        'Exact current controlled5/20 node configuration required')
    olddeploy=deployment_objects(originals);newdeploy=deployment_objects(current)
    maps=captures['baseline']['authority']['authority_maps']['items']
    oldname=code_reference(olddeploy['node']['spec'])
    matches=[cm for cm in maps if cm.get('metadata',{}).get('name')==oldname]
    agent.require(len(matches)==1,'Original full immutable recovery-enabled code ConfigMap required')
    oldcode=copy.deepcopy(matches[0]);oldcode.setdefault('apiVersion','v1');oldcode.setdefault('kind','ConfigMap')
    newcode=current['node_code'];meta=transition.object_guard(newcode,'ConfigMap')
    agent.require(newcode.get('immutable') is True and not newcode.get('binaryData')
        and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
        and meta['namespace']==oldcode['metadata']['namespace']
        and meta['name'].startswith('cps-native-node-code-')
        and newcode['data']==dict(oldcode['data'],**{'node_agent.py':extend_source(oldcode['data']['node_agent.py'],node_agent_source)}),
        'Node code may change only through the pinned terminal-only extension; all recovery source bytes remain exact')
    for key,obj in newdeploy.items():
        transition.object_guard(obj,'Deployment')
        agent.require(obj['metadata']['uid']==olddeploy[key]['metadata']['uid'],
            'Existing deployment ownership must survive the handover')
        expected=copy.deepcopy(forward['deployment_patches'][key][-1]['value'])
        if key!='gateway':
            proposed_name=forward['configurations'][key]['metadata']['name']
            actual_name=current['node_config' if key=='node' else key]['metadata']['name'] if key=='node' else current[key]['config']['metadata']['name']
            agent.require(actual_name==proposed_name,'Exact reviewed immutable configuration name required')
        if key=='node':
            for volume in expected['template']['spec']['volumes']:
                if volume.get('name')=='code':volume['configMap']['name']=meta['name']
        agent.require(obj['spec']==expected,'Full current deployment spec may change only reviewed configuration/code references')
    return oldnode,node,oldpolicy,olddeploy,newdeploy,meta


def derive_inverse(originals,current,captures,approval,*,baseline_history_raw,node_agent_source,
                   historical_configuration_reference):
    """Derive fully tested CAS proposals; output is disabled and never applies."""
    oldnode,node,oldpolicy,olddeploy,newdeploy,meta=validate_configuration_handover(
        originals,current,captures,node_agent_source)
    fullmap,newuids=validate_extension(captures,approval,oldnode,node,baseline_history_raw)
    restored=copy.deepcopy(oldnode)
    runtime_map={uid:copy.deepcopy(entry) for uid,entry in fullmap.items() if entry['policy_hash']!=oldnode['policy_hash']}
    ref=copy.deepcopy(historical_configuration_reference)
    agent.closed(ref,{'namespace','name','uid','data_sha256','policy_hash'},
        'Independently reviewed actual staged historical configuration pin required')
    archive=copy.deepcopy(fullmap)
    for uid in newuids:
        runtime_map[uid]['configuration_authority']=copy.deepcopy(ref)
        archive[uid]['configuration_authority']=copy.deepcopy(ref)
        agent.validate_historical_configuration(current['node_config'],ref,restored,runtime_map[uid])
    restored['terminal_history']=runtime_map;agent.validate_config(restored)
    # Replay the full original plus new authority using the resulting active15
    # configuration. Same-active-policy rows remain validated by the unchanged
    # released current path; the archive still contains every one of them.
    authority=copy.deepcopy(captures['current']['authority'])
    existing=[cm for cm in authority['authority_maps']['items']
        if cm.get('metadata',{}).get('name')==ref['name']]
    agent.require(not existing or existing==[current['node_config']],
        'Captured historical configuration must agree with the actual current immutable object')
    if not existing:authority['authority_maps']['items'].append(copy.deepcopy(current['node_config']))
    remapped=terminal.map_history(authority,captures['current']['ledger'],restored)
    agent.require(remapped==archive,'Expanded full authority archive must round-trip without any old record loss')
    data=dict(originals['node_config']['data'],**{'config.json':transition.canonical(restored)})
    cm=transition.immutable_config(current['node_config'],data,'cps-native-node-qualification')
    patches={}
    for key,obj in newdeploy.items():
        desired=copy.deepcopy(olddeploy[key]['spec'])
        if key=='node':
            for volume in desired['template']['spec']['volumes']:
                if volume.get('name')=='code':volume['configMap']['name']=meta['name']
                elif volume.get('configMap',{}).get('name')==originals['node_config']['metadata']['name']:
                    volume['configMap']['name']=cm['metadata']['name']
        patches[key]=transition.replace_patch(obj,'/spec',obj['spec'],desired)
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'restored_policy_hash':oldpolicy.hash,'node-config.json':restored,'node-configmap.json':cm,
        'full-terminal-authority-archive.json':archive,'authority-replay.json':authority,
        'policy.patch.json':transition.replace_patch(current['policy'],'/data',current['policy']['data'],originals['policy']['data']),
        'runtime.patch.json':transition.replace_patch(current['runtime'],'/data',current['runtime']['data'],originals['runtime']['data']),
        'deployment_patches':patches,'retained-node-code.json':copy.deepcopy(current['node_code']),
        'source_inverse_order':['fence-all-Starts-and-writers','fresh-complete-terminal-and-zero-proof',
            'stage-derived-immutable-old-policy-node-config','restore-old-gateway-policy-runtime-and-wait-Ready',
            'audited-Source-profile-course-grant-and-original-hash-registration-inverses',
            'restore-original-grant-expiry','restore-Hub-and-node-references-and-verify-full-readbacks'],
        'fresh_uid_resource_version_and_full_current_spec_tests_required':True}


def pre_start_inverse(originals,current,captures,*,node_agent_source):
    """Only exact zero-new-claim history permits the original full inverse."""
    oldnode,node,oldpolicy,olddeploy,newdeploy,_=validate_configuration_handover(
        originals,current,captures,node_agent_source)
    baseline=captures['baseline'];now=captures['current']
    old=allocation_state(baseline['ledger'],oldnode);actual=allocation_state(now['ledger'],node)
    agent.require(actual==old and baseline['ledger']['metadata']['uid']==now['ledger']['metadata']['uid'],
        'Exact original full ledger with zero new claims required for original configuration inverse')
    before=terminal.map_history(baseline['authority'],baseline['ledger'],oldnode)
    after=terminal.map_history(now['authority'],now['ledger'],node)
    agent.require(before==after and now['history']==baseline['history']
        and now['authority']['host_snapshot']['directories']==baseline['authority']['host_snapshot']['directories'],
        'Every original protected intent, enrollment, journal and immutable history must be unchanged')
    _,oldrecords=history_records(baseline,oldnode);_,newrecords=history_records(now,node)
    agent.require(physical_records(baseline,oldnode,oldrecords)==physical_records(now,node,newrecords),
        'Original full zero-charge finite/recovery witness required with no new physical entry')
    pods=now['pods'];agent.require(pods.get('apiVersion')=='v1' and pods.get('kind')=='PodList'
        and isinstance(pods.get('items'),list) and isinstance(pods.get('metadata'),dict)
        and not pods['metadata'].get('continue'),'Full current PodList required before original inverse')
    names={(row['namespace'],row['name']) for row in old.values() if row['workspace'] in transition.SCOPES.values()}
    agent.require(all((p.get('metadata',{}).get('namespace'),p.get('metadata',{}).get('name')) not in names
        for p in pods['items']),'All controlled workspace Pods must remain absent before original inverse')
    return {'enabled':False,'live_applied':False,'selection':'zero-new-claims-original-full-configuration',
        'original_configurations':{name:copy.deepcopy(cm) for name,cm in {
            'node':originals['node_config'],'cps':originals['cps']['config'],'cit':originals['cit']['config']}.items()},
        'full-terminal-authority-archive.json':before,'restored_policy_hash':oldpolicy.hash,
        'policy.patch.json':transition.replace_patch(current['policy'],'/data',current['policy']['data'],originals['policy']['data']),
        'runtime.patch.json':transition.replace_patch(current['runtime'],'/data',current['runtime']['data'],originals['runtime']['data']),
        'deployment_patches':{key:transition.replace_patch(obj,'/spec',obj['spec'],olddeploy[key]['spec'])
            for key,obj in newdeploy.items()},'source_inverse_gateway_first_required':True}
