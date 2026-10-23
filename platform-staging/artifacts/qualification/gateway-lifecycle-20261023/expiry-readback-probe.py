import datetime,hashlib,importlib.util,json
from pathlib import Path
import boto3
from botocore.client import Config
NAME='cps-17b066f83a1f881e0f881284bbe2864be5d59f527c511158';UID='99c163bf-f6ec-45e9-a263-d895729b61c0';IDENT=NAME.removeprefix('cps-');BUCKET=None
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
proof=OwnedProof();workflow=proof.get(NAME);states=m.lifecycle(workflow)['artifacts'];assert set(states)=={'snapshot','executed-notebook'} and all(x['state']=='deleting' for x in states.values())
missing=[]
for key in sorted(allowed):
 try:client.head_object(Bucket=BUCKET,Key=key)
 except client.exceptions.ClientError as error:assert error.response['ResponseMetadata']['HTTPStatusCode']==404;missing.append(key)
 else:raise AssertionError('Object still exists')
print(json.dumps({'passed':True,'workflow':NAME,'uid':UID,'durable_deletion_claims_verified':True,'objects_confirmed_absent':missing,'read_only_readback':True}))
