#!/usr/bin/env python3
"""Legacy read-only S3 retention inventory. Use the packaged controller for cleanup."""
import argparse
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import ssl
import urllib.request
from urllib.parse import quote,urlsplit

POLICY={'notebook-inputs/':('temporary-expirable',14),'run-artifacts/':('run-expirable',90)}

def category(key):
    for prefix,(tag,days) in POLICY.items():
        if key.startswith(prefix) and len(key.split('/'))>=3:return tag,days
    return None

def eligible(key,modified,tags,now):
    selected=category(key)
    if not selected:return False
    tag,days=selected
    return tags.get('retention')==tag and tags.get('active')=='false' and tags.get('retained')=='false' and now-modified>=timedelta(days=days)

def terminal_proof(workflow,namespace,identifier,uid,now):
    meta=workflow.get('metadata',{});status=workflow.get('status',{})
    if not uid or meta.get('uid')!=uid or meta.get('namespace')!=namespace or meta.get('annotations',{}).get('cps.compute/notebook-id')!=identifier:return False
    if status.get('phase') not in ('Succeeded','Failed','Error'):return False
    try:finished=datetime.fromisoformat(status['finishedAt'].replace('Z','+00:00'))
    except (KeyError,ValueError,TypeError):return False
    return finished.tzinfo is not None and finished<=now

class ArgoProof:
    def __init__(self,url,namespace,token,ca):
        if urlsplit(url).scheme!='https':raise ValueError('Argo proof endpoint requires verified HTTPS')
        self.url=url.rstrip('/');self.namespace=namespace;self.token=token;self.context=ssl.create_default_context(cafile=ca)
    def get(self,name):
        request=urllib.request.Request(self.url+'/api/v1/workflows/'+quote(self.namespace,safe='')+'/'+quote(name,safe=''),headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(request,context=self.context,timeout=30) as response:return json.load(response)

def sweep(s3,bucket,proof,*,apply=False,max_deletes=10,prefix=None,now=None):
    if apply:raise ValueError('Legacy retention inventory is read-only; use the qualified packaged controller')
    now=now or datetime.now(timezone.utc);report={'examined':0,'eligible':0,'deleted':0,'skipped':0,'errors':0,'objects':[]}
    prefixes=[prefix] if prefix else list(POLICY)
    if any(not any(p.startswith(allowed) for allowed in POLICY) for p in prefixes):raise ValueError('Unmanaged retention prefix')
    paginator=s3.get_paginator('list_objects_v2')
    for scan_prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket,Prefix=scan_prefix):
            for obj in page.get('Contents',[]):
                key=obj['Key'];report['examined']+=1
                try:
                    tags={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
                    if not eligible(key,obj['LastModified'],tags,now):report['skipped']+=1;continue
                    head=s3.head_object(Bucket=bucket,Key=key);meta=head.get('Metadata',{})
                    name=meta.get('cps-workflow');uid=meta.get('cps-workflow-uid');identifier=key.split('/')[1]
                    if not name or not uid:report['skipped']+=1;continue
                    workflow=proof.get(name)
                    if not terminal_proof(workflow,proof.namespace,identifier,uid,now):report['skipped']+=1;continue
                    finished=datetime.fromisoformat(workflow['status']['finishedAt'].replace('Z','+00:00'))
                    if now-finished<timedelta(days=category(key)[1]):report['skipped']+=1;continue
                    report['eligible']+=1
                except Exception:
                    # Unknown/missing telemetry, old SDKs or unsupported conditional delete preserve data.
                    report['errors']+=1
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--max-deletes',type=int,default=10);p.add_argument('--prefix');args=p.parse_args()
    if args.apply:p.error('Legacy retention inventory is read-only; use the qualified packaged controller')
    import boto3
    from botocore.client import Config
    if not 1<=args.max_deletes<=1000:raise ValueError('Bounded deletion limit required')
    settings=json.loads(args.config.read_text())
    if urlsplit(settings['endpoint']).scheme!='https':raise ValueError('S3 requires verified HTTPS')
    s3=boto3.client('s3',endpoint_url=settings['endpoint'],aws_access_key_id=settings['accessKey'],aws_secret_access_key=settings['secretKey'],region_name='us-east-1',verify=settings['ca'],config=Config(s3={'addressing_style':'path'}))
    proof=ArgoProof(settings['argoUrl'],settings['namespace'],Path(settings['argoTokenFile']).read_text().strip(),settings.get('argoCa'))
    print(json.dumps(sweep(s3,settings['bucket'],proof,apply=args.apply,max_deletes=args.max_deletes,prefix=args.prefix),indent=2))
if __name__=='__main__':main()
