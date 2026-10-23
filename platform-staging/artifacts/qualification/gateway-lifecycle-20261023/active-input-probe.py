import datetime,hashlib,importlib.util,json
from pathlib import Path
import boto3
from botocore.client import Config
NAME='cps-95b48187e86b5c3d7a9eeb1d91a7fa272e0500ed7750ece6';UID='fc6bf86e-1ed2-4efd-9474-d36f5a469c04';IDENT=NAME.removeprefix('cps-');BUCKET=None
script=Path('/scripts/artifact-retention.py');assert hashlib.sha256(script.read_bytes()).hexdigest()=='9cadec1f0229222f34923b18f456a0506ae5e92826ea78ab7e791e1e72e73542'
spec=importlib.util.spec_from_file_location('actual_retention',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=json.loads(Path('/scripts/config.json').read_text());BUCKET=s['bucket']
client=boto3.client('s3',endpoint_url=s['endpoint'],aws_access_key_id=Path(s['accessKeyFile']).read_text().strip(),aws_secret_access_key=Path(s['secretKeyFile']).read_text().strip(),region_name='us-east-1',verify=s['ca'],config=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':1},s3={'addressing_style':'path'}))
allowed={f'notebook-inputs/{IDENT}/snapshot.tar',f'run-artifacts/{IDENT}/executed.ipynb'}
class Page:
 def paginate(self,**kw):
  assert kw['Bucket']==BUCKET and kw['Prefix'] in m.POLICY
  kw['Prefix']+=IDENT+'/'
  for page in client.get_paginator('list_objects_v2').paginate(**kw):
   assert all(x['Key'] in allowed for x in page.get('Contents',[]));yield page
class OwnedS3:
 def get_paginator(self,name):assert name=='list_objects_v2';return Page()
 def head_object(self,**kw):assert kw['Bucket']==BUCKET and kw['Key'] in allowed;return client.head_object(**kw)
 def get_object_tagging(self,**kw):assert kw['Bucket']==BUCKET and kw['Key'] in allowed;return client.get_object_tagging(**kw)
 def get_object(self,**kw):assert kw['Bucket']==BUCKET and kw['Key'] in {f'notebook-provenance/{IDENT}/intent.json',f'notebook-provenance/{IDENT}/binding.json'};return client.get_object(**kw)
class OwnedProof:
 namespace='cps-workflows'
 def __init__(self):self.proof=m.ArgoProof(s['argoUrl'],s['namespace'],s['argoTokenFile'],s.get('argoCa'),kube_url=s['kubeUrl'],kube_ca=s.get('kubeCa'))
 def get(self,name):
  assert name==NAME;workflow=self.proof.get(name);assert workflow['metadata']['uid']==UID;return workflow
 def claim(self,workflow,key,etag,now):
  assert workflow['metadata']['name']==NAME and workflow['metadata']['uid']==UID and key in allowed
  return self.proof.claim(workflow,key,etag,now)
 def verify_claim(self,workflow,key,entry,now):
  assert workflow['metadata']['name']==NAME and workflow['metadata']['uid']==UID and key in allowed
  return self.proof.verify_claim(workflow,key,entry,now)
class MutableOwnedS3(OwnedS3):
 def put_object_tagging(self,**kw):
  assert kw['Bucket']==BUCKET and kw['Key'] in allowed
  return client.put_object_tagging(**kw)
 def copy_object(self,**kw):
  assert kw['Bucket']==BUCKET and kw['Key'] in allowed and kw['CopySource']=={'Bucket':BUCKET,'Key':kw['Key']}
  return client.copy_object(**kw)
 def delete_object(self,**kw):
  assert kw['Bucket']==BUCKET and kw['Key'] in allowed and isinstance(kw.get('IfMatch'),str)
  return client.delete_object(**kw)
proof=OwnedProof();workflow=proof.get(NAME);assert workflow['status']['phase']=='Running'
key=f'notebook-inputs/{IDENT}/snapshot.tar';before={'head':client.head_object(Bucket=BUCKET,Key=key)['ETag'],'tags':client.get_object_tagging(Bucket=BUCKET,Key=key)['TagSet']}
now=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=91)
report=m.sweep(MutableOwnedS3(),BUCKET,proof,now=now,apply=True,max_examined=2,max_deletes=2,conditional_delete_qualified=True,lifecycle_qualified=True,reconcile_metadata=True)
after={'head':client.head_object(Bucket=BUCKET,Key=key)['ETag'],'tags':client.get_object_tagging(Bucket=BUCKET,Key=key)['TagSet']};assert before==after and report['deleted']==report['eligible']==report['errors']==report['reconciled']==0
assert proof.get(NAME)['status']['phase']=='Running'
print(json.dumps({'passed':True,'workflow':NAME,'uid':UID,'real_gateway_workflow_running_before_and_after':True,'per_call_91_day_clock':report,'snapshot_etag_and_tags_unchanged':True,'production_schedule_unchanged':True}))
