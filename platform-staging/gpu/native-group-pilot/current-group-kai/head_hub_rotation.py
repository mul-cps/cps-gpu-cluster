"""Pure paired-Hub v4 rotation intents; never apply or qualify a rollout.

One-time process/configuration rotation retains current head bindings and the
same journal lineage. Root supplies fresh captures, maintenance and readbacks.
"""
from copy import deepcopy
import re
from pathlib import Path
import image_adoption as image
from head_gateway_rotation import (_guard,_actual,_core,_reference,_mounted_head,
    _role_rules,_grow,_permissions)

HUBS=('hub:cps','hub:cit')

# Actual separately pinned stdlib-only materializer from retained2026-10-27
# Deployment captures. Hash the ENTIRE container: image, inline seed checksum,
# command, mounts, security and defaulted fields. No arbitrary helper override.
SEPARATE_HUB_INPUT_IMAGE='ghcr.io/mul-cps/cps-compute@sha256:435c080630b71dc9af7656052f96d3e038380d5a87e484b398f7c0a27e5cb466'
SEPARATE_HUB_INPUT_PINS={
    'hub:cps':'sha256:b29a2a6309f1bc8ff735c3272a98efe278b73ebf3f39f16b311138a7b24768ac',
    'hub:cit':'sha256:87fd98e298734a42ca43b9e01511ee8275b52010020427dc1a730bed555a36ca'}


def _separate_hub_input(component,helper,main_image):
    if helper['image']==main_image:return False  # Original coupled path.
    image.require(helper['image']==SEPARATE_HUB_INPUT_IMAGE
        and image.sha(helper)==SEPARATE_HUB_INPUT_PINS[component],
        'Independently pinned separate Hub input helper differs')
    return True


OPERATORS={'observer':('cps-native-system','cps-native-observer-operator','observer','cps-native-observer'),
           'writer':('cps-compute','cps-native-head-delivery','delivery','cps-compute')}

def _qualified(value,node=False,repository=None):
    repository=repository or ('cps-native-node' if node else 'cps-compute')
    image.require(isinstance(value,str) and re.fullmatch(
        'ghcr.io/mul-cps/'+repository+r'@sha256:[a-f0-9]{64}',value)
        and not value.endswith('0'*64),'Qualified immutable component image required')

def _selected(inputs,declarations):
    hub=inputs['hub_image'];_qualified(hub)
    targets={c:declarations[c]['image'] for c in image.COMPONENTS}
    targets.update({c:hub for c in HUBS})
    supplied=inputs.get('component_images')
    if supplied is None:
        image.require(all(hub!=declarations[c]['image'] for c in HUBS),
            'Distinct qualified immutable shared Hub successor image required')
    else:
        image.require(type(supplied)is dict and bool(supplied)
            and set(supplied)<=set(image.COMPONENTS),'Closed selected component images required')
        hubs=set(supplied)&set(HUBS)
        image.require(not hubs or hubs==set(HUBS) and all(supplied[c]==hub for c in HUBS),
            'Paired Hubs must match shared Hub image')
        targets.update(supplied)
    for c,value in targets.items():_qualified(value,c=='node')
    changed={c for c in targets if targets[c]!=declarations[c]['image']}
    image.require(changed in ({'gateway'},{'node'},{'gateway','node'},set(HUBS)),
        'Unsupported actual component image rotation set')
    image.require(inputs.get('personal_cpu_profile_aliases') is None or changed==set(HUBS),
        'CPU alias update requires paired Hub rotation')
    return {c:targets[c] for c in targets if c in changed}

def _operator_specs(inputs):
    selected=inputs.get('operator_images')
    if selected is None:return {}
    image.require(type(selected)is dict and bool(selected) and set(selected)<=set(OPERATORS),
        'Closed operator image selection required')
    result={}
    for label,target in selected.items():
        namespace,name,main,repository=OPERATORS[label]
        _qualified(target,repository=repository)
        dep=image._get(inputs['snapshot'],'Deployment',namespace,name);meta=_guard(dep,'Deployment')
        image.require(meta['namespace']==namespace and meta['name']==name,'Fixed operator controller identity required')
        spec=deepcopy(dep['spec']);pod=spec['template']['spec']
        image.require(pod['serviceAccountName']==name,'Fixed operator ServiceAccount required')
        container=image._one(pod['containers'],main);old=container['image'];_qualified(old,repository=repository)
        container['image']=target
        if label=='writer':
            helper=image._one(pod['initContainers'],'private-inputs')
            image.require(helper['image']==old,'Writer private-input image drift')
            helper['image']=target
        result[label]=spec
    return result

def _context(inputs):
    from cps_compute.native_observer_permissions import ObserverRelease, observe_head_permissions, role_targets
    from cps_compute.native_group_process import _template
    snapshot = inputs['snapshot']; previous = inputs['previous_release']; operators = inputs['operator_baselines']
    image.require(isinstance(snapshot, dict) and snapshot.get('version') == 1
        and set(snapshot['deployments']) == set(image.COMPONENTS)
        and image.sha(snapshot) == inputs['expected_snapshot_sha256']
        and image.sha(previous) == inputs['expected_release_sha256']
        and image.sha(operators) == inputs['expected_operator_baselines_sha256'],
        'Independent snapshot, release and operator baseline pins required')
    policy, configuration = image._context(snapshot); document = configuration.document
    aliases=inputs.get('personal_cpu_profile_aliases')
    if aliases is not None:
        image.require(type(aliases) is dict and aliases=={'cpu-default':'interactive-cpu'},
            'Exact reviewed personal CPU profile alias required')
        profile=policy.catalog['profiles'].get('interactive-cpu')
        image.require(isinstance(profile,dict) and profile.get('enabled',True) is True
            and profile.get('kind')=='interactive', 'Enabled interactive CPU profile required')
        gpu=profile.get('gpu')
        image.require(gpu.get('mode')=='none' if isinstance(gpu,dict) else str(gpu)=='0',
            'Personal CPU alias cannot select GPU resources')
        policy.resources('interactive-cpu')
    release = ObserverRelease.from_dict(previous)
    image.require(document['version'] == 4 and previous['version'] == 2
        and previous['node_configuration'] == configuration.reference.to_dict(),
        'Actual matching v4 Node and v2 observer release required')
    heads, head_names = observe_head_permissions(_core(snapshot), release, configuration, policy)
    image.require(isinstance(inputs['expected_revision'], str)
        and re.fullmatch(r'sha256:[a-f0-9]{64}', inputs['expected_revision'])
        and all(h.reference['revision'] == inputs['expected_revision'] for h in heads.values()),
        'Independently pinned current Source revision differs')
    declarations = document['component_declarations']
    _selected(inputs,declarations)
    _operator_specs(inputs)
    runtime_secret = image.secret_volume(snapshot, 'gateway', 'config')
    _guard(runtime_secret, 'Secret')
    image.require(runtime_secret.get('type') == 'Opaque' and (runtime_secret.get('immutable') is None
        or type(runtime_secret.get('immutable')) is bool), 'Existing Opaque Gateway runtime Secret required')
    runtime = image._decode(runtime_secret['data']['runtime.json']); approvals = runtime['nativeGroupApprovals']
    epoch = {k: configuration.deployment.node_pool[k] for k in ('node_uid', 'boot_id', 'driver_generation', 'gpu_uuid')}
    image.require(runtime['policy_hash'] == policy.hash and set(approvals) == {
        'enabled', 'version', 'acknowledgments', 'processes', 'driver_epoch', 'ttlSeconds', 'heads'}
        and type(approvals['version']) is int and approvals['version'] == 2 and approvals['enabled'] is True
        and set(approvals['processes']) == set(image.COMPONENTS)
        and approvals['heads'] == previous['heads'] and approvals['acknowledgments'] == document['acknowledgment_targets']
        and approvals['driver_epoch'] == epoch and type(approvals['ttlSeconds']) is int
        and 15 <= approvals['ttlSeconds'] <= 120, 'Actual dynamic runtime approval authority differs')
    for component, declaration in declarations.items():
        dep = snapshot['deployments'][component]; meta = _guard(dep, 'Deployment')
        process = {k: v for k, v in declaration.items() if k != 'service_account_uid'}
        pod = dep['spec']['template']['spec']
        image.require(image._get(snapshot, 'Deployment', meta['namespace'], meta['name']) == dep
            and all(meta[k] == process[k] for k in ('namespace', 'name', 'uid'))
            and process == approvals['processes'][component]
            and pod['serviceAccountName'] == process['service_account']
            and image._one(pod['containers'], process['container'])['image'] == process['image'],
            'Actual controller, duplicate capture or process declaration drift')
        account = image._get(snapshot, 'ServiceAccount', meta['namespace'], process['service_account'])
        image.require(_guard(account, 'ServiceAccount')['uid'] == declaration['service_account_uid'],
                      'Declared actual ServiceAccount UID differs')
        _mounted_head(snapshot, component, declaration, previous['heads'][component])
    node = snapshot['deployments']['node']; node_pod = node['spec']['template']['spec']
    image.require(previous['held_node_template_sha256'] == image.sha(_template(node)),
                  'Independent old full Node template pin differs')
    image._node_initializer_image(node_pod, declarations['node']['image'])
    image.require(image._one(node_pod['containers'], declarations['node']['container'])['command']
        == ['python', '-m', 'cps_compute.native_node.service'], 'Packaged Node service command differs')
    bootstrap = image.volume(snapshot, 'node', 'packaged-bootstrap-input'); _guard(bootstrap, 'ConfigMap')
    image.require(bootstrap['data']['release'] == 'true' and bootstrap.get('immutable') is not True,
                  'Actual released mutable old bootstrap required')
    pod = snapshot['deployments']['gateway']['spec']['template']['spec']
    main=image._one(pod['containers'],declarations['gateway']['container'])
    coordinator_env=[e for e in main.get('env',[])if e.get('name')=='CPS_NATIVE_KAI_COORDINATOR_CONFIG']
    image.require(coordinator_env==[{'name':'CPS_NATIVE_KAI_COORDINATOR_CONFIG',
        'value':'/kai-private/config/coordinator.json'}], 'Current installed Coordinator path required')
    private=image._one(pod['volumes'],'kai-private')
    image.require(private=={'name':'kai-private','emptyDir':{}},'Original private Coordinator emptyDir required')
    main_mount=image._one(main.get('volumeMounts',[]),'kai-private')
    image.require(main_mount=={'name':'kai-private','mountPath':'/kai-private','readOnly':True},
        'Read-only complete private Coordinator mount required')
    initializer=image._one(pod.get('initContainers',[]),'native-kai-private-inputs')
    image.require(initializer.get('image')==declarations['gateway']['image'],
        'Existing Coordinator initializer must retain the qualified Gateway image')
    image.require(image._one(initializer.get('volumeMounts',[]),'kai-seed')=={
        'name':'kai-seed','mountPath':'/kai-seed','readOnly':True},'Read-only complete Coordinator seed input required')
    private_mount=deepcopy(image._one(initializer.get('volumeMounts',[]),'kai-private'))
    image.require(private_mount.pop('readOnly',False) is False and private_mount=={
        'name':'kai-private','mountPath':'/kai-private'},'Writable complete initializer private output required')
    seed=image._immutable(image.volume(snapshot,'gateway','kai-seed'));_guard(seed,'ConfigMap')
    coordinator=image._parse(seed['data']['coordinator.json'])
    image.require(coordinator.get('enabled') is True and type(coordinator.get('version'))is int
        and coordinator['version']==2 and coordinator.get('mode')=='current-groups'
        and coordinator['nodeConfigurationRef']==configuration.reference.to_dict(),
        'Actual mounted Coordinator must reference current immutable Node configuration')
    for component in ('hub:cps','hub:cit'):
        hpod=snapshot['deployments'][component]['spec']['template']['spec']
        helper=image._one(hpod.get('initContainers',[]),'cps-native-kai-hub-inputs')
        _separate_hub_input(component,helper,declarations[component]['image'])
        if aliases is not None:
            main=image._one(hpod['containers'],declarations[component]['container'])
            env=main.get('env',[]);names=[row['name'] for row in env]
            literal={'name':'CPS_PERSONAL_CPU_PROFILE_ALIASES','value':image.canonical(aliases)}
            image.require(len(names)==len(set(names)) and [row for row in env if row['name']==literal['name']] in ([],[literal]),
                'Duplicate, indirect or conflicting personal CPU profile environment')
    capture = image._immutable(image.secret_volume(snapshot, 'gateway', 'capture-seed'))
    settings = image._decode(capture['data']['config.json'])
    image.require(settings['version'] == 2 and settings['approval_head'] == previous['heads']['node']
        and settings['node_process'] == approvals['processes']['node']
        and settings['node_acknowledgment'] == approvals['acknowledgments']['node'], 'Unchanged capture seed authority differs')
    publishers={}
    for component in ('gateway','hub:cps','hub:cit'):
        publisher=image._immutable(image.volume(snapshot,component,'cps-native-approval-publisher'));_guard(publisher,'ConfigMap')
        body=image._parse(publisher['data']['publisher.json'])
        image.require(set(publisher['data'])=={'publisher.json'} and set(body)=={
            'version','component','process','acknowledgment','driver_epoch','ttlSeconds'}
            and type(body['version'])is int and body['version']==1 and body['component']==component
            and body['process']==approvals['processes'][component] and body['driver_epoch']==epoch
            and body['acknowledgment']==approvals['acknowledgments'][component]
            and type(body['ttlSeconds'])is int and 15<=body['ttlSeconds']<=120,
            'Actual immutable component publisher authority differs')
        publishers[component]=(publisher,body)
    baseline = {(r['namespace'], r['name']): r for r in previous['roles']}
    image.require(set(baseline) == set(role_targets(document)), 'Exact seven component Role baselines required')
    rows = {(r['namespace'], r['name']): r['index'] for r in previous['head_get_rows']}
    for key, pinned in baseline.items():
        _role_rules(image._get(snapshot, 'Role', *key), pinned, rows[key], head_names[key[0]], component=True)
    namespaces = {d['namespace'] for d in declarations.values()}
    image.require(isinstance(operators, list) and len(operators) == 4
        and {r['namespace'] for r in operators} == namespaces, 'Four distinct namespace-local operator reader baselines required')
    for pinned in operators:
        image.require(set(pinned) == {'namespace', 'name', 'uid', 'index', 'rules'}, 'Closed independent operator Role baseline required')
        _role_rules(image._get(snapshot, 'Role', pinned['namespace'], pinned['name']), pinned,
                    pinned['index'], head_names[pinned['namespace']], component=False)
    ledger = image._get(snapshot, 'ConfigMap', configuration.deployment.authority_namespace, 'cps-native-gpu-allocations')
    state = image._parse(ledger['data']['state.json'])
    image.require(state.get('version') == 1 and isinstance(state.get('allocations'), dict)
        and all(v.get('state') == 'released' for v in state['allocations'].values()),
        'Released-only ledger capture required; actual SQL/writer fences remain Root gates')
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    terminal = ImmutableConfigMapRef.from_dict(document['terminal_index_ref'])
    terminal.validate(image._get(snapshot, 'ConfigMap', terminal.to_dict()['namespace'], terminal.to_dict()['name']))
    return policy, configuration, runtime, seed, coordinator, publishers


def prepare(snapshot,previous_release,operator_baselines,hub_image,*,expected_snapshot_sha256,
            expected_release_sha256,expected_operator_baselines_sha256,expected_revision,personal_cpu_profile_aliases=None,
            component_images=None,operator_images=None):
    inputs=deepcopy(locals())
    for key in ('personal_cpu_profile_aliases','component_images','operator_images'):
        if inputs[key] is None:inputs.pop(key)
    try:
        _,configuration,*_=_context(inputs)
        document=configuration.document
        if 'policy_transition' in document:
            document['service_image_predecessor_ref']=configuration.reference.to_dict()
        for component,value in _selected(inputs,document['component_declarations']).items():
            document['component_declarations'][component]['image']=value
        old=image._get(snapshot,'ConfigMap',configuration.reference.to_dict()['namespace'],configuration.reference.to_dict()['name'])
        return {'version':1,'kind':'head-hub-pair-rotation','inputs':inputs,
            'creates':{'node-config':image._candidate(old,'cps-native-head-config',{'config.json':image.canonical(document)})},
            'live_applied':False,'hardware_qualified':False,'journal_rotation_required':True}
    except (KeyError,TypeError,AttributeError,StopIteration):
        raise ValueError('Incomplete pinned Hub-pair successor inputs')from None


def bind_node(snapshot,prepared,actual_node_config):
    try:
        image.require(snapshot==prepared['inputs']['snapshot'] and prepared==prepare(**prepared['inputs']),
            'Exact original Hub-pair plan and captured preimages required')
        _actual(prepared['creates']['node-config'],actual_node_config)
        policy,old,runtime,seed,coordinator,publishers=_context(prepared['inputs'])
        reference=_reference(actual_node_config)
        extended=deepcopy(snapshot);meta=actual_node_config['metadata']
        extended['objects'][image._key('ConfigMap',meta['namespace'],meta['name'])]=deepcopy(actual_node_config)
        from cps_compute.native_node.config import NodeConfiguration
        new=NodeConfiguration.load(_core(extended),reference,policy)
        image.require(new.document==image._parse(prepared['creates']['node-config']['data']['config.json']),
            'Typed successor Node configuration differs')
        bootstrap=image.volume(snapshot,'node','packaged-bootstrap-input')
        data=deepcopy(bootstrap['data']);data.update({'config-ref.json':image.canonical(reference.to_dict()),'release':'false'})
        creates={'node.bootstrap':image._candidate(bootstrap,'cps-native-head-bootstrap',data,immutable=False)}
        selected=_selected(prepared['inputs'],old.document['component_declarations'])
        coordinator['nodeConfigurationRef']=reference.to_dict()
        if 'node' in selected:coordinator['epoch']['nodeProcess']['image']=selected['node']
        data=deepcopy(seed['data']);data['coordinator.json']=image.canonical(coordinator)
        creates['coordinator.seed']=image._candidate(seed,'cps-native-kai-config',data)
        specs={c:deepcopy(d['spec'])for c,d in snapshot['deployments'].items()}
        image._one(specs['node']['template']['spec']['volumes'],'packaged-bootstrap-input')['configMap']['name']=creates['node.bootstrap']['metadata']['name']
        image._one(specs['gateway']['template']['spec']['volumes'],'kai-seed')['configMap']['name']=creates['coordinator.seed']['metadata']['name']
        for component in selected:
            if component=='node':continue
            publisher,body=publishers[component];body['process']['image']=selected[component]
            creates[component+'.publisher']=image._candidate(publisher,'cps-native-approval-publisher',{'publisher.json':image.canonical(body)})
            pod=specs[component]['template']['spec'];decl=old.document['component_declarations'][component]
            main=image._one(pod['containers'],decl['container']);main['image']=selected[component]
            aliases=prepared['inputs'].get('personal_cpu_profile_aliases') if component in HUBS else None
            if aliases is not None:
                env=main.setdefault('env',[])
                literal={'name':'CPS_PERSONAL_CPU_PROFILE_ALIASES','value':image.canonical(aliases)}
                if not any(row['name']==literal['name'] for row in env):env.append(literal)
            if component in HUBS:
                helper=image._one(pod['initContainers'],'cps-native-kai-hub-inputs')
                if not _separate_hub_input(component,helper,decl['image']):
                    helper['image']=selected[component]
                # Separate materializer has no SDK dependency; retain its exact
                # original image/command/seed/mounts for forward AND inverse.
            else:
                for section,name in (('containers','approval-capture'),('initContainers','capture-private-inputs'),
                                     ('initContainers','native-kai-private-inputs')):
                    helper=image._one(pod[section],name)
                    image.require(helper['image']==decl['image'],'Gateway helper image drift')
                    helper['image']=selected[component]
            image._one(pod['volumes'],'cps-native-approval-publisher')['configMap']['name']=creates[component+'.publisher']['metadata']['name']
            runtime['nativeGroupApprovals']['processes'][component]['image']=selected[component]
        if 'node' in selected:
            pod=specs['node']['template']['spec'];decl=old.document['component_declarations']['node']
            image._one(pod['containers'],decl['container'])['image']=selected['node']
            image._node_initializer_image(pod,decl['image'],selected['node'])
            runtime['nativeGroupApprovals']['processes']['node']['image']=selected['node']
            capture=image.secret_volume(snapshot,'gateway','capture-seed')
            data=deepcopy(capture['data']);settings=image._decode(data['config.json'])
            settings['node_process']['image']=selected['node'];data['config.json']=image._encoded(settings)
            creates['gateway.capture-seed']=image._candidate(capture,'cps-native-capture-config',data)
            image._one(specs['gateway']['template']['spec']['volumes'],'capture-seed')['secret']['secretName']=creates['gateway.capture-seed']['metadata']['name']
        secret=image.secret_volume(snapshot,'gateway','config');runtime_data=deepcopy(secret['data'])
        runtime_data['runtime.json']=image._encoded(runtime)
        runtime_patch=None
        if secret.get('immutable') is True:
            creates['gateway.runtime-secret']=image._candidate(secret,'cps-native-head-hub-runtime',runtime_data)
            image._one(specs['gateway']['template']['spec']['volumes'],'config')['secret']['secretName']=creates['gateway.runtime-secret']['metadata']['name']
        else:
            runtime_patch=image._patch(secret,'/data',runtime_data)
        return {'version':1,'prepared':deepcopy(prepared),'actual_node_config':deepcopy(actual_node_config),
            'node_config_ref':reference.to_dict(),'creates':creates,'runtime_specs':specs,
            'gateway_runtime_patch':runtime_patch,
            'live_applied':False,'hardware_qualified':False}
    except (KeyError,TypeError,AttributeError,StopIteration):
        raise ValueError('Incomplete Hub-pair actual configuration binding')from None

def bind(snapshot, plan, actual_creates, *, actual_permissions=None):
    """Return CAS patches only after exact supplemental permission readbacks.

    The fixed observer subject retains its existing name-based Kubernetes RBAC
    identity. Its actual UID is validated when included in the pinned capture;
    RoleBinding itself cannot pin a ServiceAccount UID. The four original
    producer-owned operator Roles and their independent baselines stay exact.
    """
    try:
        expected = bind_node(snapshot, plan['prepared'], plan['actual_node_config'])
        image.require(plan == expected, 'Exact bound Node/config/dependent plan required')
        image.require(isinstance(actual_creates, dict) and set(actual_creates) == set(plan['creates']),
                      'Exact actual dependent CREATE readbacks required')
        for label, candidate in plan['creates'].items():
            _actual(candidate, actual_creates[label], immutable=label != 'node.bootstrap')
        inputs = plan['prepared']['inputs']; previous = inputs['previous_release']
        _, old, _, _, _, _ = _context(inputs)
        declarations = old.document['component_declarations']; node_ns = declarations['node']['namespace']
        additions = {(node_ns, 'cps-native-approval-node'): {plan['node_config_ref']['name']},
            (node_ns, 'cps-native-approval-gateway'): {plan['node_config_ref']['name']}}
        release = deepcopy(previous); release['node_configuration'] = deepcopy(plan['node_config_ref'])
        from cps_compute.native_group_process import _template
        old_template = _template(snapshot['deployments']['node'])
        new_node = deepcopy(snapshot['deployments']['node']); new_node['spec'] = deepcopy(plan['runtime_specs']['node'])
        release['held_node_template_sha256'] = image.sha(_template(new_node))
        rows = {(r['namespace'], r['name']): r['index'] for r in release['head_get_rows']}
        patches = ({'gateway.runtime-secret': deepcopy(plan['gateway_runtime_patch'])}
                   if plan['gateway_runtime_patch'] is not None else {}); roles = []
        for offset, pinned in enumerate(previous['roles']):
            key = pinned['namespace'], pinned['name']; actual = image._get(snapshot, 'Role', *key)
            trusted, desired = _grow(pinned, actual, rows[key], additions.get(key, set()))
            release['roles'][offset] = trusted
            value = deepcopy(actual); value['rules'] = desired; roles.append(value)
            if desired != actual['rules']: patches['component-role:' + '/'.join(key)] = image._patch(actual, '/rules', desired)
        operators = deepcopy(inputs['operator_baselines'])
        controllers = []
        for component, original in snapshot['deployments'].items():
            value = deepcopy(original); value['spec'] = deepcopy(plan['runtime_specs'][component]); controllers.append(value)
            if value['spec'] != original['spec']: patches[component + '.deployment'] = image._patch(original, '/spec', value['spec'])
        operator_specs=_operator_specs(inputs)
        for label,spec in operator_specs.items():
            original=image._get(snapshot,'Deployment',*OPERATORS[label][:2])
            if spec!=original['spec']:patches[label+'.deployment']=image._patch(original,'/spec',spec)
        maps = {image._key('ConfigMap', o['metadata']['namespace'], o['metadata']['name']): deepcopy(o)
                for o in snapshot['objects'].values() if o['kind'] == 'ConfigMap'}
        for value in [plan['actual_node_config'], *actual_creates.values()]:
            if value['kind'] != 'ConfigMap': continue
            maps[image._key('ConfigMap', value['metadata']['namespace'], value['metadata']['name'])] = deepcopy(value)
        from cps_compute.native_observer_permissions import ObserverRelease
        ObserverRelease.from_dict(release)
        permissions, verified_permissions, observer_account = _permissions(snapshot, plan, actual_creates, actual_permissions)
        pending = actual_permissions is None
        return {**({'operator_specs':operator_specs} if 'operator_images' in inputs else {}),
            'version': 1, 'observer_release': release, 'prospective_capture': {'version': 1,
            'configmaps': list(maps.values()), 'deployments': controllers, 'roles': roles},
            'creates': permissions, 'permissions_pending': pending,
            'actual_permissions': verified_permissions, 'observer_service_account': observer_account,
            'patches': {} if pending else patches, 'operator_baselines': operators,
            'actual_coordinator_seed': deepcopy(actual_creates['coordinator.seed']), 'node_config_ref': deepcopy(plan['node_config_ref']),
            'previous_node_template': old_template, 'previous_node_template_sha256': image.sha(old_template),
            'runtime_specs': deepcopy(plan['runtime_specs']), 'prospective': True, 'live_applied': False,
            'hardware_qualified': False, 'process_readiness_verified': False,
            'actual_only_render_required': True, 'journal_rotation_required': True}
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise ValueError('Incomplete actual Hub-pair dependent readbacks') from None
