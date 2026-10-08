import asyncio,json,tempfile,secrets,uuid
from pathlib import Path
from types import SimpleNamespace
import httpx
from fastapi import FastAPI
from kubernetes import client,config
from cps_compute.internal import ControlStore,ServiceIdentity,install_internal
from cps_compute.reservations import Reservations
from cps_compute.storage import KubernetesStorage,StorageController,StorageError,binding
config.load_incluster_config();core=client.CoreV1Api()
identity=client.AuthenticationV1Api().create_self_subject_review({'apiVersion':'authentication.k8s.io/v1','kind':'SelfSubjectReview'}).status.user_info.username
assert identity=='system:serviceaccount:cps-compute:cps-compute-controller',identity
class NeverMutateNAS:
 def __init__(self):self.calls=0
 async def action(self,*args,**kwargs):self.calls+=1;raise AssertionError('NAS mutation forbidden in probe')
async def main():
 nas=NeverMutateNAS();kube=KubernetesStorage(core,client.BatchV1Api());rows=[]
 with tempfile.TemporaryDirectory() as temporary:
  store=ControlStore(Path(temporary)/'control.db');reservations=Reservations(Path(temporary)/'reservations.db')
  tokens={secrets.token_urlsafe(32):ServiceIdentity('qualification-cps','cps'),secrets.token_urlsafe(32):ServiceIdentity('qualification-cit','cit'),secrets.token_urlsafe(32):ServiceIdentity('qualification-metrics','cps',True)}
  async def authenticate(token):return tokens[token]
  async def owner(source,workspace):return workspace['owner'].startswith('qualification-')
  async def shutdown(source,workspace):return True
  policy=SimpleNamespace(hash='sha256:051cd754210af2830d67968eea898f674a55ff66f5c88b3db95dff205f04e33d')
  app=FastAPI();install_internal(app,store,reservations,authenticate,shutdown,policy,workspace_owner_check=owner,storage_controller=StorageController(nas,kube))
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://qualification') as http:
   for source in ['cps','cit']:
    name='qualification-'+uuid.uuid4().hex;body={'workspace':name,'owner':name,'server':'','group_id':name,'policy_hash':policy.hash,'members':[],'profile':'interactive-cpu'}
    service=next(s for s in tokens.values() if s.source==source and not s.metrics_only);store.put_workspace(body,service,reservations)
    _,path=binding(source,name)
    try:
     writers=await kube.writers({'pv':'','path':path},parents_only=True)
     assert writers,'No active parent mount: this refusal-only fixture does not qualify provisioning'
     guard={'kind':'active-parent-mount','count':len(writers)}
    except StorageError as e:
     assert str(e)=='Unresolved active Pod claim',str(e)
     guard={'kind':'unresolved-active-claim','failClosed':True}
    cases=[('missing-auth',None,401),('invalid-auth','invalid',401),('metrics-only',next(t for t,s in tokens.items() if s.metrics_only),403),('wrong-console',next(t for t,s in tokens.items() if s.source!=source and not s.metrics_only),409),('source-authorized-guard',next(t for t,s in tokens.items() if s.source==source and not s.metrics_only),409)]
    for label,token,expected in cases:
     response=await http.post('/internal/v1/workspaces/provision',json={'workspace':name},headers={'Authorization':'Bearer '+token} if token else {})
     assert response.status_code==expected,(source,label,response.status_code,response.text)
     assert nas.calls==0,'NAS was invoked'
     rows.append({'source':source,'case':label,'status':response.status_code})
    assert store.workspace(source,name).get('storage') is None,'Denied request added storage'
    rows.append({'source':source,'writerGuard':guard,'noStorageBindingCreated':True})
 print(json.dumps({'passed':True,'imageComputeRevision':'6bb6a57bc8d8426e281c0654ac8eedd1668ae600','serviceAccountIdentity':identity,'cases':rows,'nasCalls':nas.calls,'databaseScope':'temporary probe only','httpScope':'ASGI application with operator fixture credentials','limitations':['Refusal/authorization gate only; NAS lifecycle, actual Hub ownership, production OAuth and successful storage provisioning are not qualified.']}))
asyncio.run(main())
