#!/usr/bin/env python3
"""Installed-image asset transport check; fixture identity is NOT Hub OAuth proof.

Run through stdin in the owned QA frontend. The unchanged launcher on 8080 must
fail closed without a cookie. A separate loopback-only fixture on an ephemeral
port tests the actual installed allowlisted asset handler against the real TLS
backend. No credential is forwarded to that backend or emitted in the receipt.
"""
import asyncio
import json
import logging
import re
import urllib.parse

from tornado import netutil, web
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httpserver import HTTPServer

from e2x_course_hub.cps.argo_service import ArgoAssetsHandler, ArgoServiceConfig, create_argo_service


async def main():
    config=ArgoServiceConfig.from_env()
    upstream=AsyncHTTPClient(force_instance=True)
    requests=[]

    class RecordingClient:
        def fetch(self, request, **kwargs):
            assert request.validate_cert and request.ca_certs==config.native_argo_ca_file
            assert not request.headers.get('Authorization') and not request.headers.get('Cookie')
            requests.append(request.url)
            return upstream.fetch(request,**kwargs)

    class FixtureAssets(ArgoAssetsHandler):
        def get_current_user(self):
            return {'name':'asset-transport-fixture','kind':'user','admin':False}

    original=create_argo_service(config,http_client=RecordingClient())
    fixture=web.Application([(r'/argo/(.*)',FixtureAssets)],**original.settings)
    sockets=netutil.bind_sockets(0,'127.0.0.1')
    port=sockets[0].getsockname()[1]
    server=HTTPServer(fixture);server.add_sockets(sockets)
    browser=AsyncHTTPClient(force_instance=True)
    try:
        # This is the real unchanged service, with no fixture auth override.
        redirects=[]
        for path in ('/argo/','/argo/api/v1/info'):
            response=await browser.fetch(HTTPRequest('http://127.0.0.1:8080'+path,follow_redirects=False),raise_error=False)
            assert response.code==302
            target=urllib.parse.urlsplit(response.headers['Location'])
            query=urllib.parse.parse_qs(target.query)
            assert target.scheme=='https' and target.netloc==urllib.parse.urlsplit(config.hub_authorization_url).netloc
            assert query['client_id']==[config.oauth_client_id]
            assert query['redirect_uri']==[config.public_origin+'/argo/oauth_callback']
            redirects.append({'path':path,'status':302,'clientId':config.oauth_client_id})
        root='http://127.0.0.1:'+str(port)
        page=await browser.fetch(root+'/argo/workflows/cps-workflows')
        assert page.code==200 and 'text/html' in page.headers['Content-Type']
        html=page.body.decode();assert re.search(r'<base\s+href=["\']/argo/["\']',html)
        asset=re.search(r'<script[^>]+src=["\']([^"\']+)["\']',html).group(1).lstrip('/')
        assert '/' not in asset
        javascript=await browser.fetch(root+'/argo/'+asset)
        assert javascript.code==200 and 'javascript' in javascript.headers['Content-Type']
        assert not javascript.body.lstrip().startswith(b'<')
        count=len(requests)
        denied=await browser.fetch(root+'/argo/private.txt',raise_error=False)
        assert denied.code==404 and len(requests)==count
        print(json.dumps({'qualifiedScope':'installed native asset transport and unauthenticated fail-closed startup',
            'authenticationForAssetTransport':'loopback test fixture only; not Hub OAuth',
            'nativeTlsValidated':True,'nativeRoot':config.native_argo_url,'indexStatus':200,'indexBaseHref':'/argo/',
            'assetPath':'/argo/'+asset,'assetStatus':200,'assetContentType':javascript.headers['Content-Type'],
            'upstreamCredentialHeadersSent':False,'arbitraryNonAssetStatus':404,
            'arbitraryNonAssetForwarded':False,'unauthenticatedRedirects':redirects,
            'realBrowserOAuthQualified':False,'normalUserOwnershipQualified':False}))
    finally:
        server.stop();await server.close_all_connections();browser.close();upstream.close()


if __name__=='__main__':
    logging.disable(logging.CRITICAL)
    asyncio.run(main())
