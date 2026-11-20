#!/usr/bin/env python3
"""Write sanitized status, image identity, and token probe results; never read Secrets."""
import datetime
import json
from pathlib import Path
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from run import COMPUTE, FRONTEND, NS, ROOT, command


def public_endpoint(url, expected_base=False):
    try:
        response = urllib.request.urlopen(url, context=ssl.create_default_context(), timeout=15)
        body = response.read(100000)
        result = {'url':url,'status':response.status,'systemCaVerified':True}
        if expected_base:
            result['argoBaseHref'] = b'<base href="/argo/">' in body
        return result
    except urllib.error.HTTPError as error:
        return {'url':url,'status':error.code,'systemCaVerified':True}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def frontend_probe():
    result = {'status':'pending-local-port-forward','browserOwnerAuthorizationQualified':False}
    opener = urllib.request.build_opener(NoRedirect)
    observations = []
    for path in ('/argo/','/argo/api/v1/workflows/cps-workflows'):
        try:
            response = opener.open('http://127.0.0.1:18080'+path,timeout=5)
            observations.append({'path':path,'status':response.status})
        except urllib.error.HTTPError as error:
            location = urllib.parse.urlsplit(error.headers.get('Location',''))
            query = urllib.parse.parse_qs(location.query)
            observations.append({'path':path,'status':error.code,
                'locationOrigin':location.scheme+'://'+location.netloc,'locationPath':location.path,
                'clientId':query.get('client_id'),'redirectUri':query.get('redirect_uri'),
                'queryKeys':sorted(query)})
        except urllib.error.URLError:
            return result
    result['unauthenticatedRequests'] = observations
    assert all(o['status'] == 302 and o['locationOrigin'] == 'https://jupyterhub.dshl.unileoben.ac.at'
               and o['locationPath'] == '/hub/api/oauth2/authorize' for o in observations)
    result['status'] = 'startup-and-unauthenticated-failclosed-passed'
    result['trustedCaParsing'] = json.loads(command(['kubectl','-n',NS,'exec','deployment/cps-argo-ui','--',
        'python','-c',"import json,ssl; paths=['/trust/ca.crt','/etc/ssl/certs/ca-certificates.crt']; [ssl.create_default_context(cafile=p) for p in paths]; print(json.dumps({'computeCaParsed':True,'hubNativeSystemCaParsed':True}))"]))
    return result


pods = json.loads(command(['kubectl','-n',NS,'get','pods','-o','json']))['items']
report = {
    'schemaVersion':1, 'scope':'supporting-not-production', 'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'namespace':NS, 'clusterSource':command(['git','-C',str(ROOT),'rev-parse','HEAD']).strip(),
    'compute':{'image':COMPUTE,'sourceCommit':'40b9525'},
    'frontend':{'image':FRONTEND,'sourceCommit':'5bf026f'},
    'boundaries':{'productionActivation':False,'dynamicSharingActivation':False,'hubOAuthRegistration':False,
        'publicIngress':False,'existingNetworkPolicyEdits':False,'productionCredentialReads':False,'gpuUse':False},
    'publicHttps':[public_endpoint('https://jupyterhub.dshl.unileoben.ac.at/hub/api'),
        public_endpoint('https://jupyterhub.dshl.unileoben.ac.at/argo/', True)],
    'pods':[], 'tokenProbe':{'status':'pending'}, 'frontendProbe':frontend_probe(),
}
cron = json.loads(command(['kubectl','-n',NS,'get','cronjob','argo-ui-token-rotator','-o','json']))
report['rotatorTemplateSha256'] = cron['metadata']['annotations']['qualification.cps/rotator-template-sha256']
report['rotatorSuspended'] = cron['spec']['suspend']
report['qualificationHistory'] = [
    {'stage':'unmodified-8a05bc8-chart','outcome':'failed','error':"AttributeError: module 'kubernetes.client' has no attribute 'V1TokenRequest'"},
    {'stage':'root-chart-correction','change':'Use API TokenRequest dictionary to avoid generated Python client model-name drift'},
    {'stage':'reader-probe-client','change':'Disable in-cluster rotating-SA credential refresh hook before testing a distinct issued-reader token'},
    {'stage':'image-auth','change':'Operator independently provisioned scratch imagePullSecret; harness reads only its reference'}]
for pod in pods:
    entry = {'name':pod['metadata']['name'],'node':pod['spec'].get('nodeName'),'phase':pod['status']['phase'],
             'containers':[]}
    for container in pod['status'].get('containerStatuses',[]):
        state = container['state']
        requested = next(c['image'] for c in pod['spec']['containers'] if c['name'] == container['name'])
        entry['containers'].append({'name':container['name'],'runtimeImage':container['image'],'requestedImage':requested,
            'imageID':container.get('imageID',''),'ready':container['ready'],
            'state':next(iter(state)), 'reason':next(iter(state.values())).get('reason'),
            'exitCode':next(iter(state.values())).get('exitCode')})
    report['pods'].append(entry)
    # The harness logs only generic rotation success and sanitized booleans/statuses.
    if pod['metadata']['name'].startswith('bounded-personal-probe') and any('terminated' in s['state'] for s in pod['status'].get('containerStatuses',[])):
        logs = command(['kubectl','-n',NS,'logs',pod['metadata']['name']])
        for line in logs.splitlines():
            if line.startswith('QUALIFICATION_JSON='):
                report['tokenProbe'] = {'status':'passed',**json.loads(line.split('=',1)[1])}
                if report['tokenProbe'].get('chart_rotator_unmodified') != 'passed':
                    report['tokenProbe']['status'] = 'chart-failed-protocol-passed-after-correction'
        if report['tokenProbe']['status'] != 'passed':
            report['tokenProbe'] = {'status':'failed','reason':'runner exited without sanitized success record'}
events = json.loads(command(['kubectl','-n',NS,'get','events','-o','json']))['items']
report['imagePullFailures'] = [{'reason':e['reason'],'message':e['message']} for e in events if e.get('reason') == 'Failed' and e.get('message','').startswith('Failed to pull image')]
if any(c['reason'] in ('ErrImagePull','ImagePullBackOff') for p in report['pods'] for c in p['containers']):
    report['tokenProbe']['status'] = 'blocked-image-pull'
    report['frontendProbe']['status'] = 'blocked-image-pull'
Path(__file__).with_name('observed.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'tokenProbe':report['tokenProbe']['status'],'frontendProbe':report['frontendProbe']['status'],
    'podCount':len(pods),'imagePullFailureCount':len(report['imagePullFailures'])}))
