#!/usr/bin/env python3
"""Plan by default. Reviewed backend preparation never publishes an ingress."""
import argparse
import base64
import copy
import datetime
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
COMPUTE = 'ghcr.io/mul-cps/cps-compute@sha256:74cfb93dcf0078c116b88662b19b6ef14611f616e34ae3141f1fd24ceb3e12ce'
FRONTEND = 'ghcr.io/mul-cps/e2x-course-hub:qualification-native-assets-373dc09@sha256:c4df863a35a46d598cb319508b7d4e45caae3d1f9b71e24b2f1692c65e5f07bc'
FRONTEND_REVISION = '373dc09c34e0add10cad1a3f52ae6cb593955d01'
SOURCES = {'cps':('jupyterhub','https://jupyterhub.dshl.unileoben.ac.at'),
           'cit':('cit-jhub','https://jhub.dshl.unileoben.ac.at')}
RUNTIME_OLD = 'cps-compute-runtime'
RUNTIME_NEW = 'cps-compute-runtime-personal-argo'


def kubectl(args, body=None):
    result = subprocess.run(['kubectl',*args], input=None if body is None else json.dumps(body),
                            capture_output=True, text=True)
    if result.returncode:
        # Request/response bodies, configuration, and exception details may contain secrets.
        raise RuntimeError('kubectl operation failed; inspect sanitized Kubernetes status separately')
    return result.stdout


def get(kind, name, namespace):
    return json.loads(kubectl(['-n',namespace,'get',kind,name,'-o','json']))


def create(obj):
    # Generated Secret bytes go through stdin and are never persisted locally.
    kubectl(['create','-f','-'],obj)


def replace(obj):
    # resourceVersion from the preceding read provides Kubernetes CAS.
    kubectl(['replace','-f','-'],obj)


def obj(kind, name, namespace, **fields):
    api = 'v1' if kind in ('Secret','ConfigMap') else 'networking.k8s.io/v1'
    return {'apiVersion':api,'kind':kind,'metadata':{'name':name,'namespace':namespace,
        'labels':{'qualification.cps/owner':'personal-argo-preparation'}},**fields}


def hub_module(source):
    namespace, origin = SOURCES[source]
    return f'''# Appended service and default normal-user access; no admin API role.
from pathlib import Path
_personal_name = {source + '-argo-ui'!r}
if any(s.get('name') == _personal_name for s in c.JupyterHub.services):
    raise RuntimeError('Dedicated personal Argo service already configured')
c.JupyterHub.services = list(c.JupyterHub.services) + [{{
    'name': _personal_name,
    'api_token': Path('/etc/personal-argo/oauth-client-secret').read_text().strip(),
    'oauth_client_id': 'service-' + _personal_name,
    'oauth_redirect_uri': {origin + '/argo/oauth_callback'!r},
    'oauth_client_allowed_scopes': [],
    'display': False,
}}]
_personal_roles = [dict(role) for role in c.JupyterHub.load_roles]
_personal_user = next((role for role in _personal_roles if role.get('name') == 'user'), None)
if _personal_user is None:
    _personal_user = {{'name': 'user', 'scopes': ['self']}}
    _personal_roles.append(_personal_user)
_personal_scope = 'access:services!service=' + _personal_name
_personal_user['scopes'] = list(dict.fromkeys([*_personal_user.get('scopes', ['self']), _personal_scope]))
c.JupyterHub.load_roles = _personal_roles
'''


def rendered_objects():
    policy = json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
    values = {'enabled':True,'namespace':'cps-compute','policyJson':json.dumps(policy),'policyHash':policy['policyHash'],
        'gateway':{'image':COMPUTE,'argoUi':{'enabled':True}},
        'consoles':{s:{'image':FRONTEND,'publicCallbackUrl':origin+'/services/'+s+'-admin/oauth_callback'} for s,(_,origin) in SOURCES.items()},
        'personalArgo':{'enabled':True,'image':FRONTEND,
            'nativeUrl':'https://cps-argo-argo-workflows-server.cps-argo.svc.cluster.local:2746',
            'nativeCaFile':'/trust/ca.crt','upstreamCaConfigMapRef':'cps-compute-gateway-ca',
            'sources':{s:{'enabled':True,'publicOrigin':origin,'hubApiUrl':origin+'/hub/api',
                'secretRef':s+'-argo-ui-oauth','ingress':{'enabled':False}} for s,(_,origin) in SOURCES.items()}}}
    with tempfile.NamedTemporaryFile('w',suffix='.yaml') as handle:
        yaml.safe_dump(values,handle);handle.flush()
        result = subprocess.run(['helm','template','personal-reviewed',str(ROOT/'platform-staging/chart'),'-f',handle.name,
            '--show-only','templates/argo-ui-reader.yaml','--show-only','templates/personal-argo.yaml'],capture_output=True,text=True)
    if result.returncode: raise RuntimeError('Focused credential-free chart render failed')
    objects = [o for o in yaml.safe_load_all(result.stdout) if o]
    assert not any(o['kind']=='Ingress' for o in objects)
    for o in objects:
        if o['kind']=='CronJob': o['spec']['suspend']=True
    peers = [{'podSelector':{'matchExpressions':[{'key':'app','operator':'In','values':['cps-argo-ui','cit-argo-ui']}]}}]
    objects.append(obj('NetworkPolicy','personal-argo-to-gateway','cps-compute',spec={
        'podSelector':{'matchLabels':{'app':'compute-gateway'}},'policyTypes':['Ingress'],
        'ingress':[{'from':peers,'ports':[{'protocol':'TCP','port':8000}]}]}))
    objects.append(obj('NetworkPolicy','personal-argo-native-assets','cps-argo',spec={
        'podSelector':{'matchLabels':{'app.kubernetes.io/instance':'cps-argo','app.kubernetes.io/name':'argo-workflows-server'}},
        'policyTypes':['Ingress'],'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'cps-compute'}},**peers[0]}],
        'ports':[{'protocol':'TCP','port':2746}]}]}))
    for source,(namespace,_) in SOURCES.items():
        objects.append(obj('ConfigMap','personal-argo-registration',namespace,data={'personal-argo.py':hub_module(source)}))
    return objects


def deployment_summary(deployment):
    pod=deployment['spec']['template']['spec']
    return {'resourceVersion':deployment['metadata']['resourceVersion'],
            'images':{c['name']:c['image'] for c in pod['containers']},
            'configSecretRefs':{v['name']:v['secret']['secretName'] for v in pod['volumes'] if 'secret' in v}}


def plan():
    objects=rendered_objects()
    result={'schemaVersion':1,'stage':'proposal-only-no-production-mutation','computeImage':COMPUTE,'frontendImage':FRONTEND,
        'frontendSourceRevision':FRONTEND_REVISION,'frontendSdkIncluded':False,'gatewaySdkRevision':'40b9525',
        'gateway':deployment_summary(get('deployment','compute-gateway','cps-compute')),
        'hubs':{s:deployment_summary(get('deployment','hub',ns)) for s,(ns,_) in SOURCES.items()},
        'sources':{s:{'namespace':ns,'origin':origin,'callback':origin+'/argo/oauth_callback',
            'clientId':'service-'+s+'-argo-ui','scope':'access:services!service='+s+'-argo-ui'} for s,(ns,origin) in SOURCES.items()},
        'runtimeChange':{'originalSecretPreserved':RUNTIME_OLD,'newSecret':RUNTIME_NEW,
            'onlyAddedKey':{'argoUi':{'enabled':True,'readerTokenFile':'/argo-reader/token','temporaryDirectory':'/tmp'}}},
        'resources':[{'kind':o['kind'],'namespace':o['metadata']['namespace'],'name':o['metadata']['name']} for o in objects],
        'activationBlockedBy':['normal gateway canonical identity maps currently empty; grants also empty',
            'real normal-user browser/ownership/callback/download/SSE qualification pending',
            'reviewed canonical and optional alias identity inventory pending',
            'reviewed removal/replacement of BOTH CPS legacy /argo regex ingresses pending',
            'Fleet reconciliation persistence for Hub mounts and legacy route removal pending'],
        'scopeExclusions':['no identity or grant edits','no GPU flags','no ingress publication','no full chart apply','no Fleet edits']}
    encoded=json.dumps(result,sort_keys=True,separators=(',',':')).encode()
    result['reviewSha256']=hashlib.sha256(encoded).hexdigest()
    (HERE/'activation-plan.json').write_text(json.dumps(result,indent=2)+'\n')
    (HERE/'activation-resources.yaml').write_text(yaml.safe_dump_all(objects,sort_keys=False))
    return result


def gateway_pod_update(pod, *, image, runtime_secret, add):
    container=next(c for c in pod['containers'] if c['name']=='gateway')
    container['image']=image
    next(v for v in pod['volumes'] if v['name']=='config')['secret']['secretName']=runtime_secret
    pod['volumes']=[v for v in pod['volumes'] if v['name']!='argo-ui-reader']
    container['volumeMounts']=[v for v in container['volumeMounts'] if v['name']!='argo-ui-reader']
    if add:
        pod['volumes'].append({'name':'argo-ui-reader','secret':{'secretName':'cps-argo-ui-reader','items':[{'key':'token','path':'token'}]}})
        container['volumeMounts'].append({'name':'argo-ui-reader','mountPath':'/argo-reader','readOnly':True})


def hub_pod_update(pod, add):
    names={'personal-argo-registration','personal-argo-oauth'}
    pod['volumes']=[v for v in pod['volumes'] if v['name'] not in names]
    container=next(c for c in pod['containers'] if c['name']=='hub')
    container['volumeMounts']=[v for v in container['volumeMounts'] if v['name'] not in names]
    if add:
        pod['volumes'] += [{'name':'personal-argo-registration','configMap':{'name':'personal-argo-registration'}},
                          {'name':'personal-argo-oauth','secret':{'secretName':'personal-argo-oauth'}}]
        container['volumeMounts'] += [{'name':'personal-argo-registration','mountPath':'/usr/local/etc/jupyterhub/jupyterhub_config.d/personal-argo.py',
            'subPath':'personal-argo.py','readOnly':True},
            {'name':'personal-argo-oauth','mountPath':'/etc/personal-argo','readOnly':True}]


def native_preflight_code(native):
    # This reads current runtime only inside its existing Pod. Nothing secret is emitted.
    return ("import os,json,pathlib,ssl,urllib.request,re; "
        "c=json.loads(pathlib.Path(os.environ['CPS_COMPUTE_CONFIG']).read_text()); "
        "ctx=ssl.create_default_context(cafile=c['argo_ca_file']); "
        "native="+repr(native)+"; "
        "html=urllib.request.urlopen(native+'/',context=ctx,timeout=15).read().decode(); "
        "scripts=re.findall(r'<script[^>]+src=[\\\"\\\x27]([^\\\"\\\x27]+)[\\\"\\\x27]',html); "
        "assert scripts and '/' not in scripts[0]; "
        "r=urllib.request.urlopen(native+'/'+scripts[0],context=ctx,timeout=15); "
        "print(json.dumps({'nativeAssetsQualified':r.status==200 and 'javascript' in r.headers.get('Content-Type','') "
        "and bool(re.search(r'<base\\s+href=[\\\"\\\x27]/argo/[\\\"\\\x27]',html))}))")


def rollback_fields(old_image, hub_sources, gateway_updated):
    # Fresh reads and replace resourceVersion CAS preserve unrelated changes.
    if gateway_updated:
        live=get('deployment','compute-gateway','cps-compute')
        pod=live['spec']['template']['spec']
        assert next(c['image'] for c in pod['containers'] if c['name']=='gateway')==COMPUTE
        assert next(v for v in pod['volumes'] if v['name']=='config')['secret']['secretName']==RUNTIME_NEW
        gateway_pod_update(pod,image=old_image,runtime_secret=RUNTIME_OLD,add=False);replace(live)
    for source in hub_sources:
        namespace=SOURCES[source][0]
        hub=get('deployment','hub',namespace);hub_pod_update(hub['spec']['template']['spec'],False);replace(hub)


def prepare(review_sha, backup_evidence, receipt_file):
    expected=json.loads((HERE/'activation-plan.json').read_text())
    assert review_sha==expected['reviewSha256'], 'Exact concrete plan review hash required'
    current=plan()
    assert current['reviewSha256']==review_sha, 'Live image/resource-version drift; prepare a fresh plan'
    gateway=get('deployment','compute-gateway','cps-compute')
    assert receipt_file and not Path(receipt_file).exists(), 'A new sanitized preparation receipt path is required'
    for deployment in [gateway,*[get('deployment','hub',ns) for ns,_ in SOURCES.values()]]:
        assert not any(v['name'] in ('argo-ui-reader','personal-argo-registration','personal-argo-oauth')
                       for v in deployment['spec']['template']['spec']['volumes'])
    old_image=next(c['image'] for c in gateway['spec']['template']['spec']['containers'] if c['name']=='gateway')
    evidence=json.loads(Path(backup_evidence).read_text())
    assert evidence['gatewayStateSnapshotVerified'] is True and evidence['gatewayImage']==old_image
    assert evidence['hubDatabaseConfigSnapshotsVerified']=={'cps':True,'cit':True}
    # Production preparation stays blocked until root reviews actual identity/privacy evidence.
    assert evidence['activationGates']=={'realBrowserHubOAuthQualified':True,
        'normalOwnerPrivacyQualified':True,'aliasInventoryReviewed':True}
    # Verify the exact planned native prefix before creating any Secret or changing a Pod.
    # Argo serves a SPA index for unknown paths, so status=200 alone is insufficient.
    native=next(e['value'] for o in rendered_objects() if o['kind']=='Deployment' for e in o['spec']['template']['spec']['containers'][0]['env'] if e['name']=='ARGO_USER_NATIVE_ARGO_URL')
    check=native_preflight_code(native)
    preflight=json.loads(kubectl(['-n','cps-compute','exec','deployment/compute-gateway','--','python','-c',check]))
    assert preflight['nativeAssetsQualified'] is True
    assert next(v for v in gateway['spec']['template']['spec']['volumes'] if v['name']=='config')['secret']['secretName']==RUNTIME_OLD
    # Only this apply phase reads runtime Secret bytes; capture remains process memory.
    runtime=get('secret',RUNTIME_OLD,'cps-compute')
    config=json.loads(base64.b64decode(runtime['data']['runtime.json']))
    assert 'argoUi' not in config or config['argoUi']=={'enabled':False}
    assert config.get('artifacts') and config.get('argo_ca_file')
    updated=copy.deepcopy(config);updated['argoUi']={'enabled':True,'readerTokenFile':'/argo-reader/token','temporaryDirectory':'/tmp'}
    create(obj('Secret',RUNTIME_NEW,'cps-compute',type='Opaque',stringData={'runtime.json':json.dumps(updated)}))
    for source,(namespace,_) in SOURCES.items():
        credential=secrets.token_urlsafe(48)
        create(obj('Secret',source+'-argo-ui-oauth','cps-compute',type='Opaque',stringData={
            'oauth-client-secret':credential,'cookie-secret':secrets.token_urlsafe(48)}))
        create(obj('Secret','personal-argo-oauth',namespace,type='Opaque',stringData={'oauth-client-secret':credential}))
    create(obj('Secret','cps-argo-ui-reader','cps-compute',type='Opaque',stringData={'token':''}))
    # Every object is specific and outside the full chart; collisions fail instead of overwriting.
    resources=rendered_objects()
    for resource in resources: create(resource)
    cron=next(o for o in resources if o['kind']=='CronJob')
    job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':'personal-argo-initial-rotation','namespace':'cps-compute'},
         'spec':copy.deepcopy(cron['spec']['jobTemplate']['spec'])}
    job['spec']['activeDeadlineSeconds']=300;job['spec']['backoffLimit']=0
    job['spec']['template']['spec']['containers'][0]['resources']['limits']={'cpu':'1','memory':'512Mi'}
    create(job)
    kubectl(['-n','cps-compute','wait','--for=condition=complete','job/personal-argo-initial-rotation','--timeout=300s'])
    changed_hubs=[];gateway_updated=False
    receipt={'reviewSha256':review_sha,'oldGatewayImage':old_image,'changedHubs':changed_hubs,
             'gatewayUpdated':False,'ingressPublished':False,'normalUserOwnershipQualified':False}
    Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
    try:
        # Update only the relevant template fields; preserve all other current configuration.
        gateway=get('deployment','compute-gateway','cps-compute')
        assert deployment_summary(gateway)['resourceVersion']==expected['gateway']['resourceVersion']
        gateway_pod_update(gateway['spec']['template']['spec'],image=COMPUTE,runtime_secret=RUNTIME_NEW,add=True)
        replace(gateway)
        gateway_updated=True;receipt['gatewayUpdated']=True
        Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
        kubectl(['-n','cps-compute','rollout','status','deployment/compute-gateway','--timeout=300s'])
        for source,(namespace,_) in SOURCES.items():
            hub=get('deployment','hub',namespace)
            assert deployment_summary(hub)['resourceVersion']==expected['hubs'][source]['resourceVersion']
            hub_pod_update(hub['spec']['template']['spec'],True);replace(hub)
            changed_hubs.append(source);Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
            kubectl(['-n',namespace,'rollout','status','deployment/hub','--timeout=300s'])
        # Unsuspend only after gateway and both restart-persistent registration modules start.
        cron=get('cronjob','argo-ui-token-rotator','cps-compute');cron['spec']['suspend']=False;replace(cron)
    except BaseException:
        # Restore only owned fields from freshly read resources; do not revert unrelated edits.
        rollback_fields(old_image,changed_hubs,gateway_updated)
        receipt['ownedFieldsRolledBack']=True;Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
        raise RuntimeError('Preparation failed; owned deployment fields restored; created resources remain dormant for explicit cleanup') from None
    receipt['backendPrepared']=True;Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
    return {'status':'backend-prepared-not-public','reviewSha256':review_sha,'ingressPublished':False,
        'normalUserOwnershipQualified':False,'fleetPersistenceQualified':False}


def rollback(review_sha, receipt_file):
    receipt=json.loads(Path(receipt_file).read_text())
    assert receipt['reviewSha256']==review_sha and receipt.get('backendPrepared') is True
    assert not receipt.get('ownedFieldsRolledBack')
    cron=get('cronjob','argo-ui-token-rotator','cps-compute');cron['spec']['suspend']=True;replace(cron)
    rollback_fields(receipt['oldGatewayImage'],receipt['changedHubs'],receipt['gatewayUpdated'])
    for namespace in ['cps-compute',*[SOURCES[s][0] for s in receipt['changedHubs']]]:
        name='compute-gateway' if namespace=='cps-compute' else 'hub'
        kubectl(['-n',namespace,'rollout','status','deployment/'+name,'--timeout=300s'])
    receipt['ownedFieldsRolledBack']=True;Path(receipt_file).write_text(json.dumps(receipt,indent=2)+'\n')
    return {'status':'owned-fields-rolled-back-private-resources-retained','reviewSha256':review_sha}


if __name__=='__main__':
    if not __debug__:raise SystemExit('operator requires validation-enabled Python')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-reviewed-sha256',help='Execute only an explicitly reviewed concrete backend plan; does not publish routes')
    parser.add_argument('--backup-evidence',help='Sanitized verified matching gateway-state and Hub database/config snapshot evidence; required for preparation')
    parser.add_argument('--receipt-file',help='Sanitized preparation journal required for preparation and rollback')
    parser.add_argument('--rollback-reviewed-sha256',help='Restore only owned deployment fields from the matching preparation journal')
    options=parser.parse_args()
    try:
        assert not (options.prepare_reviewed_sha256 and options.rollback_reviewed_sha256)
        result=(prepare(options.prepare_reviewed_sha256,options.backup_evidence,options.receipt_file) if options.prepare_reviewed_sha256
                else rollback(options.rollback_reviewed_sha256,options.receipt_file) if options.rollback_reviewed_sha256 else plan())
        print(json.dumps({'status':result.get('status',result.get('stage')),'reviewSha256':result['reviewSha256']}))
    except Exception:
        # No secret-bearing exception/body/config repr is printed.
        print('personal-argo operator stopped; no request bodies or credentials logged')
        raise SystemExit(1)
