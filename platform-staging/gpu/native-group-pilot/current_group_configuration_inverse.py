"""Pure current-group configuration inverse; Root supplies fresh complete custody.

No live calls, file reads, credential lookup, code changes or GPU actions. This
separate path replays the reviewed current-group forward proposal and preserves
all released authority while restoring the exact original policy and Hub hooks.
"""
import copy
from types import FunctionType
import current_group_historical_source as historical
import node_agent as agent
import terminal_policy_proposal as terminal
import qualification_transition_proposal as transition
import qualification_configuration_inverse as custody

FIELDS={'policy','runtime','node_config','node_deployment','gateway_deployment','cps','cit'}


def same_owner(previous,current,kind):
    old=transition.object_guard(previous,kind);now=transition.object_guard(current,kind)
    agent.require(all(now[k]==old[k] for k in ('namespace','name','uid')),
        'Full current API object must retain its exact original namespace/name/UID')


def validate_configuration_handover(proposal,originals,current,captures,original_hub_secrets,current_hub_secrets,*,node_agent_source=None):
    """Match full fresh actual readbacks to both exact pure forward intents."""
    from cps_compute.policy import Policy
    agent.closed(originals,FIELDS,'Full original current-group configuration required')
    agent.closed(current,FIELDS|{'node_code'},'Full fresh configurations and unchanged immutable node code required')
    forward=transition.current_group_configuration_intent(proposal,originals)
    hooks=transition.current_group_hub_hook_intent(proposal,forward,original_hub_secrets)
    agent.closed(current_hub_secrets,{'cps','cit'},'Both full fresh Hub Secrets required')
    for key,kind in (('policy','ConfigMap'),('runtime','Secret')):
        same_owner(originals[key],current[key],kind)
        agent.require(current[key]['data']==forward[key+'.patch.json'][-1]['value'],
            'Full current '+key+' differs from exact current-group handover')
    for source in ('node','cps','cit'):
        actual=current['node_config'] if source=='node' else current[source]['config']
        expected=forward['configurations'][source];meta=transition.object_guard(actual,'ConfigMap')
        agent.require(actual.get('immutable') is True and not actual.get('binaryData')
            and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
            and all(meta[k]==expected['metadata'][k] for k in ('namespace','name'))
            and actual['data']==expected['data'], 'Exact reviewed immutable current configuration required')
        if source!='node':
            agent.closed(current[source],{'config','deployment'},'Full fresh Hub configuration and Deployment required')
            same_owner(original_hub_secrets[source],current_hub_secrets[source],'Secret')
            agent.require(current_hub_secrets[source]['data']==hooks['secret_patches'][source][-1]['value'],
                'Full current Hub Secret differs from exact reviewed qualification hook handover')
    olddeploy=custody.deployment_objects(originals);newdeploy=custody.deployment_objects(current)
    code_plan=None
    name=custody.code_reference(olddeploy['node']['spec'])
    matches=[cm for cm in captures['baseline']['authority']['authority_maps']['items']
        if cm.get('metadata',{}).get('name')==name]
    agent.require(len(matches)==1,'One full original immutable node code authority required')
    original_code=copy.deepcopy(matches[0]);original_code.setdefault('apiVersion','v1');original_code.setdefault('kind','ConfigMap')
    if node_agent_source is not None:code_plan=historical.code_intent(proposal,originals,original_code,node_agent_source)
    for source,obj in newdeploy.items():
        same_owner(olddeploy[source],obj,'Deployment')
        expected=(code_plan['node-deployment.patch.json'][-1]['value'] if source=='node' and code_plan is not None
            else forward['deployment_patches'][source][-1]['value'])
        agent.require(obj['spec']==expected,
            'Images, code references, mounts and unrelated full Deployment fields must remain exact')
    code=current['node_code'];meta=transition.object_guard(code,'ConfigMap')
    agent.require(meta['uid']!='00000000-0000-0000-0000-000000000000','Actual created immutable code UID required')
    expected_code=original_code if code_plan is None else code_plan['node-code-configmap.json']
    agent.require(code.get('immutable') is True and original_code.get('immutable') is True
        and not code.get('binaryData') and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
        and all(meta[k]==expected_code['metadata'][k] for k in ('namespace','name'))
        and (code_plan is not None or meta['uid']==original_code['metadata']['uid'])
        and code['data']==expected_code['data']
        and custody.code_reference(newdeploy['node']['spec'])==meta['name'],
        'Only the explicit pinned one-key terminal extension may change immutable node code')
    oldnode=agent.validate_config(agent.parse(originals['node_config']['data']['config.json']))
    node=agent.validate_config(agent.parse(current['node_config']['data']['config.json']))
    oldpolicy=Policy(agent.parse(originals['policy']['data']['policy.json']))
    return oldnode,node,oldpolicy,olddeploy,newdeploy


def configuration_reference(cm,reference):
    """Require Root's actual created immutable object UID and complete data pin."""
    agent.closed(reference,{'namespace','name','uid','data_sha256','policy_hash'},
        'Closed independently reviewed actual historical configuration reference required')
    meta=transition.object_guard(cm,'ConfigMap');node=agent.validate_config(agent.parse(cm['data']['config.json']))
    agent.require(cm.get('immutable') is True and not cm.get('binaryData')
        and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
        and all(meta[k]==reference[k] for k in ('namespace','name','uid'))
        and reference['data_sha256']==agent.canonical_sha256(cm['data'])
        and reference['policy_hash']==node['policy_hash'],
        'Actual immutable current node configuration namespace/name/UID/data/policy must match')
    return copy.deepcopy(reference)


def replay_history(authority,ledger,restored,reviewed_agent):
    replay=FunctionType(terminal.map_history.__code__,dict(terminal.map_history.__globals__,agent=reviewed_agent))
    return replay(authority,ledger,restored)


def derive_inverse(proposal,originals,current,captures,approval,*,baseline_history_raw,
                   original_hub_secrets,current_hub_secrets,historical_configuration_reference,node_agent_source):
    """Prepare disabled CAS only after the exact released controlled pair is proven."""
    oldnode,node,oldpolicy,olddeploy,newdeploy=validate_configuration_handover(
        proposal,originals,current,captures,original_hub_secrets,current_hub_secrets,node_agent_source=node_agent_source)
    original_code=next(cm for cm in captures['baseline']['authority']['authority_maps']['items']
        if cm.get('metadata',{}).get('name')==custody.code_reference(olddeploy['node']['spec']))
    reviewed_agent=historical.validated_agent(original_code['data']['node_agent.py'],node_agent_source)
    fullmap,newuids=custody.validate_extension(captures,approval,oldnode,node,baseline_history_raw)
    ref=configuration_reference(current['node_config'],historical_configuration_reference)
    restored=copy.deepcopy(oldnode);archive=copy.deepcopy(fullmap)
    runtime_map={uid:copy.deepcopy(entry) for uid,entry in fullmap.items()
        if entry['policy_hash']!=oldnode['policy_hash']}
    for uid in newuids:
        agent.require(uid in runtime_map and archive[uid]['policy_hash']==node['policy_hash'],
            'Every new actual lifetime must retain distinct qualification policy authority')
        runtime_map[uid]['configuration_authority']=copy.deepcopy(ref)
        archive[uid]['configuration_authority']=copy.deepcopy(ref)
        reviewed_agent.validate_historical_configuration(current['node_config'],ref,restored,runtime_map[uid])
    restored['terminal_history']=runtime_map;reviewed_agent.validate_config(restored)
    agent.require(all(runtime_map.get(uid)==entry for uid,entry in oldnode.get('terminal_history',{}).items()),
        'Every original historical configuration pin must remain byte-equivalent')
    authority=copy.deepcopy(captures['current']['authority'])
    existing=[copy.deepcopy(cm) for cm in authority['authority_maps']['items'] if cm.get('metadata',{}).get('name')==ref['name']]
    if authority['authority_maps'].get('kind')=='ConfigMapList':
        for cm in existing:
            cm.setdefault('apiVersion','v1');cm.setdefault('kind','ConfigMap')
    agent.require(not existing or existing==[current['node_config']],
        'Full fresh captured historical configuration must equal actual created immutable object')
    if not existing:authority['authority_maps']['items'].append(copy.deepcopy(current['node_config']))
    agent.require(replay_history(authority,captures['current']['ledger'],restored,reviewed_agent)==archive,
        'Complete prior and new terminal authority archive must replay without loss')
    data=dict(originals['node_config']['data'],**{'config.json':transition.canonical(restored)})
    cm=transition.immutable_config(current['node_config'],data,'cps-native-node-qualification')
    patches={}
    for source,obj in newdeploy.items():
        desired=copy.deepcopy(olddeploy[source]['spec'])
        if source=='node':
            changed=0
            for volume in desired['template']['spec']['volumes']:
                if volume.get('name')=='code':volume['configMap']['name']=current['node_code']['metadata']['name']
                if volume.get('configMap',{}).get('name')==originals['node_config']['metadata']['name']:
                    volume['configMap']['name']=cm['metadata']['name'];changed+=1
            agent.require(changed==1,'One exact restored node configuration reference required')
        patches[source]=transition.replace_patch(obj,'/spec',obj['spec'],desired)
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'restored_policy_hash':oldpolicy.hash,'node-config.json':restored,'node-configmap.json':cm,
        'full-terminal-authority-archive.json':archive,'authority-replay.json':authority,
        'policy.patch.json':transition.replace_patch(current['policy'],'/data',current['policy']['data'],originals['policy']['data']),
        'runtime.patch.json':transition.replace_patch(current['runtime'],'/data',current['runtime']['data'],originals['runtime']['data']),
        'deployment_patches':patches,'hub_secret_patches':{source:transition.replace_patch(current_hub_secrets[source],
            '/data',current_hub_secrets[source]['data'],original_hub_secrets[source]['data']) for source in ('cps','cit')},
        'retained-node-code.json':copy.deepcopy(current['node_code']),
        'source_inverse_order':['fence-all-Starts-and-writers','fresh-complete-terminal-and-zero-proof',
            'stage-derived-immutable-original-policy-node-config','restore-original-gateway-policy-runtime-and-wait-Ready',
            'audited-Source-and-original-policy-registration-inverses','restore-original-grant-and-membership-expiry',
            'restore-original-Hub-hooks-and-Hub-and-node-references','verify-full-readbacks-and-terminal-custody'],
        'fresh_uid_resource_version_and_full_current_spec_tests_required':True,
        'fresh_uid_resource_version_and_full_current_data_tests_required':True}
