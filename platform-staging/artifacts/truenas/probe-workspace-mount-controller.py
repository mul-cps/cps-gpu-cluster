import json,uuid,copy
from kubernetes import client,config
config.load_incluster_config();core=client.CoreV1Api();identity=client.AuthenticationV1Api().create_self_subject_review({'apiVersion':'authentication.k8s.io/v1','kind':'SelfSubjectReview'}).status.user_info.username
assert identity=='system:serviceaccount:cps-compute:cps-compute-controller';rows=[]
for source,namespace in [('cps','jupyterhub'),('cit','cit-jhub')]:
 name='cps-workspace-'+uuid.uuid4().hex+'0'*8
 body={'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':'1Ti'},'accessModes':['ReadWriteMany'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'name':name,'namespace':namespace},'nfs':{'server':'193.170.30.58','path':'/mnt/persistent1/cps_compute_workspaces/'+source+'/'+'a'*64,'readOnly':False}}}
 for case in ['valid','wrong_namespace','wrong_server','delete_policy','parent_root']:
  obj=copy.deepcopy(body)
  if case=='wrong_namespace':obj['spec']['claimRef']['namespace']='cit-jhub' if namespace=='jupyterhub' else 'jupyterhub'
  if case=='wrong_server':obj['spec']['nfs']['server']='truenas.local'
  if case=='delete_policy':obj['spec']['persistentVolumeReclaimPolicy']='Delete'
  if case=='parent_root':obj['spec']['nfs']['path']='/mnt/persistent1'
  try:core.create_persistent_volume(obj,dry_run='All');allowed=True
  except client.exceptions.ApiException as e:
   assert e.status==422,e.status;allowed=False
  rows.append({'source':source,'case':case,'allowed':allowed,'expected':case=='valid'})
assert all(x['allowed']==x['expected'] for x in rows)
print(json.dumps({'identity':identity,'cases':rows,'onlyServerDryRuns':True,'passed':True}))
