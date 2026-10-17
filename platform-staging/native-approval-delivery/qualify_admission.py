"""Root-executed isolated K3s admission qualification; default is inert.

Setup/cleanup creates only fresh QA namespaces, local fixtures/RBAC, and narrowly
scoped temporary policies. Every test request is server dry-run. No Pod, Secret,
image, GPU, production policy, or production namespace is changed.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid

SA = 'cps-native-head-delivery'
ROLE = 'cps-native-observer-operator'
PREFIX = 'cps-head-admission-qa-'
SSR = '/apis/authentication.k8s.io/v1/selfsubjectreviews'
ROUTES = {'Namespace': ('/api/v1', 'namespaces'), 'ConfigMap': ('/api/v1', 'configmaps'),
    'ServiceAccount': ('/api/v1', 'serviceaccounts'), 'Role': ('/apis/rbac.authorization.k8s.io/v1', 'roles'),
    'RoleBinding': ('/apis/rbac.authorization.k8s.io/v1', 'rolebindings'),
    'ValidatingAdmissionPolicy': ('/apis/admissionregistration.k8s.io/v1', 'validatingadmissionpolicies'),
    'ValidatingAdmissionPolicyBinding': ('/apis/admissionregistration.k8s.io/v1', 'validatingadmissionpolicybindings')}


def require(value, message):
    if not value: raise ValueError(message)


def runtime():
    spec = importlib.util.spec_from_file_location('qualified_delivery_render', Path(__file__).with_name('render.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def identity(obj):
    meta = obj['metadata']
    require(isinstance(meta.get('uid'), str) and meta['uid'] and isinstance(meta.get('resourceVersion'), str)
        and meta['resourceVersion'], 'Actual API UID/resourceVersion required')
    return {'kind': obj['kind'], 'namespace': meta.get('namespace'), 'name': meta['name'],
            'uid': meta['uid'], 'resourceVersion': meta['resourceVersion']}


def endpoint(value, named=True):
    group, plural = ROUTES[value['kind']]; namespace = value.get('namespace')
    return group + ('/namespaces/' + namespace if namespace else '') + '/' + plural + ('/' + value['name'] if named else '')


def policy_config(pointers, roles):
    require(len(pointers) == len(roles) == 4, 'Four actual pointer and Role fixtures required')
    return {'observer_release': {'heads': {c: {'anchor': {'pointer': {
        **{k: p['metadata'][k] for k in ('namespace', 'name', 'uid')}, 'key': 'head.json'}}}
        for c, p in zip(('gateway', 'hub:cps', 'hub:cit', 'node'), pointers)}},
        'pregrant_roles': [{**{k: r['metadata'][k] for k in ('namespace', 'name', 'uid')},
            'index': 0, 'rules': deepcopy(r['rules'])} for r in roles]}


def isolated_policies(config, namespaces, suffix):
    require(isinstance(suffix, str) and re.fullmatch('[a-f0-9]{12}', suffix)
        and namespaces == [PREFIX + suffix + '-' + str(i) for i in range(4)], 'Four exact fresh QA namespaces required')
    selector = {'matchExpressions': [{'key': 'kubernetes.io/metadata.name', 'operator': 'In', 'values': namespaces}]}
    result = runtime()._policies(config, namespaces[0])
    for obj in result:
        obj['metadata']['name'] += '-qa-' + suffix
        if obj['kind'] == 'ValidatingAdmissionPolicy':
            obj['spec']['matchConstraints']['namespaceSelector'] = deepcopy(selector)
            obj['spec']['matchConditions'].append({'name': 'only-fresh-qa-namespaces',
                'expression': 'request.namespace in ' + canonical(namespaces)})
        else:
            obj['spec']['policyName'] = obj['metadata']['name']
            obj['spec']['matchResources'] = {'namespaceSelector': deepcopy(selector)}
    return result


def patch(actual, field, value, *, labels=None):
    meta = actual['metadata']
    result = [{'op': 'test', 'path': '/metadata/uid', 'value': meta['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': meta['resourceVersion']},
        {'op': 'test', 'path': '/' + field, 'value': deepcopy(actual[field])},
        {'op': 'replace', 'path': '/' + field, 'value': deepcopy(value)}]
    if labels is not None: result.append({'op': 'add', 'path': '/metadata/labels', 'value': labels})
    return result


def cases(pointers, roles, foreign, suffix):
    result = []
    def add(name, kind, namespace, target, body, accepted, family=None, actor='test', method='PATCH'):
        result.append({'name': name, 'namespace': namespace, 'method': method,
            'path': endpoint({'kind': kind, 'namespace': namespace, 'name': target}, named=method != 'POST'),
            'body': body, 'accepted': accepted, 'actor': actor,
            'policy': SA + '-' + family + '-qa-' + suffix if family else None})
    for i, (pointer, role) in enumerate(zip(pointers, roles)):
        ns = pointer['metadata']['namespace']; data = {'head.json': canonical({'generation': 2,
            'reference': {'namespace': ns}, 'version': 1})}
        approval = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'namespace': ns, 'name': 'cps-native-approvals-' + 'a' * 16},
            'data': {'approval.json': '{"history":[],"version":2}'}}
        growth = deepcopy(role['rules']); growth[0]['resourceNames'].append('cps-native-approvals-' + 'a' * 16)
        add('approval-positive-' + str(i), 'ConfigMap', ns, '', approval, True, method='POST')
        add('pointer-positive-' + str(i), 'ConfigMap', ns, pointer['metadata']['name'], patch(pointer, 'data', data), True)
        add('role-positive-' + str(i), 'Role', ns, ROLE, patch(role, 'rules', growth), True)
        wrong = deepcopy(data); wrong['head.json'] = canonical({'generation': 2, 'reference': {'namespace': 'foreign'}, 'version': 1})
        add('pointer-reference-namespace-' + str(i), 'ConfigMap', ns, pointer['metadata']['name'], patch(pointer, 'data', wrong), False, 'pointer-update')
        if i: continue
        for fault in ('name', 'extra-data', 'mutable', 'labels', 'owner'):
            body = deepcopy(approval)
            if fault == 'name': body['metadata']['name'] = 'unapproved-name'
            elif fault == 'extra-data': body['data']['extra'] = 'unexpected'
            elif fault == 'mutable': body['immutable'] = False
            elif fault == 'labels': body['metadata']['labels'] = {'unsafe': 'change'}
            else: body['metadata']['ownerReferences'] = [{'apiVersion': 'v1', 'kind': 'ConfigMap',
                'name': pointer['metadata']['name'], 'uid': pointer['metadata']['uid']}]
            add('approval-' + fault, 'ConfigMap', ns, '', body, False, 'approval-create', method='POST')
        add('pointer-extra-data', 'ConfigMap', ns, pointer['metadata']['name'], patch(pointer, 'data', dict(data, extra='unexpected')), False, 'pointer-update')
        add('pointer-labels', 'ConfigMap', ns, pointer['metadata']['name'], patch(pointer, 'data', data, labels={'unsafe': 'change'}), False, 'pointer-update')
        add('pointer-wrong-name', 'ConfigMap', ns, foreign[0]['metadata']['name'], patch(foreign[0], 'data', data), False, 'pointer-update')
        for fault in ('verbs', 'wildcard', 'removal', 'foreign-name', 'static-row', 'labels'):
            rules = deepcopy(growth)
            if fault == 'verbs': rules[0]['verbs'].append('list')
            elif fault == 'wildcard': rules[0]['resourceNames'].append('*')
            elif fault == 'removal': rules[0]['resourceNames'].remove('static-config')
            elif fault == 'foreign-name': rules[0]['resourceNames'].append('unrelated')
            elif fault == 'static-row': rules[1]['resources'] = ['secrets']
            add('role-' + fault, 'Role', ns, ROLE, patch(role, 'rules', rules,
                labels={'unsafe': 'change'} if fault == 'labels' else None), False, 'pregrant-update')
        add('foreign-root-pointer', 'ConfigMap', ns, pointer['metadata']['name'], patch(pointer, 'data', data), False, 'pointer-update', 'root')
        add('foreign-root-role', 'Role', ns, ROLE, patch(role, 'rules', growth), False, 'pregrant-update', 'root')
        add('foreign-root-approval', 'ConfigMap', ns, '', approval, False, 'approval-create', 'root', 'POST')
        other = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'namespace': ns, 'name': 'unrelated'}, 'data': {}}
        add('foreign-root-unrelated-create', 'ConfigMap', ns, '', other, True, actor='root', method='POST')
        add('foreign-root-unrelated-role', 'Role', ns, 'unrelated-observer', patch(dict(role,
            metadata=dict(role['metadata'], name='unrelated-observer')), 'rules', role['rules']), True, actor='root')
    return result


def policy_denial(result, policy):
    message = result.get('message', '')
    # Kubernetes defaults a failed validation to reason Invalid (HTTP422).
    # Accept only this exact policy/binding and our fixed validation message;
    # generic schema errors and CEL evaluation failures are not evidence.
    signature = "ValidatingAdmissionPolicy '" + policy + "' with binding '" + policy + "' denied request: Only the reviewed dynamic delivery write is permitted"
    return (result['status'], result.get('reason')) in ((403, 'Forbidden'), (422, 'Invalid')) and message.endswith(signature)


def private_directory(value):
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink(), 'Absolute private directory outside Git required')
    resolved = path.resolve()
    require(not any((p / '.git').exists() for p in (resolved, *resolved.parents)), 'Evidence must remain outside Git')
    if not path.exists(): path.mkdir(mode=0o700)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700
        and not any(path.iterdir()), 'New empty owned 0700 directory required')
    return path


def write_private(directory, name, value):
    target = directory / name; temporary = directory / (name + '.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, target)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


class Kube:
    def __init__(self, context):
        from kubernetes import client, config
        settings = client.Configuration(); config.load_kube_config(context=context, client_configuration=settings)
        settings.debug = False; self.api = client.ApiClient(settings)
    def request(self, method, path, body=None, *, actor=None, dryrun=False):
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json-patch+json' if method == 'PATCH' else 'application/json'}
        if actor: headers['Impersonate-User'] = actor
        try:
            value = self.api.call_api(path, method, body=body, header_params=headers,
                query_params=[('dryRun', 'All')] if dryrun else [], auth_settings=['BearerToken'],
                response_type='object', _return_http_data_only=True, _request_timeout=(5, 15))
            return {'status': 200, 'object': value}
        except Exception as error:
            try: value = json.loads(getattr(error, 'body', '') or '{}')
            except (ValueError, TypeError): value = {}
            return {'status': getattr(error, 'status', 0) or 0, 'reason': value.get('reason', 'Unknown'),
                'message': value.get('message', ''), 'error_class': type(error).__name__}


def response_diagnostic(response, intended_username):
    message = str(response.get('message', ''))
    message = re.sub(r'(?i)bearer\s+\S+', 'Bearer [REDACTED]', message)
    message = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED]', message)
    return {'http_status': response.get('http_status', response['status']), 'reason': str(response.get('reason', ''))[:128],
        'message': message[:1024], 'intended_username': intended_username}


def user_info_diagnostic(response, expected):
    info = response.get('object', {}).get('status', {}).get('userInfo', {})
    username = info.get('username'); groups = info.get('groups', [])
    matches = response['status'] == 200 and username == expected
    return {'http_status': response['status'], 'matches_expected': matches, 'expected_username': expected,
        'observed_username': username if matches else None,
        'observed_username_sha256': hashlib.sha256(str(username).encode()).hexdigest(),
        'group_classes': {'authenticated': 'system:authenticated' in groups,
            'serviceaccounts': 'system:serviceaccounts' in groups, 'masters': 'system:masters' in groups}}


def broker_request_allowed(method, path, dryrun, namespaces):
    if method == 'POST' and path == SSR: return True
    if dryrun is not True or method not in ('POST', 'PATCH') or len(namespaces) != 4: return False
    for ns in namespaces:
        if not re.fullmatch(PREFIX + r'[a-f0-9]{12}-[0-3]', ns): return False
    for ns in namespaces:
        base = '/api/v1/namespaces/' + ns + '/configmaps'
        if method == 'POST' and path == base: return True
        if method == 'PATCH' and re.fullmatch(re.escape(base) + r'/[a-z0-9][-a-z0-9.]{0,252}', path): return True
        if method == 'PATCH' and path == '/apis/rbac.authorization.k8s.io/v1/namespaces/' + ns + '/roles/' + ROLE: return True
    return False


# Fixed program, never caller-provided code. Token exists only in stdin/memory.
BROKER_CODE = r"""
import json,os,re,ssl,sys,urllib.request,urllib.error
try:
    raw=sys.stdin.read(1048577)
    assert len(raw)<=1048576
    p=json.loads(raw);method=p['method'];path=p['path'];namespaces=p['namespaces']
    assert len(namespaces)==4 and all(re.fullmatch('cps-head-admission-qa-[a-f0-9]{12}-[0-3]',n) for n in namespaces)
    review=method=='POST' and path=='/apis/authentication.k8s.io/v1/selfsubjectreviews'
    allowed=review
    if p['dryrun'] is True:
        for ns in namespaces:
            base='/api/v1/namespaces/'+ns+'/configmaps'
            allowed=allowed or (method=='POST' and path==base) or (method=='PATCH' and bool(re.fullmatch(re.escape(base)+'/[a-z0-9][-a-z0-9.]{0,252}',path)))
            allowed=allowed or (method=='PATCH' and path=='/apis/rbac.authorization.k8s.io/v1/namespaces/'+ns+'/roles/cps-native-observer-operator')
    assert allowed and isinstance(p['token'],str) and len(p['token'])>20 and not any(c.isspace() for c in p['token'])
    host=os.environ['KUBERNETES_SERVICE_HOST'];host='['+host+']' if ':' in host else host
    url='https://'+host+':'+os.environ.get('KUBERNETES_SERVICE_PORT_HTTPS','443')+path+('?dryRun=All' if p['dryrun'] else '')
    context=ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
    request=urllib.request.Request(url,data=json.dumps(p['body']).encode(),method=method,headers={
        'Authorization':'Bearer '+p['token'],'Accept':'application/json',
        'Content-Type':'application/json-patch+json' if method=='PATCH' else 'application/json'})
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context))
        with opener.open(request,timeout=15) as response:
            value=json.loads(response.read(1048576));result={'status':200,'http_status':response.status}
            if review:result['object']={'status':{'userInfo':value.get('status',{}).get('userInfo',{})}}
    except urllib.error.HTTPError as error:
        value=json.loads(error.read(1048576));result={'status':error.code,'http_status':error.code,
            'reason':value.get('reason','Unknown'),'message':value.get('message','').replace(p['token'],'[REDACTED]')[:1024]}
except Exception as error:
    result={'status':0,'error_class':type(error).__name__,'reason':'BrokerFailure'}
print(json.dumps(result))
"""


class Broker:
    def __init__(self, api, options, namespaces, actor, context):
        self.options=options;self.namespaces=namespaces;self.actor=actor;self.context=context;self.api=api
        required={'namespace','deployment','deployment_uid','pod','pod_uid','container','image','audience'}
        require(set(options)==required and all(isinstance(v,str) and v for v in options.values()), 'Complete explicitly pinned broker required')
        for field in ('namespace','deployment','pod','container'):
            require(re.fullmatch(r'[a-z0-9][-a-z0-9.]{0,252}',options[field]), 'Canonical broker identity required')
        for field in ('deployment_uid','pod_uid'): require(str(uuid.UUID(options[field]))==options[field], 'Exact broker UID required')
        require(re.fullmatch(r'ghcr.io/mul-cps/cps-compute@sha256:[a-f0-9]{64}',options['image'])
            and not options['image'].endswith('0'*64) and len(options['audience'])<=256
            and not any(c.isspace() for c in options['audience']), 'Qualified image and explicit audience required')
        self.verify(api)
        response=api.request('POST','/api/v1/namespaces/'+namespaces[0]+'/serviceaccounts/'+SA+'/token',
            {'apiVersion':'authentication.k8s.io/v1','kind':'TokenRequest','spec':{'audiences':[options['audience']],'expirationSeconds':600}})
        self.token=response.get('object',{}).get('status',{}).get('token')
        require(response['status']==200 and isinstance(self.token,str) and len(self.token)>20, 'Ephemeral QA token request failed')
    def verify(self,api):
        o=self.options;ns=o['namespace']
        def read(path):
            response=api.request('GET',path);require(response['status']==200,'Pinned broker readback failed');return response['object']
        dep=read('/apis/apps/v1/namespaces/'+ns+'/deployments/'+o['deployment'])
        pod=read('/api/v1/namespaces/'+ns+'/pods/'+o['pod'])
        require(dep['metadata']['uid']==o['deployment_uid'] and pod['metadata']['uid']==o['pod_uid']
            and not dep['metadata'].get('deletionTimestamp') and not pod['metadata'].get('deletionTimestamp'), 'Pinned broker identity changed')
        owners=[r for r in pod['metadata'].get('ownerReferences',[]) if r.get('controller') is True and r.get('kind')=='ReplicaSet']
        require(len(owners)==1,'Actual broker ReplicaSet owner required')
        rs=read('/apis/apps/v1/namespaces/'+ns+'/replicasets/'+owners[0]['name'])
        require(rs['metadata']['uid']==owners[0]['uid'] and any(r.get('controller') is True and r.get('kind')=='Deployment'
            and r.get('name')==o['deployment'] and r.get('uid')==o['deployment_uid'] for r in rs['metadata'].get('ownerReferences',[])), 'Broker ownership changed')
        for spec in (dep['spec']['template']['spec'],pod['spec']):
            selected=[c for c in spec['containers'] if c['name']==o['container']]
            require(len(selected)==1 and selected[0]['image']==o['image'],'Broker image changed')
        require(pod['spec'].get('serviceAccountName')==dep['spec']['template']['spec'].get('serviceAccountName')
            and pod.get('status',{}).get('phase')=='Running' and any(c.get('type')=='Ready' and c.get('status')=='True' for c in pod['status'].get('conditions',[]))
            and any(c.get('name')==o['container'] and c.get('ready') is True and c.get('imageID','').endswith(o['image'].split('@')[1])
                for c in pod['status'].get('containerStatuses',[])), 'Actual broker is not ready at the pinned digest')
    def request(self,method,path,body=None,*,actor=None,dryrun=False):
        require(actor==self.actor and broker_request_allowed(method,path,dryrun,self.namespaces),'Only QA review/dryrun requests may use broker')
        self.verify(self.api)
        args=['kubectl']+(['--context',self.context] if self.context else [])+['--request-timeout=25s','-n',self.options['namespace'],
            'exec',self.options['pod'],'-c',self.options['container'],'-i','--','python','-I','-B','-c',BROKER_CODE]
        result=subprocess.run(args,input=json.dumps({'method':method,'path':path,'body':body,'dryrun':dryrun,
            'namespaces':self.namespaces,'token':self.token}),text=True,capture_output=True,timeout=30)
        if result.returncode:return {'status':0,'reason':'BrokerExecutionFailure'}
        value=json.loads(result.stdout);require(isinstance(value,dict) and type(value.get('status')) is int,'Closed broker response required')
        return value


def cleanup(api, resources):
    results = []
    for item in reversed(resources):
        row = dict(item, deleted=False)
        for _ in range(3):
            response = api.request('GET', endpoint(item))
            if response['status'] == 404: row['deleted'] = True; break
            if response['status'] != 200: break
            meta = response['object'].get('metadata', {})
            if meta.get('uid') != item['uid']: row['uid_changed'] = True; break
            response = api.request('DELETE', endpoint(item), {'apiVersion': 'v1', 'kind': 'DeleteOptions',
                'preconditions': {'uid': item['uid'], 'resourceVersion': meta['resourceVersion']}, 'propagationPolicy': 'Foreground'})
            if response['status'] in (200, 202, 404): row['deleted'] = True; break
            if response['status'] != 409: break
        results.append(row)
    return results


def wait_fixture_absent(api, item):
    deadline = time.monotonic() + 30
    while True:
        response = api.request('GET', endpoint(item))
        if response['status'] == 404: return
        require(response['status'] == 200, 'Isolated fixture disappearance read failed')
        require(response['object'].get('metadata', {}).get('uid') == item['uid'], 'Isolated fixture UID changed during disappearance wait')
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'Isolated fixture disappearance timed out')
        time.sleep(min(0.25, remaining))


def execute(private_dir, context=None, broker=None):
    directory = private_directory(private_dir); api = Kube(context); suffix = uuid.uuid4().hex[:12]
    namespaces = [PREFIX + suffix + '-' + str(i) for i in range(4)]
    actor = 'system:serviceaccount:' + namespaces[0] + ':' + SA
    actor_api = api
    resources = []; report = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'passed': False,
        'namespaces': namespaces, 'tests': [], 'barriers': [], 'type_checking': [], 'cleanup': [], 'stage': 'setup',
        'production_source_sha256': hashlib.sha256(Path(__file__).with_name('render.py').read_bytes()).hexdigest(),
        'limitations': ['Admission-only server dry-runs; no SDK authority, workload, image, GPU or production release qualification',
            'API-invalid UID/name mutation is not counted as VAP enforcement; replacement fixtures exercise actual UID pins',
            'Writer CREATE outside the four QA namespaces is not exercised; no outside permission is granted']}
    def create(kind, name, namespace=None, **fields):
        group = 'admissionregistration.k8s.io/v1' if kind.startswith('Validating') else 'rbac.authorization.k8s.io/v1' if kind in ('Role', 'RoleBinding') else 'v1'
        meta = {'name': name, 'labels': {'cps.compute/admission-qa': suffix}}
        if namespace: meta['namespace'] = namespace
        obj = {'apiVersion': group, 'kind': kind, 'metadata': meta, **fields}
        target = {'kind': kind, 'name': name, 'namespace': namespace}
        report['stage'] = 'create-' + kind
        response = api.request('POST', endpoint(target, False), obj)
        report['last_api_status'] = response['status']
        if response['status'] != 200:
            # A lost CREATE reply may still have committed. Adopt for cleanup
            # only the exact fresh-run labelled identity, never an older object.
            observed = api.request('GET', endpoint(target))
            if observed['status'] == 200 and observed['object'].get('metadata', {}).get('labels', {}).get('cps.compute/admission-qa') == suffix:
                resources.append(identity(observed['object'])); write_private(directory, 'resources.private.json', resources)
            raise RuntimeError('Isolated setup failed')
        actual = response['object']; resources.append(identity(actual)); write_private(directory, 'resources.private.json', resources)
        return actual
    def request(case):
        return (actor_api if case['actor'] == 'test' else api).request(case['method'], case['path'], case['body'],
            actor=actor if case['actor'] == 'test' else None, dryrun=True)
    def record(case):
        report['stage'] = case['name']
        response = request(case); accepted = response['status'] == 200
        passed = accepted if case['accepted'] else policy_denial(response, case['policy'])
        report['tests'].append({'name': case['name'], 'accepted': accepted, 'passed': passed,
            'http_status': response['status'], 'enforced_by': case['policy'] if not case['accepted'] and passed else None})
        require(passed, 'Admission decision did not match the exact policy contract')
    try:
        for ns in namespaces: create('Namespace', ns)
        create('ServiceAccount', SA, namespaces[0], automountServiceAccountToken=False)
        pointers = []; roles = []; foreign = []; unrelated = []
        for ns in namespaces:
            pointers.append(create('ConfigMap', 'qa-head', ns, data={'head.json': canonical({'generation': 1, 'reference': {'namespace': ns}, 'version': 1})}))
            foreign.append(create('ConfigMap', 'foreign-head', ns, data=deepcopy(pointers[-1]['data'])))
            rules = [{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get'], 'resourceNames': ['static-config']},
                {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get'], 'resourceNames': ['static-pod']}]
            roles.append(create('Role', ROLE, ns, rules=rules)); unrelated.append(create('Role', 'unrelated-observer', ns, rules=rules))
            access = [{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['create']},
                {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get', 'patch'], 'resourceNames': ['qa-head', 'foreign-head']},
                {'apiGroups': ['rbac.authorization.k8s.io'], 'resources': ['roles'], 'verbs': ['get', 'patch', 'escalate'],
                    'resourceNames': [ROLE, 'unrelated-observer']}]
            create('Role', SA + '-qa-access', ns, rules=access)
            create('RoleBinding', SA + '-qa-access', ns, roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': SA + '-qa-access'},
                subjects=[{'kind': 'ServiceAccount', 'namespace': namespaces[0], 'name': SA}])
        report['stage']='identity-proof'
        if broker is not None: actor_api=Broker(api,broker,namespaces,actor,context)
        review={'apiVersion':'authentication.k8s.io/v1','kind':'SelfSubjectReview','spec':{}}
        root_user=user_info_diagnostic(api.request('POST',SSR,review),actor)
        test_user=user_info_diagnostic(actor_api.request('POST',SSR,review,actor=actor),actor)
        report['identity_checks']={'root':root_user,'test':test_user,'transport':'in-cluster-token' if broker else 'impersonation'}
        require(root_user['http_status']==200 and not root_user['matches_expected'] and test_user['matches_expected'],
            'Actual request identity differs from intended isolated writer')
        definitions = isolated_policies(policy_config(pointers, roles), namespaces, suffix)
        deployed = [create(d['kind'], d['metadata']['name'], spec=d['spec']) for d in definitions]
        matrix = cases(pointers, roles, foreign, suffix)
        # Use the actual unrelated Role UID/RV; a fabricated oldObject would
        # fail an API precondition rather than prove unrelated VAP matching.
        case = next(c for c in matrix if c['name'] == 'foreign-root-unrelated-role')
        case['body'] = patch(unrelated[0], 'rules', unrelated[0]['rules'])
        def check_policies():
            report['type_checking'] = []
            for definition in deployed:
                state = api.request('GET', endpoint(identity(definition)))
                require(state['status'] == 200 and state['object']['metadata']['uid'] == definition['metadata']['uid']
                    and state['object']['spec'] == definition['spec'], 'Temporary policy or binding changed')
                if definition['kind'] != 'ValidatingAdmissionPolicy': continue
                status = state['object'].get('status', {}); warnings = status.get('typeChecking', {}).get('expressionWarnings', [])
                report['type_checking'].append({'policy': definition['metadata']['name'], 'available': 'typeChecking' in status,
                    'warning_count': len(warnings), 'observed_generation': status.get('observedGeneration')})
                require(not warnings, 'Admission type checking warnings')
        check_policies()
        report['namespace_selectors'] = []
        for ns in namespaces:
            observed=api.request('GET','/api/v1/namespaces/'+ns)
            label=observed.get('object',{}).get('metadata',{}).get('labels',{}).get('kubernetes.io/metadata.name')
            report['namespace_selectors'].append({'namespace':ns,'name_label':label,'matches':label==ns})
            require(observed['status']==200 and label==ns,'Actual namespace selector label differs')
        for family in ('approval-create', 'pointer-update', 'pregrant-update'):
            barrier = next(c for c in matrix if c.get('policy') == SA + '-' + family + '-qa-' + suffix)
            deadline = time.monotonic() + 45
            report['stage'] = 'barrier-' + family
            row = {'policy': barrier['policy'], 'attempts': 0, 'enforced': False}
            report['barriers'].append(row)
            while True:
                response = request(barrier); row['attempts'] += 1; row['http_status'] = response['status']
                row['last_response']=response_diagnostic(response,actor);row['user_info']=report['identity_checks']['test']
                if policy_denial(response, barrier['policy']): row['enforced'] = True; break
                require(time.monotonic() < deadline and response['status'] in (200, 403), 'Admission propagation barrier failed')
                time.sleep(0.25)
        for case in matrix: record(case)
        # Recreate only isolated fixtures after normal cases. Same-name API
        # updates then reach admission with a genuine changed UID, not a 422.
        for kind, old, field, value, family in [('ConfigMap', pointers[0], 'data', pointers[0]['data'], 'pointer-update'),
                ('Role', roles[0], 'rules', roles[0]['rules'], 'pregrant-update')]:
            report['stage'] = 'replacement-delete-' + kind.lower()
            require(cleanup(api, [identity(old)])[0]['deleted'], 'Isolated UID replacement delete failed')
            report['stage'] = 'replacement-wait-' + kind.lower()
            wait_fixture_absent(api, identity(old))
            report['stage'] = 'replacement-create-' + kind.lower()
            replacement = create(kind, old['metadata']['name'], old['metadata']['namespace'], **{field: value})
            record({'name': kind.lower() + '-actual-replaced-uid', 'method': 'PATCH', 'path': endpoint(identity(replacement)),
                'body': patch(replacement, field, value), 'accepted': False, 'actor': 'test', 'policy': SA + '-' + family + '-qa-' + suffix})
        check_policies()
        report['passed'] = True; report['stage'] = 'complete'
    except Exception as error:
        report['error_class'] = type(error).__name__
    finally:
        # Old identities intentionally replaced above are already gone; their
        # original records must not be allowed to delete a replacement twice.
        latest = {endpoint(item): item for item in resources}
        report['cleanup'] = cleanup(api, list(latest.values()))
        deadline = time.monotonic() + 60
        while True:
            remaining = [item for item in latest.values() if api.request('GET', endpoint(item))['status'] != 404]
            if not remaining or time.monotonic() >= deadline: break
            time.sleep(0.25)
        report['residual_count'] = len(remaining)
        report['passed'] = report['passed'] and not remaining and all(row['deleted'] for row in report['cleanup'])
        write_private(directory, 'receipt.private.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--private-dir'); parser.add_argument('--context')
    fields=('namespace','deployment','deployment-uid','pod','pod-uid','container','image','audience')
    for field in fields: parser.add_argument('--broker-'+field)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'api_calls': False})); return 0
    try:
        require(args.private_dir, 'Explicit private evidence directory required')
        options={field.replace('-','_'):getattr(args,'broker_'+field.replace('-','_')) for field in fields}
        if not any(options.values()): options=None
        result = execute(args.private_dir, args.context, broker=options)
        print(json.dumps({'passed': result['passed'], 'tests': len(result['tests']), 'residual_count': result['residual_count']}))
        return 0 if result['passed'] else 1
    except Exception as error:
        print(json.dumps({'passed': False, 'error_class': type(error).__name__})); return 1


if __name__ == '__main__': raise SystemExit(main())
