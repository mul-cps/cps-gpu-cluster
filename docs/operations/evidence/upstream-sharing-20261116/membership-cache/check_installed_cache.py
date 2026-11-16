"""Offline behavior checks inside exact immutable notebook; no network or real tokens."""
import asyncio
import json
import os
from unittest.mock import patch
from traitlets.config import Config
from jupyterhub.services.auth import HubAuth, HubOAuth
from jupyterhub.singleuser.extension import JupyterHubIdentityProvider
from jupyter_server.serverapp import ServerApp

async def case(age):
    auth=HubOAuth(config=Config({'HubOAuth':{'cache_max_age':age}}))
    calls=[]
    allowed={'name':'offline-user','scopes':['access:servers!server=offline/rtc']}
    revoked={'name':'offline-user','scopes':[]}
    async def fake_api(*args,**kwargs):
        calls.append(1)
        return allowed if len(calls)==1 else revoked
    auth._api_request=fake_api
    with patch('jupyterhub.services.auth.time.monotonic',return_value=100.0):
        first=await auth.user_for_token('offline-test-value',session_id='offline-session',sync=False)
    with patch('jupyterhub.services.auth.time.monotonic',return_value=100.1):
        cached=await auth.user_for_token('offline-test-value',session_id='offline-session',sync=False)
    with patch('jupyterhub.services.auth.time.monotonic',return_value=401.1 if age==300 else 101.1):
        after=await auth.user_for_token('offline-test-value',session_id='offline-session',sync=False)
    assert first==allowed and cached==allowed
    assert after==(allowed if age==0 else revoked)
    return {'cache_max_age':age,'actual_cache_max_age':auth.cache.max_age,'hub_api_calls':len(calls),'cached_after_authoritative_change':cached==allowed,'expired_response_has_removed_scope':after==revoked}

async def main():
    rows=[await case(age) for age in [300,1,0]]
    with patch.dict(os.environ,{'JUPYTERHUB_AUTH_CACHE_MAX_AGE':'1'}):
        assert HubOAuth().cache_max_age==300
    config=Config({'HubOAuth':{'cache_max_age':1}})
    provider=JupyterHubIdentityProvider(config=config)
    assert provider.hub_auth.cache_max_age==1 and provider.hub_auth.cache.max_age==1
    inherited=HubOAuth(config=Config({'HubAuth':{'cache_max_age':1}}))
    assert inherited.cache_max_age==1
    app=ServerApp()
    app.parse_command_line(['--HubOAuth.cache_max_age=1'])
    cli_provider=JupyterHubIdentityProvider(parent=app)
    assert cli_provider.hub_auth.cache_max_age==1 and cli_provider.hub_auth.cache.max_age==1
    print(json.dumps({'status':'PASS','offline_only':True,'cases':rows,'invented_env_ignored':True,'identity_provider_nested_huboauth_setting':1,'base_hubauth_setting_inherited':True,'serverapp_cli_nested_identity_cache_age':1},indent=2))

asyncio.run(main())
