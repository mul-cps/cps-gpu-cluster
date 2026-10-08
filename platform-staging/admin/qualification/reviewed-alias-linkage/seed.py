#!/usr/bin/env python3
"""Explicit own-account API seed using existing Hub administration and short TTL.

No service token is a visitor credential. A minimal user token is issued by the
owning Hub API or explicitly authorized native Hub operator and used only against
its unchanged authenticated console handler, including federation freshness.
Tokens remain in process memory and are revoked in finally; output is sanitized.
"""
import argparse
import base64
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess

import capture
import handover

HUB = r'''
import json,os,sys,urllib.request,urllib.error
input=json.load(sys.stdin)
url=os.environ['JUPYTERHUB_API_URL'].rstrip('/')+'/users/'+input['username']+'/tokens'
if input['operation']=='delete':url+='/'+input['token_id']
body=json.dumps(input['body']).encode() if input['operation']=='create' else None
request=urllib.request.Request(url,data=body,method='POST' if body else 'DELETE',
    headers={'Authorization':'token '+input['admin_token'],'Content-Type':'application/json'})
try:
    reply=urllib.request.urlopen(request,timeout=15)
    print(json.dumps({'status':reply.status,'body':json.load(reply) if body else None}))
except urllib.error.HTTPError as error:
    print(json.dumps({'status':error.code,'body':None}))
'''

CONSOLE = r'''
import json,os,sys,urllib.request,urllib.error
from http.cookies import SimpleCookie
input=json.load(sys.stdin)
base='http://127.0.0.1:10101'+os.environ['JUPYTERHUB_SERVICE_PREFIX'].rstrip('/')
headers={'Authorization':'token '+input['user_token'],'Content-Type':'application/json'}
bootstrap=urllib.request.urlopen(urllib.request.Request(base+'/api/compute/xsrf',headers=headers),timeout=15)
assert bootstrap.status==200
xsrf=json.load(bootstrap)['xsrf_token']
cookies=SimpleCookie()
for cookie in bootstrap.headers.get_all('Set-Cookie',[]):cookies.load(cookie)
assert '_xsrf' in cookies
headers.update({'X-XSRFToken':xsrf,'Cookie':'_xsrf='+cookies['_xsrf'].value})
url=base+'/api/identities'
request=urllib.request.Request(url,data=json.dumps(input['payload']).encode(),method='POST',
    headers=headers)
try:
    reply=urllib.request.urlopen(request,timeout=15)
    data=json.load(reply)
    # Never echo a credential or optional email metadata.
    linked=data['linked'][input['username']]
    print(json.dumps({'status':reply.status,'method':'POST','path':url.split('10101',1)[1],
        'authenticated_csrf_bootstrap':True,'identity':{k:linked[k] for k in ('person_id','authority','review_actor','review_reason','reviewed_at')}}))
except urllib.error.HTTPError as error:
    print(json.dumps({'status':error.code,'method':'POST','body_omitted':True}))
'''

OPERATOR = r'''
import contextlib,io,json,sys
from jupyterhub.app import JupyterHub
from jupyterhub import orm
input=json.load(sys.stdin)
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
    hub=JupyterHub();hub.load_config_file('/usr/local/etc/jupyterhub/jupyterhub_config.py');hub.init_db()
user=orm.User.find(hub.db,USER)
assert user is not None and user.name==USER and user.admin is True
note='Authorized reviewed own-account alias linkage; Rancher u-vhm9n/cpsadmin'
scopes=['read:users:name!user='+USER,'access:services!service='+SERVICE]
if input['operation']=='create':
    token=user.new_api_token(note=note,expires_in=900,scopes=scopes)
    entry=orm.APIToken.find(hub.db,token)
    assert entry is not None and entry.user_id==user.id and entry.scopes==scopes and entry.expires_at is not None
    print(json.dumps({'status':201,'body':{'token':token,'id':str(entry.id),'user':USER,'scopes':entry.scopes,'expires_at':entry.expires_at.isoformat()+'Z'}}))
elif input['operation']=='delete':
    entry=hub.db.query(orm.APIToken).filter(orm.APIToken.id==int(input['token_id']),orm.APIToken.user_id==user.id,orm.APIToken.note==note).one()
    hub.db.delete(entry);hub.db.commit()
    assert hub.db.query(orm.APIToken).filter(orm.APIToken.id==int(input['token_id'])).first() is None
    print(json.dumps({'status':204,'body':None}))
elif input['operation']=='cleanup-owned':
    entries=hub.db.query(orm.APIToken).filter(orm.APIToken.user_id==user.id,orm.APIToken.note==note).all()
    for entry in entries:
        assert entry.scopes==scopes and entry.expires_at is not None
        hub.db.delete(entry)
    hub.db.commit();print(json.dumps({'status':204,'removed_count':len(entries)}))
else:raise ValueError('Only explicit reviewed token issuance/revocation supported')
hub.db.close()
'''

VERIFY_REVOKED = r'''
import json,os,sys,urllib.request,urllib.error
token=json.load(sys.stdin)['token']
request=urllib.request.Request(os.environ['JUPYTERHUB_API_URL'].rstrip('/')+'/user',headers={'Authorization':'token '+token})
try:
    reply=urllib.request.urlopen(request,timeout=15)
    print(json.dumps({'status':reply.status}))
except urllib.error.HTTPError as error:print(json.dumps({'status':error.code}))
'''


def call(deployment, code, value):
    result = subprocess.run(['kubectl','-n',capture.NS,'exec','-i','deployment/'+deployment,
                             '--','python','-c',code],input=json.dumps(value),capture_output=True,text=True,timeout=45)
    if result.returncode: raise RuntimeError('Authenticated API operation failed; response and credentials omitted')
    return json.loads(result.stdout)


def operator_call(hub, operation, token_id=None):
    handover.require(hub in handover.ALIASES, 'Operator issuance is limited to the two exact reviewed accounts')
    namespace={'cps':'jupyterhub','cit':'cit-jhub'}[hub]
    code='USER='+repr(handover.ALIASES[hub])+'\nSERVICE='+repr(hub+'-admin')+'\n'+OPERATOR
    value={'operation':operation}
    if token_id is not None:value['token_id']=token_id
    result=subprocess.run(['kubectl','-n',namespace,'exec','-i','deployment/hub','--','python','-c',code],
                          input=json.dumps(value),capture_output=True,text=True,timeout=45)
    if result.returncode:raise RuntimeError('Native Hub operator issuance/revocation failed; credentials and stderr omitted')
    return json.loads(result.stdout)


def seed_account(hub, person, *, expected_inventory, native_operator=False):
    handover.require(hub in handover.ALIASES, 'Exact owning Hub required')
    deployment=hub+'-admin';username=handover.ALIASES[hub]
    console_receipt=capture.qualified_console(hub)
    observed=capture.exec_json(deployment,'TARGET='+repr((hub,username))+'\nSOURCE='+repr(handover.SOURCE)+'\nIMAGE='+repr(handover.IMAGE)+'\n'+capture.CONSOLE)
    handover.require(observed == expected_inventory, 'Concurrent account/identity inventory change; re-review before seed')
    if observed['alias_proofs']:
        handover.validate_proof(observed['alias_proofs'][0],person)
        # Explicit retry re-reviews the same preserved UUID via the real API.
        # It cannot reassign a person; a lost HTTP receipt is not inferred success.
    created=token=token_id=None
    try:
        if native_operator:
            created=operator_call(hub,'create')
        else:
            secret=capture.get('secret',deployment+'-oauth')
            admin_token=base64.b64decode(secret['data']['hub-api-token'],validate=True).decode()
            created=call(deployment,HUB,{'operation':'create','username':username,'admin_token':admin_token,
                'body':{'note':'Explicit own-account reviewed-alias API qualification; Rancher u-vhm9n/cpsadmin',
                        'expires_in':900,'scopes':['read:users:name!user='+username,'access:services!service='+deployment]}})
        handover.require(created['status']==201 and isinstance(created.get('body'),dict), 'Owning Hub must issue minimal short-lived actual-user token')
        token=created['body'].get('token');token_id=created['body'].get('id')
        handover.require(isinstance(token,str) and token and isinstance(token_id,str) and token_id, 'Exact native Hub token/ID receipt required')
        expected_scopes=['read:users:name!user='+username,'access:services!service='+deployment]
        handover.require(created['body'].get('scopes')==expected_scopes and created['body'].get('user')==username, 'Actual minimal owning user token scopes/owner required')
        stamp=created['body'].get('expires_at')
        handover.require(isinstance(stamp,str) and stamp, 'Actual token expiry timestamp required')
        expires=datetime.fromisoformat(stamp)
        handover.require(expires.tzinfo is not None, 'Actual token expiry must include a timezone')
        remaining=(expires-datetime.now(timezone.utc)).total_seconds()
        handover.require(0<remaining<=930, 'Actual bounded900s token expiry required')
        handover.require(capture.qualified_console(hub)==console_receipt, 'Concurrent qualified console generation changed before API review')
        response=call(deployment,CONSOLE,{'username':username,'user_token':token,'payload':handover.alias_payload(hub,person)})
        handover.require(response['status'] == 200, 'Unchanged authenticated owning console API rejected review; no bypass permitted')
        after=capture.exec_json(deployment,'TARGET='+repr((hub,username))+'\nSOURCE='+repr(handover.SOURCE)+'\nIMAGE='+repr(handover.IMAGE)+'\n'+capture.CONSOLE)
        handover.require(len(after['alias_proofs']) == 1, 'One exact persisted source alias required')
        proof=after['alias_proofs'][0];handover.validate_proof(proof,person)
        handover.require(capture.qualified_console(hub)==console_receipt, 'Concurrent console image/generation changed during review')
        handover.require(response['identity']['person_id'] == person and response['identity']['review_actor'] == username, 'Truthful owning Hub actor/UUID required')
        return {'status':'reviewed','api':response,'proof':proof,'console_receipt':console_receipt,'token_metadata':{
            'ttl_seconds':900,'expires_at':created['body'].get('expires_at'),'scopes':created['body'].get('scopes'),
            'revoked':True,'issuance':'authorized-native-Hub-operator' if native_operator else 'owning-Hub-token-API',
            'credential_reference':'Rancher u-vhm9n/cpsadmin Kubernetes owning Hub authority' if native_operator else deployment+'-oauth:hub-api-token'}}
    finally:
        if created is None and native_operator:
            deleted=operator_call(hub,'cleanup-owned')
            handover.require(deleted['status']==204, 'Unknown native issuance outcome must be reconciled by exact user/note/scopes cleanup')
        elif created is not None and created['status']==201:
            if native_operator and token_id is None:
                deleted=operator_call(hub,'cleanup-owned')
            else:
                deleted=operator_call(hub,'delete',token_id) if native_operator else call(deployment,HUB,{'operation':'delete','username':username,'token_id':token_id,'admin_token':admin_token})
            handover.require(deleted['status'] == 204, 'Short-lived audit token revocation failed; reconcile its TTL without exposing it')
        if native_operator and token:
            unusable=call(deployment,VERIFY_REVOKED,{'token':token})
            handover.require(unusable['status'] in (401,403), 'Revoked token must be rejected by the actual owning Hub')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir',type=Path,required=True)
    parser.add_argument('--person',required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--native-operator',action='store_true',help='Explicit authorized narrow owning Hub operator issuance for these accounts only')
    args=parser.parse_args()
    handover.require(args.execute, 'Explicit execution flag required after administrative review and backup')
    inventory=handover.private_read(args.private_dir/'inventory-with-backups.json')
    runtime=handover.private_read(args.private_dir/'runtime-before.json')
    person=handover.select_person(inventory['accounts'],runtime,proposed=args.person)
    results={}
    for hub in handover.ALIASES:
        results[hub]=seed_account(hub,person,expected_inventory=inventory['accounts'][hub],native_operator=args.native_operator)
        handover.private_write(args.private_dir/(hub+'-api-result.json'),results[hub])
    proofs=[results[hub]['proof'] for hub in handover.ALIASES]
    handover.private_write(args.private_dir/'alias-proofs.json',proofs)
    handover.private_write(args.private_dir/'runtime-reviewed-alias.json',handover.compile_runtime(runtime,proofs,person))
    print(json.dumps({'person_id':person,'api_results':results,'gateway_activated':False,'grants_changed':False},indent=2))


if __name__ == '__main__': main()
