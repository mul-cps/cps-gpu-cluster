#!/usr/bin/env python3
"""Authorized native Hub token issuance for exact disposable-user administration.

No browser/session issuance. The native token authorizes only the listed fixture
API endpoints and is revoked in finally, with actual Hub rejection checked.
Visitor tokens come from unchanged Hub REST APIs and remain only in a Secret.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

import fixture_hub_users as fixtures

SCOPES=['read:users:name!user=bjoern',*[scope+'!user='+user for user in fixtures.USERS
    for scope in ('admin:users','read:users','tokens')]]

ISSUER=r'''
import contextlib,datetime,io,json,sys
value=json.load(sys.stdin)
sink=io.StringIO()
with contextlib.redirect_stdout(sink),contextlib.redirect_stderr(sink):
    from jupyterhub.app import JupyterHub
    from jupyterhub import orm
    hub=JupyterHub();hub.load_config_file('/usr/local/etc/jupyterhub/jupyterhub_config.py');hub.init_db()
    user=orm.User.find(hub.db,'bjoern')
    assert user is not None and user.admin is True
    if value['operation']=='create':
        token=user.new_api_token(note=value['note'],expires_in=900,scopes=value['scopes'])
        entry=orm.APIToken.find(hub.db,token)
        assert entry.user_id==user.id and entry.scopes==value['scopes']
        remaining=(entry.expires_at-datetime.datetime.utcnow()).total_seconds()
        assert 880<=remaining<=900
        result={'token':token,'id':entry.id,'ttlSeconds':900,'scopes':entry.scopes,
                'expiresAt':entry.expires_at.isoformat()+'Z','owningAdminUser':'bjoern'}
    else:
        assert value['operation']=='delete'
        entry=hub.db.query(orm.APIToken).filter(orm.APIToken.id==value['id'],orm.APIToken.user_id==user.id,
                                             orm.APIToken.note==value['note']).one()
        hub.db.delete(entry);hub.db.commit()
        assert hub.db.query(orm.APIToken).filter(orm.APIToken.id==value['id']).first() is None
        result={'nativeTokenRevoked':True}
    hub.db.close()
print(json.dumps(result))
'''


def operator(value):
    result=subprocess.run(['kubectl','-n','jupyterhub','exec','-i','deployment/hub','--','python','-c',ISSUER],
        input=json.dumps(value),capture_output=True,text=True,timeout=45)
    if result.returncode:raise RuntimeError('Native fixture maintenance token operation failed; private output suppressed')
    return json.loads(result.stdout)


def execute(receipt_file, cleanup=False):
    fixtures.NAMESPACE='cps-compute';fixtures.PLAN['secretReference']['namespace']=fixtures.NAMESPACE
    fixtures.SHA=hashlib.sha256(json.dumps(fixtures.PLAN,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    note='Authorized bounded personal Argo disposable-fixture API maintenance '+str(uuid.uuid4())
    issued=operator({'operation':'create','note':note,'scopes':SCOPES})
    token=issued.pop('token')
    try:
        status,identity=fixtures.request('/user',token)
        assert status==200 and identity['name']=='bjoern' and identity['admin'] is True
        result=fixtures.execute(None,receipt_file,cleanup,True,native_token=token)
        result['fixtureMaintenanceIssuance']={'authority':'authorized owning Hub Kubernetes maintenance',
            'ttlSeconds':issued['ttlSeconds'],'scopes':issued['scopes'],'expiresAt':issued['expiresAt'],
            'nativeTokenRevoked':True,'notAVisitorCredential':True}
        return result
    finally:
        revoked=operator({'operation':'delete','id':issued['id'],'note':note})
        assert revoked['nativeTokenRevoked'] is True
        assert fixtures.request('/user',token)[0] in (401,403)


if __name__=='__main__':
    if not __debug__:raise SystemExit('Native fixture helper requires validation-enabled Python')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--receipt-file',required=True)
    parser.add_argument('--cleanup',action='store_true');options=parser.parse_args()
    try:print(json.dumps(execute(options.receipt_file,options.cleanup)))
    except Exception:
        print('native fixture administration stopped; credential and response bodies suppressed')
        raise SystemExit(1)
