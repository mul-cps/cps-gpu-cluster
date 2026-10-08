#!/usr/bin/env python3
"""Review by default: two CPS normal fixtures, no servers/homes, expiring API tokens."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import ssl
import stat
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

HUB='https://jupyterhub.dshl.unileoben.ac.at/hub/api'
USERS=['cps-argo-qa-a-20261008','cps-argo-qa-b-20261008']
NAMESPACE='cps-personal-argo-qualification-20261008'
SECRET='scratch-normal-hub-fixtures'
PLAN={'hubApi':HUB,'users':USERS,'createBody':{'admin':False},
    'tokenBody':{'note':'bounded personal Argo HTTP fixture','expires_in':900,'scopes':['inherit']},
    'secretReference':{'namespace':NAMESPACE,'name':SECRET},'noServerStart':True,
    'noHomeProvisioningRequested':True,'authenticatorAddUserSideEffectsQualified':False,
    'cleanup':'Require matching sanitized creation receipt; DELETE only its created users after verifying no active servers; delete owned scratch Secret',
    'oauthAuthorizeTokenAuthentication':False,'productionIdentityGrantEdits':False}
SHA=hashlib.sha256(json.dumps(PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def request(path, token, *, method='GET', body=None):
    payload=None if body is None else json.dumps(body).encode()
    headers={'Authorization':'token '+token,'Content-Type':'application/json'}
    try:
        response=urllib.request.urlopen(urllib.request.Request(HUB+path,data=payload,headers=headers,method=method),
            context=ssl.create_default_context(),timeout=15)
        content=response.read(1024*1024)
        return response.status,json.loads(content) if content else None
    except urllib.error.HTTPError as error:return error.code,None


def execute(admin_file, receipt_file, cleanup=False, authenticator_hooks_reviewed=False):
    path=Path(admin_file);assert stat.S_IMODE(path.stat().st_mode)&0o077==0
    admin=path.read_text().strip()
    receipt_path=Path(receipt_file)
    if cleanup:
        receipt=json.loads(receipt_path.read_text())
        assert receipt['reviewSha256']==SHA and receipt['hubApi']==HUB
        assert receipt['createdUsers'] and set(receipt['createdUsers'])<=set(USERS)
        lookup=subprocess.run(['kubectl','-n',NAMESPACE,'get','secret',SECRET,'-o','jsonpath={.metadata}'],capture_output=True,text=True)
        if lookup.returncode==0:
            metadata=json.loads(lookup.stdout)
            assert metadata['labels']['qualification.cps/owner']=='normal-hub-fixtures'
            assert metadata['annotations']['qualification.cps/receipt-id']==receipt['receiptId']
        else:
            assert 'NotFound' in lookup.stderr
        for user in receipt['createdUsers']:
            name='/users/'+urllib.parse.quote(user,safe='');status,current=request(name,admin)
            if status==404:continue
            assert status==200 and current['admin'] is False and not current.get('servers')
            assert request(name,admin,method='DELETE')[0] in (204,200)
        result=subprocess.run(['kubectl','-n',NAMESPACE,'delete','secret',SECRET,'--ignore-not-found=true'],capture_output=True,text=True)
        assert result.returncode==0
        receipt['cleanedUp']=True;receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        return {'cleanedUp':True,'normalFixtureCount':len(receipt['createdUsers'])}
    # Check both names before creating either; never adopt existing user accounts.
    assert authenticator_hooks_reviewed, 'Root must review actual Hub add_user hooks for no home provisioning'
    assert not receipt_path.exists(), 'Use a new receipt path for each creation'
    lookup=subprocess.run(['kubectl','-n',NAMESPACE,'get','secret',SECRET,'-o','name'],capture_output=True,text=True)
    assert lookup.returncode and 'NotFound' in lookup.stderr
    assert all(request('/users/'+urllib.parse.quote(u,safe=''),admin)[0]==404 for u in USERS)
    created=[];tokens={}
    receipt={'reviewSha256':SHA,'hubApi':HUB,'createdUsers':created,'receiptId':str(uuid.uuid4()),
             'createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cleanedUp':False}
    try:
        for index,user in enumerate(USERS):
            name='/users/'+urllib.parse.quote(user,safe='')
            status,current=request(name,admin,method='POST',body=PLAN['createBody']);assert status==201
            created.append(user);receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
            assert current['admin'] is False and not current.get('servers')
            status,issued=request(name+'/tokens',admin,method='POST',body=PLAN['tokenBody']);assert status==201
            token=issued['token']
            status,identity=request('/user',token)
            assert status==200 and identity['name']==user and identity['admin'] is False
            assert 'admin' not in identity.get('roles',[]) and not identity.get('servers')
            tokens['token-'+str(index)]=token
        secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':SECRET,'namespace':NAMESPACE,
            'labels':{'qualification.cps/owner':'normal-hub-fixtures'},
            'annotations':{'qualification.cps/receipt-id':receipt['receiptId']}},'type':'Opaque','stringData':tokens}
        result=subprocess.run(['kubectl','create','-f','-'],input=json.dumps(secret),capture_output=True,text=True)
        assert result.returncode==0
    except BaseException:
        for user in created:
            name='/users/'+urllib.parse.quote(user,safe='');status,current=request(name,admin)
            if status==200 and current['admin'] is False and not current.get('servers'):
                request(name,admin,method='DELETE')
        raise
    return {'createdNormalFixtures':2,'tokenLifetimeSeconds':900,'tokensStoredOnlyInScratchSecret':True,
        'serversStarted':0,'homesProvisioned':0,'browserOAuthQualified':False}


if __name__=='__main__':
    if not __debug__:raise SystemExit('fixture script requires validation-enabled Python')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-reviewed-sha256');parser.add_argument('--admin-token-file')
    parser.add_argument('--receipt-file',help='Required sanitized creation receipt, also required for cleanup')
    parser.add_argument('--authenticator-hooks-reviewed',action='store_true',help='Root reviewed actual Hub add_user hooks and confirmed no home provisioning')
    parser.add_argument('--cleanup',action='store_true')
    options=parser.parse_args()
    try:
        if options.execute_reviewed_sha256:
            assert options.execute_reviewed_sha256==SHA
            print(json.dumps(execute(options.admin_token_file,options.receipt_file,options.cleanup,options.authenticator_hooks_reviewed)))
        else:print(json.dumps({**PLAN,'reviewSha256':SHA},indent=2))
    except Exception:
        print('fixture operation stopped; credential and user response bodies suppressed')
        raise SystemExit(1)
