"""Pinned terminal-only adaptation of the actual recovery-enabled node agent.

This changes no driver, controller, active allocation or qualification gate. A
retained immutable 5/20 configuration can validate only finite released history
when the exact reviewed shared 5/10 policy is restored.
"""
import copy
import hashlib
from types import SimpleNamespace
import node_agent as agent
import historical_configuration_source as prior
import qualification_transition_proposal as transition

ORIGINAL_SHA256=prior.ORIGINAL_SHA256
EXTENSION_SHA256=prior.EXTENSION_SHA256
RESTORED_POLICY='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
QUALIFICATION_POLICY='sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012'


def historical_validator_source(old):
    new=prior.once(old,"config['mode'] == old['mode'] == 'operator-qualification'",
        "config['mode'] == 'qualified-group' and old['mode'] == 'operator-qualification'\n"
        "            and config['policy_hash'] == '"+RESTORED_POLICY+"'\n"
        "            and old['policy_hash'] == '"+QUALIFICATION_POLICY+"'")
    new=prior.once(new,"'cps:native-group-b': {'profile':'interactive-native-qualification-5', 'cap_mib':5120},\n"
        "                'cit:native-group-a': {'profile':'interactive-native-qualification-10', 'cap_mib':10240}",
        "'cps:native-group-b': {'profile':'interactive-shared-5', 'cap_mib':5120},\n"
        "                'cit:native-group-a': {'profile':'interactive-shared-10', 'cap_mib':10240}")
    return new


def extend_source(original,extension):
    source=prior.extend_source(original,extension)
    old=prior.definitions(source)['validate_historical_configuration']
    new=historical_validator_source(old)
    source=prior.once(source,old,new)
    before=prior.definitions(original);after=prior.definitions(source)
    agent.require(set(after)==set(before)|{'validate_configuration_reference','validate_historical_configuration'}
        and all(after[name]==text for name,text in before.items()
            if name not in ('validate_config','validate_authority_enrollments')),
        'All original active, recovery, cleanup and source-loader definitions must remain exact')
    compile(source,'reviewed-current-group-terminal-history-agent.py','exec')
    return source


def validated_agent(original,extension):
    """Evaluate only four pinned pure validators, never an agent entrypoint."""
    definitions=prior.definitions(extend_source(original,extension));namespace=dict(vars(agent))
    for name in ('validate_config','validate_configuration_reference','validate_historical_configuration'):
        exec(compile(definitions[name],'<pinned-pure-terminal-validator>','exec'),namespace)
    return SimpleNamespace(**namespace)


def code_intent(proposal,originals,original_code,extension):
    """Separate disabled one-key code and coordinated full node-spec CAS intent."""
    forward=transition.current_group_configuration_intent(proposal,originals)
    meta=transition.object_guard(original_code,'ConfigMap')
    agent.require(meta['namespace']==originals['node_deployment']['metadata']['namespace']
        and original_code.get('immutable') is True and not original_code.get('binaryData')
        and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'),
        'Actual immutable original code object required')
    data=copy.deepcopy(original_code['data']);data['node_agent.py']=extend_source(data['node_agent.py'],extension)
    cm=transition.immutable_config(original_code,data,'cps-native-node-code')
    spec=copy.deepcopy(forward['deployment_patches']['node'][-1]['value']);changed=0
    for volume in spec['template']['spec']['volumes']:
        if volume.get('name')=='code' and volume.get('configMap',{}).get('name')==meta['name']:
            volume['configMap']['name']=cm['metadata']['name'];changed+=1
    agent.require(changed==1,'One exact existing immutable node code reference required')
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'node-code-configmap.json':cm,'node-deployment.patch.json':transition.replace_patch(
            originals['node_deployment'],'/spec',originals['node_deployment']['spec'],spec),
        'one_key_diff':['node_agent.py'],'original_agent_sha256':ORIGINAL_SHA256,
        'extension_source_sha256':EXTENSION_SHA256,
        'prospective_agent_sha256':hashlib.sha256(data['node_agent.py'].encode()).hexdigest(),
        'controller_images_driver_and_all_other_source_files_unchanged':True,
        'readback_uid_resource_version_and_full_data_required':True}
