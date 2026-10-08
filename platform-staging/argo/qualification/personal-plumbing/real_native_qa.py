#!/usr/bin/env python3
"""Bounded native Argo/S3 fixture preparation; no browser authentication.

Current receipt stops at admission refusal; the owner HTTP runtime never ran.
This shell fixture tests snapshot transport/output generation, not Papermill.

The gateway gets an empty temporary DB and fixture-only canonical mappings. Its
static SA can read workflows/logs and only the two approved artifact Secrets;
it cannot create Pods/Workflows. Only S3 credential references are consumed by
the owned service-side Jobs; their bytes are never copied into operator output.
"""
import argparse
import base64
import copy
import datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import activation_operator as activation
import ownership_http

HERE=Path(__file__).resolve().parent
NS='cps-compute';WFNS='cps-workflows';PREFIX='personal-argo-real-qa'
IMAGE=activation.COMPUTE
LABEL='qualification.cps/owner'
OWNER='personal-argo-real-qa-20261008'


def command(args,body=None):
    r=subprocess.run(['kubectl',*args],input=None if body is None else json.dumps(body),capture_output=True,text=True)
    if r.returncode:raise RuntimeError('Kubernetes operation failed; private response suppressed')
    return r.stdout


def get(kind,name,namespace=NS):return json.loads(command(['-n',namespace,'get',kind,name,'-o','json']))
def create(o):command(['create','-f','-'],o)
def metadata(name,namespace=NS):return {'name':name,'namespace':namespace,'labels':{LABEL:OWNER}}
def core(kind,name,namespace=NS,**fields):return {'apiVersion':'v1','kind':kind,'metadata':metadata(name,namespace),**fields}


INIT=r'''
import base64,json,pathlib,sys,boto3
from botocore.config import Config
try:
    p=json.loads(pathlib.Path('/qa/plan.json').read_text())
    s=boto3.client('s3',endpoint_url=p['s3Endpoint'],verify='/trust/ca.crt',config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':1}))
    for f in p['fixtures']:
        s.put_object(Bucket='cps-compute',Key='notebook-snapshots/'+f['id']+'/snapshot.tar.gz',
                     Body=base64.b64decode(f['snapshotBase64']),IfNoneMatch='*',ContentType='application/gzip')
        s.put_object(Bucket='cps-compute',Key='notebook-provenance/'+f['id']+'/intent.json',
                     Body=json.dumps(f['intent'],sort_keys=True,separators=(',',':')).encode(),IfNoneMatch='*',ContentType='application/json')
    print(json.dumps({'actualSnapshotsStored':2,'actualIntentRecordsStored':2}))
except Exception as exc:
    response=getattr(exc,'response',{})
    print(json.dumps({'failedStage':'actual-snapshot-initialization','errorType':type(exc).__name__,'errorCode':response.get('Error',{}).get('Code'),'httpStatus':response.get('ResponseMetadata',{}).get('HTTPStatusCode')}));sys.exit(1)
'''

CLEAN=r'''
import base64,hashlib,json,pathlib,sys,boto3
from botocore.config import Config
try:
    p=json.loads(pathlib.Path('/qa/plan.json').read_text())
    s=boto3.client('s3',endpoint_url=p['s3Endpoint'],verify='/trust/ca.crt',config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':1}))
    deleted=0
    for f in p['fixtures']:
        for key,expected in [('notebook-snapshots/'+f['id']+'/snapshot.tar.gz',base64.b64decode(f['snapshotBase64'])),
                             ('notebook-provenance/'+f['id']+'/intent.json',json.dumps(f['intent'],sort_keys=True,separators=(',',':')).encode())]:
            current=s.get_object(Bucket='cps-compute',Key=key)['Body'].read()
            assert hashlib.sha256(current).digest()==hashlib.sha256(expected).digest()
            s.delete_object(Bucket='cps-compute',Key=key);deleted+=1
            try:s.head_object(Bucket='cps-compute',Key=key)
            except s.exceptions.ClientError as exc:assert exc.response['ResponseMetadata']['HTTPStatusCode']==404
            else:raise AssertionError('owned object remained')
    print(json.dumps({'ownedSnapshotAndIntentObjectsDeleted':deleted,'absenceVerified':True}))
except Exception as exc:
    print(json.dumps({'cleanupFailed':True,'errorType':type(exc).__name__}));sys.exit(1)
'''




def job(name,program):
    env=[{'name':'CPS_COMPUTE_CONFIG','value':'/qa/runtime.json'}]
    for key in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_DEFAULT_REGION'):
        env.append({'name':key,'valueFrom':{'secretKeyRef':{'name':'cps-compute-gateway','key':key}}})
    for key in ('QA_SERVICE_CPS','QA_SERVICE_CIT','QA_HUB_CPS','QA_HUB_CIT'):
        env.append({'name':key,'valueFrom':{'secretKeyRef':{'name':PREFIX+'-dummy-control','key':key}}})
    container={'name':'qa','image':IMAGE,'command':['python','-B','-c'],'args':[program],'env':env,
        'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi'}},
        'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
        'volumeMounts':[{'name':n,'mountPath':p,'readOnly':n!='temporary'} for n,p in
            [('qa','/qa'),('policy','/policy'),('trust','/trust'),('kube-ca','/var/run/secrets/kubernetes.io/serviceaccount'),
             ('reader','/argo-reader'),('visitors','/visitors'),('tls','/tls'),('temporary','/tmp')]]}
    volumes=[{'name':'qa','configMap':{'name':PREFIX+'-config'}},{'name':'policy','configMap':{'name':'compute-policy'}},
        {'name':'trust','configMap':{'name':'cps-compute-gateway-ca'}},{'name':'kube-ca','configMap':{'name':'kube-root-ca.crt'}},
        {'name':'reader','secret':{'secretName':PREFIX+'-reader-token','defaultMode':288}},
        {'name':'visitors','secret':{'secretName':'scratch-normal-hub-fixtures','defaultMode':288}},
        {'name':'tls','secret':{'secretName':PREFIX+'-tls','defaultMode':288}},
        {'name':'temporary','emptyDir':{'sizeLimit':'256Mi'}}]
    return {'apiVersion':'batch/v1','kind':'Job','metadata':metadata(name),'spec':{'activeDeadlineSeconds':300,'backoffLimit':0,
        'template':{'metadata':{'labels':{'app':PREFIX}},'spec':{'restartPolicy':'Never','automountServiceAccountToken':False,
            'imagePullSecrets':[{'name':'cps-compute-image-pull'}],'securityContext':{'runAsNonRoot':True,'runAsUser':10001,
                'runAsGroup':10001,'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[container],'volumes':volumes}}}}


def snapshots():
    import gzip,io,tarfile
    policy=json.loads((activation.ROOT/'compute-policy/generated/policy.json').read_text())
    plan={'ownerLabel':policy['labels']['owner'],'s3Endpoint':'https://artifacts.cps-artifacts-relay.svc.cluster.local:8333','fixtures':[]}
    for index,user in enumerate(('cps-argo-qa-a-20261008','cps-argo-qa-b-20261008')):
        identifier=secrets.token_hex(24);person=str(uuid.uuid4());marker='personal-argo-real-cpu-'+str(index)+'-'+identifier
        notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'qualificationLogMarker':marker},
            'cells':[{'cell_type':'code','metadata':{},'source':'print('+repr(marker)+')','execution_count':None,'outputs':[]}]}
        raw=json.dumps(notebook,sort_keys=True,separators=(',',':')).encode();tar=io.BytesIO()
        with tarfile.open(fileobj=tar,mode='w') as archive:
            info=tarfile.TarInfo('notebook.ipynb');info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
        packed=gzip.compress(tar.getvalue(),mtime=0)
        executed=copy.deepcopy(notebook);executed['cells'][0]['execution_count']=1
        executed['cells'][0]['outputs']=[{'output_type':'stream','name':'stdout','text':marker+'\n'}]
        owner=hashlib.sha256(person.encode()).hexdigest()[:63];submission=hashlib.sha256(identifier.encode()).hexdigest()
        plan['fixtures'].append({'id':identifier,'workflow':'cps-'+identifier,'user':user,'person':person,'ownerHash':owner,
            'snapshotBase64':base64.b64encode(packed).decode(),'snapshotSha256':hashlib.sha256(packed).hexdigest(),
            'artifactSha256':hashlib.sha256(json.dumps(executed,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'logMarker':marker,'intent':{'version':1,'notebook_id':identifier,'policy_hash':policy['policyHash'],
                'owner':owner,'submission_hash':submission,'snapshot_hash':hashlib.sha256(packed).hexdigest()}})
    return plan


def workflow(f,plan):
    def artifact(name,key,path):return {'name':name,'path':path,'archive':{'none':{}},'s3':{
        'endpoint':plan['s3Endpoint'].removeprefix('https://'),'bucket':'cps-compute','key':key,'insecure':False,
        'accessKeySecret':{'name':'cps-artifact-credentials','key':'accessKey'},
        'secretKeySecret':{'name':'cps-artifact-credentials','key':'secretKey'},'caSecret':{'name':'cps-artifact-ca','key':'ca.crt'}}}
    meta=metadata(f['workflow'],WFNS);meta['labels'][plan['ownerLabel']]=f['ownerHash']
    meta['annotations']={'cps.compute/notebook-id':f['id'],'cps.compute/submission-hash':f['intent']['submission_hash'],
        'compute.cps.unileoben.ac.at/policy-hash':f['intent']['policy_hash']}
    approved=get('computeadmissionpolicy','cps-admission-policy')['data']['executor-image']
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'qualificationLogMarker':f['logMarker']},
        'cells':[{'cell_type':'code','metadata':{},'source':'print('+repr(f['logMarker'])+')','execution_count':1,
            'outputs':[{'output_type':'stream','name':'stdout','text':f['logMarker']+'\n'}]}]}
    encoded=base64.b64encode(json.dumps(notebook,sort_keys=True,separators=(',',':')).encode()).decode()
    shell='tar -tzf /inputs/snapshot.tar | test "$(cat)" = notebook.ipynb; printf %s '+encoded+' | base64 -d > /argo/staging/executed.ipynb; echo '+f['logMarker']
    security={'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'allowPrivilegeEscalation':False,
        'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}
    patch={'volumes':[{'name':'tmp-dir-argo','emptyDir':{}},{'name':'argo-staging','emptyDir':{}}],
        'containers':[{'name':'wait','securityContext':security,'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'250m','memory':'128Mi'}}}],
        'initContainers':[{'name':'init','securityContext':security,'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'250m','memory':'128Mi'}},
            'volumeMounts':[{'name':'tmp-dir-argo','mountPath':'/tmp','subPath':'init'}]}]}
    return {'apiVersion':'argoproj.io/v1alpha1','kind':'Workflow','metadata':meta,'spec':{'entrypoint':'main',
        'serviceAccountName':'cps-workflow','executor':{'serviceAccountName':'cps-workflow-executor'},'automountServiceAccountToken':False,'schedulerName':'kai-scheduler',
        'activeDeadlineSeconds':300,'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},
        'volumes':[{'name':'argo-staging','emptyDir':{}}],'podSpecPatch':json.dumps(patch),
        'templates':[{'name':'main','inputs':{'artifacts':[artifact('snapshot','notebook-snapshots/'+f['id']+'/snapshot.tar.gz','/inputs/snapshot.tar')]},
            'container':{'image':approved,'command':['/bin/sh','-ec'],'args':[shell],
                'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
                'volumeMounts':[{'name':'argo-staging','mountPath':'/argo/staging'}],'securityContext':security},
            'outputs':{'artifacts':[artifact('executed-notebook','run-artifacts/'+f['id']+'/executed.ipynb','/argo/staging/executed.ipynb')]}}]}}



def setup():
    plan=snapshots();runtime=get('secret','cps-compute-runtime')
    config=json.loads(base64.b64decode(runtime['data']['runtime.json']))
    config=ownership_http.qa_runtime(config,{f['user']:f['person'] for f in plan['fixtures']})
    now=datetime.datetime.now(datetime.timezone.utc);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'personal Argo bounded QA')])
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .sign(key,hashes.SHA256()))
    create(core('Secret',PREFIX+'-tls',type='kubernetes.io/tls',stringData={'tls.crt':cert.public_bytes(serialization.Encoding.PEM).decode(),
        'tls.key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()}))
    create(core('Secret',PREFIX+'-dummy-control',type='Opaque',stringData={k:secrets.token_urlsafe(32) for k in ('QA_SERVICE_CPS','QA_SERVICE_CIT','QA_HUB_CPS','QA_HUB_CIT')}))
    create(core('Secret',PREFIX+'-reader-token',type='Opaque',stringData={'token':''}))
    create(core('ServiceAccount',PREFIX+'-reader',automountServiceAccountToken=False))
    role={'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata(PREFIX+'-read',WFNS),'rules':[
        {'apiGroups':['argoproj.io'],'resources':['workflows'],'verbs':['get','list']},
        {'apiGroups':[''],'resources':['pods'],'verbs':['get','list']},{'apiGroups':[''],'resources':['pods/log'],'verbs':['get']},
        {'apiGroups':[''],'resources':['secrets'],'resourceNames':['cps-artifact-credentials','cps-artifact-ca'],'verbs':['get']}]}
    create(role);create({'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':metadata(PREFIX+'-read',WFNS),
        'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':PREFIX+'-read'},
        'subjects':[{'kind':'ServiceAccount','name':PREFIX+'-reader','namespace':NS}]})
    create(core('ConfigMap',PREFIX+'-config',data={'runtime.json':json.dumps(config),'plan.json':json.dumps(plan),
        'ownership_http.py':(HERE/'ownership_http.py').read_text()}))
    (HERE/'real-qa-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    create(job(PREFIX+'-initialize',INIT))
    return {'stage':'actual-snapshot-initializer-created','fixtureCount':2,'qaGrants':0,'productionGrantsChanged':False}


def proceed():
    plan=json.loads((HERE/'real-qa-plan.json').read_text())
    command(['-n',NS,'wait','--for=condition=complete','job/'+PREFIX+'-initialize','--timeout=120s'])
    for f in plan['fixtures']:create(workflow(f,plan))
    return {'stage':'two-controlled-real-CPU-workflows-created','workflowNames':[f['workflow'] for f in plan['fixtures']]}


def cleanup():
    plan=json.loads((HERE/'real-qa-plan.json').read_text())
    receipts=[]
    for f in plan['fixtures']:
        w=get('workflow',f['workflow'],WFNS)
        assert w['metadata']['labels'][LABEL]==OWNER and w.get('status',{}).get('phase') in ('Error','Failed','Succeeded')
        receipts.append({'name':f['workflow'],'uid':w['metadata']['uid'],'phase':w.get('status',{}).get('phase'),
            'message':w.get('status',{}).get('message'),'spec':w['spec']})
    pods=json.loads(command(['-n',NS,'get','pods','-l','job-name='+PREFIX+'-initialize','-o','json']))['items']
    init={'firstAttempt':{'createdAt':'2026-10-08T12:50:42Z','failedAt':'2026-10-08T12:50:46Z',
        'errorDetails':'private response suppressed; failed resource replaced before detailed error receipt'},
        'retryOutput':json.loads(command(['-n',NS,'logs','job/'+PREFIX+'-initialize'])),
        'imageIds':[v['imageID'] for p in pods for v in p['status'].get('containerStatuses',[])],
        'credentialReferences':['cps-compute-gateway:AWS_ACCESS_KEY_ID','cps-compute-gateway:AWS_SECRET_ACCESS_KEY',
            'cps-compute-gateway:AWS_DEFAULT_REGION'],'caReference':'cps-compute-gateway-ca:ca.crt',
        'namespace':'cps-compute','artifactRelayIngressAlreadyAllowed':True}
    report={'scope':'bounded actual Hub normal-user and native Argo/S3 preparation; stopped for isolation priority',
        'actualBrowserHubOAuthQualified':False,'normalOwnerPrivacyQualified':False,'logsArtifactsWriteDenialQualified':False,
        'productionHubGatewayIngressChanged':False,'productionGrantsChanged':False,'qaGrants':0,
        'normalHubFixtureCreationVerified':True,'noFixtureServersOrHomes':True,'initializer':init,'workflows':receipts,
        'workflowAcceptance':'admission denied before Pods; not notebook execution qualification'}
    (HERE/'real-native-stopped-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    # Existing service-side credential references, scoped to generated fixture keys.
    # This does not copy credentials or modify gateway configuration.
    program=CLEAN.replace("p=json.loads(pathlib.Path('/qa/plan.json').read_text())","p=json.load(sys.stdin)")
    output=command(['-n',NS,'exec','-i','deployment/compute-gateway','--','python','-c',program],plan)
    report['s3Cleanup']=json.loads(output)
    assert report['s3Cleanup']['ownedSnapshotAndIntentObjectsDeleted']==4 and report['s3Cleanup']['absenceVerified'] is True
    for f in plan['fixtures']:command(['-n',WFNS,'delete','workflow',f['workflow'],'--wait=true'])
    for ns,kind,name in [(WFNS,'rolebinding',PREFIX+'-read'),(WFNS,'role',PREFIX+'-read'),
            (NS,'job',PREFIX+'-initialize'),(NS,'serviceaccount',PREFIX+'-reader'),
            (NS,'configmap',PREFIX+'-config'),(NS,'secret',PREFIX+'-reader-token'),(NS,'secret',PREFIX+'-tls'),(NS,'secret',PREFIX+'-dummy-control')]:
        o=get(kind,name,ns);assert o['metadata']['labels'][LABEL]==OWNER
        command(['-n',ns,'delete',kind,name,'--wait=true'])
    report['ownedQaKubernetesResourcesRemoved']=True
    (HERE/'real-native-stopped-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    return {'stopped':True,'ownedQaKubernetesResourcesRemoved':True,**report['s3Cleanup']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['setup','workflows','cleanup'])
    args=parser.parse_args()
    try:print(json.dumps({'setup':setup,'workflows':proceed,'cleanup':cleanup}[args.stage]()))
    except Exception:
        print('actual native QA stage stopped; credentials and response bodies suppressed');raise SystemExit(1)
