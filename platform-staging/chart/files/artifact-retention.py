#!/usr/bin/env python3
"""Conservative S3 retention with live terminal Argo proof. Dry run is the default."""
import argparse
import hashlib
import uuid
import urllib.error
from datetime import datetime,timezone,timedelta
import json
import re
import time
from pathlib import Path
import ssl
import urllib.request
from urllib.parse import quote,urlsplit

ANNOTATION='cps.compute/artifact-lifecycle'
ARTIFACTS={'snapshot':('notebook-inputs','snapshot.tar','temporary-expirable',14),'executed-notebook':('run-artifacts','executed.ipynb','run-expirable',90)}

def lifecycle(workflow):
    raw=workflow.get('metadata',{}).get('annotations',{}).get(ANNOTATION)
    if not isinstance(raw,str) or len(raw)>8192:raise ValueError('Versioned artifact lifecycle required')
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)!={'version','artifacts'} or value['version']!=1 or not isinstance(value['artifacts'],dict) or set(value['artifacts'])-ARTIFACTS.keys():raise ValueError('Invalid lifecycle schema')
    for state in value['artifacts'].values():
        if not isinstance(state,dict) or state.get('state') not in ('retained','deleting') or not isinstance(state.get('actor'),str) or not isinstance(state.get('at'),str):raise ValueError('Invalid artifact claim')
    return value

def artifact_name(key):
    parts=key.split('/')
    if len(parts)!=3 or not re.fullmatch(r'[a-f0-9]{48}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',parts[1]):raise ValueError('Fixed notebook artifact key required')
    for artifact,(prefix,filename,_,_) in ARTIFACTS.items():
        if parts[0]==prefix and parts[2]==filename:return artifact
    raise ValueError('Fixed notebook artifact key required')

def expected_metadata(workflow,key):
    artifact=artifact_name(key);identifier=key.split('/')[1];meta=workflow.get('metadata',{})
    if meta.get('name')!='cps-'+identifier or meta.get('namespace')!='cps-workflows' or not meta.get('uid') or meta.get('annotations',{}).get('cps.compute/notebook-id')!=identifier:raise ValueError('Server artifact identity required')
    lifecycle(workflow)
    return {'cps-workflow':meta['name'],'cps-workflow-namespace':'cps-workflows','cps-workflow-uid':meta['uid'],'cps-notebook-id':identifier,'cps-artifact':artifact,'cps-lifecycle-version':'1'}

POLICY={'notebook-inputs/':('temporary-expirable',14),'run-artifacts/':('run-expirable',90)}


def same_identity(left,right):
    a=left.get('metadata',{});b=right.get('metadata',{})
    if any(a.get(k)!=b.get(k) for k in ('name','namespace','uid')):return False
    for k in ('cps.compute/notebook-id','cps.compute/submission-hash','compute.cps.unileoben.ac.at/policy-hash'):
        if a.get('annotations',{}).get(k)!=b.get('annotations',{}).get(k):return False
    return a.get('labels',{}).get('compute.cps.unileoben.ac.at/owner')==b.get('labels',{}).get('compute.cps.unileoben.ac.at/owner')

def provenance(s3,bucket,key,workflow):
    identity=key.split('/')[1];records={}
    for kind in ('intent','binding'):
        response=s3.get_object(Bucket=bucket,Key='notebook-provenance/'+identity+'/'+kind+'.json')
        try:
            raw=response['Body'].read(16385)
            if len(raw)>16384:raise ValueError('Oversized immutable provenance')
            records[kind]=json.loads(raw)
        finally:response['Body'].close()
    intent=records['intent'];saved=records['binding'];meta=workflow['metadata'];annotations=meta.get('annotations',{})
    if (not isinstance(intent,dict) or set(intent)!={'version','notebook_id','policy_hash','owner','submission_hash','snapshot_hash'}
            or intent.get('version')!=1 or intent.get('notebook_id')!=identity
            or intent.get('submission_hash')!=annotations.get('cps.compute/submission-hash')
            or intent.get('policy_hash')!=annotations.get('compute.cps.unileoben.ac.at/policy-hash')
            or intent.get('owner')!=meta.get('labels',{}).get('compute.cps.unileoben.ac.at/owner')):
        raise ValueError('Trusted immutable submission intent required')
    expected={'version':1,'notebook_id':identity,'namespace':'cps-workflows','name':meta['name'],'uid':meta['uid'],
        'intent_hash':hashlib.sha256(json.dumps(intent,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    if saved!=expected:raise ValueError('Permanent first workflow UID mismatch')
    return True

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
    def __init__(self,url,namespace,token_file,ca,*,kube_url=None,kube_ca=None):
        if urlsplit(url).scheme!='https':raise ValueError('Argo proof endpoint requires verified HTTPS')
        if namespace!='cps-workflows':raise ValueError('Fixed workflow namespace required')
        self.token_file=Path(token_file)
        self.token()
        self.url=url.rstrip('/');self.namespace=namespace;self.context=ssl.create_default_context(cafile=ca)
        self.kube_url=kube_url;self.kube_context=ssl.create_default_context(cafile=kube_ca) if kube_url else None
        if kube_url and urlsplit(kube_url).scheme!='https':raise ValueError('Kubernetes CAS requires verified HTTPS')
    def token(self):
        token=self.token_file.read_text().strip()
        if not token or any(c.isspace() for c in token):raise ValueError('Projected Argo token missing')
        return token
    def get(self,name):
        # Startup qualification observed transient refused connections.
        # Retry only a refused read; metadata PATCH ambiguity remains fenced.
        for attempt in range(3):
            request=urllib.request.Request(self.url+'/api/v1/workflows/'+quote(self.namespace,safe='')+'/'+quote(name,safe=''),headers={'Authorization':'Bearer '+self.token()})
            try:
                with urllib.request.urlopen(request,context=self.context,timeout=15) as response:
                    body=response.read(1048577)
                    if len(body)>1048576:raise ValueError('Oversized Argo proof')
                    return json.loads(body)
            except urllib.error.URLError as exc:
                if not isinstance(exc.reason,ConnectionRefusedError) or attempt==2:raise
                time.sleep(attempt+1)


    def kube_request(self,name,body=None):
        if not self.kube_url:raise ValueError('Kubernetes lifecycle coordination is unconfigured')
        url=self.kube_url.rstrip('/')+'/apis/argoproj.io/v1alpha1/namespaces/cps-workflows/workflows/'+quote(name,safe='')
        request=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
            method='PATCH' if body is not None else 'GET',headers={'Authorization':'Bearer '+self.token(),'Content-Type':'application/merge-patch+json'})
        with urllib.request.urlopen(request,context=self.kube_context,timeout=15) as response:
            raw=response.read(1048577)
            if len(raw)>1048576:raise ValueError('Oversized lifecycle proof')
            return json.loads(raw)
    def claim(self,workflow,key,etag,now):
        name=workflow['metadata']['name'];uid=workflow['metadata']['uid'];artifact=artifact_name(key)
        for _ in range(3):
            current=self.kube_request(name);meta=current.get('metadata',{})
            if not same_identity(current,workflow) or meta.get('uid')!=uid or not terminal_proof(current,self.namespace,key.split('/')[1],uid,now):raise ValueError('Live terminal identity changed')
            expected_metadata(current,key)
            finished=datetime.fromisoformat(current['status']['finishedAt'].replace('Z','+00:00'))
            if now-finished<timedelta(days=ARTIFACTS[artifact][3]):raise ValueError('Terminal proof age changed')
            value=lifecycle(current)
            if artifact in value['artifacts']:return None
            if not meta.get('resourceVersion'):raise ValueError('CAS resourceVersion required')
            entry={'state':'deleting','at':now.isoformat(),'actor':'retention','token':uuid.uuid4().hex,'etag':etag}
            value['artifacts'][artifact]=entry
            body={'metadata':{'resourceVersion':meta['resourceVersion'],'uid':uid,'annotations':{ANNOTATION:json.dumps(value,sort_keys=True,separators=(',',':'))}}}
            try:saved=self.kube_request(name,body)
            except urllib.error.HTTPError as exc:
                if exc.code==409:continue
                raise
            if saved.get('metadata',{}).get('uid')!=uid or lifecycle(saved)['artifacts'].get(artifact)!=entry:raise ValueError('Unverified deletion CAS response')
            return entry
        raise ValueError('Bounded deletion CAS retries exhausted')
    def verify_claim(self,workflow,key,entry,now):
        current=self.kube_request(workflow['metadata']['name'])
        expected_metadata(current,key)
        return (same_identity(current,workflow) and current['metadata']['uid']==workflow['metadata']['uid'] and terminal_proof(current,self.namespace,key.split('/')[1],workflow['metadata']['uid'],now)
                and now-datetime.fromisoformat(current['status']['finishedAt'].replace('Z','+00:00'))>=timedelta(days=ARTIFACTS[artifact_name(key)][3])
                and lifecycle(current)['artifacts'].get(artifact_name(key))==entry)

def reconcile(s3,bucket,proof,key,head,now):
    """Terminal metadata repair is explicit and never part of ordinary dry-run."""
    artifact=artifact_name(key);identifier=key.split('/')[1]
    workflow=proof.get('cps-'+identifier);expected=expected_metadata(workflow,key)
    provenance(s3,bucket,key,workflow)
    if not terminal_proof(workflow,proof.namespace,identifier,expected['cps-workflow-uid'],now):return False
    state=lifecycle(workflow)['artifacts'].get(artifact,{})
    if state.get('state')=='deleting':return False
    if artifact=='executed-notebook':
        nodes=workflow.get('status',{}).get('nodes',{})
        if len(nodes)>1000:raise ValueError('Bounded output inventory required')
        outputs=[o for node in nodes.values() for o in node.get('outputs',{}).get('artifacts',[])]+workflow.get('status',{}).get('outputs',{}).get('artifacts',[])
        if not any(o.get('name')=='executed-notebook' and o.get('s3',{}).get('key')==key and o.get('s3',{}).get('bucket')==bucket for o in outputs):return False
    metadata=head.get('Metadata',{})
    if any(k in metadata and metadata[k]!=v for k,v in expected.items()):raise ValueError('Artifact metadata identity mismatch')
    if not head.get('ETag'):raise ValueError('Conditional metadata binding required')
    if any(metadata.get(k)!=v for k,v in expected.items()):
        s3.copy_object(Bucket=bucket,Key=key,CopySource={'Bucket':bucket,'Key':key},CopySourceIfMatch=head['ETag'],MetadataDirective='REPLACE',Metadata={**metadata,**expected})
    current={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
    tags={**current,'retention':ARTIFACTS[artifact][2],'active':'false','retained':'true' if state.get('state')=='retained' or current.get('retained')=='true' else 'false'}
    s3.put_object_tagging(Bucket=bucket,Key=key,Tagging={'TagSet':[{'Key':k,'Value':v} for k,v in tags.items()]})
    return True

def sweep(s3,bucket,proof,*,apply=False,max_deletes=10,max_examined=1000,prefix=None,now=None,conditional_delete_qualified=False,lifecycle_qualified=False,reconcile_metadata=False):
    if not isinstance(max_examined,int) or isinstance(max_examined,bool) or not 1<=max_examined<=10000:raise ValueError('Bounded examination limit required')
    if not isinstance(max_deletes,int) or isinstance(max_deletes,bool) or not 1<=max_deletes<=1000:raise ValueError('Bounded deletion limit required')
    if apply and not lifecycle_qualified:raise ValueError('Full lifecycle qualification required')
    if apply and not conditional_delete_qualified:raise ValueError('Conditional deletion capability qualification required')
    now=now or datetime.now(timezone.utc);report={'examined':0,'eligible':0,'deleted':0,'skipped':0,'errors':0,'objects':[],'apply':apply,'truncated':False,'reconciled':0}
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
                    if reconcile_metadata:
                        initial=s3.head_object(Bucket=bucket,Key=key)
                        if reconcile(s3,bucket,proof,key,initial,now):report['reconciled']+=1
                    tags={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
                    if not eligible(key,obj['LastModified'],tags,now):report['skipped']+=1;continue
                    head=s3.head_object(Bucket=bucket,Key=key);meta=head.get('Metadata',{})
                    name=meta.get('cps-workflow');uid=meta.get('cps-workflow-uid');identifier=key.split('/')[1]
                    if not name or not uid:report['skipped']+=1;continue
                    artifact=artifact_name(key)
                    workflow=proof.get(name)
                    if workflow.get('metadata',{}).get('name')!=name or not terminal_proof(workflow,proof.namespace,identifier,uid,now):report['skipped']+=1;continue
                    expected=expected_metadata(workflow,key)
                    provenance(s3,bucket,key,workflow)
                    if any(meta.get(k)!=v for k,v in expected.items()) or artifact in lifecycle(workflow)['artifacts']:report['skipped']+=1;continue
                    finished=datetime.fromisoformat(workflow['status']['finishedAt'].replace('Z','+00:00'))
                    if now-finished<timedelta(days=category(key)[1]):report['skipped']+=1;continue
                    report['eligible']+=1
                    if not apply:continue
                    if report['deleted']>=max_deletes:report['truncated']=True;return report
                    entry=proof.claim(workflow,key,head['ETag'],now)
                    if entry is None:report['skipped']+=1;continue
                    # A permanent CAS claim fences retain; it is never released after ambiguity.
                    # Re-read mutable eligibility and condition deletion on the observed ETag.
                    current={t['Key']:t['Value'] for t in s3.get_object_tagging(Bucket=bucket,Key=key)['TagSet']}
                    if current!=tags or not eligible(key,head['LastModified'],current,now):report['skipped']+=1;continue
                    latest=s3.head_object(Bucket=bucket,Key=key)
                    if latest.get('ETag')!=head.get('ETag') or latest.get('Metadata')!=meta or not eligible(key,latest['LastModified'],current,now):report['skipped']+=1;continue
                    final=proof.get(name)
                    if final.get('metadata',{}).get('name')!=name or not terminal_proof(final,proof.namespace,identifier,uid,now) or now-datetime.fromisoformat(final['status']['finishedAt'].replace('Z','+00:00'))<timedelta(days=category(key)[1]):report['skipped']+=1;continue
                    provenance(s3,bucket,key,final)
                    if not proof.verify_claim(workflow,key,entry,now):report['skipped']+=1;continue
                    s3.delete_object(Bucket=bucket,Key=key,IfMatch=head['ETag'])
                    report['deleted']+=1;report['objects'].append({'key':key,'workflow_uid':uid,'time':now.isoformat()})
                except Exception:
                    # Unknown/missing telemetry, old SDKs or unsupported conditional delete preserve data.
                    report['errors']+=1
    return report

def validate_mutations(settings, *, apply=False, reconcile=False):
    if apply or reconcile:
        evidence=settings.get('qualificationEvidence')
        if settings.get('lifecycleQualified') is not True or not isinstance(evidence,str) or not evidence.strip():raise ValueError('Reviewed full lifecycle evidence required')
    if apply and settings.get('conditionalDeleteQualified') is not True:raise ValueError('Reviewed conditional deletion required')
    if reconcile and settings.get('reconcileMetadata') is not True:raise ValueError('Explicit reconciliation authorization required')

def main():
    import boto3
    from botocore.client import Config
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--max-deletes',type=int,default=10);p.add_argument('--prefix');p.add_argument('--max-examined',type=int,default=1000);p.add_argument('--reconcile-metadata',action='store_true');args=p.parse_args()
    if not 1<=args.max_deletes<=1000:raise ValueError('Bounded deletion limit required')
    settings=json.loads(args.config.read_text())
    if settings.get('version')!=1 or not re.fullmatch(r'.+@sha256:[a-f0-9]{64}',settings.get('image','')) or not re.fullmatch(r'sha256:[a-f0-9]{64}',settings.get('policyHash','')):raise ValueError('Versioned image/policy provenance required')
    validate_mutations(settings,apply=args.apply,reconcile=args.reconcile_metadata)
    if urlsplit(settings['endpoint']).scheme!='https':raise ValueError('S3 requires verified HTTPS')
    s3=boto3.client('s3',endpoint_url=settings['endpoint'],aws_access_key_id=Path(settings['accessKeyFile']).read_text().strip(),aws_secret_access_key=Path(settings['secretKeyFile']).read_text().strip(),region_name='us-east-1',verify=settings['ca'],config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':2},s3={'addressing_style':'path'}))
    proof=ArgoProof(settings['argoUrl'],settings['namespace'],settings['argoTokenFile'],settings.get('argoCa'),kube_url=settings.get('kubeUrl'),kube_ca=settings.get('kubeCa'))
    if settings.get('probeWorkflow'):
        probe=proof.get(settings['probeWorkflow'])
        if probe.get('metadata',{}).get('namespace')!=settings['namespace'] or probe.get('metadata',{}).get('name')!=settings['probeWorkflow']:raise ValueError('Argo JWT probe mismatch')
        print(json.dumps({'argo_jwt_probe':True,'namespace':settings['namespace']}))
    report=sweep(s3,settings['bucket'],proof,apply=args.apply,max_deletes=args.max_deletes,max_examined=args.max_examined,prefix=args.prefix,conditional_delete_qualified=settings.get('conditionalDeleteQualified') is True,lifecycle_qualified=settings.get('lifecycleQualified') is True,reconcile_metadata=args.reconcile_metadata)
    report.update(version=1,image=settings['image'],policy_hash=settings['policyHash'])
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
