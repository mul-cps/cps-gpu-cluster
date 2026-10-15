import copy
import urllib.error
from datetime import datetime,timezone,timedelta
import importlib.util
import io,json
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('deployed_retention',ROOT/'platform-staging/chart/files/artifact-retention.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

ID='a'*48
NAME='cps-'+ID

class S3:
    def __init__(self,now):
        self.key='notebook-inputs/'+ID+'/snapshot.tar';self.now=now;self.deleted=[]
        self.tags={'retention':'temporary-expirable','active':'false','retained':'false'}
        self.head={'ETag':'"etag"','LastModified':now-timedelta(days=100),'Metadata':{'cps-workflow':NAME,'cps-workflow-uid':'uid','cps-workflow-namespace':'cps-workflows','cps-notebook-id':ID,'cps-artifact':'snapshot','cps-lifecycle-version':'1'}}
    def get_object(self,Bucket,Key):
        intent={'version':1,'notebook_id':ID,'policy_hash':'sha256:'+('a'*64),'owner':'b'*63,'submission_hash':'c'*64,'snapshot_hash':'d'*64}
        value=intent if Key.endswith('/intent.json') else {'version':1,'notebook_id':ID,'namespace':'cps-workflows','name':NAME,'uid':'uid','intent_hash':m.hashlib.sha256(json.dumps(intent,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
        return {'Body':io.BytesIO(json.dumps(value).encode())}
    def get_paginator(self,name):return self
    def paginate(self,**kwargs):
        yield {'Contents':[{'Key':self.key,'LastModified':self.head['LastModified']}] if self.key.startswith(kwargs['Prefix']) else []}
    def get_object_tagging(self,**kwargs):return {'TagSet':[{'Key':k,'Value':v} for k,v in self.tags.items()]}
    def head_object(self,**kwargs):return copy.deepcopy(self.head)
    def delete_object(self,**kwargs):self.deleted.append(kwargs)
    def copy_object(self,**kwargs):self.copied=kwargs;self.head['Metadata']=copy.deepcopy(kwargs['Metadata'])
    def put_object_tagging(self,**kwargs):self.tags={t['Key']:t['Value'] for t in kwargs['Tagging']['TagSet']}

class Proof(m.ArgoProof):
    namespace='cps-workflows'
    def __init__(self,now):
        self.patch_calls=0;self.before_patch=None;self.conflicts=False
        self.workflow={'metadata':{'name':NAME,'resourceVersion':'1','labels':{'compute.cps.unileoben.ac.at/owner':'b'*63},'namespace':self.namespace,'uid':'uid','annotations':{'cps.compute/notebook-id':ID,'cps.compute/submission-hash':'c'*64,'compute.cps.unileoben.ac.at/policy-hash':'sha256:'+('a'*64),m.ANNOTATION:'{"artifacts":{},"version":1}'}},'status':{'phase':'Succeeded','finishedAt':(now-timedelta(days=100)).isoformat()}}
    def get(self,name):return copy.deepcopy(self.workflow)
    def kube_request(self,name,body=None):
        if body is None:return copy.deepcopy(self.workflow)
        self.patch_calls+=1
        if self.before_patch:
            hook=self.before_patch;self.before_patch=None;hook()
        if self.conflicts or body['metadata']['resourceVersion']!=self.workflow['metadata']['resourceVersion']:
            raise urllib.error.HTTPError('https://kube',409,'Conflict',{},None)
        assert body['metadata']['uid']==self.workflow['metadata']['uid']
        assert set(body)=={'metadata'} and set(body['metadata']['annotations'])=={m.ANNOTATION}
        self.workflow['metadata']['annotations'].update(body['metadata']['annotations'])
        self.workflow['metadata']['resourceVersion']=str(int(self.workflow['metadata']['resourceVersion'])+1)
        return copy.deepcopy(self.workflow)

class Retention(unittest.TestCase):
    def setUp(self):self.now=datetime.now(timezone.utc);self.s3=S3(self.now);self.proof=Proof(self.now)
    def test_dryrun_and_conditional_delete_only_after_qualified_rechecked_proof(self):
        report=m.sweep(self.s3,'bucket',self.proof,now=self.now)
        self.assertEqual(report['eligible'],1);self.assertFalse(self.s3.deleted)
        with self.assertRaises(ValueError):m.sweep(self.s3,'bucket',self.proof,apply=True,now=self.now)
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['deleted'],1);self.assertEqual(self.s3.deleted[0]['IfMatch'],'"etag"')
    def test_active_retained_unknown_workflows_and_recent_finish_preserved(self):
        for changes in ({'active':'true'},{'retained':'true'},{'retention':'unknown'}):
            self.s3.tags.update(changes);self.assertEqual(m.sweep(self.s3,'bucket',self.proof,now=self.now)['eligible'],0)
            self.s3=S3(self.now)
        for field,value in [('namespace','other'),('uid','other'),('name','other')]:
            self.proof=Proof(self.now);self.proof.workflow['metadata'][field]=value
            self.assertEqual(m.sweep(self.s3,'bucket',self.proof,now=self.now)['eligible'],0)
        self.proof=Proof(self.now);self.proof.workflow['status']['finishedAt']=(self.now-timedelta(days=13)).isoformat()
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,now=self.now)['eligible'],0)
    def test_mutable_tag_or_final_workflow_change_preserves_object(self):
        original=self.s3.get_object_tagging;calls=[]
        def tags(**kwargs):
            calls.append(1)
            if len(calls)>1:self.s3.tags['retained']='true'
            return original(**kwargs)
        self.s3.get_object_tagging=tags
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)['deleted'],0)
        self.s3=S3(self.now);self.proof=Proof(self.now);calls=[];original=self.proof.get
        def proof(name):
            calls.append(1)
            if len(calls)>1:self.proof.workflow['status']['phase']='Running'
            return original(name)
        self.proof.get=proof
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)['deleted'],0)
    def test_unsupported_ifmatch_is_error_and_never_falls_back(self):
        calls=[]
        def delete(**kwargs):calls.append(kwargs);raise TypeError('unsupported IfMatch')
        self.s3.delete_object=delete
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['errors'],1);self.assertEqual(report['deleted'],0);self.assertEqual(len(calls),1);self.assertIn('IfMatch',calls[0])
    def test_max_examined_is_bounded_and_prefix_cannot_escape_policy(self):
        def pages(**kwargs):yield {'Contents':[{'Key':self.s3.key,'LastModified':self.s3.head['LastModified']}]*10}
        self.s3.paginate=pages
        report=m.sweep(self.s3,'bucket',self.proof,max_examined=2,now=self.now)
        self.assertEqual(report['examined'],2);self.assertTrue(report['truncated'])
        with self.assertRaises(ValueError):m.sweep(self.s3,'bucket',self.proof,prefix='unmanaged/')
    def test_argo_jwt_is_read_each_request_and_missing_workflow_preserves(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'token';token.write_text('first');seen=[]
            def request(req,**kwargs):seen.append(req.headers['Authorization']);return io.BytesIO(b'{"metadata":{}}')
            with patch.object(m.ssl,'create_default_context',return_value=object()),patch.object(m.urllib.request,'urlopen',side_effect=request):
                proof=m.ArgoProof('https://argo','cps-workflows',token,None);proof.get('wf');token.write_text('second');proof.get('wf')
            self.assertEqual(seen,['Bearer first','Bearer second'])
        def absent(name):raise LookupError('workflow TTL removed proof')
        self.proof.get=absent
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['errors'],1);self.assertFalse(self.s3.deleted)

    def test_monotonic_retain_wins_cas_race_and_delete_claim_never_expires(self):
        def retained():
            self.proof.workflow['metadata']['annotations'][m.ANNOTATION]=json.dumps({'version':1,'artifacts':{'snapshot':{'state':'retained','actor':'owner','at':self.now.isoformat()}}})
            self.proof.workflow['metadata']['resourceVersion']='2'
        self.proof.before_patch=retained
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['deleted'],0);self.assertFalse(self.s3.deleted)
        self.assertEqual(m.lifecycle(self.proof.workflow)['artifacts']['snapshot']['state'],'retained')
        self.proof=Proof(self.now)
        def ambiguous(**kwargs):raise TimeoutError('delete response lost')
        self.s3.delete_object=ambiguous
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['errors'],1);self.assertEqual(report['deleted'],0)
        state=m.lifecycle(self.proof.workflow)['artifacts']['snapshot']
        self.assertEqual(state['state'],'deleting');self.assertIn('token',state)
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now+timedelta(days=100))
        self.assertEqual(report['eligible'],0);self.assertEqual(m.lifecycle(self.proof.workflow)['artifacts']['snapshot'],state)

    def test_conditional_capability_alone_missing_metadata_protocol_and_conflicts_preserve(self):
        with self.assertRaises(ValueError):m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)
        self.proof.conflicts=True
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(self.proof.patch_calls,3);self.assertEqual(report['errors'],1);self.assertFalse(self.s3.deleted)
        self.proof=Proof(self.now);self.s3.head['Metadata'].pop('cps-workflow-namespace')
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,now=self.now)['eligible'],0)
        self.s3=S3(self.now);self.proof.workflow['metadata']['annotations'].pop(m.ANNOTATION)
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,now=self.now)['eligible'],0)

    def test_completed_output_retain_survives_tag_update_crash(self):
        for phase in ('Succeeded', 'Failed'):
            with self.subTest(phase=phase):
                self.s3=S3(self.now);self.proof=Proof(self.now)
                self.s3.key='run-artifacts/'+ID+'/executed.ipynb'
                self.s3.tags['retention']='run-expirable'
                self.proof.workflow['status']['phase']=phase
                self.proof.workflow['status']['nodes']={'run':{'outputs':{'artifacts':[
                    {'name':'executed-notebook','s3':{'bucket':'bucket','key':self.s3.key}}]}}}
                self.s3.head['Metadata']=m.expected_metadata(self.proof.workflow,self.s3.key)
                claim={'state':'retained','actor':'owner','at':self.now.isoformat()}
                self.proof.workflow['metadata']['annotations'][m.ANNOTATION]=json.dumps(
                    {'version':1,'artifacts':{'executed-notebook':claim}})
                # A crash leaves the S3 tag false after the durable owner claim.
                report=m.sweep(self.s3,'bucket',self.proof,apply=True,
                    conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
                self.assertEqual(report['errors'],0);self.assertEqual(report['eligible'],0)
                self.assertFalse(self.s3.deleted);self.assertEqual(self.proof.patch_calls,0)
                self.assertTrue(m.reconcile(self.s3,'bucket',self.proof,
                    self.s3.key,self.s3.head,self.now))
                self.assertEqual(self.s3.tags['retained'],'true')
                self.assertEqual(m.lifecycle(self.proof.workflow)['artifacts']['executed-notebook'],claim)

    def test_terminal_reconcile_is_explicit_idempotent_and_preserves_retain(self):
        self.s3.head['Metadata']={};self.s3.tags={'retained':'true'}
        report=m.sweep(self.s3,'bucket',self.proof,now=self.now)
        self.assertEqual(report['reconciled'],0);self.assertFalse(hasattr(self.s3,'copied'))
        self.assertTrue(m.reconcile(self.s3,'bucket',self.proof,self.s3.key,self.s3.head,self.now))
        self.assertEqual(self.s3.head['Metadata'],m.expected_metadata(self.proof.workflow,self.s3.key))
        self.assertEqual(self.s3.tags['retained'],'true')
        del self.s3.copied
        modified=self.s3.head['LastModified']
        self.assertTrue(m.reconcile(self.s3,'bucket',self.proof,self.s3.key,self.s3.head,self.now))
        self.assertFalse(hasattr(self.s3,'copied'));self.assertEqual(self.s3.head['LastModified'],modified)
        self.s3.key='run-artifacts/'+ID+'/executed.ipynb';self.s3.head['Metadata']={}
        self.assertFalse(m.reconcile(self.s3,'bucket',self.proof,self.s3.key,self.s3.head,self.now))
        self.proof.workflow['status']['nodes']={'run':{'outputs':{'artifacts':[{'name':'executed-notebook','s3':{'bucket':'bucket','key':self.s3.key}}]}}}
        self.assertTrue(m.reconcile(self.s3,'bucket',self.proof,self.s3.key,self.s3.head,self.now))
        self.assertEqual(self.s3.head['Metadata']['cps-artifact'],'executed-notebook')

    def test_missing_or_recreated_provenance_prevents_claim_and_unmanaged_prefix_is_never_scanned(self):
        original=self.s3.get_object
        def missing(**kwargs):raise LookupError('provenance disappeared')
        self.s3.get_object=missing
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['eligible'],0);self.assertEqual(self.proof.patch_calls,0);self.assertFalse(self.s3.deleted)
        self.s3.get_object=original;self.proof.workflow['metadata']['uid']='recreated'
        self.s3.head['Metadata']['cps-workflow-uid']='recreated'
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['eligible'],0);self.assertEqual(self.proof.patch_calls,0)
        with self.assertRaises(ValueError):m.sweep(self.s3,'bucket',self.proof,prefix='notebook-provenance/')

    def test_final_cas_identity_or_terminal_age_change_preserves_claim_and_object(self):
        original=self.proof.verify_claim
        def changed(workflow,key,entry,now):
            self.proof.workflow['metadata']['labels']['compute.cps.unileoben.ac.at/owner']='other'
            return original(workflow,key,entry,now)
        self.proof.verify_claim=changed
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,lifecycle_qualified=True,now=self.now)
        self.assertEqual(report['deleted'],0);self.assertFalse(self.s3.deleted)
        self.assertEqual(m.lifecycle(self.proof.workflow)['artifacts']['snapshot']['state'],'deleting')

class RetentionChart(unittest.TestCase):
    def render(self,overrides=None):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text());image='registry.invalid/image@sha256:'+'a'*64
        values={'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],'gateway':{'image':image},'consoles':{'cps':{'image':image},'cit':{'image':image,'publicCallbackUrl':'https://example.invalid/cb'}},'artifactRetention':{'enabled':True,'image':image}}
        values['artifactRetention'].update(overrides or {})
        with tempfile.NamedTemporaryFile('w',suffix='.yaml') as file:
            yaml.safe_dump(values,file);file.flush()
            return subprocess.run(['helm','template','compute',str(ROOT/'platform-staging/chart'),'-f',file.name],capture_output=True,text=True)
    def test_dedicated_get_patch_only_rbac_and_suspended_dryrun_projected_token(self):
        result=self.render();self.assertEqual(result.returncode,0,result.stderr)
        documents=[d for d in yaml.safe_load_all(result.stdout) if d]
        cron=next(d for d in documents if d['kind']=='CronJob' and d['metadata']['name']=='cps-artifact-retention')
        argo=yaml.safe_load((ROOT/'platform-staging/argo/values.yaml').read_text())
        self.assertGreaterEqual(argo['controller']['workflowDefaults']['spec']['ttlStrategy']['secondsAfterCompletion'],93*86400)
        self.assertTrue(cron['spec']['suspend']);pod=cron['spec']['jobTemplate']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken']);self.assertEqual(pod['serviceAccountName'],'cps-artifact-retention')
        self.assertNotEqual(pod['serviceAccountName'],'cps-compute-controller');self.assertNotIn('--apply',pod['containers'][0]['args'])
        role=next(d for d in documents if d['kind']=='Role' and d['metadata']['name']=='cps-artifact-retention-proof')
        self.assertEqual(role['metadata']['namespace'],'cps-workflows');self.assertEqual(role['rules'],[{'apiGroups':['argoproj.io'],'resources':['workflows'],'verbs':['get','patch']}])
        binding=next(d for d in documents if d['kind']=='RoleBinding' and d['metadata']['name']=='cps-artifact-retention-proof')
        self.assertEqual(binding['subjects'],[{'kind':'ServiceAccount','name':'cps-artifact-retention','namespace':'cps-compute'}])
        projected=next(v for v in pod['volumes'] if v['name']=='argo-token')['projected']['sources'][0]
        self.assertEqual(projected['serviceAccountToken']['expirationSeconds'],3600)
        policy=next(d for d in documents if d['kind']=='NetworkPolicy' and d['metadata']['name']=='cps-artifact-retention-argo')
        self.assertEqual(policy['spec']['ingress'][0]['from'][0]['podSelector'],{'matchLabels':{'app':'cps-artifact-retention'}})
    def test_apply_and_limits_fail_closed_without_evidence(self):
        for override in ({'reconcileMetadata':True},{'reconcileMetadata':True,'lifecycleQualified':True},{'apply':True},{'apply':True,'conditionalDeleteQualified':True,'qualificationEvidence':'conditional-only'},{'maxExamined':0},{'maxDeletes':1001}):self.assertNotEqual(self.render(override).returncode,0)

if __name__=='__main__':unittest.main()

class ProofTransport(unittest.TestCase):
    def test_refused_read_retries_with_rotated_projected_token(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'token';token.write_text('first');seen=[]
            def request(req,**kwargs):
                seen.append(req.headers['Authorization'])
                if len(seen)==1:
                    token.write_text('second')
                    raise urllib.error.URLError(ConnectionRefusedError('cold policy path'))
                return io.BytesIO(b'{"metadata":{"uid":"fixture-uid"}}')
            with patch.object(m.ssl,'create_default_context',return_value=object()),patch.object(m.urllib.request,'urlopen',side_effect=request),patch.object(m.time,'sleep'):
                proof=m.ArgoProof('https://argo','cps-workflows',token,None)
                self.assertEqual(proof.get('fixture')['metadata']['uid'],'fixture-uid')
            self.assertEqual(seen,['Bearer first','Bearer second'])

    def test_refused_read_is_bounded_and_auth_failure_is_not_retried(self):
        for error,count in ((urllib.error.URLError(ConnectionRefusedError('not ready')),3),(urllib.error.HTTPError('https://argo',403,'denied',{},None),1)):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as directory:
                token=Path(directory)/'token';token.write_text('fixture');seen=[]
                def request(req,**kwargs):seen.append(req);raise error
                with patch.object(m.ssl,'create_default_context',return_value=object()),patch.object(m.urllib.request,'urlopen',side_effect=request),patch.object(m.time,'sleep'):
                    proof=m.ArgoProof('https://argo','cps-workflows',token,None)
                    with self.assertRaises(urllib.error.URLError):proof.get('fixture')
                self.assertEqual(len(seen),count)

    def test_ambiguous_metadata_patch_is_never_transport_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'token';token.write_text('fixture');seen=[]
            def request(req,**kwargs):seen.append(req.get_method());raise urllib.error.URLError(ConnectionRefusedError('ambiguous'))
            with patch.object(m.ssl,'create_default_context',return_value=object()),patch.object(m.urllib.request,'urlopen',side_effect=request):
                proof=m.ArgoProof('https://argo','cps-workflows',token,None,kube_url='https://kube')
                with self.assertRaises(urllib.error.URLError):proof.kube_request('fixture',{'metadata':{'uid':'fixture-uid'}})
            self.assertEqual(seen,['PATCH'])


class RetentionJobOutcome(unittest.TestCase):
    def test_unknown_object_proof_fails_job_without_deleting_and_prints_report(self):
        import sys
        from types import SimpleNamespace
        now=datetime.now(timezone.utc);s3=S3(now);proof=Proof(now)
        s3.head_object=lambda **kw: (_ for _ in ()).throw(RuntimeError('Proof unavailable'))
        modules={'boto3':SimpleNamespace(client=lambda *a,**kw:s3),
                 'botocore':SimpleNamespace(), 'botocore.client':SimpleNamespace(Config=lambda **kw:kw)}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('access','secret'): (root/name).write_text('fixture-only')
            settings={'version':1,'image':'registry.invalid/image@sha256:'+'a'*64,'policyHash':'sha256:'+'a'*64,
                      'endpoint':'https://s3.invalid','accessKeyFile':str(root/'access'),'secretKeyFile':str(root/'secret'),
                      'ca':None,'argoUrl':'https://argo.invalid','namespace':'cps-workflows','argoTokenFile':'unused','bucket':'bucket'}
            config=root/'config.json';config.write_text(json.dumps(settings));output=io.StringIO()
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['retention','--config',str(config)]),patch.object(m,'ArgoProof',return_value=proof),patch('sys.stdout',output):
                with self.assertRaises(SystemExit) as failure:m.main()
            self.assertEqual(failure.exception.code,1)
            report=json.loads(output.getvalue());self.assertEqual(report['errors'],1);self.assertEqual(report['deleted'],0)
            self.assertFalse(s3.deleted)
