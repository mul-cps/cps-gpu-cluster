"""Inert-by-default, two fixed read-only ConfigMap metadata watches. Not authority."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,math,os
from pathlib import Path
import re,stat,threading,time
from uuid import UUID

NAMESPACE='cps-native-system'
ACK='cps-native-approval-ack-node'
LEDGER='cps-native-gpu-allocations'
CUSTODY='cps.compute/node-custody-generation'
PENDING='cps.compute/node-pending-generation'
MAX_BODY=8*1024*1024

class SampleError(ValueError):pass

def require(ok,code):
    if not ok:raise SampleError(code)

def sha(raw):return 'sha256:'+hashlib.sha256(raw.encode()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def uid(value):
    try:require(isinstance(value,str) and str(UUID(value))==value and UUID(value).int!=0,'invalid_uid')
    except (ValueError,TypeError,AttributeError):raise SampleError('invalid_uid') from None
    return value

def rv(value):
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}',value) is not None,'invalid_resource_version')
    return value

def digest(value):
    require(isinstance(value,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',value) is not None,'invalid_digest')
    return value

def parse(raw,limit=MAX_BODY):
    require(isinstance(raw,str) and len(raw.encode())<=limit,'invalid_json_size')
    def pairs(items):
        result={}
        for key,value in items:require(key not in result,'duplicate_json_key');result[key]=value
        return result
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(SampleError('nonfinite_json')))
    except (ValueError,TypeError,RecursionError):raise SampleError('invalid_json') from None

def reference(value,*,immutable=False,approval=False):
    require(isinstance(value,dict) and value.get('namespace')==NAMESPACE,'foreign_reference')
    name=value.get('name');require(isinstance(name,str) and re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?',name),'invalid_reference_name')
    result={'namespace':NAMESPACE,'name':name,'uid':uid(value.get('uid'))}
    if immutable:result.update(resourceVersion=rv(value.get('resourceVersion')),data_sha256=digest(value.get('data_sha256')),key='config.json');require(value.get('key')=='config.json','invalid_configuration_key')
    if approval:
        for key in ('data_sha256','revision','policy_hash'):result[key]=digest(value.get(key))
    return result

def timestamp(value):
    require(isinstance(value,str) and len(value)<=64,'invalid_timestamp')
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'));require(parsed.tzinfo is not None,'invalid_timestamp')
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError,TypeError):raise SampleError('invalid_timestamp') from None

def witness(raw,kind,ack,expected_uid):
    result={'annotation_sha256':sha(raw),'valid':False}
    try:
        value=parse(raw,128*1024)
        fields={'version','acknowledgment','ack_sha256','node_configuration_ref', 'ledger','enrollments'} if kind==CUSTODY else {'version','acknowledgment','ack_sha256','node_configuration_ref','pending'}
        require(isinstance(value,dict) and set(value)==fields and type(value['version']) is int and value['version']==1,'invalid_witness')
        target=reference(value['acknowledgment']);require(target['name']==ACK and target['uid']==expected_uid,'wrong_witness_target')
        result.update(ack_sha256=digest(value['ack_sha256']),node_configuration_ref=reference(value['node_configuration_ref'],immutable=True))
        result['matches_ack']=result['ack_sha256']==sha(canonical(ack))
        if kind==CUSTODY:
            ledger=value['ledger'];result['ledger']=reference(ledger)
            require(ledger['name']==LEDGER,'foreign_ledger')
            result['ledger'].update(resource_version=rv(ledger['resource_version']),data_sha256=digest(ledger['data_sha256']))
            rows=value['enrollments'];require(isinstance(rows,list) and len(rows)<=4096,'invalid_enrollment_metadata')
            require(all(isinstance(row,dict) and isinstance(row.get('name'),str)
                and re.fullmatch(r'cps-native-enrollment-[a-f0-9]{40}',row['name']) for row in rows),'invalid_enrollment_name')
            result['enrollments']=[dict(reference(row),pod_uid=uid(row['pod_uid']),data_sha256=digest(row['data_sha256'])) for row in rows]
        else:
            rows=value['pending'];require(isinstance(rows,list) and len(rows)<=4096,'invalid_pending_metadata')
            result['pending']=[{'pod_uid':uid(row['pod_uid']),'document_sha256':digest(row['document_sha256'])} for row in rows]
        result['valid']=True
        return result
    except (SampleError,KeyError,TypeError,AttributeError):return {'annotation_sha256':sha(raw),'valid':False}

def project(cm,name,expected_uid=None):
    require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap','invalid_configmap')
    meta=cm.get('metadata',{});require(meta.get('namespace')==NAMESPACE and meta.get('name')==name,'wrong_target')
    actual_uid=uid(meta.get('uid'));require(expected_uid is None or actual_uid==expected_uid,'uid_replaced')
    result={'uid':actual_uid,'resource_version':rv(meta.get('resourceVersion'))}
    key='ack.json' if name==ACK else 'state.json';data=cm.get('data')
    require(isinstance(data,dict) and set(data)=={key} and not cm.get('binaryData'),'invalid_data_keys')
    body=parse(data[key]);require(isinstance(body,dict),'invalid_body')
    if name==LEDGER:
        rows=body.get('allocations');require(isinstance(rows,dict) and len(rows)<=16384,'invalid_ledger')
        counts=Counter()
        for row in rows.values():
            state=row.get('state') if isinstance(row,dict) else None
            counts[state if state in ('reserved','enrolling','enrolled','releasing','released') else 'other']+=1
        result.update(state_sha256=sha(data[key]),allocation_count=len(rows),state_counts=dict(counts))
    else:
        result.update(ack_sha256=sha(data[key]),ack_data_sha256=sha(canonical(data)),empty=body=={})
        if body:
            # Only independently format-checked receipt metadata; never body text.
            try:result.update(ack_observed_at=timestamp(body.get('observed_at')),process_uid=uid(body.get('process',{}).get('uid')))
            except (SampleError,AttributeError):result['ack_metadata_valid']=False
            if 'document' in body:
                try:result['head_reference']=reference(body['document'],approval=True)
                except SampleError:result['head_reference_valid']=False
        annotations=meta.get('annotations',{})
        if isinstance(annotations,dict):
            for kind in (CUSTODY,PENDING):
                raw=annotations.get(kind)
                if isinstance(raw,str) and len(raw.encode())<=128*1024:result[kind]=witness(raw,kind,body,actual_uid)
    return result

def private_output(path):
    path=Path(path);require(path.is_absolute() and '..' not in path.parts,'absolute_private_output_required')
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        info=os.fstat(directory);require(info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700,'owned_0700_parent_required')
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
        os.fchmod(fd,0o600)
        return os.fdopen(fd,'w',encoding='utf-8')
    finally:os.close(directory)

def watch_one(core,factory,name,expected_uid,version,deadline,stop,emit,clock=time.monotonic):
    while not stop.is_set() and clock()<deadline:
        watcher=factory();remaining=deadline-clock()
        if remaining<=0:return
        timeout=max(1,min(30,math.ceil(remaining)))
        try:
            # timeout_seconds disables the SDK's implicit 410/relist retry.
            events=watcher.stream(core.list_namespaced_config_map,namespace=NAMESPACE,
                field_selector='metadata.name='+name,resource_version=version,allow_watch_bookmarks=True,
                timeout_seconds=timeout,_request_timeout=(3,timeout+2))
            for event in events:
                if stop.is_set() or clock()>=deadline:break
                kind=event.get('type');obj=event.get('raw_object',event.get('object'))
                if kind=='ERROR':
                    status=obj.get('code') if isinstance(obj,dict) else None
                    raise SampleError('history_lost' if status==410 else 'watch_error')
                if kind=='BOOKMARK':
                    version=rv(obj.get('metadata',{}).get('resourceVersion'));emit({'target':name,'event':'BOOKMARK','resource_version':version});continue
                require(kind in ('ADDED','MODIFIED','DELETED'),'unknown_watch_event')
                value=project(obj,name,expected_uid);version=value['resource_version'];emit({'target':name,'event':kind,**value})
                if kind=='DELETED':raise SampleError('target_deleted')
        except SampleError:raise
        except Exception as error:
            status=getattr(error,'status',None)
            if status==410:raise SampleError('history_lost') from None
            if status in (401,403,404):raise SampleError('watch_access_or_target_denied') from None
            emit({'target':name,'event':'RECONNECT','reason':'transport','http_status':status if type(status) is int and 100<=status<=599 else None})
        finally:watcher.stop()
        if not stop.is_set() and clock()<deadline:
            emit({'target':name,'event':'RECONNECT','reason':'resume_last_resource_version','resource_version':version})
            stop.wait(.1)

def initial_snapshot(core,name,remaining):
    # MostRecent exact-name LIST gives a fresh collection cursor even when the
    # unchanged object's last modification RV has fallen out of watch history.
    value=core.list_namespaced_config_map(namespace=NAMESPACE,field_selector='metadata.name='+name,
        limit=2,_request_timeout=(min(3,remaining),min(10,remaining)))
    if not isinstance(value,dict):value=core.api_client.sanitize_for_serialization(value)
    require(isinstance(value,dict) and value.get('apiVersion')=='v1'
        and value.get('kind')=='ConfigMapList' and isinstance(value.get('items'),list)
        and len(value['items'])==1,'initial_list_requires_one_target')
    metadata=value.get('metadata');require(isinstance(metadata,dict),'invalid_list_metadata')
    version=rv(metadata.get('resourceVersion'))
    require(metadata.get('continue') in (None,'') and (metadata.get('remainingItemCount') is None
        or type(metadata['remainingItemCount']) is int and metadata['remainingItemCount']==0),
        'incomplete_initial_list')
    item=value['items'][0]
    require(isinstance(item,dict) and all(key not in item or item[key]==expected
        for key,expected in (('apiVersion','v1'),('kind','ConfigMap'))),'conflicting_list_item_type')
    # A validated typed list may omit item GVK. Add only those known defaults
    # on a copy; standalone GET/watch object validation remains strict.
    return project({'apiVersion':'v1','kind':'ConfigMap',**item},name),version

def collect(core,factory,out,seconds):
    started=time.monotonic();deadline=started+seconds;stop=threading.Event();lock=threading.Lock();errors=[];threads=[];count=[0];completed=False
    def emit(value):
        record={'observed_at':datetime.now(timezone.utc).isoformat(),'monotonic_elapsed':round(time.monotonic()-started,6),**value}
        with lock:
            out.write(canonical(record)+'\n');out.flush();count[0]+=1
    def worker(name,expected_uid,version):
        try:watch_one(core,factory,name,expected_uid,version,deadline,stop,emit)
        except Exception as error:
            code=str(error) if type(error) is SampleError else 'watch_failed'
            with lock:errors.append(code)
            emit({'target':name,'event':'ERROR','reason':code});stop.set()
    try:
        emit({'event':'START','seconds':seconds,'streams':2,'read_only':True})
        pinned=[]
        for name in (ACK,LEDGER):
            remaining=deadline-time.monotonic();require(remaining>0,'initial_list_deadline')
            value,collection_version=initial_snapshot(core,name,remaining)
            emit({'target':name,'event':'INITIAL','collection_resource_version':collection_version,**value})
            pinned.append((name,value['uid'],collection_version))
        for args in pinned:
            thread=threading.Thread(target=worker,args=args,daemon=True,name='cm-metadata-'+args[0]);threads.append(thread);thread.start()
        stop.wait(max(0,deadline-time.monotonic()));completed=not errors
    finally:
        stop.set()
        # Each watch's final server timeout is capped by its remaining budget;
        # client read timeout adds at most two seconds. Never leave silent work.
        drain_deadline=time.monotonic()+35
        for thread in threads:thread.join(max(0,drain_deadline-time.monotonic()))
        drained=all(not thread.is_alive() for thread in threads)
        emit({'event':'END','threads_drained':drained,'complete':completed and drained and not errors})
    require(drained,'watch_threads_not_drained')
    require(not errors,errors[0] if errors else 'watch_failed')
    return count[0]

def clients():
    from kubernetes import client,config,watch
    config.load_kube_config()
    return client.CoreV1Api(),watch.Watch

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--seconds',type=int,default=10);parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if not args.execute:print(json.dumps({'inert':True,'api_calls':False,'files_written':False}));return 0
    try:
        require(10<=args.seconds<=420 and args.output is not None,'bounded_seconds_and_output_required')
        with private_output(args.output) as out:
            core,factory=clients()
            try:count=collect(core,factory,out,args.seconds)
            finally:core.api_client.close()
        print(json.dumps({'complete':True,'records':count,'read_only':True}));return 0
    except Exception as error:
        code=str(error) if type(error) is SampleError else 'sampler_failed'
        print(json.dumps({'complete':False,'reason':code}),file=__import__('sys').stderr);return 1
if __name__=='__main__':raise SystemExit(main())
