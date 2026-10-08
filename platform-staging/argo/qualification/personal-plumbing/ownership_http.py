#!/usr/bin/env python3
"""Focused real HTTP ownership probe; accepts only normal-user Hub token files."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request


def qa_runtime(current, fixture_users):
    """Clone configuration only: production identities/grants/credentials are untouched."""
    result=copy.deepcopy(current)
    result.update({'state_directory':'/tmp/qa-state','policy_file':'/policy/policy.json',
        'argo_url':'https://jupyterhub.dshl.unileoben.ac.at/argo',
        'argo_ca_file':'/etc/ssl/certs/ca-certificates.crt','argo_token_file':'/argo-reader/token',
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


def get(url, *, token=None, source=None, context):
    headers={}
    if token:headers['Authorization']=('Bearer ' if source else 'token ')+token
    if source:headers['X-CPS-Hub']=source
    try:
        response=urllib.request.urlopen(urllib.request.Request(url,headers=headers),context=context,timeout=15)
        body=response.read(8*1024*1024+1)
        assert len(body)<=8*1024*1024, 'Bounded response required'
        return response.status,json.loads(body)
    except urllib.error.HTTPError as error:
        return error.code, None  # Do not print private error bodies or workflow data.


def probe(spec):
    gateway=spec['gatewayUrl'].rstrip('/')
    assert urllib.parse.urlsplit(gateway).scheme=='https'
    context=ssl.create_default_context(cafile=spec['gatewayCaFile'])
    namespace='cps-workflows';base=gateway+'/argo/api/v1/workflows/'+namespace
    results=[]
    for case in spec['visitors']:
        source=case['source'];assert source in ('cps','cit')
        token=Path(case['tokenFile']).read_text().strip()
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


if __name__=='__main__':
    if not __debug__:raise SystemExit('ownership probe requires validation-enabled Python')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('private_fixture_spec')
    options=parser.parse_args()
    try:print(json.dumps(probe(json.loads(Path(options.private_fixture_spec).read_text()))))
    except Exception:
        print('ownership probe failed; credentials, identities, and response bodies suppressed')
        raise SystemExit(1)
