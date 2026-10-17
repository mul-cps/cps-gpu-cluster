"""Pure private v3-to-v4 runtime composition. No API or process operations.

Compose this proposal with the independently reviewed observer release before
applying any patch. Actual staged UID readbacks are required at both phases.
"""
from copy import deepcopy
import image_adoption as image
import head_bootstrap as heads


def prepare(snapshot,pointers,anchors,bindings,actual_node_config,*,expected_snapshot_sha256):
    try:
        return _prepare(snapshot,pointers,anchors,bindings,actual_node_config,expected_snapshot_sha256)
    except (KeyError,TypeError,AttributeError,StopIteration):
        raise ValueError('Incomplete coordinated head runtime snapshot') from None


def _prepare(snapshot,pointers,anchors,bindings,actual_node_config,expected_snapshot_sha256):
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    image.require(snapshot.get('version')==1 and image.sha(snapshot)==expected_snapshot_sha256,
        'Exact independently pinned preimage snapshot required')
    policy,configuration=image._context(snapshot)
    for deployment in snapshot['deployments'].values():
        meta=image._guard(deployment,'Deployment')
        image.require(image._get(snapshot,'Deployment',meta['namespace'],meta['name'])==deployment,
            'Duplicate controller capture differs from runtime preimage')
    approvals={c:image.volume(snapshot,c,'cps-native-approval-document') for c in image.COMPONENTS}
    bound=heads.bind(configuration,approvals,policy,pointers,anchors)
    heads._readback(bound['node_configuration'],actual_node_config,immutable=True)
    meta=actual_node_config['metadata']
    reference=ImmutableConfigMapRef.from_dict({**{k:meta[k] for k in ('namespace','name','uid','resourceVersion')},
        'key':'config.json','data_sha256':image.sha(actual_node_config['data'])})
    reference.validate(actual_node_config)
    ledger=image._get(snapshot,'ConfigMap',configuration.deployment.authority_namespace,'cps-native-gpu-allocations')
    state=image._parse(ledger['data']['state.json'])
    image.require(isinstance(state.get('allocations'),dict) and
        all(v.get('state')=='released' for v in state['allocations'].values()),'Migration requires all claims released')
    runtime_secret=image.secret_volume(snapshot,'gateway','config')
    image.require(runtime_secret.get('type')=='Opaque' and runtime_secret.get('immutable') is not True,
        'Actual mutable Opaque Gateway runtime Secret required')
    runtime=image._decode(runtime_secret['data']['runtime.json'])
    image.require(runtime['policy_hash']==policy.hash,'Gateway runtime policy differs')
    updated=deepcopy(runtime)
    updated['nativeGroupApprovals']=heads.readiness_settings(configuration,approvals,policy,pointers,anchors,
        runtime['nativeGroupApprovals'])
    data=deepcopy(runtime_secret['data']);data['runtime.json']=image._encoded(updated)
    runtime_patch=image._patch(runtime_secret,'/data',data)
    seed=image._immutable(image.secret_volume(snapshot,'gateway','capture-seed'))
    image.require(seed.get('type')=='Opaque','Actual Opaque capture Secret required')
    settings=image._decode(seed['data']['config.json'])
    image.require(set(settings)=={'version','database','policy_json','qualification_json','token_file',
        'node_acknowledgment','node_process','ttl_seconds','host','port','tls_cert_file','tls_key_file'}
        and type(settings['version']) is int and settings['version']==1,
        'Closed legacy capture configuration required')
    image.require(settings['node_acknowledgment']==runtime['nativeGroupApprovals']['acknowledgments']['node']
        and settings['node_process']==runtime['nativeGroupApprovals']['processes']['node'],
        'Capture and runtime Node authorities differ')
    from pathlib import PurePosixPath
    image.require(all(isinstance(settings[k],str) and PurePosixPath(settings[k]).is_absolute()
        for k in ('database','policy_json','qualification_json','token_file','tls_cert_file','tls_key_file'))
        and type(settings['ttl_seconds']) is int and 15<=settings['ttl_seconds']<=120
        and isinstance(settings['host'],str) and bool(settings['host'])
        and type(settings['port']) is int and 1<=settings['port']<=65535,'Valid existing private capture paths and limits required')
    capture=deepcopy(settings);capture.update(version=2,approval_head=bound['heads']['node'])
    seed_data=deepcopy(seed['data']);seed_data['config.json']=image._encoded(capture)
    capture_candidate=image._candidate(seed,'cps-native-head-capture',seed_data)
    old_bootstrap=image.volume(snapshot,'node','packaged-bootstrap-input')
    bootstrap_data=deepcopy(old_bootstrap['data'])
    bootstrap_data.update({'config-ref.json':image.canonical(reference.to_dict()),'release':'false'})
    bootstrap=image._candidate(old_bootstrap,'cps-native-head-bootstrap',bootstrap_data,immutable=False)
    mounts=heads.bind_runtime(configuration,approvals,policy,pointers,anchors,bindings,snapshot['deployments'])
    specs={c:p[-1]['value'] for c,p in mounts.items()}
    image._one(specs['node']['template']['spec']['volumes'],'packaged-bootstrap-input')['configMap']['name']=bootstrap['metadata']['name']
    image._one(specs['gateway']['template']['spec']['volumes'],'capture-seed')['secret']['secretName']=capture_candidate['metadata']['name']
    return {'version':1,'snapshot_sha256':expected_snapshot_sha256,'heads':bound['heads'],
        'node_config_ref':reference.to_dict(),'creates':{'node.bootstrap':bootstrap,'gateway.capture-seed':capture_candidate},
        'runtime_specs':specs,'gateway_runtime_patch':runtime_patch,'live_applied':False,'hardware_qualified':False}


def bind(snapshot,pointers,anchors,bindings,actual_node_config,*,plan,actual_creates):
    image.require(plan==prepare(snapshot,pointers,anchors,bindings,actual_node_config,
        expected_snapshot_sha256=plan['snapshot_sha256']),'Exact unmodified prepared plan required')
    image.require(isinstance(actual_creates,dict) and set(actual_creates)==set(plan['creates']),
        'Actual two staged readbacks required')
    for label,candidate in plan['creates'].items():
        value=actual_creates[label];meta=image._guard(value,candidate['kind'])
        image.require(all(meta[k]==candidate['metadata'][k] for k in ('namespace','name'))
            and not meta.get('ownerReferences') and value.get('data')==candidate['data']
            and value.get('type')==candidate.get('type') and not value.get('binaryData')
            and (value.get('immutable') is True if candidate.get('immutable') is True
                 else value.get('immutable') in (None,False)), 'Actual staged object differs')
    return {c:image._patch(snapshot['deployments'][c],'/spec',spec)['patch'] for c,spec in plan['runtime_specs'].items()}
