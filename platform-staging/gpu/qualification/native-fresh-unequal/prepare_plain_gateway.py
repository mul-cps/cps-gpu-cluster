"""Offline temporary-Gateway proposal from full actual preimages; no executor.

No Secret bytes are emitted. Caller supplies new object names, never fabricated
UIDs. Actual PVC attachment, TLS identity, dedicated-principal admission/RBAC,
central grants/storage and legacy Node compatibility remain external hard gates.
"""
import copy
import hashlib
import json
import re

IMAGE='ghcr.io/mul-cps/cps-compute@sha256:0e215c9c5767b4162ae0e57ff3f1614ad16be144c57b19a187f7c6cbe6bdb8cd'
PREVIOUS_IMAGE='ghcr.io/mul-cps/cps-compute@sha256:5f1dd4f55710f1cdf97d24a1165b265681c61c67578680b8f5ef8bd67a34fc3c'
def require(ok,message):
    if not ok:raise ValueError(message)
def digest(x):return 'sha256:'+hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def named(rows):
    require(type(rows) is list and all(type(x) is dict and type(x.get('name')) is str for x in rows),'Named actual rows required')
    out={x['name']:x for x in rows};require(len(out)==len(rows),'Duplicate named actual rows');return out

def prepare(*,deployment,runtime,pilot,tls_secret_ref,ca_configmap_ref,policy_configmap_ref,
            runtime_secret_ref,new_name,selected_state_node,credential_secret_metadata=None,fresh_provisioning=None):
    require(type(deployment) is dict and deployment.get('apiVersion')=='apps/v1'
            and deployment.get('kind')=='Deployment','Full actual Gateway Deployment required')
    meta=deployment.get('metadata',{})
    require(meta.get('namespace')=='cps-compute' and meta.get('name')=='compute-gateway'
            and all(type(meta.get(k)) is str and meta[k] for k in ('uid','resourceVersion'))
            and not meta.get('deletionTimestamp'),'Current Gateway identity/preimage required')
    require(type(new_name) is str and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?',new_name)
            and len(new_name)<=63 and new_name!=meta['name'],'Distinct temporary name required')
    require(selected_state_node=='k3s-wk-gpu1','Actual canonical RWO attachment node GPU1 required')
    refs=[tls_secret_ref,ca_configmap_ref,policy_configmap_ref,runtime_secret_ref]
    require(all(type(r) is dict and set(r)=={'namespace','name'} and r['namespace']=='cps-compute'
            and type(r['name']) is str and re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?',r['name']) for r in refs),
            'Explicit same-namespace new named object references required')
    require(len({r['name'] for r in refs})==4,'Separate TLS/CA/policy/runtime references required')
    require(type(runtime) is dict and runtime.get('state_directory')=='/data'
            and type(pilot) is dict and pilot.get('proposal_only') is True
            and pilot.get('production_qualified') is False and pilot.get('lifecycle_runnable') is False
            and pilot.get('runtime',{}).get('state_directory')=='/data'
            and pilot['runtime'].get('nativeGpuPilot',{}).get('enabled') is True,
            'Validated but nonauthorizing pilot projection and canonical runtime required')
    policy_hash=pilot.get('policy',{}).get('policyHash')
    require(type(policy_hash) is str and re.fullmatch(r'sha256:[a-f0-9]{64}',policy_hash),'Derived pilot policy hash required')
    pod=copy.deepcopy(deployment['spec']['template']['spec']);containers=named(pod['containers'])
    require('gateway'in containers and containers['gateway'].get('image') in (PREVIOUS_IMAGE,IMAGE),'Exact released768 Gateway image required')
    main=copy.deepcopy(containers['gateway']);main['image']=IMAGE;volumes=named(pod.get('volumes',[]));mounts=main.get('volumeMounts',[])
    require(type(mounts) is list,'Actual mounts required')
    data=[m for m in mounts if m.get('mountPath')=='/data']
    require(len(data)==1 and not any(data[0].get(k) for k in ('readOnly','subPath','subPathExpr'))
            and volumes.get(data[0]['name'],{}).get('persistentVolumeClaim')=={'claimName':'compute-state'},
            'Exact complete writable compute-state PVC mount required')
    command=main.get('command',[]);tail=main.get('args')
    require(type(command) is list and (tail is None or type(tail) is list),'Actual command/args arrays required')
    args=command+(tail or [])
    require(bool(args) and args[0]=='uvicorn' and 'cps_compute.runtime:create_runtime'in args and '--factory'in args,
            'Actual reviewed runtime factory command required')
    for flag in ('--ssl-certfile','--ssl-keyfile'):
        require(args.count(flag)==1 and args.index(flag)+1<len(args),'Actual explicit TLS command required')
    args=list(args);args[args.index('--ssl-certfile')+1]='/pilot-tls/tls.crt';args[args.index('--ssl-keyfile')+1]='/pilot-tls/tls.key';main['command']=args;main.pop('args',None)
    ports=main.get('ports',[]);require(type(ports) is list and len(ports)==1 and type(ports[0].get('name')) is str
            and type(ports[0].get('containerPort')) is int,'Single actual HTTPS port required')
    required=set(runtime.get('service_token_envs',{}).values())|set(runtime.get('metrics_token_envs',{}).values())
    require(type(runtime.get('hubs')) is dict and runtime['hubs'],'Actual upstream Hub configurations required')
    required|={x['service_token_env'] for x in runtime['hubs'].values()}
    if runtime.get('argo_token_env'):required.add(runtime['argo_token_env'])
    require(runtime.get('argo_token_env') or runtime.get('argo_token_file'),'Existing mandatory Argo credential reference required')
    env=named(main.get('env',[]))
    inherited=main.get('envFrom',[])
    require(type(inherited) is list,'Actual envFrom array required')
    sources={}
    if inherited:
        require(type(credential_secret_metadata) is list,'Actual authenticated Secret metadata/keysets required')
        for row in credential_secret_metadata:
            require(type(row) is dict and set(row)=={'namespace','name','uid','resourceVersion','keys'}
                and row['namespace']=='cps-compute' and all(type(row[k]) is str and row[k] for k in ('name','uid','resourceVersion'))
                and type(row['keys']) is list and all(type(k) is str for k in row['keys'])
                and len(set(row['keys']))==len(row['keys']),'Closed actual Secret metadata/keyset required')
            require(row['name'] not in sources,'Duplicate Secret metadata identity');sources[row['name']]=row
        for source in inherited:
            require(type(source) is dict and set(source)=={'secretRef'} and type(source['secretRef']) is dict
                and set(source['secretRef'])<={'name','optional'} and source['secretRef'].get('optional') is not True
                and source['secretRef'].get('name') in sources,'Exact nonoptional envFrom Secret metadata required')
        require(set(sources)=={x['secretRef']['name'] for x in inherited},'No foreign Secret metadata allowed')
        for key in required:
            if key in env:continue
            matches=[row for row in sources.values() if key in row['keys']]
            require(len(matches)==1,'Inherited required credential key absent or ambiguous')
            env[key]={'name':key,'valueFrom':{'secretKeyRef':{'name':matches[0]['name'],'key':key}}}
    require(all(k in env and set(env[k])=={'name','valueFrom'} and set(env[k]['valueFrom'])=={'secretKeyRef'} for k in required),
            'Actual protected upstream credential environment references required')
    main['env']=[copy.deepcopy(env[k]) for k in sorted(required)]+[{'name':'CPS_COMPUTE_CONFIG','value':'/pilot-runtime/runtime.json'},{'name':'PYTHONDONTWRITEBYTECODE','value':'1'}]
    main.pop('envFrom',None)
    fresh_storage=None
    provider=None
    if fresh_provisioning is not None:
        import importlib.util
        from pathlib import Path
        source=Path(__file__).with_name('plain_lifecycle_storage_rbac.py')
        spec=importlib.util.spec_from_file_location('_reviewed_fresh_storage',source)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        provider=copy.deepcopy(runtime.get('storage'))
        require(type(provider) is dict and provider.get('enabled') is True,'Actual enabled original storage provider required')
        provider['allowedOperations']=['provision']
        fresh_storage=helper.build(provider=provider,targets=fresh_provisioning)
        scopes=pilot['runtime']['nativeGpuPilot']['native_pilot_workspaces']
        require({t['source']+':'+t['workspace'] for t in fresh_storage['targets']}==set(scopes),
                'Fresh storage targets must equal exact pilot workspace scopes')
        approvals=pilot.get('reviewed_approvals',{})
        require(all(approvals.get(t['source']+':'+t['workspace'],{}).get('group_id')==t['group_id']
                    for t in fresh_storage['targets']),'Fresh group must match reviewed pilot approval')
    paths=[runtime[k] for k in ('argo_ca_file','argo_token_file') if runtime.get(k)]
    if provider is not None:paths += [provider['ssh'][k] for k in ('identity_file','known_hosts_file')]
    kept=[copy.deepcopy(data[0])]
    for path in paths:
        matches=[m for m in mounts if type(m.get('mountPath')) is str and (path==m['mountPath'] or path.startswith(m['mountPath'].rstrip('/')+'/'))]
        require(len(matches)==1 and matches[0].get('readOnly') is True,'Unique actual read-only Argo credential/CA mount required')
        mount=matches[0]
        volume=volumes.get(mount['name'],{})
        tokens=[x['serviceAccountToken'] for x in volume.get('projected',{}).get('sources',[]) if 'serviceAccountToken'in x]
        if path=='/var/run/secrets/kubernetes.io/serviceaccount/token':
            require(mount['mountPath']=='/var/run/secrets/kubernetes.io/serviceaccount'
                and not mount.get('subPath') and not mount.get('subPathExpr')
                and len(tokens)==1 and tokens[0].get('path')=='token',
                'Exact standard original SA token projection required before replacement')
            # New SA automount supplies this exact factory path; old bound token
            # and disabled UI reader token must not be inherited.
            continue
        require(not tokens,'Nonstandard old SA token path cannot be retained')
        if mount not in kept:kept.append(copy.deepcopy(mount))
    additions=[('pilot-runtime',{'secret':{'secretName':runtime_secret_ref['name']}},'/pilot-runtime'),
               ('pilot-policy',{'configMap':{'name':policy_configmap_ref['name']}},'/pilot-policy'),
               ('pilot-tls',{'secret':{'secretName':tls_secret_ref['name']}},'/pilot-tls')]
    require(not {x[0] for x in additions}.intersection(m['name'] for m in kept),'Temporary volume name collision')
    selected=[copy.deepcopy(volumes[m['name']]) for m in kept]
    for name,body,path in additions:selected.append({'name':name,**body});kept.append({'name':name,'mountPath':path,'readOnly':True})
    require(not any('serviceAccountToken'in x for v in selected for x in v.get('projected',{}).get('sources',[])),
            'Old service-account token projection cannot be retained')
    main['volumeMounts']=kept
    pod['containers']=[main];pod.pop('initContainers',None);pod.pop('ephemeralContainers',None)
    pod['volumes']=selected;pod['serviceAccountName']=new_name;pod['automountServiceAccountToken']=True;pod['nodeName']=selected_state_node
    pod.pop('affinity',None);pod.pop('nodeSelector',None)
    labels={'app.kubernetes.io/name':new_name}
    result={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':'cps-compute','name':new_name},
            'spec':{'replicas':1,'strategy':{'type':'Recreate'},'selector':{'matchLabels':labels},
                    'template':{'metadata':{'labels':labels},'spec':pod}}}
    cfg=copy.deepcopy(runtime);cfg.update(copy.deepcopy(pilot['runtime']));cfg['policy_hash']=policy_hash;cfg['policy_file']='/pilot-policy/policy.json'
    for key in ('nativeGpuGroups','nativeGpuQualification','nativeGroupApprovals','jobsets','argoUi','argoUI','storage'):cfg[key]={'enabled':False}
    if provider is not None:cfg['storage']=provider
    cfg.pop('artifacts',None);cfg['shutdownObserver']={'kubernetes':True}
    return {'version':1,'proposal_only':True,'deploy_ready':False,'production_qualified':False,
            'preimages':{'deployment_sha256':digest(deployment),'runtime_sha256':digest(runtime),'uid':meta['uid'],'resourceVersion':meta['resourceVersion']},
            'deployment':result,'runtime':cfg,'service':{'apiVersion':'v1','kind':'Service','metadata':{'namespace':'cps-compute','name':new_name},'spec':{'type':'ClusterIP','selector':labels,'ports':[{'name':'https','port':443,'targetPort':ports[0]['name']}]}},
            'service_account':{'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':'cps-compute','name':new_name}},
            'hub_endpoint':{'origin':'https://'+new_name+'.cps-compute.svc.cluster.local','ca_configmap_ref':copy.deepcopy(ca_configmap_ref)},
            'credential_secret_preimages':copy.deepcopy(credential_secret_metadata or []),
            'fresh_storage':fresh_storage,
            'rbac':{'pending':True,'required':'Dedicated SA exact-node GET, target-Pod GET, pilot-namespace ledger GET/PATCH and shape-restricted CM CREATE; explicit SAR and admission qualification required.'},
            'pending':(['SDK provision-only allowedOperations enforcement and actual denied archive before metadata/NAS changes'] if fresh_storage is not None else [])+['Actual PVC attachment/current-node preflight','Actual new TLS SAN/CA and Secret content verification','Full runtime factory and health-probe qualification','Temporary canonical registrations, alias grants and active storage verification','Legacy Node768 and complete prior inventory compatibility']}
