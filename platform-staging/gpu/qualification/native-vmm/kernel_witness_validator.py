"""Pure CPU validation of Root-captured /dev/kmsg IPC witnesses; no device/API access."""
import base64,hashlib,json,re,uuid

NODE='k3s-wk-gpu2'
NODE_UID='3336cdd5-d245-436e-b57c-2f66c6dcaa41'
BOOT='209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GENERATION='b10498fc-9153-4394-875a-ea7cfb498625'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
FIELDS={'version','kind','trial_id','nonce','node','node_uid','boot_id','driver_generation',
 'collector_sha256','validator_sha256','attribution_sha256','api_result_sha256','overruns',
 'truncated','same_time_namespace','identity_verified','markers','records_b64'}
CLOCKS={'monotonic_ns','monotonic_raw_ns','boottime_ns','realtime_ns'}

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(value):return 'sha256:'+hashlib.sha256(canonical(value)).hexdigest()
def parse_json(raw):
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result,'Duplicate JSON field');result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'Finite JSON required'))
def canonical_uuid(value):
    require(isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0,'Canonical nonzero UUID required')
def marker_message(trial,nonce,phase,attribution):
    canonical_uuid(trial);canonical_uuid(nonce)
    require(phase in ('begin','end'),'Exact marker phase required')
    return (f'CPS_IPC_WITNESS trial={trial} nonce={nonce} phase={phase} '
            f'tgid={attribution["host_tgid"]} start={attribution["pid_start_ticks"]} gpu={attribution["gpu_id"]}')
def parse_record(raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=65536 and raw.endswith(b'\n'),'Complete bounded kmsg record required')
    first,*context=raw.decode('utf-8',errors='strict').splitlines()
    require(all(line.startswith(' ') for line in context),'Invalid kmsg record continuation')
    header,sep,message=first.partition(';');parts=header.split(',')
    require(sep and len(parts)>=4 and all(re.fullmatch('[0-9]+',p) for p in parts[:3]),'Typed kmsg header required')
    priority,sequence,timestamp=map(int,parts[:3])
    require(priority<=2047 and sequence<2**64 and timestamp<2**64,'Bounded kmsg values required')
    return {'priority':priority,'sequence':sequence,'timestamp_us':timestamp,'flags':parts[3],'message':message}
def _clock(value):
    require(isinstance(value,dict) and set(value)==CLOCKS and all(type(x)is int and x>0 for x in value.values()),'Complete paired Root clocks required')

def validate_capture(capture,attribution,api_result,*,collector_sha256,validator_sha256):
    c,a,e=capture,attribution,api_result
    require(isinstance(c,dict) and set(c)==FIELDS and type(c['version'])is int and c['version']==1
        and c['kind']=='root-kernel-import-sequence-witness','Closed Root witness required')
    canonical_uuid(c['trial_id']);canonical_uuid(c['nonce'])
    require(c['node']==NODE and c['node_uid']==NODE_UID and c['boot_id']==BOOT and c['driver_generation']==GENERATION,'Exact node/boot/epoch required')
    require(all(isinstance(s,str) and re.fullmatch('[a-f0-9]{64}',s) for s in (collector_sha256,validator_sha256))
        and c['collector_sha256']==collector_sha256 and c['validator_sha256']==validator_sha256,'Separately reviewed collector/validator pins required')
    require(c['attribution_sha256']==sha(a) and c['api_result_sha256']==sha(e),'Exact attribution and API bytes required')
    require(a.get('kind')=='root-read-only-importer-attribution' and a.get('trial_id')==c['trial_id']
        and a.get('boot_id')==BOOT and a.get('driver_generation')==GENERATION and a.get('gpu_uuid')==GPU
        and all(type(a.get(k))is int and a[k]>0 for k in ('host_pid','host_tgid','namespace_pid','pid_start_ticks','gpu_id'))
        and a['host_pid']==a['host_tgid'],'Exact actual importer lifetime required')
    require(type(c['overruns'])is int and c['overruns']==0 and c['truncated']is False
        and c['same_time_namespace']is True and c['identity_verified']is True,'Lost, truncated or unverified Root capture rejected')
    require(e.get('phase')=='import-result' and e.get('trial_id')==c['trial_id'] and e.get('namespace_pid')==a['namespace_pid']
        and e.get('api')in('cuIpcOpenMemHandle_v2','cuMemImportFromShareableHandle') and e.get('expect')=='deny' and type(e.get('cuda_result'))is int
        and e['cuda_result']==800 and e.get('cuda_name')=='CUDA_ERROR_NOT_PERMITTED'
        and type(e.get('expected_kernel_status'))is int and e['expected_kernel_status']==27
        and type(e.get('expected_kernel_reason'))is int and e['expected_kernel_reason']==6
        and e.get('production_qualified')is False,'Exact raw CUDA denial result required')
    markers=c['markers'];require(isinstance(markers,dict) and set(markers)=={'begin','end'},'Both Root markers required')
    for marker in markers.values():
        require(isinstance(marker,dict) and set(marker)=={'clock_before','clock_after'},'Exact paired marker clock fields required')
        _clock(marker['clock_before']);_clock(marker['clock_after'])
        require(all(marker['clock_before'][k]<=marker['clock_after'][k]for k in CLOCKS),'Root marker clocks reversed')
    start,end=e.get('call_started_monotonic_ns'),e.get('call_ended_monotonic_ns')
    require(type(start)is int and type(end)is int
        and markers['begin']['clock_after']['monotonic_ns']<=start<=end<=markers['end']['clock_before']['monotonic_ns']
        and 0<markers['end']['clock_after']['monotonic_ns']-markers['begin']['clock_before']['monotonic_ns']<=30_000_000_000,
        'Actual CUDA call must occur between bounded Root marker commands')
    encoded=c['records_b64'];require(isinstance(encoded,list) and 3<=len(encoded)<=4096,'Bounded complete kmsg records required')
    try:raw=[base64.b64decode(x,validate=True)for x in encoded]
    except (ValueError,TypeError):raise ValueError('Exact base64 kernel bytes required')from None
    require(sum(map(len,raw))<=262144,'Bounded Root kernel capture required')
    records=[parse_record(r)for r in raw]
    require(all(b['sequence']==a['sequence']+1 for a,b in zip(records,records[1:])),'Kernel sequence gap, duplicate or reorder rejected')
    actual=[]
    for phase in ('begin','end'):
        expected=marker_message(c['trial_id'],c['nonce'],phase,a)
        matching=[r for r in records if r['message']==expected]
        require(len(matching)==1 and matching[0]['priority']==14 and matching[0]['flags']=='-','Unique actual userspace Root marker required')
        actual.append(matching[0])
    begin,finish=actual;require(begin['sequence']<finish['sequence'],'Root markers reversed')
    pattern=re.compile(r'NVRM: CPS native import denied gpu=([0-9]+) reason=([0-9]+) clientKind=([0-9]+) status=0x([a-f0-9]+) tgid=([0-9]+)')
    matching=[]
    for record in records:
        if not begin['sequence']<record['sequence']<finish['sequence']:continue
        found=pattern.fullmatch(record['message'])
        if found and int(found[5])==a['host_tgid']:
            require(record['priority']//8==0 and record['flags']=='-' and tuple(map(int,(found[1],found[2])))==(a['gpu_id'],6)
                and (int(found[3])==4 if e['api']=='cuIpcOpenMemHandle_v2' else 0<=int(found[3])<=7)
                and int(found[4],16)==27,'Actual kernel origin/exact denial branch required')
            matching.append(dict(record,client_kind=int(found[3])))
    require(len(matching)==1,'Exactly one kernel-origin denial for actual importer required')
    return {'state':'bounded-kernel-import-witness-correlated','kernel_witness_correlated':True,'production_qualified':False,
        'trial_id':c['trial_id'],'host_tgid':a['host_tgid'],'pid_start_ticks':a['pid_start_ticks'],'gpu_id':a['gpu_id'],
        'begin_sequence':begin['sequence'],'kernel_sequence':matching[0]['sequence'],'end_sequence':finish['sequence'],
        'kernel_status':27,'kernel_reason':6,'client_kind':matching[0]['client_kind'],'clock_offset_rule_used':False,'capture_sha256':sha(c)}
