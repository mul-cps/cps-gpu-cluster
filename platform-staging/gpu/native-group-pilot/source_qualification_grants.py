"""Bounded default-inert Source grant transition for CPS5/CIT10 qualification.

Derivative of frozen10001 grant1590; only existing selected fixture grants
change one profile, preserving all original times, resources and source fields.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone
from urllib.parse import urlsplit

OLD='interactive-shared-5'
NEW='interactive-native-qualification-5'
NEW_BY_SOURCE={'cps':NEW,'cit':'interactive-native-qualification-10'}
ACTOR='operator:native-profile-qualification-20261011:scoped-grant-handover'
COURSE='native-gpu-pilot-20261009'
TERM='qualification-20261009'
CEILING={'cpu':'4','memory':'16Gi','gpuMemoryGiB':5}
PEOPLE={'cps':{'cpsgpumembera':'386feebb-df1a-4f3c-9ef9-6d9c026d5aea','cpsgpumemberb':'d1fb4e43-64ec-4ac5-914f-e9cd39ad1c62','cpsgpumemberc':'8edde4a2-257c-42d7-9732-13f1e8742a33','cpsgpumemberd':'3237c91b-cef3-4f6f-960e-875b9e93c4be'},'cit':{'citgpumembera':'386feebb-df1a-4f3c-9ef9-6d9c026d5aea','citgpumemberb':'d1fb4e43-64ec-4ac5-914f-e9cd39ad1c62'}}
MAX=1048576

def require(ok,msg):
    if not ok: raise ValueError(msg)

def canonical(doc): return json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(doc): return hashlib.sha256(canonical(doc).encode()).hexdigest()
def closed(doc,keys): require(type(doc) is dict and set(doc)==set(keys),'Closed reviewed document required')
def decode(raw):
    def unique(items):
        out={}
        for k,v in items: require(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def protected(path,sha):
    require(type(sha) is str and re.fullmatch('[0-9a-f]{64}',sha),'Exact file SHA required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        a=os.fstat(fd);require(stat.S_ISREG(a.st_mode) and a.st_uid==10001 and a.st_nlink==1 and stat.S_IMODE(a.st_mode) in (0o400,0o600) and 0<a.st_size<=MAX,'Protected bounded trusted operator UID10001 400/600 file required')
        raw=os.read(fd,MAX+1);b=os.fstat(fd)
        require(len(raw)==a.st_size and hashlib.sha256(raw).hexdigest()==sha and (a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_size,b.st_mtime_ns,b.st_ctime_ns),'Changed or mismatched Root file')
        return raw
    finally: os.close(fd)

def write(path,doc):
    raw=(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=MAX,'Bounded receipt required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try: os.write(fd,raw);os.fsync(fd)
    finally: os.close(fd)

def workspaces(source):
    require(source in PEOPLE,'Exact source required')
    owners=['cpsnativegroupa','cpsnativegroupb'] if source=='cps' else ['citnativegroupa']
    return [{'id':'native-group-'+x[-1],'group_id':'native-pilot-group-'+x[-1],'hub_user':x,'hub_server':'rtc','namespace':'jupyterhub' if source=='cps' else 'cit-jhub','pod':'jupyter-'+x+'--rtc'} for x in owners]

def expected_grants(source): return {'native-pilot-'+source+'-'+u:p for u,p in PEOPLE[source].items() if source=='cit' or u[-1] in ('c','d')}

def replacement(grant,source):
    allowed={'id','person','source','profiles','projects','allowance','starts','expires','reason'}
    require(type(grant) is dict and {'id','person','source','profiles','projects','allowance','expires'}<=set(grant)<=allowed,'Existing normal grant document required')
    require(grant['source']==source and expected_grants(source).get(grant['id'])==grant['person'],'Exact reviewed source fixture grant required')
    NEW=NEW_BY_SOURCE[source]
    profiles=grant['profiles'];require(type(profiles) is list and all(type(x) is str and x for x in profiles) and len(set(profiles))==len(profiles) and profiles.count(OLD)==1 and NEW not in profiles,'Replace exactly one old pilot profile; no other profile changes')
    require(type(grant['projects']) is list and all(type(x) is str for x in grant['projects']) and type(grant['allowance']) is int and grant['allowance']==1,'Original fixture allowance/projects required')
    for k in ('starts','expires'):
        if k in grant: require(type(grant[k]) is str and datetime.fromisoformat(grant[k]).tzinfo is not None,'Preserved timezone-bearing grant times required')
    now=datetime.now(timezone.utc);require(datetime.fromisoformat(grant['expires'])>now and (not grant.get('starts') or datetime.fromisoformat(grant['starts'])<=now),'Existing fixture grant must still be effective; no expiry extensions')
    after=copy.deepcopy(grant);after['profiles']=[NEW if x==OLD else x for x in profiles]
    return after

def settings_guard(settings,source):
    from e2x_course_hub.cps.providers import LocalCourseProvider
    from e2x_course_hub.cps.compute import ComputePolicyClient
    from e2x_course_hub.cps.workspaces import WorkspaceService,HubWorkspaceAdapter
    provider=settings.get('course_provider');compute=settings.get('compute_policy');service=settings.get('workspace_service')
    require(settings.get('console_owner')==source and type(provider) is LocalCourseProvider and provider.console==source and type(compute) is ComputePolicyClient and compute.console==source and type(service) is WorkspaceService and type(service.hub) is HubWorkspaceAdapter,'Actual configured source-owned released clients required')
    hub=settings['api'].course_api.hub_api
    require(service.provider is provider and service.compute is compute and service.hub.hub is hub,'Actual configured shared client identities required')
    require(settings['service_prefix']=='/services/'+source+'-admin','Exact owning source service prefix required')
    h=urlsplit(hub.api_url);g=urlsplit(compute.base_url)
    require(h.hostname in {'hub.'+('jupyterhub' if source=='cps' else 'cit-jhub')+'.svc','hub.'+('jupyterhub' if source=='cps' else 'cit-jhub')+'.svc.cluster.local'} and g.scheme=='https' and g.hostname in {'compute-gateway.cps-compute.svc','compute-gateway.cps-compute.svc.cluster.local'},'Exact owning Hub/shared policy endpoints required')
    return provider,compute,service

async def stopped_snapshot(settings,source):
    provider,compute,service=settings_guard(settings,source)
    course=next((c for c in await provider.courses() if c['id']==COURSE),None)
    require(course and course.get('source')=='local' and course.get('external_id') is None and course.get('resource_ceiling')==CEILING and not course.get('reconciliation_pending'),'Exact local course/ceiling and clear barrier required')
    expected=workspaces(source)
    require(sorted(course.get('workspace_bindings',[]),key=lambda x:x['hub_user'])==sorted([{k:w[k] for k in ('group_id','hub_user','hub_server','namespace','pod')} for w in expected],key=lambda x:x['hub_user']),'Exact reviewed source course bindings required')
    records={k:sorted([r for r in await provider.list(k) if r.get('course_id')==COURSE],key=lambda r:r['id']) for k in ('terms','groups','memberships','workspaces')}
    require(len(records['terms'])==1 and records['terms'][0]['id']==TERM,'Exact existing course term required')
    require({w['id'] for w in records['workspaces']}=={w['id'] for w in expected},'All existing fixture workspaces must be included')
    require({g['id'] for g in records['groups']}=={w['group_id'] for w in expected} and len(records['groups'])==len(expected),'Exact fixture groups required')
    require(len(records['memberships'])==len(PEOPLE[source]),'All fixture memberships must be included exactly once')
    for w in records['workspaces']:
        e=next(x for x in expected if x['id']==w['id'])
        require(all(w.get(k)==v for k,v in e.items()) and w.get('course_id')==COURSE and w.get('term_id')==TERM and w.get('source')=='local' and w.get('external_id') is None and w.get('state')=='stopped' and (w.get('profile')==OLD or (source=='cps' and w['id']=='native-group-a' and w.get('profile')=='interactive-native-pilot-5')) and w.get('course_ceiling')==CEILING and not any(w.get(k) for k in ('archive_pending','reconciliation_pending','membership_removal_pending')),'Exact stopped existing fixture workspace with clear barriers required')
        await service.hub.assert_stopped(w)
        selected=[r for r in records['memberships'] if r.get('group_id')==w['group_id']]
        names={u for u in PEOPLE[source] if u[-1] in (('a','b') if w['id'].endswith('a') else ('c','d'))}
        require({r.get('person_id') for r in selected}==names and len(selected)==len(names) and all(r.get('canonical_person_id')==PEOPLE[source][r['person_id']] and r.get('term_id')==TERM and r.get('role')=='student' and r.get('source')=='local' and not any(r.get(k) for k in ('membership_removal_pending','reconciliation_pending')) for r in selected),'Exact restored source canonical student memberships required')
        group=next(g for g in records['groups'] if g['id']==w['group_id'])
        require(group.get('term_id')==TERM and group.get('source')=='local' and set(group.get('members',[]))==names,'Restored source group binding differs')
        require(sorted(await service.members(w))==sorted(PEOPLE[source][u] for u in names),'Effective source-owned canonical membership differs')
    return {'course':course,**records}

async def capture(settings,source):
    first=await stopped_snapshot(settings,source);compute=settings['compute_policy'];grants={}
    for person in sorted(set(PEOPLE[source].values())):
        rows=await compute.grants(person)
        require(type(rows) is list and all(type(r) is dict and r.get('source')==source and r.get('person')==person for r in rows) and len({r.get('id') for r in rows})==len(rows),'Complete source-authenticated grant GET required')
        grants[person]=copy.deepcopy(sorted(rows,key=lambda r:r['id']))
    for gid,person in expected_grants(source).items():
        rows=[r for r in grants[person] if r.get('id')==gid];require(len(rows)==1,'Existing reviewed fixture grant must be discovered, never seeded');replacement(rows[0],source)
    require(await stopped_snapshot(settings,source)==first,'Source records changed during capture')
    return {'version':1,'source':source,'actor':ACTOR,'captured_at':datetime.now(timezone.utc).isoformat(),'records':first,'grants':grants}

def review_guard(review,before):
    closed(review,{'version','source','actor','before_sha256','writer_exclusion'})
    require(type(review['version']) is int and review['version']==1 and review['source']==before['source'] and review['actor']==ACTOR and review['before_sha256']==digest(before),'Exact complete captured before review required')
    e=review['writer_exclusion'];closed(e,{'passed','observed_at','source_writers_stopped','fixture_starts_excluded','source_token_custody','operator'})
    require(e['passed'] is True and e['source_writers_stopped'] is True and e['fixture_starts_excluded'] is True and e['source_token_custody']=='Root-exclusive' and e['operator']==ACTOR,'Genuine reviewed external writer/start exclusion required; helper does not establish it')
    t=datetime.fromisoformat(e['observed_at']);require(t.tzinfo is not None and 0<=(datetime.now(timezone.utc)-t).total_seconds()<=600,'Fresh Root writer-exclusion review required')

async def apply(settings,before,review,output):
    source=before['source'];review_guard(review,before)
    fresh=await capture(settings,source);require({k:v for k,v in fresh.items() if k!='captured_at'}=={k:v for k,v in before.items() if k!='captured_at'},'Fresh complete source/grant before changed; no PUT allowed')
    provider,compute,service=settings_guard(settings,source);expected=copy.deepcopy(before['grants']);receipt={'state':'incomplete','source':source,'actor':ACTOR,'before_sha256':digest(before),'changes':[],'automatic_start':False,'qualification':False,'profile':NEW_BY_SOURCE[source]}
    try:
        for gid,person in sorted(expected_grants(source).items()):
            review_guard(review,before)
            require(await stopped_snapshot(settings,source)==before['records'],'Source writer/start changed before PUT')
            current=sorted(await compute.grants(person),key=lambda r:r['id']);require(current==expected[person],'Full source person grant list changed before PUT')
            original=next(r for r in current if r['id']==gid);after=replacement(original,source)
            write(output/('before-'+gid+'.json'),original)
            receipt['attempting']=gid
            result=await compute.put_grant(after,actor=ACTOR)
            require(result==after,'PUT response changed identity/provenance/resources/times')
            expected[person]=[after if r['id']==gid else r for r in expected[person]]
            readback=sorted(await compute.grants(person),key=lambda r:r['id']);require(readback==expected[person],'Fresh authenticated grant readback differs')
            with provider.db: provider._audit(ACTOR,'compute-grants',gid,canonical(original),canonical(result))
            receipt['changes'].append({'id':gid,'person':person,'before':original,'after':result})
            receipt.pop('attempting',None)
        require(await stopped_snapshot(settings,source)==before['records'],'Source/start changed after PUT')
        for person,rows in expected.items(): require(sorted(await compute.grants(person),key=lambda r:r['id'])==rows,'Final full authenticated grant list differs')
        receipt['state']='canonical-fixture-grants-updated-and-read-back'
        return receipt
    except BaseException as error:
        receipt['error_type']=type(error).__name__;raise
    finally: write(output/'receipt.json',receipt)

def local_only_configuration(value):
    minimal={'local':{'enabled':True},'moodle':{'enabled':False}}
    planned={'local':{'enabled':True},'moodle':{'enabled':False,'baseUrl':None,'authSecretRef':None,'syncInterval':'10m','readOnly':True}}
    try: return type(value) is dict and canonical(value) in {canonical(minimal),canonical(planned)}
    except (TypeError,ValueError): return False


def load_app(args):
    from e2x_course_hub.course_service.app import CourseServiceApp
    protected(args.config,args.config_sha256)
    for path in (args.database,args.server_config):require(Path(path).is_file() and Path(path).stat().st_size>0,'Existing actual app data/config required')
    app=CourseServiceApp();app.load_config_file(str(args.config))
    require(app.console_owner==args.source and os.path.realpath(app.database_path)==os.path.realpath(args.database) and os.path.realpath(app.server_config_file)==os.path.realpath(args.server_config) and local_only_configuration(app.course_providers),'Exact actual source app paths and disabled Moodle required')
    protected(args.config,args.config_sha256);app.init_tornado_settings();settings_guard(app.tornado_settings,args.source)
    return app

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--operation',choices=['capture','apply'],default='capture')
    for n in ('source','source-sha256','config-sha256','before-sha256','review-sha256'):p.add_argument('--'+n)
    for n in ('config','database','server-config','before','review','output'):p.add_argument('--'+n,type=Path)
    a=p.parse_args(argv);own=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not a.execute: print(json.dumps({'state':'inert','source_sha256':own,'api_calls':False,'writes':False,'qualification':False}));return 0
    require(os.geteuid()==10001,'Trusted operator UID10001 execute required')
    require(a.source in PEOPLE and a.source_sha256==own and all(x is not None for x in (a.config,a.database,a.server_config,a.output)),'Explicit source/config/output pins required')
    parent=a.output.parent.lstat();require(stat.S_ISDIR(parent.st_mode) and parent.st_uid==10001 and stat.S_IMODE(parent.st_mode)==0o700,'Private output parent required');a.output.mkdir(mode=0o700);a.output.chmod(0o700)
    if a.operation=='apply':
        require(a.before is not None and a.review is not None,'Pinned complete before/review files required')
        before=decode(protected(a.before,a.before_sha256));review=decode(protected(a.review,a.review_sha256));review_guard(review,before);require(before['source']==a.source,'Own source before required')
    app=load_app(a)
    try:
        if a.operation=='capture':write(a.output/'before.json',asyncio.run(asyncio.wait_for(capture(app.tornado_settings,a.source),timeout=180)));print(json.dumps({'state':'captured-review-required','source':a.source,'qualification':False}))
        else: result=asyncio.run(asyncio.wait_for(apply(app.tornado_settings,before,review,a.output),timeout=300));print(json.dumps({'state':result['state'],'source':a.source,'qualification':False}))
    finally:app.tornado_settings['course_provider'].db.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
