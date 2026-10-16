"""Root-contract scoped version of the frozen read-only Gateway reader."""
import hashlib

import node_successor

BASE_SHA256='bc16a76773fefb1d6c1b97385a08d815222064b2a888bb250313949b07466fe4'
ORIGINAL_GUARD="    require(request['source']+':'+request['workspace'] in {'cps:native-group-b','cit:native-group-a'},'Exact approved source workspace required')"


def scope_guard(contract,pin):
    scopes=tuple(sorted(contract['workspaces']))
    return (f'    # Independently reviewed Root pair contract raw SHA256: {pin}\n'
        f"    require(request['source']+':'+request['workspace'] in {scopes!r},'Exact approved source workspace required')")


def reader_source(original,*,contract_raw,contract_sha256):
    if not isinstance(original,bytes) or hashlib.sha256(original).hexdigest()!=BASE_SHA256:
        raise ValueError('Exact frozen projected-config readonly reader required')
    contract=node_successor.validate_contract(contract_raw,contract_sha256)
    source=original.decode('utf-8')
    if source.count(ORIGINAL_GUARD)!=1:raise ValueError('Unique original reader scope guard required')
    result=source.replace(ORIGINAL_GUARD,scope_guard(contract,contract_sha256),1)
    compile(result,'<root-pair-readonly-reader>','exec')
    return result


class GatewayReader:
    """Read the exact configured store in a UID/spec/image-bound Gateway child."""
    def __init__(self,metadata,*,core,original,contract_raw,contract_sha256,execute=None):
        import copy
        required={'namespace','pod','pod_uid','pod_spec_sha256','container','image_id','python_path','request'}
        if not isinstance(metadata,dict) or set(metadata)!=required or metadata['namespace']!='cps-compute':
            raise ValueError('Closed actual Gateway process metadata required')
        self.metadata=copy.deepcopy(metadata);self.core=core;self.execute=execute or sdk_exec
        self.source=reader_source(original,contract_raw=contract_raw,contract_sha256=contract_sha256)
        self.scopes=frozenset(node_successor.validate_contract(contract_raw,contract_sha256)['workspaces'])

    def _check(self):
        import json
        m=self.metadata
        value=self.core.read_namespaced_pod(m['pod'],m['namespace'],_request_timeout=(5,15))
        pod=value if isinstance(value,dict) else self.core.api_client.sanitize_for_serialization(value)
        meta=pod.get('metadata',{});statuses=pod.get('status',{}).get('containerStatuses',[])
        states=[s for s in statuses if s.get('name')==m['container']]
        spec_pin=hashlib.sha256(json.dumps(pod.get('spec'),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if not (pod.get('apiVersion')=='v1' and pod.get('kind')=='Pod' and meta.get('namespace')==m['namespace']
                and meta.get('name')==m['pod'] and meta.get('uid')==m['pod_uid'] and not meta.get('deletionTimestamp')
                and spec_pin==m['pod_spec_sha256'] and len(states)==1 and states[0].get('imageID')==m['image_id']
                and states[0].get('ready') is True and 'running' in states[0].get('state',{})):
            raise ValueError('Actual Gateway UID/spec/running image changed')

    def get(self,source,workspace):
        import json
        if source+':'+workspace not in self.scopes:raise ValueError('Foreign workspace outside reviewed Root reader contract')
        self._check();m=self.metadata
        request={**m['request'],'source':source,'workspace':workspace}
        prefix='import sys\nsys.argv=["-",'+repr(json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False))+']\n'
        payload=prefix+self.source
        output=self.execute(namespace=m['namespace'],pod=m['pod'],container=m['container'],python_path=m['python_path'],payload=payload)
        if not isinstance(output,str) or len(output.encode())>1048576:raise ValueError('Bounded actual Gateway output required')
        def unique(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError('Duplicate Gateway result key')
                result[key]=value
            return result
        try:value=json.loads(output,object_pairs_hook=unique)
        except (ValueError,TypeError):raise ValueError('Actual Gateway reader returned invalid JSON') from None
        self._check()
        if not isinstance(value,dict) or value.get('workspace')!=workspace or value.get('principal')!='workspace:'+source+':'+workspace:
            raise ValueError('Actual reader returned a foreign registration')
        return value


BOOTSTRAP="import sys;exec(compile(sys.stdin.buffer.read(int(sys.argv[1])),'<root-readonly-registration>','exec'))"

def sdk_exec(*,namespace,pod,container,python_path,payload,core=None,stream_factory=None,timeout=30):
    """Fixed short argv and length-framed stdin; output/error/deadline bounded."""
    import time
    if not isinstance(payload,str) or not 0<len(payload.encode())<=262144 or '\x00' in payload or not 0<timeout<=30:
        raise ValueError('Bounded UTF-8 readonly source and timeout required')
    if core is None:
        from kubernetes import client
        core=client.CoreV1Api()  # isolate websocket transport from metadata client
    if stream_factory is None:
        from kubernetes.stream import stream
        stream_factory=stream
    connection=stream_factory(core.connect_get_namespaced_pod_exec,pod,namespace,container=container,
        command=[python_path,'-B','-c',BOOTSTRAP,str(len(payload.encode()))],stdin=True,stdout=True,stderr=True,
        tty=False,_preload_content=False,_request_timeout=(5,15))
    deadline=time.monotonic()+timeout;output=[];errors=[];size=error_size=0
    try:
        connection.write_stdin(payload)
        while connection.is_open():
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Readonly Gateway exec timed out')
            connection.update(timeout=min(1,remaining))
            text=connection.read_stdout();error=connection.read_stderr()
            size+=len(text.encode());error_size+=len(error.encode())
            if size>1048576 or error_size>1048576:raise ValueError('Gateway exec output bound exceeded')
            output.append(text);errors.append(error)
        if connection.returncode!=0 or any(errors):raise ValueError('Readonly Gateway child did not complete cleanly')
        return ''.join(output)
    finally:connection.close()
