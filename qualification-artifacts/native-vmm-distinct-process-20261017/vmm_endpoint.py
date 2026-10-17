#!/usr/bin/env python3
"""Qualification-only bounded VMM export/import endpoints; inert unless explicit."""
import argparse,array,ctypes as C,hashlib,json,os,select,socket,stat,subprocess,sys,threading,time,uuid
from pathlib import Path
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
GENERATION='b10498fc-9153-4394-875a-ea7cfb498625'
BOOT='209f8bc9-a478-48e4-925a-6e07ffa56f7a'
LIBCUDA_SHA='85a8cc8cf00419ceb295ec62c481d05b4cdbdab10f25c5375d6d24bdbe00b4d9'
CAP=5368709120
MIB,STEP_MIB=1048576,256
BYTES=64*MIB
TRIAL=None
ROLE=None

def require(ok,message):
    if not ok:raise ValueError(message)
PTX = b'''.version 7.0
.target sm_70
.address_size 64
.visible .entry vector(.param .u64 output, .param .u32 bias) {
 .reg .b32 %r0, %r1, %r2; .reg .b64 %rd0, %rd1, %rd2;
 mov.u32 %r0, %tid.x; ld.param.u32 %r1, [bias]; add.u32 %r2, %r0, %r1;
 ld.param.u64 %rd0, [output]; mul.wide.u32 %rd1, %r0, 4;
 add.u64 %rd2, %rd0, %rd1; st.global.u32 [%rd2], %r2; ret;
}\n'''

def identity(pid):
    path = Path('/proc') / str(pid)
    before = path.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19]
    status = dict(line.split(':', 1) for line in path.joinpath('status').read_text().splitlines() if ':' in line)
    uid, gid = [int(x) for x in status['Uid'].split()], [int(x) for x in status['Gid'].split()]
    require(uid == [1000] * 4 and gid == [100] * 4, 'Exact non-root process UID/GID required')
    value = {'pid': pid, 'start_ticks': int(before), 'uid': 1000, 'gid': 100,
        'namespace_pids': [int(x) for x in status.get('NSpid', str(pid)).split()],
        'cgroup': path.joinpath('cgroup').read_text().strip()}
    require(before == path.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19], 'Process identity changed')
    return value

def binary_digest(path, *, executable=True):
    info = Path(path).stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o6022
        and (not executable or os.access(path, os.X_OK)), 'Root-owned readonly injected object required')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class DlInfo(C.Structure):
    _fields_ = [('filename', C.c_char_p), ('base', C.c_void_p), ('symbol', C.c_char_p), ('address', C.c_void_p)]

class Cuda:
    def __init__(self):
        self.lib = C.CDLL('libcuda.so.1'); self.held = []; self.context = C.c_void_p(); self.module = C.c_void_p()
        signatures = {'cuInit': [C.c_uint], 'cuDriverGetVersion': [C.POINTER(C.c_int)],
            'cuDeviceGetCount': [C.POINTER(C.c_int)], 'cuDeviceGetUuid_v2': [C.c_void_p, C.c_int],
            'cuCtxCreate_v2': [C.POINTER(C.c_void_p), C.c_uint, C.c_int], 'cuCtxDestroy_v2': [C.c_void_p],
            'cuMemAlloc_v2': [C.POINTER(C.c_uint64), C.c_size_t], 'cuMemFree_v2': [C.c_uint64],
            'cuMemsetD8_v2': [C.c_uint64, C.c_ubyte, C.c_size_t], 'cuMemcpyDtoH_v2': [C.c_void_p, C.c_uint64, C.c_size_t],
            'cuModuleLoadDataEx': [C.POINTER(C.c_void_p), C.c_void_p, C.c_uint, C.c_void_p, C.c_void_p],
            'cuModuleGetFunction': [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p], 'cuModuleUnload': [C.c_void_p],
            'cuLaunchKernel': [C.c_void_p, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_uint,
                               C.c_uint, C.c_void_p, C.c_void_p, C.c_void_p], 'cuCtxSynchronize': []}
        for name, types in signatures.items():
            getattr(self.lib, name).argtypes = types; getattr(self.lib, name).restype = C.c_int
        dl = C.CDLL(None); dl.dladdr.argtypes = [C.c_void_p, C.POINTER(DlInfo)]; dl.dladdr.restype = C.c_int
        info = DlInfo()
        require(dl.dladdr(C.cast(self.lib.cuMemAlloc_v2, C.c_void_p), C.byref(info)) != 0 and info.filename,
            'Actual raw CUDA symbol object required')
        self.driver_object = str(Path(info.filename.decode()).resolve())
        require(Path(self.driver_object).name.startswith('libcuda.so'), 'Raw CUDA driver symbol must not resolve to an interposer')
        self.driver_object_sha256 = binary_digest(self.driver_object, executable=False)
        self.check(self.lib.cuInit(0)); count = C.c_int(); self.check(self.lib.cuDeviceGetCount(C.byref(count)))
        require(count.value == 1, 'Exactly one visible CUDA device required')
        raw = (C.c_ubyte * 16)(); self.check(self.lib.cuDeviceGetUuid_v2(raw, 0))
        require('GPU-' + str(uuid.UUID(bytes=bytes(raw))) == GPU, 'Wrong physical GPU')
        version = C.c_int(); self.check(self.lib.cuDriverGetVersion(C.byref(version))); require(version.value >= 13040, 'R615 CUDA driver API required')
        self.driver_version = version.value
        self.check(self.lib.cuCtxCreate_v2(C.byref(self.context), 0, 0))
        self.work = C.c_uint64(); self.check(self.lib.cuMemAlloc_v2(C.byref(self.work), 1024))
        self.ptx = C.create_string_buffer(PTX)
        self.check(self.lib.cuModuleLoadDataEx(C.byref(self.module), self.ptx, 0, None, None))
        self.function = C.c_void_p(); self.check(self.lib.cuModuleGetFunction(C.byref(self.function), self.module, b'vector'))
        self.tick()

    @staticmethod
    def check(code): require(code == 0, 'CUDA operation failed: ' + str(code))

    def allocate(self, mib, touch=True):
        require(type(mib) is int and mib in (64, STEP_MIB) and len(self.held) <= 20, 'Fixed bounded allocation required')
        pointer = C.c_uint64(); result = self.lib.cuMemAlloc_v2(C.byref(pointer), mib * MIB)
        if result == 0:
            self.held.append(pointer)
            if touch: self.check(self.lib.cuMemsetD8_v2(pointer, 19, mib * MIB)); self.check(self.lib.cuCtxSynchronize())
        return {'cuda_result': result, 'mib': mib, 'held_allocations': len(self.held)}

    def free(self):
        while self.held:
            self.check(self.lib.cuMemFree_v2(self.held[-1])); self.held.pop()
        return {'cuda_result': 0}

    def tick(self):
        bias = C.c_uint32(37); params = (C.c_void_p * 2)(C.cast(C.byref(self.work), C.c_void_p), C.cast(C.byref(bias), C.c_void_p))
        self.check(self.lib.cuLaunchKernel(self.function, 1, 1, 1, 256, 1, 1, 0, None, params, None))
        self.check(self.lib.cuCtxSynchronize()); result = (C.c_uint32 * 256)()
        self.check(self.lib.cuMemcpyDtoH_v2(result, self.work, 1024)); require(list(result) == [i + 37 for i in range(256)], 'Vector kernel mismatch')
        return {'cuda_result': 0, 'vector_elements': 256, 'vector_verified': True}

    def close(self):
        self.free(); self.check(self.lib.cuModuleUnload(self.module)); self.check(self.lib.cuMemFree_v2(self.work)); self.check(self.lib.cuCtxDestroy_v2(self.context))

class Location(C.Structure):
    _fields_=[('type',C.c_int),('id',C.c_int)]
class Flags(C.Structure):
    _fields_=[('compressionType',C.c_ubyte),('gpuDirectRDMACapable',C.c_ubyte),('usage',C.c_ushort),('reserved',C.c_ubyte*4)]
class AllocationProp(C.Structure):
    _fields_=[('type',C.c_int),('requestedHandleTypes',C.c_int),('location',Location),('win32',C.c_void_p),('allocFlags',Flags)]
class AccessDesc(C.Structure):
    _fields_=[('location',Location),('flags',C.c_int)]

class VmmCuda(Cuda):
    def __init__(self):
        require(C.sizeof(AllocationProp)==32 and C.sizeof(AccessDesc)==12,'Reviewed x86_64 CUDA VMM ABI required')
        self.address=C.c_uint64();self.handle=C.c_uint64();self.fd=-1;self.reserved=False;self.mapped=False
        super().__init__()
        require(self.driver_object_sha256==LIBCUDA_SHA and self.driver_version==13040,'Exact reviewed injected CUDA object required')
        signatures={
          'cuMemGetInfo_v2':[C.POINTER(C.c_size_t),C.POINTER(C.c_size_t)],
          'cuMemGetAllocationGranularity':[C.POINTER(C.c_size_t),C.POINTER(AllocationProp),C.c_int],
          'cuMemCreate':[C.POINTER(C.c_uint64),C.c_size_t,C.POINTER(AllocationProp),C.c_uint64],
          'cuMemAddressReserve':[C.POINTER(C.c_uint64),C.c_size_t,C.c_size_t,C.c_uint64,C.c_uint64],
          'cuMemMap':[C.c_uint64,C.c_size_t,C.c_size_t,C.c_uint64,C.c_uint64],
          'cuMemSetAccess':[C.c_uint64,C.c_size_t,C.POINTER(AccessDesc),C.c_size_t],
          'cuMemExportToShareableHandle':[C.c_void_p,C.c_uint64,C.c_int,C.c_uint64],
          'cuMemImportFromShareableHandle':[C.POINTER(C.c_uint64),C.c_void_p,C.c_int],
          'cuMemUnmap':[C.c_uint64,C.c_size_t], 'cuMemRelease':[C.c_uint64],
          'cuMemAddressFree':[C.c_uint64,C.c_size_t]}
        for name,types in signatures.items():getattr(self.lib,name).argtypes=types;getattr(self.lib,name).restype=C.c_int
        free,total=C.c_size_t(),C.c_size_t();self.check(self.lib.cuMemGetInfo_v2(C.byref(free),C.byref(total)))
        require(total.value==CAP and 0<=free.value<CAP,'Actual finite5GiB CUDA allowance required')

    def map(self):
        self.check(self.lib.cuMemAddressReserve(C.byref(self.address),BYTES,0,0,0));self.reserved=True
        self.check(self.lib.cuMemMap(self.address,BYTES,0,self.handle,0));self.mapped=True
        access=AccessDesc(Location(1,0),3);self.check(self.lib.cuMemSetAccess(self.address,BYTES,C.byref(access),1))

    def create(self):
        prop=AllocationProp();prop.type=1;prop.requestedHandleTypes=1;prop.location=Location(1,0)
        granularity=C.c_size_t();self.check(self.lib.cuMemGetAllocationGranularity(C.byref(granularity),C.byref(prop),0))
        require(granularity.value>0 and BYTES%granularity.value==0,'Fixed64MiB must fit actual granularity')
        self.check(self.lib.cuMemCreate(C.byref(self.handle),BYTES,C.byref(prop),0));self.map()
        self.check(self.lib.cuMemsetD8_v2(self.address,19,BYTES));self.check(self.lib.cuCtxSynchronize())
        fd=C.c_int(-1);self.check(self.lib.cuMemExportToShareableHandle(C.byref(fd),self.handle,1,0))
        require(fd.value>=0,'Actual exported POSIX descriptor required');self.fd=fd.value

    def import_fd(self,fd):
        require(type(fd)is int and fd>=0,'One actual received VMM descriptor required');self.fd=fd
        self.check(self.lib.cuMemImportFromShareableHandle(C.byref(self.handle),C.c_void_p(fd),1));self.map()
        value=C.c_ubyte();self.check(self.lib.cuMemcpyDtoH_v2(C.byref(value),self.address,1));require(value.value==19,'Valid creator backing positive control required')

    def verify(self):
        require(self.mapped and self.handle.value and self.fd>=0,'Importer must retain its actual mapping/handle/FD')
        bias=C.c_uint32(41);params=(C.c_void_p*2)(C.cast(C.byref(self.address),C.c_void_p),C.cast(C.byref(bias),C.c_void_p))
        self.check(self.lib.cuLaunchKernel(self.function,1,1,1,256,1,1,0,None,params,None));self.check(self.lib.cuCtxSynchronize())
        result=(C.c_uint32*256)();self.check(self.lib.cuMemcpyDtoH_v2(result,self.address,1024))
        require(list(result)==[i+41 for i in range(256)],'Actual retained VMM vector kernel mismatch')
        return {'vector_elements':256,'vector_verified':True}

    def close(self):
        if self.mapped:self.check(self.lib.cuMemUnmap(self.address,BYTES));self.mapped=False
        if self.handle.value:self.check(self.lib.cuMemRelease(self.handle));self.handle=C.c_uint64()
        if self.reserved:self.check(self.lib.cuMemAddressFree(self.address,BYTES));self.reserved=False;self.address=C.c_uint64()
        if self.fd>=0:os.close(self.fd);self.fd=-1
        super().close();self.context=C.c_void_p();self.module=C.c_void_p();self.work=C.c_uint64()

def parse(raw):
    def unique(pairs):
        result={}
        for k,v in pairs:require(k not in result,'Duplicate frame field');result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'Finite frame required'))
    require(isinstance(value,dict),'Typed frame required');return value

def send_frame(sock,value,fd=None):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    require(0<len(raw)<=4096,'Bounded frame required')
    ancillary=[] if fd is None else [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))]
    require(sock.sendmsg([raw],ancillary)==len(raw),'Whole SEQPACKET frame required')

def receive_frame(sock,*,want_fd=False):
    raw,ancillary,flags,_=sock.recvmsg(4097,socket.CMSG_SPACE(8*array.array('i').itemsize),socket.MSG_CMSG_CLOEXEC)
    descriptors=[];unknown=False
    try:
        # Collect every received descriptor before validating other ancillary
        # types, so malformed mixed controls cannot leak earlier/later rights.
        for level,kind,data in ancillary:
            if level!=socket.SOL_SOCKET or kind!=socket.SCM_RIGHTS:unknown=True;continue
            values=array.array('i');require(len(data)%values.itemsize==0,'Whole descriptors required');values.frombytes(data);descriptors.extend(values)
        require(not unknown and raw and len(raw)<=4096 and not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC)
          and len(descriptors)==int(want_fd),'Exact complete frame and descriptor count required')
        value=parse(raw);fd=descriptors.pop() if want_fd else None;return value,fd
    finally:
        for fd in descriptors:os.close(fd)

def valid_fd_identity(value):
    require(isinstance(value,dict) and set(value)=={'device','inode','mode','rdev'}
        and all(type(n)is int and n>=0 for n in value.values()) and value['inode']>0,'Closed typed descriptor identity required')

def fd_identity(fd):
    s=os.fstat(fd)
    return {'device':s.st_dev,'inode':s.st_ino,'mode':s.st_mode,'rdev':s.st_rdev}

def require_root_peer(sock):
    pid,uid,gid=array.array('i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    # Host Root is outside the Pod PID namespace, where its visible PID is0.
    require(pid>=0 and uid==gid==0,'Actual Root peer credentials required')
    return {'namespace_pid':pid,'uid':uid,'gid':gid}

def emit(phase,**values):
    raw=json.dumps({'phase':phase,'trial_id':TRIAL,'role':ROLE,'namespace_pid':os.getpid(),
        'monotonic_ns':time.monotonic_ns(),'production_qualified':False,**values},sort_keys=True,allow_nan=False).encode()+b'\n'
    require(len(raw)<=4096 and os.write(1,raw)==len(raw),'Whole bounded endpoint event required')

def command(op,trial):
    require(select.select([0],[],[],30)[0],'Bounded Root command required')
    raw=os.read(0,4097)
    require(raw and len(raw)<=4096 and raw.endswith(b'\n') and raw.count(b'\n')==1,'Whole bounded Root command required')
    require(parse(raw)=={'op':op,'trial_id':trial},'Exact Root operation/trial required')

def require_import_result(value):
    require(value.get('api')=='cuMemImportFromShareableHandle' and value.get('expect')in ('allow','deny')
        and type(value.get('cuda_result'))is int and value['cuda_result']==(800 if value['expect']=='deny' else 0)
        and value.get('cuda_name')==('CUDA_ERROR_NOT_PERMITTED' if value['expect']=='deny' else 'CUDA_SUCCESS'),
        'Exact typed VMM import result required')

def _try_import(self,fd):
    require(type(fd)is int and fd>=0,'Actual received descriptor required');self.fd=fd
    start=time.monotonic_ns();code=self.lib.cuMemImportFromShareableHandle(C.byref(self.handle),C.c_void_p(fd),1);end=time.monotonic_ns()
    name=C.c_char_p();self.check(self.lib.cuGetErrorName(code,C.byref(name)))
    require(name.value,'Actual CUDA error name required');self.import_window=(start,end)
    return code,name.value.decode()
VmmCuda.try_import=_try_import

def _readback19(self):
    value=C.c_ubyte();self.check(self.lib.cuMemcpyDtoH_v2(C.byref(value),self.address,1));require(value.value==19,'Exact valid exporter backing required')
VmmCuda.readback19=_readback19

def _restore19(self):
    self.check(self.lib.cuMemsetD8_v2(self.address,19,BYTES));self.check(self.lib.cuCtxSynchronize())
VmmCuda.restore19=_restore19

def import_attempt(cuda,fd,expect,*,mark=emit,wait=None):
    wait=wait or (lambda op:command(op,TRIAL))
    mark('importer-before-kernel',**cuda.tick());wait('open')
    code,name=cuda.try_import(fd);start,end=cuda.import_window
    result={'api':'cuMemImportFromShareableHandle','expect':expect,'cuda_result':code,'cuda_name':name,
        'call_started_monotonic_ns':start,'call_ended_monotonic_ns':end,'expected_kernel_reason':6,'expected_kernel_status':27}
    mark('import-result',**result)
    # Wait until Root has sealed the actual end marker. Any unexpected result
    # is logged but never mapped/touched in the cross-parent branch.
    wait('finish');require_import_result(result)
    if expect=='allow':cuda.map();cuda.readback19();cuda.verify();cuda.restore19()
    mark('importer-after-kernel',**cuda.tick())

def socket_path(trial,role):return Path('/tmp')/('cpv-'+uuid.UUID(trial).hex[:16]+'-'+role)/'s'
def source_path(trial,role):return Path('/tmp')/('cpv-'+uuid.UUID(trial).hex[:16]+'-'+role+'-src')/'vmm_endpoint.py'
def listen(args):
    path=socket_path(args.trial_id,args.role);path.parent.mkdir(mode=0o700);path.parent.chmod(0o700)
    server=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET);server.settimeout(15)
    try:server.bind(str(path));os.chmod(path,0o600);server.listen(1);return server,path
    except BaseException:server.close();raise

def exporter(args,cuda,server):
    cuda.create();original=fd_identity(cuda.fd);emit('exporter-ready',socket_relative=str(socket_path(TRIAL,ROLE)),fd_identity=original,
        backing_bytes=BYTES,source_path=str(source_path(TRIAL,ROLE)),source_sha256=args.source_sha256,raw_cuda_object_sha256=cuda.driver_object_sha256)
    tick=0;cycles=0;deadline=time.monotonic()+70
    while cycles<2:
        require(time.monotonic()<deadline,'Bounded positive/cross FD handoff required')
        readable=select.select([server,0],[],[],0.4)[0]
        if 0 in readable:raise ValueError('Exporter abandoned before both handoffs')
        tick+=1;emit('exporter-tick',tick=tick,**cuda.tick())
        if server not in readable:continue
        conn,_=server.accept()
        with conn:
            conn.settimeout(10);peer=require_root_peer(conn);request,_=receive_frame(conn)
            phase='positive' if cycles==0 else 'cross'
            require(request=={'op':'export','trial_id':TRIAL,'transfer':phase,'source_sha256':args.source_sha256},'Exact ordered Root FD request required')
            require(fd_identity(cuda.fd)==original,'Original exported descriptor identity changed')
            send_frame(conn,{'phase':'exported-fd','trial_id':TRIAL,'transfer':phase,'backing_bytes':BYTES,'fd_identity':original},cuda.fd)
            ack,_=receive_frame(conn);require(ack=={'op':'forwarded','trial_id':TRIAL,'transfer':phase},'Exact Root handoff acknowledgement required')
        cycles+=1
    # Remain a live context and vector peer through the denied import/recovery.
    recovered=False
    while True:
        require(time.monotonic()<deadline,'Bounded exporter lifetime required')
        tick+=1;emit('exporter-tick',tick=tick,**cuda.tick())
        if not select.select([0],[],[],0.4)[0]:continue
        raw=os.read(0,4097);value=parse(raw);require(value.get('trial_id')==TRIAL and set(value)=={'op','trial_id'},'Exact exporter control required')
        if value['op']=='recover':require(not recovered,'One recovery required');emit('exporter-recovery',**cuda.tick());recovered=True
        elif value['op']=='finish':require(recovered,'Exporter recovery must precede finish');break
        else:raise ValueError('Unsupported exporter operation')
    emit('exporter-finished',transfers=cycles)

def importer(args,cuda,server):
    emit('socket-ready',socket_relative=str(socket_path(TRIAL,ROLE)),source_path=str(source_path(TRIAL,ROLE)),
        source_sha256=args.source_sha256,raw_cuda_object_sha256=cuda.driver_object_sha256)
    conn,_=server.accept();received=None
    with conn:
        conn.settimeout(15);peer=require_root_peer(conn)
        value,received=receive_frame(conn,want_fd=True)
        try:
            transfer='positive' if args.expect=='allow' else 'cross'
            require(set(value)=={'phase','trial_id','transfer','backing_bytes','fd_identity'} and value['phase']=='exported-fd'
                and value['trial_id']==TRIAL and value['transfer']==transfer and type(value['backing_bytes'])is int and value['backing_bytes']==BYTES
                and value['fd_identity']==fd_identity(received),'Actual one exported64MiB FD required')
            valid_fd_identity(value['fd_identity'])
            send_frame(conn,{'phase':'fd-received','trial_id':TRIAL,'transfer':transfer,'fd_identity':value['fd_identity']})
            emit('importer-ready',expect=args.expect,fd_identity=value['fd_identity'],root_peer=peer)
            # Own the received FD even if the controlled call later fails.
            fd,received=received,None;cuda.fd=fd
            import_attempt(cuda,fd,args.expect)
        finally:
            if received is not None:os.close(received)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--role',choices=['exporter','positive','importer']);p.add_argument('--expect',choices=['allow','deny'])
    p.add_argument('--trial-id');p.add_argument('--gpu-uuid');p.add_argument('--expected-pod-uid');p.add_argument('--source-sha256')
    args=p.parse_args(argv)
    if not args.execute:print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'production_qualified':False}));return
    global TRIAL,ROLE;TRIAL=args.trial_id;ROLE=args.role
    require(str(uuid.UUID(TRIAL))==TRIAL and uuid.UUID(TRIAL).int and str(uuid.UUID(args.expected_pod_uid))==args.expected_pod_uid,
        'Exact current trial/Pod UUID required')
    require(args.gpu_uuid==GPU and ROLE in ('exporter','positive','importer') and args.expect=={'exporter':'allow','positive':'allow','importer':'deny'}[ROLE],
        'Exact source-selected role/physical GPU required')
    require(os.getuid()==os.geteuid()==1000 and os.getgid()==os.getegid()==100 and not os.environ.get('LD_PRELOAD') and not os.environ.get('LD_AUDIT'),
        'Actual ordinary UID1000/GID100 raw CUDA required')
    actual=Path(__file__);expected=source_path(TRIAL,ROLE);info=actual.lstat()
    require(actual==expected and stat.S_ISREG(info.st_mode) and info.st_uid==1000 and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600
        and hashlib.sha256(actual.read_bytes()).hexdigest()==args.source_sha256,'Exact fresh staged endpoint source required')
    timer=threading.Timer(110,lambda:os._exit(124));timer.daemon=True;timer.start()
    cuda=None;server=None;path=None;errors=[];complete=False
    try:
        cuda=VmmCuda();cuda.lib.cuGetErrorName.argtypes=[C.c_int,C.POINTER(C.c_char_p)];cuda.lib.cuGetErrorName.restype=C.c_int
        server,path=listen(args)
        if ROLE=='exporter':exporter(args,cuda,server)
        else:importer(args,cuda,server)
        complete=True
    finally:
        for action in [lambda:cuda.close() if cuda else None,lambda:server.close() if server else None,
            lambda:path.unlink() if path and path.exists() else None,lambda:path.parent.rmdir() if path else None,
            lambda:actual.unlink(),lambda:actual.parent.rmdir()]:
            try:action()
            except BaseException as error:errors.append(type(error).__name__)
        timer.cancel()
        if complete and not errors:emit('receipt',state='measurement-completed',explicit_native_cleanup_completed=True)
        require(not errors,'Endpoint cleanup incomplete')
if __name__=='__main__':main()
