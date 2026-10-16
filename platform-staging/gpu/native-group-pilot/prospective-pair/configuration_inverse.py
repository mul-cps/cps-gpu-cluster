"""Offline terminal Node inverse for the exact Root-pinned fresh CPS5+20 pair.

Returns inert artifacts only. Does not change the legacy CPS+CIT inverse or
perform API, driver, credential, deployment or Source mutations.
"""
import copy
import hashlib
from types import FunctionType, ModuleType
import sys

import node_agent as frozen
import node_successor
import qualification_configuration_inverse as custody
import qualification_transition_proposal as transition
import terminal_policy_proposal as terminal


def reviewed(raw, pin):
    frozen.require(isinstance(raw, bytes) and len(raw) <= 65536
        and hashlib.sha256(raw).hexdigest() == pin, 'Independently pinned bounded approval bytes required')
    return frozen.parse(raw)


def immutable_node(cm, agent):
    meta = transition.object_guard(cm, 'ConfigMap')
    frozen.require(cm.get('apiVersion') == 'v1' and cm.get('immutable') is True
        and not cm.get('binaryData') and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'),
        'Actual immutable Node configuration required')
    frozen.closed(cm.get('data'), {'config.json'}, 'Single complete Node configuration required')
    node = agent.validate_config(agent.parse(cm['data']['config.json']))
    frozen.require(meta['namespace'] == node['authority_namespace']
        and meta['uid'] != '00000000-0000-0000-0000-000000000000',
        'Actual nonzero Node configuration ownership in its authority namespace required')
    return node


def _derive_node_inverse(*, expected_added, original, current, baseline, final, contract_raw, contract_sha256,
                        approval_raw, approval_sha256, original_node_source, original_epoch_source, now_ns):
    contract = node_successor.validate_contract(contract_raw, contract_sha256)
    bundle = node_successor.successor_bundle(original_node_source, original_epoch_source, contract_raw, contract_sha256)
    agent = ModuleType('reviewed_prospective_pair_inverse_node')
    agent.__file__ = frozen.__file__
    sys.modules[agent.__name__] = agent
    exec(compile(bundle['node_agent.py'], '<reviewed-prospective-pair-node>', 'exec'), agent.__dict__)
    old = immutable_node(original, agent); node = immutable_node(current, agent)
    frozen.require(old['mode'] == 'qualified-group' and old['enabled'] is True
        and old['policy_hash'] == 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
        and node['mode'] == 'operator-qualification' and node['enabled'] is True
        and node['policy_hash'] == contract['policy_hash'] and node['workspaces'] == contract['workspaces']
        and all(node['terminal_history'].get(u) == e for u,e in old['terminal_history'].items())
        and agent.canonical_sha256(node['terminal_history']) == contract['terminal_history_sha256']
        and node['authority_namespace'] == old['authority_namespace']
        and old['pool']['memory_budget_mib'] == 15360 and node['pool']['memory_budget_mib'] == 25600
        and node['pool']['max_workspaces'] == old['pool']['max_workspaces'] == 2
        and node['pool']['headroom_mib'] == old['pool']['headroom_mib'] == 1024
        and node['pool']['free_memory_mib'] >= 26624
        and all(node['pool'][k] == old['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation','total_memory_mib')),
        'Exact Root-pinned pair and unchanged original D48 physical epoch required')
    frozen.closed(baseline, {'authority','ledger','history','physical'}, 'Complete original custody required')
    frozen.closed(final, {'authority','ledger','history','physical','pods'}, 'Complete fresh terminal custody required')
    approval = reviewed(approval_raw, approval_sha256)
    frozen.closed(approval, {'version','original_data_sha256','current_data_sha256','baseline_ledger_sha256','claims'},
        'Closed independently reviewed pair restoration approval required')
    frozen.require(type(approval['version']) is int and approval['version'] == 1
        and approval['original_data_sha256'] == agent.canonical_sha256(original['data'])
        and approval['current_data_sha256'] == agent.canonical_sha256(current['data'])
        and approval['baseline_ledger_sha256'] == hashlib.sha256(baseline['ledger']['data']['state.json'].encode()).hexdigest(),
        'Reviewed original/current configuration and complete baseline ledger pins required')
    oldrows = custody.allocation_state(baseline['ledger'], old)
    rows = custody.allocation_state(final['ledger'], node)
    frozen.require(all(final['ledger']['metadata'][k] == baseline['ledger']['metadata'][k] for k in ('namespace','name','uid'))
        and set(oldrows) <= set(rows) and all(rows[k] == v for k,v in oldrows.items()),
        'Every original released allocation and ledger ownership must survive unchanged')
    added = [r for k,r in rows.items() if k not in oldrows]
    claims = approval['claims']
    frozen.require(isinstance(claims,list) and len(claims) == 2 and len(added) == expected_added,
        'Exactly two independently reviewed new claims required')
    for claim in claims:
        frozen.closed(claim, custody.IDENTITY, 'Complete reviewed Source claim identity required')
    frozen.require({c['source']+':'+c['workspace'] for c in claims} == set(contract['workspaces']),
        'Exactly the two pinned CPS workspace scopes required')
    new_uids = set(); names = set()
    for claim in claims:
        scope = claim['source']+':'+claim['workspace']; profile = contract['workspaces'][scope]
        frozen.require(claim['source'] == 'cps' and claim['namespace'] == 'jupyterhub'
            and claim['profile'] == profile['profile'] and claim['cap_mib'] == profile['cap_mib']
            and claim['policy_hash'] == node['policy_hash']
            and claim['members'] == sorted(contract['operator_members'][scope])
            and claim['ceiling'] == {'cpu':'4','memory':'16Gi','gpuMemoryGiB':profile['cap_mib']//1024},
            'Exact reviewed operator people, profile, ceiling and policy required')
        matches = [r for r in added if all(r[k] == v for k,v in claim.items())]
        if not matches and expected_added < 2:
            name = (claim['namespace'],claim['name'])
            frozen.require(name not in names, 'Distinct independently reviewed unstarted Pod names required')
            names.add(name)
            continue
        frozen.require(len(matches) == 1 and isinstance(matches[0]['intent'],dict),
            'Each approved Source identity requires one distinct complete released enrolled claim')
        row = matches[0]; pod_uid = row['intent']['pod_uid']; name = (row['namespace'],row['name'])
        frozen.require(pod_uid not in new_uids and name not in names
            and pod_uid not in {r['intent']['pod_uid'] for r in oldrows.values() if r['intent'] is not None},
            'Distinct fresh pair Pod UIDs and names required')
        new_uids.add(pod_uid); names.add(name)
    frozen.require(len(new_uids) == expected_added, 'Every added claim must match one reviewed pair member')
    mapper = FunctionType(terminal.map_history.__code__, dict(terminal.map_history.__globals__, agent=agent))
    oldmap = mapper(baseline['authority'],baseline['ledger'],old)
    frozen.require(node['terminal_history'] == oldmap,
        'Prospective history must equal the complete verified baseline, including original-policy lifetimes')
    fullmap = mapper(final['authority'],final['ledger'],node)
    frozen.require(set(fullmap) == set(oldmap)|new_uids and all(fullmap[k] == v for k,v in oldmap.items()),
        'Complete old terminal authority must remain unchanged; only the exact pair may grow')
    for directory in ('enrollments','intents','journal'):
        previous = baseline['authority']['host_snapshot']['directories'][directory]
        fresh = final['authority']['host_snapshot']['directories'][directory]
        oldfiles = terminal.protected_records(previous); newfiles = terminal.protected_records(fresh)
        frozen.require(previous['ownerUid'] == fresh['ownerUid'] and previous['mode'] == fresh['mode']
            and set(newfiles) == set(oldfiles)|new_uids and all(newfiles[k] == v for k,v in oldfiles.items()),
            'All original protected raw files must remain exact with only the new pair added')
    oldhistory, oldrecords = custody.history_records(baseline, old)
    history, records = custody.history_records(final, node)
    frozen.require(set(history) == set(oldhistory)|new_uids and all(history[k] == v for k,v in oldhistory.items())
        and {k:v for k,v in baseline['history'].items() if k!='records'} == {k:v for k,v in final['history'].items() if k!='records'},
        'Complete immutable journal history and original recovery must survive exactly')
    previous = custody.physical_records(baseline,old,oldrecords)
    physical = custody.physical_records(final,node,records)
    frozen.require(set(physical) == set(previous)|new_uids and all(physical[k] == v for k,v in previous.items())
        and all(records[u].state == 'retired-inert-cap' for u in new_uids)
        and len({records[u].identity.cgroup_inode for u in new_uids}) == expected_added
        and type(now_ns) is int and now_ns >= final['physical']['observed_at_ns'] >= baseline['physical']['observed_at_ns']
        and now_ns-final['physical']['observed_at_ns'] <= 60_000_000_000,
        'Distinct finite zero-charge retirements and fresh complete physical witness required')
    pods = final['pods']
    frozen.require(pods.get('apiVersion') == 'v1' and pods.get('kind') == 'PodList'
        and isinstance(pods.get('items'),list) and isinstance(pods.get('metadata'),dict) and not pods['metadata'].get('continue'),
        'Complete unpaginated PodList required')
    for pod in pods['items']:
        meta = pod.get('metadata',{})
        frozen.require(agent.canonical_uuid(meta.get('uid')) and meta['uid'] not in new_uids
            and (meta.get('namespace'),meta.get('name')) not in names, 'Pair and replacement Pods must be absent')
    reference = {k:current['metadata'][k] for k in ('namespace','name','uid')}
    reference.update(data_sha256=agent.canonical_sha256(current['data']), policy_hash=node['policy_hash'])
    restored = copy.deepcopy(old); archive = copy.deepcopy(fullmap)
    restored['terminal_history'] = {u:copy.deepcopy(e) for u,e in fullmap.items() if e['policy_hash'] != old['policy_hash']}
    for u in new_uids:
        restored['terminal_history'][u]['configuration_authority'] = copy.deepcopy(reference)
        archive[u]['configuration_authority'] = copy.deepcopy(reference)
        agent.validate_historical_configuration(current,reference,restored,archive[u])
    agent.validate_config(restored)
    frozen.require(all(restored['terminal_history'].get(u) == e for u,e in old['terminal_history'].items()),
        'Original historical references must survive byte-equivalently')
    authority = copy.deepcopy(final['authority'])
    existing = [c for c in authority['authority_maps']['items'] if c.get('metadata',{}).get('name') == reference['name']]
    frozen.require(not existing or existing == [current], 'Retained immutable pair configuration must match actual created object')
    if not existing: authority['authority_maps']['items'].append(copy.deepcopy(current))
    frozen.require(mapper(authority,final['ledger'],restored) == archive, 'Full authority must replay under the restored original policy')
    cm = transition.immutable_config(current,{'config.json':transition.canonical(restored)},'cps-native-node-qualification')
    return dict(version=1,enabled=False,live_applied=False,hardware_qualified=False,
        **{'node-config.json':restored,'node-configmap.json':cm,'full-terminal-authority-archive.json':archive,
           'authority-replay.json':authority,'retained-node-source-bundle':bundle})


def derive_node_inverse(**inputs):
    """Post-stop inverse: exactly the two new released lifetimes must exist."""
    return _derive_node_inverse(expected_added=2, **inputs)


def derive_unstarted_node_inverse(**inputs):
    """Pre-start unwind: no allocation or protected-history growth is allowed."""
    return _derive_node_inverse(expected_added=0, **inputs)


def derive_partial_node_inverse(**inputs):
    """Failure unwind: exactly one approved started lifetime must be released."""
    return _derive_node_inverse(expected_added=1, **inputs)


def derive_node_handover_inverse(*, terminal_inputs, original_deployment, current_deployment, original_code, current_code, phase='complete'):
    """Return spec-CAS only for the exact Node configuration/code handover."""
    frozen.require(type(phase) is str and phase in ('unstarted','partial','complete'), 'Explicit bounded restoration phase required')
    derive = {'unstarted':derive_unstarted_node_inverse,'partial':derive_partial_node_inverse,'complete':derive_node_inverse}[phase]
    result = derive(**terminal_inputs)
    result['restoration_phase'] = phase
    bundle = result['retained-node-source-bundle']
    for code in (original_code,current_code):
        meta = transition.object_guard(code,'ConfigMap')
        frozen.require(code.get('apiVersion') == 'v1' and code.get('immutable') is True
            and not code.get('binaryData') and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
            and meta['namespace'] == terminal_inputs['original']['metadata']['namespace']
            and isinstance(code.get('data'),dict), 'Actual retained immutable Node source ConfigMaps required')
    frozen.require(original_code['data'].get('node_agent.py') == terminal_inputs['original_node_source'].decode()
        and original_code['data'].get('native_operator_epoch.py') == terminal_inputs['original_epoch_source'].decode()
        and current_code['data'] == dict(original_code['data'],**bundle),
        'Only exact Root-contract generated Node/epoch code may change; all other source bytes remain exact')
    before = transition.object_guard(original_deployment,'Deployment')
    now = transition.object_guard(current_deployment,'Deployment')
    frozen.require(original_deployment.get('apiVersion') == current_deployment.get('apiVersion') == 'apps/v1'
        and all(now[k] == before[k] for k in ('namespace','name','uid'))
        and now['namespace'] == current_code['metadata']['namespace'],
        'Actual original Node Deployment ownership must survive')
    expected = copy.deepcopy(original_deployment['spec'])
    code_count = config_count = 0
    for volume in expected['template']['spec']['volumes']:
        if volume.get('name') == 'code' and volume.get('configMap',{}).get('name') == original_code['metadata']['name']:
            volume['configMap']['name'] = current_code['metadata']['name']; code_count += 1
        if volume.get('configMap',{}).get('name') == terminal_inputs['original']['metadata']['name']:
            volume['configMap']['name'] = terminal_inputs['current']['metadata']['name']; config_count += 1
    frozen.require(code_count == config_count == 1 and current_deployment['spec'] == expected,
        'Node handover may change only one exact code and one exact configuration reference')
    retained_code = original_code if phase == 'unstarted' else current_code
    desired = copy.deepcopy(original_deployment['spec'])
    for volume in desired['template']['spec']['volumes']:
        if volume.get('name') == 'code': volume['configMap']['name'] = retained_code['metadata']['name']
        if volume.get('configMap',{}).get('name') == terminal_inputs['original']['metadata']['name']:
            volume['configMap']['name'] = result['node-configmap.json']['metadata']['name']
    result['node-deployment.patch.json'] = transition.replace_patch(current_deployment,'/spec',current_deployment['spec'],desired)
    result['retained-node-code.json'] = copy.deepcopy(retained_code)
    return result
