async def run():
 import os,httpx,copy,hashlib
 a=CourseServiceApp();a.load_config_file('/config/config.py');a.init_tornado_settings();results=[]
 async with httpx.AsyncClient(base_url=os.environ['CPS_WORKSPACE_CONTROL_URL'],verify=os.environ['CPS_WORKSPACE_CONTROL_CA'],headers={'Authorization':'Bearer '+tokens['armin']['token'],'X-CPS-Hub':'cps'},timeout=30,trust_env=False)as c:
  r=await c.get('/v1/me');r.raise_for_status();person=r.json()['identity'];r=await c.get('/v1/profiles');r.raise_for_status();p=r.json()['batch-cpu']
  base={'apiVersion':'argoproj.io/v1alpha1','kind':'Workflow','metadata':{},'spec':{'entrypoint':'run','activeDeadlineSeconds':60,'templates':[{'name':'run','container':{'image':p['images'][0],'command':['python','-c','print("CPS_QA_NOOP")'],'resources':{'requests':{'cpu':p['cpu'],'memory':p['memory']},'limits':{'cpu':p['cpu'],'memory':p['memory']}}}}]}}
  variants=[]
  for field,value in [('serviceAccountName','cps-qa-unconfigured'),('schedulerName','default-scheduler'),('podPriorityClassName','cps-lecture'),('podMetadata',{'labels':{'kai.scheduler/queue':'cps-interactive'}}),('podSpecPatch','{}')]:
   w=copy.deepcopy(base);w['spec'][field]=value;variants.append((field,w))
  w=copy.deepcopy(base);w['metadata']['namespace']='kube-system';variants.append(('namespace',w))
  w=copy.deepcopy(base);w['spec']['templates'][0]['container']['image']='invalid.invalid/cps-qa@sha256:'+'0'*64;variants.append(('unapproved-image',w))
  w=copy.deepcopy(base);w['spec']['templates'][0]['container']['resources']['requests']['cpu']='3';variants.append(('resource-mismatch',w))
  w=copy.deepcopy(base);w['spec']['templates'][0]['container']['volumeMounts']=[{'name':'forbidden','mountPath':'/qa'}];variants.append(('mount-override',w))
  for label,w in variants:
   key='qa-reject-20261023-'+label;name='cps-'+hashlib.sha256((person+chr(0)+key).encode()).hexdigest()[:48];r=await c.post('/v1/workflows',json={'workflow':w,'project':'shared-gpu-lab','profile':'batch-cpu'},headers={'Idempotency-Key':key})
   if r.status_code in (200,201,202):await c.post('/v1/workflows/'+name+'/terminate')
   assert r.status_code==422,(label,r.status_code)
   found=await c.get('/v1/workflows/'+name);assert found.status_code==404,(label,found.status_code)
   results.append({'case':label,'status':422,'workflow_absent':True})
 print(json.dumps({'crafted_matrix_passed':True,'results':results}),flush=True)
asyncio.run(run())
