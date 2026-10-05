import copy
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

class S3:
    def __init__(self,now):
        self.key='notebook-inputs/id/snapshot.tar';self.now=now;self.deleted=[]
        self.tags={'retention':'temporary-expirable','active':'false','retained':'false'}
        self.head={'ETag':'"etag"','LastModified':now-timedelta(days=100),'Metadata':{'cps-workflow':'wf','cps-workflow-uid':'uid'}}
    def get_paginator(self,name):return self
    def paginate(self,**kwargs):
        yield {'Contents':[{'Key':self.key,'LastModified':self.head['LastModified']}] if self.key.startswith(kwargs['Prefix']) else []}
    def get_object_tagging(self,**kwargs):return {'TagSet':[{'Key':k,'Value':v} for k,v in self.tags.items()]}
    def head_object(self,**kwargs):return copy.deepcopy(self.head)
    def delete_object(self,**kwargs):self.deleted.append(kwargs)

class Proof:
    namespace='cps-workflows'
    def __init__(self,now):
        self.workflow={'metadata':{'name':'wf','namespace':self.namespace,'uid':'uid','annotations':{'cps.compute/notebook-id':'id'}},'status':{'phase':'Succeeded','finishedAt':(now-timedelta(days=100)).isoformat()}}
    def get(self,name):return copy.deepcopy(self.workflow)

class Retention(unittest.TestCase):
    def setUp(self):self.now=datetime.now(timezone.utc);self.s3=S3(self.now);self.proof=Proof(self.now)
    def test_dryrun_and_conditional_delete_only_after_qualified_rechecked_proof(self):
        report=m.sweep(self.s3,'bucket',self.proof,now=self.now)
        self.assertEqual(report['eligible'],1);self.assertFalse(self.s3.deleted)
        with self.assertRaises(ValueError):m.sweep(self.s3,'bucket',self.proof,apply=True,now=self.now)
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)
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
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)['deleted'],0)
        self.s3=S3(self.now);calls=[];original=self.proof.get
        def proof(name):
            calls.append(1)
            if len(calls)>1:self.proof.workflow['status']['phase']='Running'
            return original(name)
        self.proof.get=proof
        self.assertEqual(m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)['deleted'],0)
    def test_unsupported_ifmatch_is_error_and_never_falls_back(self):
        calls=[]
        def delete(**kwargs):calls.append(kwargs);raise TypeError('unsupported IfMatch')
        self.s3.delete_object=delete
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)
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
        report=m.sweep(self.s3,'bucket',self.proof,apply=True,conditional_delete_qualified=True,now=self.now)
        self.assertEqual(report['errors'],1);self.assertFalse(self.s3.deleted)

class RetentionChart(unittest.TestCase):
    def render(self,overrides=None):
        policy=json.loads((ROOT/'compute-policy/generated/policy.json').read_text());image='registry.invalid/image@sha256:'+'a'*64
        values={'enabled':True,'policyJson':json.dumps(policy),'policyHash':policy['policyHash'],'gateway':{'image':image},'consoles':{'cps':{'image':image},'cit':{'image':image,'publicCallbackUrl':'https://example.invalid/cb'}},'artifactRetention':{'enabled':True,'image':image}}
        values['artifactRetention'].update(overrides or {})
        with tempfile.NamedTemporaryFile('w',suffix='.yaml') as file:
            yaml.safe_dump(values,file);file.flush()
            return subprocess.run(['helm','template','compute',str(ROOT/'platform-staging/chart'),'-f',file.name],capture_output=True,text=True)
    def test_dedicated_get_only_rbac_and_suspended_dryrun_projected_token(self):
        result=self.render();self.assertEqual(result.returncode,0,result.stderr)
        documents=[d for d in yaml.safe_load_all(result.stdout) if d]
        cron=next(d for d in documents if d['kind']=='CronJob' and d['metadata']['name']=='cps-artifact-retention')
        self.assertTrue(cron['spec']['suspend']);pod=cron['spec']['jobTemplate']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken']);self.assertEqual(pod['serviceAccountName'],'cps-artifact-retention')
        self.assertNotEqual(pod['serviceAccountName'],'cps-compute-controller');self.assertNotIn('--apply',pod['containers'][0]['args'])
        role=next(d for d in documents if d['kind']=='Role' and d['metadata']['name']=='cps-artifact-retention-proof')
        self.assertEqual(role['metadata']['namespace'],'cps-workflows');self.assertEqual(role['rules'],[{'apiGroups':['argoproj.io'],'resources':['workflows'],'verbs':['get']}])
        binding=next(d for d in documents if d['kind']=='RoleBinding' and d['metadata']['name']=='cps-artifact-retention-proof')
        self.assertEqual(binding['subjects'],[{'kind':'ServiceAccount','name':'cps-artifact-retention','namespace':'cps-compute'}])
        projected=next(v for v in pod['volumes'] if v['name']=='argo-token')['projected']['sources'][0]
        self.assertEqual(projected['serviceAccountToken']['expirationSeconds'],3600)
        policy=next(d for d in documents if d['kind']=='NetworkPolicy' and d['metadata']['name']=='cps-artifact-retention-argo')
        self.assertEqual(policy['spec']['ingress'][0]['from'][0]['podSelector'],{'matchLabels':{'app':'cps-artifact-retention'}})
    def test_apply_and_limits_fail_closed_without_evidence(self):
        for override in ({'apply':True},{'apply':True,'conditionalDeleteQualified':True,'qualificationEvidence':'conditional-only'},{'maxExamined':0},{'maxDeletes':1001}):self.assertNotEqual(self.render(override).returncode,0)

if __name__=='__main__':unittest.main()
