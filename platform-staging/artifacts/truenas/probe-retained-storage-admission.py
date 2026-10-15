import json,uuid
from kubernetes import client,config
config.load_incluster_config();api=client.CoreV1Api();out=[]
for root in ['cps_persistent1_shared/compute','cps_compute_workspaces']:
 for source,ns in [('cps','jupyterhub'),('cit','cit-jhub')]:
  for change in ['valid','wrong_namespace','wrong_server','delete_policy','bad_root']:
   name='cps-workspace-'+uuid.uuid4().hex+'0'*8
   body={'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':name},'spec':{'capacity':{'storage':'1Ti'},'accessModes':['ReadWriteMany'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'','claimRef':{'namespace':ns,'name':name},'nfs':{'server':'193.170.30.58','path':'/mnt/persistent1/'+root+'/'+source+'/'+'a'*64,'readOnly':False}}}
   if change=='wrong_namespace':body['spec']['claimRef']['namespace']='cit-jhub' if ns=='jupyterhub' else 'jupyterhub'
   if change=='wrong_server':body['spec']['nfs']['server']='10.71.1.55'
   if change=='delete_policy':body['spec']['persistentVolumeReclaimPolicy']='Delete'
   if change=='bad_root':body['spec']['nfs']['path']='/mnt/persistent1/other/'+source+'/'+'a'*64
   try:api.create_persistent_volume(body,dry_run='All');allowed=True
   except client.exceptions.ApiException as e:
    if e.status!=422:raise
    allowed=False
   out.append({'root':root,'source':source,'case':change,'allowed':allowed,'expected':change=='valid'})
print(json.dumps({'cases':out,'passed':all(x['allowed']==x['expected'] for x in out)}))
