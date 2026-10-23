async def run():
 import os,httpx,base64,copy,io,tarfile,hashlib
 a=CourseServiceApp();a.load_config_file('/config/config.py');a.init_tornado_settings()
 headers=lambda user:{'Authorization':'Bearer '+tokens[user]['token'],'X-CPS-Hub':'cps'}
 results=[];jobs=[]
 async with httpx.AsyncClient(base_url=os.environ['CPS_WORKSPACE_CONTROL_URL'],verify=os.environ['CPS_WORKSPACE_CONTROL_CA'],timeout=60,trust_env=False)as c:
  async def request(method,path,user='armin',**kw):return await c.request(method,path,headers={**headers(user),**kw.pop('headers',{})},**kw)
  try:
   for label,failure in [('success',False),('failure',True)]:
    parameters={'count':3,'scale':1.25,'enabled':True,'label':label,'values':[1,2,3],'options':{'mode':'cpu'},'optional':None}
    source="from qa_selected_helper import message\nassert type(count)is int and count==3\nassert type(scale)is float and scale==1.25\nassert enabled is True and values==[1,2,3] and options=={'mode':'cpu'} and optional is None\nprint(message,label)\n"+("raise RuntimeError('CPS_QA_EXPECTED_FAILURE_20261023')\n"if failure else '')
    nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3'}},'cells':[{'id':'parameters','cell_type':'code','metadata':{'tags':['parameters']},'source':'count=0\nscale=0.0\nenabled=False\nlabel=""\nvalues=[]\noptions={}\noptional=None','execution_count':9,'outputs':[{'output_type':'stream','name':'stdout','text':'CPS_STALE_OUTPUT_MUST_BE_STRIPPED'}]},{'id':'run','cell_type':'code','metadata':{},'source':source,'execution_count':None,'outputs':[]}]}
    raw=json.dumps(nb).encode();helper=b'message="CPS_SELECTED_HELPER_20261023"\n';key='qa-batch-20261023-'+label
    body={'notebook':base64.b64encode(raw).decode(),'files':{'qa_selected_helper.py':base64.b64encode(helper).decode()},'profile':'batch-cpu','parameters':parameters,'walltime':300,'project':'shared-gpu-lab'}
    r=await request('POST','/v1/notebook-submissions',json=body,headers={'Idempotency-Key':key});r.raise_for_status();workflow=r.json();name=workflow['metadata']['name'];uid=workflow['metadata']['uid'];jobs.append({'name':name,'uid':uid});print(json.dumps({'phase':'submitted','kind':label,'name':name,'uid':uid}),flush=True)
    duplicate=await request('POST','/v1/notebook-submissions',json=body,headers={'Idempotency-Key':key});duplicate.raise_for_status();assert duplicate.json()['metadata']['uid']==uid
    mutated=copy.deepcopy(body);mutated['parameters']['count']=4
    conflict=await request('POST','/v1/notebook-submissions',json=mutated,headers={'Idempotency-Key':key});assert conflict.status_code==422,conflict.status_code
    denied={}
    for suffix,method in [('', 'GET'),('/logs','GET'),('/artifacts?download=snapshot','GET'),('/artifacts?download=executed-notebook','GET'),('/terminate','POST')]:
     foreign=await request(method,'/v1/workflows/'+name+suffix,user='mikasa');denied[suffix or 'inspect']=foreign.status_code;assert foreign.status_code==403,(suffix,foreign.status_code)
    listing=await request('GET','/v1/workflows',user='mikasa');listing.raise_for_status();assert name not in listing.text
    deadline=time.monotonic()+420
    while True:
     r=await request('GET','/v1/workflows/'+name);r.raise_for_status();current=r.json();assert current['metadata']['uid']==uid;phase=current.get('status',{}).get('phase')
     if phase in ('Succeeded','Failed','Error'):break
     if time.monotonic()>deadline:raise TimeoutError('Controlled notebook workload exceeded observation limit')
     await asyncio.sleep(3)
    assert phase==('Failed'if failure else'Succeeded'),phase
    r=await request('GET','/v1/workflows/'+name+'/logs');r.raise_for_status();logs=r.json();assert logs.get('available')is True and logs.get('logs')
    r=await request('GET','/v1/workflows/'+name+'/artifacts?download=snapshot');r.raise_for_status()
    assert len(r.content)<4*1024*1024
    with tarfile.open(fileobj=io.BytesIO(r.content))as tar:
     files={m.name:tar.extractfile(m).read()for m in tar.getmembers()if m.isfile()}
    submitted=next(v for k,v in files.items()if k.endswith('submitted.ipynb'));saved=json.loads(submitted);assert all(not cell.get('outputs')and cell.get('execution_count')is None for cell in saved['cells']if cell['cell_type']=='code');assert next(v for k,v in files.items()if k.endswith('qa_selected_helper.py'))==helper;assert json.loads(next(v for k,v in files.items()if k.endswith('parameters.json')))==parameters
    r=await request('GET','/v1/workflows/'+name+'/artifacts?download=executed-notebook');r.raise_for_status();executed=r.json();outputs=[o for cell in executed['cells']for o in cell.get('outputs',[])];text=json.dumps(outputs);assert 'CPS_SELECTED_HELPER_20261023' in text and 'CPS_STALE_OUTPUT_MUST_BE_STRIPPED' not in text;errors=[o for o in outputs if o.get('output_type')=='error'];assert bool(errors)==failure
    results.append({'kind':label,'name':name,'uid':uid,'phase':phase,'idempotent':True,'changed_request_rejected':True,'foreign_denials':denied,'foreign_listing_hidden':True,'logs_available':True,'snapshot_outputs_stripped':True,'selected_import_preserved':True,'typed_parameters_preserved':True,'executed_notebook_retained':True});print(json.dumps({'phase':'verified','result':results[-1]}),flush=True)
  finally:
   for job in jobs:
    r=await request('GET','/v1/workflows/'+job['name'])
    if r.status_code==200 and r.json()['metadata']['uid']==job['uid']and r.json().get('status',{}).get('phase')not in ('Succeeded','Failed','Error'):
     await request('POST','/v1/workflows/'+job['name']+'/terminate')
 print(json.dumps({'matrix_passed':len(results)==2,'results':results}),flush=True)
asyncio.run(run())
