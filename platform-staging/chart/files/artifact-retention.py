#!/usr/bin/env python3
"""Conservative S3 retention with live terminal Argo proof. Dry run is the default."""
import argparse
from datetime import datetime,timezone,timedelta
import json
import re
import time
from pathlib import Path
import ssl
import urllib.request
from urllib.parse import quote,urlsplit

POLICY={'notebook-inputs/':('temporary-expirable',14),'run-artifacts/':('run-expirable',90)}

def category(key):
    for prefix,(tag,days) in POLICY.items():
        if key.startswith(prefix) and len(key.split('/'))>=3 and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',key.split('/')[1]):return tag,days
    return None

def eligible(key,modified,tags,now):
    selected=category(key)
    if not selected:return False
    tag,days=selected
    return tags.get('retention')==tag and tags.get('active')=='false' and tags.get('retained')=='false' and now-modified>=timedelta(days=days)

def terminal_proof(workflow,namespace,identifier,uid,now):
    meta=workflow.get('metadata',{});status=workflow.get('status',{})
    if namespace!='cps-workflows' or not uid or meta.get('uid')!=uid or meta.get('namespace')!=namespace or meta.get('annotations',{}).get('cps.compute/notebook-id')!=identifier:return False
    if status.get('phase') not in ('Succeeded','Failed','Error'):return False
    try:finished=datetime.fromisoformat(status['finishedAt'].replace('Z','+00:00'))
    except (KeyError,ValueError,TypeError):return False
    return finished.tzinfo is not None and finished<=now

class ArgoProof:
    def __init__(self,url,namespace,token_file,ca):
        if urlsplit(url).scheme!='https':raise ValueError('Argo proof endpoint requires verified HTTPS')
        if namespace!='cps-workflows':raise ValueError('Fixed workflow namespace required')
        self.token_file=Path(token_file)
        self.token()
        self.url=url.rstrip('/');self.namespace=namespace;self.context=ssl.create_default_context(cafile=ca)
    def token(self):
        token=self.token_file.read_text().strip()
        if not token or any(c.isspace() for c in token):raise ValueError('Projected Argo token missing')
        return token
    def get(self,name):
        request=urllib.request.Request(self.url+'/api/v1/workflows/'+quote(self.namespace,safe='')+'/'+quote(name,safe=''),headers={'Authorization':'Bearer '+self.token()})
        with urllib.request.urlopen(request,context=self.context,timeout=15) as response:
            body=response.read(1048577)
            if len(body)>1048576:raise ValueError('Oversized Argo proof')
            return json.loads(body)

def sweep(s3,bucket,proof,*,apply=False,max_deletes=10,max_examined=1000,prefix=None,now=None,conditional_delete_qualified=False):
    if not isinstance(max_examined,int) or isinstance(max_examined,bool) or not 1<=max_examined<=10000:raise ValueError('Bounded examination limit required')
    if not isinstance(max_deletes,int) or isinstance(max_deletes,bool) or not 1<=max_deletes<=1000:raise ValueError('Bounded deletion limit required')
    if apply and not conditional_delete_qualified:raise ValueError('Conditional deletion capability qualification required')
    now=now or datetime.now(timezone.utc);report={'examined':0,'eligible':0,'deleted':0,'skipped':0,'errors':0,'objects':[],'apply':apply,'truncated':False}
    prefixes=[prefix] if prefix else list(POLICY)
    if any(not any(p.startswith(allowed) for allowed in POLICY) for p in prefixes):raise ValueError('Unmanaged retention prefix')
    paginator=s3.get_paginator('list_objects_v2')
    for scan_prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket,Prefix=scan_prefix,PaginationConfig={'PageSize':min(max_examined,1000)}):
            for obj in page.get('Contents',[]):
                if report['examined']>=max_examined:
                    report['truncated']=True;return report
                key=obj['Key'];report['examined']+=1
                if not key.startswith(scan_prefix):report['skipped']+=1;continue
                try:
                    tags={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
                    if not eligible(key,obj['LastModified'],tags,now):report['skipped']+=1;continue
                    head=s3.head_object(Bucket=bucket,Key=key);meta=head.get('Metadata',{})
                    name=meta.get('cps-workflow');uid=meta.get('cps-workflow-uid');identifier=key.split('/')[1]
                    if not name or not uid:report['skipped']+=1;continue
                    workflow=proof.get(name)
                    if workflow.get('metadata',{}).get('name')!=name or not terminal_proof(workflow,proof.namespace,identifier,uid,now):report['skipped']+=1;continue
                    finished=datetime.fromisoformat(workflow['status']['finishedAt'].replace('Z','+00:00'))
                    if now-finished<timedelta(days=category(key)[1]):report['skipped']+=1;continue
                    report['eligible']+=1
                    if not apply:continue
                    if report['deleted']>=max_deletes:report['truncated']=True;return report
                    # Re-read mutable eligibility and condition deletion on the observed ETag.
                    current={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
                    if current!=tags or not eligible(key,head['LastModified'],current,now):report['skipped']+=1;continue
                    latest=s3.head_object(Bucket=bucket,Key=key)
                    if latest.get('ETag')!=head.get('ETag') or latest.get('Metadata')!=meta or not eligible(key,latest['LastModified'],current,now):report['skipped']+=1;continue
                    final=proof.get(name)
                    if final.get('metadata',{}).get('name')!=name or not terminal_proof(final,proof.namespace,identifier,uid,now) or now-datetime.fromisoformat(final['status']['finishedAt'].replace('Z','+00:00'))<timedelta(days=category(key)[1]):report['skipped']+=1;continue
                    s3.delete_object(Bucket=bucket,Key=key,IfMatch=head['ETag'])
                    report['deleted']+=1;report['objects'].append({'key':key,'workflow_uid':uid,'time':now.isoformat()})
                except Exception:
                    # Unknown/missing telemetry, old SDKs or unsupported conditional delete preserve data.
                    report['errors']+=1
    return report

def main():
    import boto3
    from botocore.client import Config
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--max-deletes',type=int,default=10);p.add_argument('--prefix');p.add_argument('--max-examined',type=int,default=1000);args=p.parse_args()
    if not 1<=args.max_deletes<=1000:raise ValueError('Bounded deletion limit required')
    settings=json.loads(args.config.read_text())
    if settings.get('version')!=1 or not re.fullmatch(r'.+@sha256:[a-f0-9]{64}',settings.get('image','')) or not re.fullmatch(r'sha256:[a-f0-9]{64}',settings.get('policyHash','')):raise ValueError('Versioned image/policy provenance required')
    if urlsplit(settings['endpoint']).scheme!='https':raise ValueError('S3 requires verified HTTPS')
    s3=boto3.client('s3',endpoint_url=settings['endpoint'],aws_access_key_id=Path(settings['accessKeyFile']).read_text().strip(),aws_secret_access_key=Path(settings['secretKeyFile']).read_text().strip(),region_name='us-east-1',verify=settings['ca'],config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':2},s3={'addressing_style':'path'}))
    proof=ArgoProof(settings['argoUrl'],settings['namespace'],settings['argoTokenFile'],settings.get('argoCa'))
    if settings.get('probeWorkflow'):
        probe=proof.get(settings['probeWorkflow'])
        if probe.get('metadata',{}).get('namespace')!=settings['namespace'] or probe.get('metadata',{}).get('name')!=settings['probeWorkflow']:raise ValueError('Argo JWT probe mismatch')
        print(json.dumps({'argo_jwt_probe':True,'namespace':settings['namespace']}))
    report=sweep(s3,settings['bucket'],proof,apply=args.apply,max_deletes=args.max_deletes,max_examined=args.max_examined,prefix=args.prefix,conditional_delete_qualified=settings.get('conditionalDeleteQualified') is True)
    report.update(version=1,image=settings['image'],policy_hash=settings['policyHash'])
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
