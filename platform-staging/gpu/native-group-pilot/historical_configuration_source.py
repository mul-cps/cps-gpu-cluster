"""Pure pinned terminal-only extension of the currently deployed recovery agent.

The older local unit-fixture agent must never replace the deployed806 recovery
agent. Only its validated terminal configuration logic is transferred; all
other deployed functions and pins remain byte-identical.
"""
import ast
import hashlib
import node_agent as agent

ORIGINAL_SHA256 = '34ce5b9bb8d48aa3459c151acc19464772e498a8946c7f621fed73abc5b0ba5a'
EXTENSION_SHA256 = 'c1f2893e6c9f4f1e199578fe145a3132f509191c4233a38b28cb7a9a641a4a12'


def definitions(source):
    lines=source.splitlines(True)
    return {node.name:''.join(lines[node.lineno-1:node.end_lineno])
        for node in ast.parse(source).body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}


def once(source,old,new):
    agent.require(source.count(old)==1,'One exact pinned source integration hook required')
    return source.replace(old,new,1)


def extend_source(original,extension):
    agent.require(isinstance(original,str) and hashlib.sha256(original.encode()).hexdigest()==ORIGINAL_SHA256,
        'Exact deployed recovery-enabled node source required')
    agent.require(isinstance(extension,str) and hashlib.sha256(extension.encode()).hexdigest()==EXTENSION_SHA256,
        'Exact independently reviewed finite terminal extension source required')
    old=definitions(original);new=definitions(extension)
    source=once(original,old['validate_config'],new['validate_config'])
    helpers='\n\n'+new['validate_configuration_reference']+'\n\n'+new['validate_historical_configuration']+'\n\n'
    source=once(source,old['validate_measured_pool'],helpers+old['validate_measured_pool'])
    fn=old['validate_authority_enrollments']
    first=fn.index("        old = {key: config[key] for key in ('enabled', 'authority_namespace')}")
    last=fn.index('        envelope = validate_enrollment(cm, old, models)',first)
    nf=new['validate_authority_enrollments']
    nfirst=nf.index("        reference = entry.get('configuration_authority')")
    nlast=nf.index('        envelope = validate_enrollment(cm, old, models)',nfirst)
    fn=once(fn,fn[first:last],nf[nfirst:nlast])
    first=nf.index('            if reference is not None:',nf.index('        for _ in range(2):'))
    last=nf.index('            actual = kube.configmap(',first)
    fn=once(fn,'        for _ in range(2):\n','        for _ in range(2):\n'+nf[first:last])
    first=nf.index('            if reference is not None:',nf.index('            record = journal.read(uid)'))
    last=nf.index("            if entry['completion_kind'] == 'cleanup':",first)
    fn=once(fn,'            record = journal.read(uid)\n','            record = journal.read(uid)\n'+nf[first:last])
    source=once(source,old['validate_authority_enrollments'],fn)
    parsed=definitions(source)
    agent.require(set(parsed)==set(old)|{'validate_configuration_reference','validate_historical_configuration'}
        and all(parsed[name]==value for name,value in old.items()
            if name not in ('validate_config','validate_authority_enrollments')),
        'All existing recovery, active-capacity, cleanup, gate and source-loader definitions must remain exact')
    # Recovering806 is still handled through the original narrow proof path.
    agent.require("'recovered-cleared-offline-cap'" in parsed['validate_authority_enrollments']
        and "RECOVERY_SOURCE_PIN = '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b'" in source,
        'Original distinct recovery handling must remain pinned')
    compile(source,'reviewed-terminal-history-node-agent.py','exec')
    return source


def code_handover(original_code,current_deployment,extension):
    """Create/spec-CAS request only. No Kubernetes operation is performed."""
    import copy
    import qualification_transition_proposal as transition
    meta=transition.object_guard(original_code,'ConfigMap')
    agent.require(original_code.get('immutable') is True and not original_code.get('binaryData')
        and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'),
        'Actual original immutable code authority required')
    data=copy.deepcopy(original_code['data'])
    data['node_agent.py']=extend_source(data['node_agent.py'],extension)
    cm=transition.immutable_config(original_code,data,'cps-native-node-code')
    spec=copy.deepcopy(current_deployment['spec']);changed=0
    for volume in spec['template']['spec']['volumes']:
        if volume.get('name')=='code' and volume.get('configMap',{}).get('name')==meta['name']:
            volume['configMap']['name']=cm['metadata']['name'];changed+=1
    agent.require(changed==1,'One exact currently deployed code reference required')
    return {'enabled':False,'live_applied':False,'node-code-configmap.json':cm,
        'node-deployment.patch.json':transition.replace_patch(current_deployment,'/spec',current_deployment['spec'],spec),
        'one_key_diff':['node_agent.py'],'original_data_sha256':agent.canonical_sha256(original_code['data']),
        'original_agent_sha256':ORIGINAL_SHA256,'extension_source_sha256':EXTENSION_SHA256,
        'prospective_agent_sha256':hashlib.sha256(data['node_agent.py'].encode()).hexdigest(),
        'readback_uid_resource_version_and_full_data_required':True}
