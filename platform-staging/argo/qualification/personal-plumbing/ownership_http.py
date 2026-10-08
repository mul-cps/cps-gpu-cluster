#!/usr/bin/env python3
"""Focused real HTTP ownership probe; accepts only normal-user Hub token files."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import ssl
import stat
import urllib.error
import urllib.parse
import urllib.request


def qa_runtime(current, fixture_users):
    """Clone configuration only: production identities/grants/credentials are untouched."""
    result=copy.deepcopy(current)
    result.update({'state_directory':'/tmp/qa-state','policy_file':'/policy/policy.json',
        'argo_url':'https://cps-argo-argo-workflows-server.cps-argo.svc.cluster.local:2746',
        'argo_ca_file':'/trust/ca.crt','argo_token_file':'/argo-reader/token',
        'argoUi':{'enabled':True,'readerTokenFile':'/argo-reader/token','temporaryDirectory':'/tmp'},
        'service_token_envs':{'cps':'QA_SERVICE_CPS','cit':'QA_SERVICE_CIT'},'metrics_token_envs':{},
        'jobsets':{'enabled':False},'shutdownObserver':{'kubernetes':False},'storage':{'enabled':False}})
    result.pop('argo_token_env',None)
    for source,hub in result['hubs'].items():
        hub['url']=('https://jupyterhub.dshl.unileoben.ac.at' if source=='cps' else 'https://jhub.dshl.unileoben.ac.at')
        hub['service_token_env']='QA_HUB_'+source.upper()
        hub['canonical_people']=dict(fixture_users) if source=='cps' else {}
        hub['workspace_principals']={}
    if result.get('artifacts'):
        result['artifacts']['lifecycle']={'enabled':False}
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def request(url, *, token=None, source=None, context, method='GET'):
    headers={}
    if token:headers['Authorization']=('Bearer ' if source else 'token ')+token
    if source:headers['X-CPS-Hub']=source
    try:
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),NoRedirect())
        response=opener.open(urllib.request.Request(url,headers=headers,method=method),timeout=15)
        body=response.read(8*1024*1024+1)
        assert len(body)<=8*1024*1024, 'Bounded response required'
        return response.status,{k.lower():v for k,v in response.headers.items()},body
    except urllib.error.HTTPError as error:
        return error.code,{},b''  # Do not print private error bodies or workflow data.


def get(url, **kwargs):
    status,_,body=request(url,**kwargs)
    return status,json.loads(body) if status==200 else None


def probe(spec):
    gateway=spec['gatewayUrl'].rstrip('/')
    assert urllib.parse.urlsplit(gateway).scheme=='https'
    context=ssl.create_default_context(cafile=spec['gatewayCaFile'])
    namespace='cps-workflows';base=gateway+'/argo/api/v1/workflows/'+namespace
    results=[]
    for case in spec['visitors']:
        source=case['source'];assert source in ('cps','cit')
        token_file=Path(case['tokenFile']);assert stat.S_IMODE(token_file.stat().st_mode)&0o007==0
        token=token_file.read_text().strip()
        hub=('https://jupyterhub.dshl.unileoben.ac.at' if source=='cps' else 'https://jhub.dshl.unileoben.ac.at')
        status,user=get(hub+'/hub/api/user',token=token,context=ssl.create_default_context())
        assert status==200 and user['name']==case['expectedHubUser'] and user.get('admin') is False
        assert user.get('kind','user')=='user' and 'admin' not in user.get('roles',[])
        status,listing=get(base,token=token,source=source,context=context)
        assert status==200 and isinstance(listing.get('items'),list)
        owner=hashlib.sha256(case['canonicalPerson'].encode()).hexdigest()[:63]
        assert all(item['metadata']['labels'][spec['ownerLabel']]==owner for item in listing['items'])
        assert case['ownWorkflow'] in {item['metadata']['name'] for item in listing['items']}
        outcomes={'ownList':status,'normalHubIdentityVerified':True}
        for label,name,expected in [('ownDetail',case['ownWorkflow'],200),('foreignDetail',case['foreignWorkflow'],404),
                                    ('unknownDetail',case['unknownWorkflow'],404)]:
            status,value=get(base+'/'+urllib.parse.quote(name,safe=''),token=token,source=source,context=context)
            assert status==expected
            if expected==200:assert value['metadata']['name']==name
            outcomes[label]=status
        results.append({'source':source,'visitorLabel':case['label'],**outcomes})
    status,_=get(base,context=context);assert status==401
    return {'scope':'actual-normal-Hub-token-gateway-HTTP-only','passed':True,'cases':results,
        'unauthenticated':status,'browserOAuthQualified':False,'downloadsSSEQualified':False}


def extended_probe(spec):
    """Actual normal Hub tokens; requires independently created controlled records.

    Successful own logs/artifacts are required. Missing records or provenance do
    not count as success; a partial run produces no passing qualification receipt.
    Fixture response bytes and credentials stay in process memory.
    """
    result=probe(spec)
    gateway=spec['gatewayUrl'].rstrip('/')
    context=ssl.create_default_context(cafile=spec['gatewayCaFile'])
    namespace='cps-workflows';base=gateway+'/argo/api/v1/workflows/'+namespace
    for case,outcomes in zip(spec['visitors'],result['cases']):
        token=Path(case['tokenFile']).read_text().strip();source=case['source']
        checks={}
        for label,name,node,expected in [('own',case['ownWorkflow'],case['ownNode'],200),
                                        ('foreign',case['foreignWorkflow'],case['foreignNode'],404),
                                        ('unknown',case['unknownWorkflow'],case['unknownNode'],404)]:
            status,headers,body=request(base+'/'+urllib.parse.quote(name,safe='')+'/log',
                token=token,source=source,context=context)
            assert status==expected
            if expected==200:
                assert 'text/event-stream' in headers.get('content-type','')
                assert case['expectedLogMarker'].encode() in body
            checks[label+'Logs']=status
            artifact=(gateway+'/argo/artifact-files/'+namespace+'/workflows/'+urllib.parse.quote(name,safe='')+
                '/'+urllib.parse.quote(node,safe='')+'/outputs/executed-notebook')
            for method in ('HEAD','GET'):
                status,headers,body=request(artifact,token=token,source=source,context=context,method=method)
                assert status==expected
                if expected==200 and method=='GET':
                    assert hashlib.sha256(body).hexdigest()==case['expectedArtifactSha256']
                    assert 'application/octet-stream' in headers.get('content-type','')
                checks[label+'Artifact'+method]=status
            # The personal Argo API is read only; even an owner's terminate is denied.
            status,_,_=request(base+'/'+urllib.parse.quote(name,safe='')+'/terminate',
                token=token,source=source,context=context,method='PUT')
            assert status==403
            checks[label+'TerminateDenied']=status
        outcomes['coverage']=checks
    result.update({'logsArtifactsWriteDenialQualified':True,'browserOAuthQualified':False,
                   'downloadsSSEQualified':False,'coverageScope':'finite real HTTP logs/artifacts and read-only denial; not browser or SSE reconnect'})
    return result


if __name__=='__main__':
    if not __debug__:raise SystemExit('ownership probe requires validation-enabled Python')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('private_fixture_spec')
    parser.add_argument('--extended',action='store_true',help='Require actual own/foreign logs/artifacts and terminate denial')
    options=parser.parse_args()
    try:
        private=Path(options.private_fixture_spec);assert stat.S_IMODE(private.stat().st_mode)&0o077==0
        spec=json.loads(private.read_text())
        print(json.dumps(extended_probe(spec) if options.extended else probe(spec)))
    except Exception:
        print('ownership probe failed; credentials, identities, and response bodies suppressed')
        raise SystemExit(1)
