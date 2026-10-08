#!/usr/bin/env python3
"""Two-console, image-only rollout with private SQLite snapshots and CAS guards.

No Secret object is fetched. Database bytes and original Deployment state stay in
an operator-owned 0700 directory outside Git. Git reports contain only checksums.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

NS = 'cps-compute'
IMAGE = 'ghcr.io/mul-cps/e2x-course-hub:qualification-reviewed-alias-f5c005c@sha256:735f891ba008c58a9d3f4d324c22893d13b094dabe7ea39f80c776ffb6c89767'
SOURCE = 'f5c005ca8b36995c6b4221873d3d0b4d334be3d4'
OWNERS = {'cps-admin': 'cps', 'cit-admin': 'cit'}

class StateConflict(RuntimeError):
    """Concurrent record changes require operator reconciliation, never overwrite."""

INSPECT = r'''
import hashlib,json,sqlite3
def inspect(path):
    with sqlite3.connect('file:'+path+'?mode=ro',uri=True,timeout=30) as db:
        db.execute('BEGIN')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result={'user_version':db.execute('PRAGMA user_version').fetchone()[0],
                'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'tables':{}}
        for name in tables:
            rows=db.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall()
            result['tables'][name]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,separators=(',',':'),default=str).encode()).hexdigest()}
        result['email_verification_counts']={str(flag):count for flag,count in db.execute('SELECT verified,count(*) FROM email_links GROUP BY verified').fetchall()} if 'email_links' in tables else {}
        return result
'''

PROBE = INSPECT + r'''
import importlib.util,os,shutil,sys,time
from pathlib import Path
try:
    spec=importlib.util.spec_from_file_location('console_backup','/scripts/backup-console.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    snapshot=module.backup(os.environ['BACKUP_SOURCE'],'/backup',os.environ['BACKUP_IMAGE'],os.environ['BACKUP_OWNER'],os.environ['BACKUP_POLICY_HASH'])
    manifest=json.loads((snapshot/'manifest.json').read_text())
    original=inspect(str(snapshot/'console.sqlite'))
    target='/tmp/qualification.sqlite'
    shutil.copyfile(snapshot/'console.sqlite',target);os.chmod(target,0o600)
    assert hashlib.sha256(Path(target).read_bytes()).hexdigest()==manifest['sha256']['console.sqlite']
    from e2x_course_hub.cps.providers import LocalCourseProvider
    provider=LocalCourseProvider(target,os.environ['BACKUP_OWNER']);provider.db.close()
    migrated=inspect(target)
    assert migrated['user_version']==6 and migrated['integrity']=='ok'
    assert all(migrated['tables'][k]==v for k,v in original['tables'].items())
    assert migrated['email_verification_counts']==original['email_verification_counts']
    assert migrated['tables']['reviewed_account_aliases']['count']==0
    # Execute the unchanged mounted startup config with its existing Secret refs.
    # Redirect only provider SQLite access to the exact snapshot copy. /data is RO.
    import e2x_course_hub.course_service.app as application
    real=application.configure_provider
    def copied_provider(config,path,owner):
        assert path==os.environ['BACKUP_SOURCE'] and owner==os.environ['BACKUP_OWNER']
        return real(config,target,owner)
    application.configure_provider=copied_provider
    app=application.CourseServiceApp()
    app.initialize(['--config=/config/config.py'])
    assert app.tornado_settings['course_provider'].console==os.environ['BACKUP_OWNER']
    from cps_compute.storage import HTTPFilesystemAdapter
    import importlib.metadata as metadata
    result={'status':'qualified','backup_path':str(snapshot),'manifest':manifest,
            'before':original,'after':inspect(target),'startup_config_imports':True,
            'startup_config_sha256':hashlib.sha256(Path('/config/config.py').read_bytes()).hexdigest(),
            'filesystem_adapter':HTTPFilesystemAdapter.__module__,
            'packages':{name:metadata.version(name) for name in ('e2x-course-hub','cps-compute','jupyterhub')},
            'uid':os.getuid()}
    print('QUALIFICATION '+json.dumps(result,separators=(',',':')),flush=True)
    while not Path('/tmp/qualification-stop').exists():time.sleep(1)
except Exception as error:
    print('QUALIFICATION '+json.dumps({'status':'failed','exception':type(error).__name__}),flush=True)
    sys.exit(1)
'''

HEALTH = r'''
import os,json,urllib.request,urllib.error,urllib.parse
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
prefix=os.environ['JUPYTERHUB_SERVICE_PREFIX'].rstrip('/')
try:
    response=urllib.request.build_opener(NoRedirect()).open('http://127.0.0.1:10101'+prefix+'/app',timeout=10)
except urllib.error.HTTPError as response:
    location=urllib.parse.urlsplit(response.headers.get('Location',''))
    assert response.code==302 and location.path.endswith('/hub/api/oauth2/authorize')
    print(json.dumps({'status':response.code,'oauth_host':location.hostname,'oauth_path':location.path}))
else:raise RuntimeError('Expected authentication redirect')
'''

def run(args, *, body=None, binary=False):
    result=subprocess.run(args,input=body,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Command failed: '+args[0]+' '+args[1]+'; exit='+str(result.returncode))
    return result.stdout if binary else result.stdout.decode()

def kubectl(*args, body=None):
    return run(['kubectl','-n',NS,*args],body=body)

def get(kind,name):return json.loads(kubectl('get',kind,name,'-o','json'))

def private_write(path,data):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())

def exec_json(target,code):
    return json.loads(kubectl('exec',target,'--','python','-c',code))

def database(target):
    return exec_json(target,INSPECT+'\nprint(json.dumps(inspect("/data/courses.sqlite")))')

def configuration(deployment):
    volumes=deployment['spec']['template']['spec']['volumes']
    return {v['configMap']['name']:{'resourceVersion':(cm:=get('configmap',v['configMap']['name']))['metadata']['resourceVersion'],
            'sha256':hashlib.sha256(json.dumps(cm.get('data',{}),sort_keys=True,separators=(',',':')).encode()).hexdigest()}
            for v in volumes if 'configMap' in v}

def apply(obj):kubectl('create','-f','-',body=json.dumps(obj).encode())

def image_patch(name,old,new,replicas=None):
    deployment=get('deployment',name)
    assert deployment['spec']['strategy']['type']=='Recreate'
    containers=deployment['spec']['template']['spec']['containers']
    assert len(containers)==1 and containers[0]['name']=='console' and containers[0]['image']==old
    patch=[{'op':'test','path':'/metadata/resourceVersion','value':deployment['metadata']['resourceVersion']},
           {'op':'test','path':'/spec/strategy/type','value':'Recreate'},
           {'op':'test','path':'/spec/template/spec/containers/0/image','value':old},
           {'op':'replace','path':'/spec/template/spec/containers/0/image','value':new}]
    if replicas is not None:patch.append({'op':'replace','path':'/spec/replicas','value':replicas})
    else:
        assert deployment['spec']['replicas']==1
        patch.insert(2,{'op':'test','path':'/spec/replicas','value':1})
    kubectl('patch','deployment',name,'--type=json','-p',json.dumps(patch))
    return deployment['metadata']['resourceVersion']

def await_ready(name,image):
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        deployment=get('deployment',name);status=deployment.get('status',{})
        pods=json.loads(kubectl('get','pods','-l','app='+name,'-o','json'))['items']
        live=[p for p in pods if not p['metadata'].get('deletionTimestamp')]
        if status.get('observedGeneration',0)>=deployment['metadata']['generation'] and status.get('readyReplicas')==1 and status.get('updatedReplicas')==1 and len(live)==1:
            pod=live[0];c=pod['status'].get('containerStatuses',[{}])[0]
            if c.get('ready') and pod['spec']['containers'][0]['image']==image:
                assert image.split('@')[1] in c['imageID']
                return {'pod':pod['metadata']['name'],'imageID':c['imageID']}
        time.sleep(2)
    raise RuntimeError('Deployment did not become ready within 300 seconds')

def patch_backup_image(name,old,new):
    cron=get('cronjob',name+'-backup');before=copy.deepcopy(cron['spec'])
    env=cron['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['env']
    index=next(i for i,e in enumerate(env) if e['name']=='BACKUP_IMAGE')
    assert env[index]['value']==old
    path='/spec/jobTemplate/spec/template/spec/containers/0/env/'+str(index)
    patch=[{'op':'test','path':'/metadata/resourceVersion','value':cron['metadata']['resourceVersion']},
           {'op':'test','path':path+'/name','value':'BACKUP_IMAGE'},
           {'op':'test','path':path+'/value','value':old},
           {'op':'replace','path':path+'/value','value':new}]
    kubectl('patch','cronjob',name+'-backup','--type=json','-p',json.dumps(patch))
    current=get('cronjob',name+'-backup');normalized=copy.deepcopy(current['spec'])
    normalized['jobTemplate']['spec']['template']['spec']['containers'][0]['env'][index]['value']=old
    assert normalized==before
    return {'before':old,'after':new,'resourceVersion_precondition':cron['metadata']['resourceVersion'],
            'resourceVersion_after':current['metadata']['resourceVersion'],'only_BACKUP_IMAGE_changed':True,
            'runner_image':current['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['image'],
            'schedule':current['spec']['schedule']}

def probe(name,deployment,bundle):
    cron=get('cronjob',name+'-backup')
    spec=copy.deepcopy(cron['spec']['jobTemplate']['spec'])
    pod=spec['template']['spec'];container=pod['containers'][0]
    original=deployment['spec']['template']['spec'];live=original['containers'][0]
    assert next(v for v in pod['volumes'] if v['name']=='source')['persistentVolumeClaim']['claimName']==name+'-data'
    assert next(m for m in container['volumeMounts'] if m['name']=='source')['readOnly'] is True
    env={e['name']:e for e in container['env']}
    assert env['BACKUP_SOURCE']['value']=='/data/courses.sqlite'
    assert env['BACKUP_OWNER']['value']==OWNERS[name]
    env['BACKUP_IMAGE']={'name':'BACKUP_IMAGE','value':live['image']}
    env.update({e['name']:e for e in live.get('env',[])})
    container.update(image=IMAGE,command=['python','-c',PROBE],env=list(env.values()),securityContext=copy.deepcopy(live['securityContext']))
    container['securityContext']['readOnlyRootFilesystem']=True
    pod['volumes'].append({'name':'qualification-tmp','emptyDir':{'medium':'Memory','sizeLimit':'128Mi'}})
    container['volumeMounts'].append({'name':'qualification-tmp','mountPath':'/tmp'})
    pod['automountServiceAccountToken']=False
    pod['restartPolicy']='Never';pod['imagePullSecrets']=original.get('imagePullSecrets',[])
    for volume in original['volumes']:
        if 'configMap' in volume and volume['name'] not in {v['name'] for v in pod['volumes']}:
            pod['volumes'].append(copy.deepcopy(volume))
    for mount in live['volumeMounts']:
        if mount['name']!='data':container['volumeMounts'].append(copy.deepcopy(mount))
    spec['template']['metadata']={'labels':{'qualification.cps/scope':'admin-reviewed-alias','qualification.cps/owner':OWNERS[name]}}
    spec['activeDeadlineSeconds']=900;spec['backoffLimit']=0;spec.pop('ttlSecondsAfterFinished',None)
    job='reviewed-alias-'+OWNERS[name]+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S')
    apply({'apiVersion':'batch/v1','kind':'Job','metadata':{'name':job,'namespace':NS},'spec':spec})
    deadline=time.monotonic()+300;proof=None;target=None
    while time.monotonic()<deadline:
        pods=json.loads(kubectl('get','pods','-l','job-name='+job,'-o','json'))['items']
        if pods:
            target=pods[0]['metadata']['name']
            if pods[0]['status'].get('phase') in ('Running','Succeeded','Failed'):
                logs=kubectl('logs',target)
                markers=[line[len('QUALIFICATION '):] for line in logs.splitlines() if line.startswith('QUALIFICATION ')]
                if markers:
                    proof=json.loads(markers[-1]);break
        time.sleep(2)
    if not proof or proof['status']!='qualified':raise RuntimeError('Copy-only backup/startup qualification failed; job='+job)
    directory=bundle/name;directory.mkdir(mode=0o700)
    for filename in ('console.sqlite','manifest.json'):
        command=['kubectl','-n',NS,'exec',target,'--','python','-c',
                 'from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(proof['backup_path']+'/'+filename)+').read_bytes())']
        private_write(directory/filename,run(command,binary=True))
    assert hashlib.sha256((directory/'console.sqlite').read_bytes()).hexdigest()==proof['manifest']['sha256']['console.sqlite']
    assert (directory/'console.sqlite').stat().st_mode & 0o777==0o600
    assert database('deployment/'+name)==proof['before']
    private_write(directory/'deployment-before.json',json.dumps(deployment).encode())
    kubectl('delete','job',job,'--wait=false')
    proof.pop('status');proof['backup_file_mode']='0600';proof['backup_job']=job
    return proof

def rollback(name,bundle):
    directory=bundle/name
    original=json.loads((directory/'deployment-before.json').read_text())
    old=original['spec']['template']['spec']['containers'][0]['image']
    state=json.loads((bundle/'state.json').read_text())
    backup=state['consoles'][name]['qualification']['backup_path']
    image_patch(name,IMAGE,IMAGE,replicas=0)
    deadline=time.monotonic()+180
    while json.loads(kubectl('get','pods','-l','app='+name,'-o','json'))['items']:
        if time.monotonic()>deadline:raise RuntimeError('Cannot restore while a console pod remains')
        time.sleep(2)
    cron=get('cronjob',name+'-backup');spec=copy.deepcopy(cron['spec']['jobTemplate']['spec'])
    pod=spec['template']['spec'];container=pod['containers'][0]
    next(m for m in container['volumeMounts'] if m['name']=='source')['readOnly']=False
    next(m for m in container['volumeMounts'] if m['name']=='backup')['readOnly']=True
    code=INSPECT+'\n'+f'''
from pathlib import Path
assert hashlib.sha256(Path({backup+'/console.sqlite'!r}).read_bytes()).hexdigest()=={state['consoles'][name]['qualification']['manifest']['sha256']['console.sqlite']!r}
current=inspect('/data/courses.sqlite')
expected={state['consoles'][name]['qualification']['before']!r}
assert all(current['tables'][k]==v for k,v in expected['tables'].items()), 'Concurrent record changes: restore refused'
assert current['email_verification_counts']==expected['email_verification_counts']
assert all(v['count']==0 for k,v in current['tables'].items() if k not in expected['tables']), 'New identity records: restore refused'
with sqlite3.connect('file:'+{backup+'/console.sqlite'!r}+'?mode=ro',uri=True) as reader:
    with sqlite3.connect('/data/courses.sqlite',timeout=30) as writer:reader.backup(writer)
assert inspect('/data/courses.sqlite')=={state['consoles'][name]['qualification']['before']!r}
print('RESTORE_OK',flush=True)
'''
    container.update(image=old,command=['python','-c',code])
    pod['restartPolicy']='Never';pod['automountServiceAccountToken']=False
    spec['template']['metadata']={'labels':{'qualification.cps/scope':'admin-reviewed-alias-restore'}}
    spec['activeDeadlineSeconds']=180;spec['backoffLimit']=0
    job='reviewed-alias-restore-'+OWNERS[name]+'-'+str(int(time.time()))
    apply({'apiVersion':'batch/v1','kind':'Job','metadata':{'name':job,'namespace':NS},'spec':spec})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        status=get('job',job).get('status',{})
        if status.get('succeeded')==1:break
        if status.get('failed'):raise RuntimeError('Restore failed; console remains stopped')
        time.sleep(2)
    else:raise RuntimeError('Restore timed out; console remains stopped')
    image_patch(name,IMAGE,old,replicas=1)
    await_ready(name,old)
    cron=get('cronjob',name+'-backup')
    metadata=next(e['value'] for e in cron['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['env'] if e['name']=='BACKUP_IMAGE')
    if metadata==IMAGE:patch_backup_image(name,IMAGE,old)
    else:assert metadata==old
    kubectl('delete','job',job,'--wait=false')

def verify_snapshot(name,qualification):
    """Read the persisted backup PVC after rollout without mounting live data."""
    cron=get('cronjob',name+'-backup');spec=copy.deepcopy(cron['spec']['jobTemplate']['spec'])
    pod=spec['template']['spec'];container=pod['containers'][0]
    pod['volumes']=[v for v in pod['volumes'] if v['name']=='backup']
    container['volumeMounts']=[{'name':'backup','mountPath':'/backup','readOnly':True}]
    container['image']=IMAGE
    snapshot=qualification['backup_path'];digest=qualification['manifest']['sha256']['console.sqlite']
    version=qualification['manifest']['user_version']
    container['command']=['python','-c',f'''
import hashlib,json,sqlite3,stat
from pathlib import Path
path=Path({snapshot+'/console.sqlite'!r})
assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()=={digest!r}
with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('PRAGMA user_version').fetchone()[0]=={version!r}
assert stat.S_IMODE(path.stat().st_mode)==0o600
assert stat.S_IMODE(path.parent.stat().st_mode) & 0o007==0
print('BACKUP_VERIFIED '+json.dumps({{'file_mode':oct(stat.S_IMODE(path.stat().st_mode)),
    'directory_mode':oct(stat.S_IMODE(path.parent.stat().st_mode))}}),flush=True)
''']
    pod['automountServiceAccountToken']=False;pod['restartPolicy']='Never'
    pod['securityContext']['fsGroupChangePolicy']='OnRootMismatch'
    spec['template']['metadata']={'labels':{'qualification.cps/scope':'admin-reviewed-alias-backup-proof'}}
    spec['activeDeadlineSeconds']=180;spec['backoffLimit']=0
    job='reviewed-alias-backup-proof-'+OWNERS[name]+'-'+str(int(time.time()))
    apply({'apiVersion':'batch/v1','kind':'Job','metadata':{'name':job,'namespace':NS},'spec':spec})
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        status=get('job',job).get('status',{})
        if status.get('succeeded')==1:break
        if status.get('failed'):raise RuntimeError('Persisted backup verification failed; job='+job)
        time.sleep(2)
    else:raise RuntimeError('Persisted backup verification timed out')
    lines=kubectl('logs','job/'+job).splitlines()
    modes=json.loads(next(line[len('BACKUP_VERIFIED '):] for line in lines if line.startswith('BACKUP_VERIFIED ')))
    kubectl('delete','job',job,'--wait=false')
    return {'present':True,'integrity':'ok','schema':version,**modes,'sha256':digest}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--rollback',choices=OWNERS)
    args=parser.parse_args();bundle=args.private_dir.resolve()
    if any((parent/'.git').exists() for parent in (bundle,*bundle.parents)):
        raise ValueError('Private database evidence must be outside Git')
    os.umask(0o077);bundle.mkdir(parents=True,mode=0o700,exist_ok=True)
    if bundle.stat().st_uid!=os.getuid() or bundle.stat().st_mode & 0o777!=0o700:
        raise ValueError('Private evidence directory requires operator ownership and 0700')
    if args.rollback:rollback(args.rollback,bundle);print('Matching backup and old image restored');return
    if args.execute and (bundle/'state.json').exists():
        raise ValueError('Existing rollout state requires a new private directory; refuse to overwrite rollback evidence')
    report={'source':SOURCE,'image':IMAGE,'namespace':NS,'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'consoles':{}}
    for name in OWNERS:
        deployment=get('deployment',name)
        assert deployment['spec']['replicas']==1 and deployment['spec']['strategy']['type']=='Recreate'
        entry={'old_image':deployment['spec']['template']['spec']['containers'][0]['image'],
               'deployment_resourceVersion':deployment['metadata']['resourceVersion'],
               'configuration':configuration(deployment),'before':database('deployment/'+name)}
        report['consoles'][name]=entry
        if args.execute:entry['qualification']=probe(name,deployment,bundle)
    if args.execute:
        (bundle/'state.json').write_text(json.dumps(report,indent=2)+'\n');os.chmod(bundle/'state.json',0o600)
        for name,entry in report['consoles'].items():
            try:
                assert configuration(get('deployment',name))==entry['configuration']
                assert database('deployment/'+name)==entry['before']
                entry['patch_resourceVersion']=image_patch(name,entry['old_image'],IMAGE)
                entry['ready']=await_ready(name,IMAGE)
                entry['after']=database('deployment/'+name)
                if entry['after']!=entry['qualification']['after']:
                    raise StateConflict('Database differs from qualified copy; refuse automatic restore over concurrent changes')
                entry['oauth_redirect']=exec_json('deployment/'+name,HEALTH)
                assert configuration(get('deployment',name))==entry['configuration']
                entry['configuration_unchanged']=True
                entry['rollback_available']=True
                entry['persisted_backup']=verify_snapshot(name,entry['qualification'])
                entry['backup_metadata_patch']=patch_backup_image(name,entry['old_image'],IMAGE)
                post=bundle/'post-upgrade';post.mkdir(mode=0o700,exist_ok=True)
                entry['post_upgrade_backup']=probe(name,get('deployment',name),post)
                assert entry['post_upgrade_backup']['manifest']['application_image']==IMAGE
                assert entry['post_upgrade_backup']['manifest']['user_version']==6
                entry['post_upgrade_backup']['persisted']=verify_snapshot(name,entry['post_upgrade_backup'])
            except StateConflict:
                entry['state_conflict']=True
                (bundle/'state.json').write_text(json.dumps(report,indent=2)+'\n')
                raise
            except Exception:
                # Never restart an older application against the migrated schema.
                if get('deployment',name)['spec']['template']['spec']['containers'][0]['image']==IMAGE:
                    rollback(name,bundle)
                raise
            (bundle/'state.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
