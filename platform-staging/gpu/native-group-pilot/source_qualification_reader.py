"""Pinned readonly reader for the exact Kubernetes-projected gateway config."""
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import quote

MAX_BYTES = 67108864


def require(value,message):
    if not value: raise ValueError(message)


def file_bytes(path,sha256):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=MAX_BYTES,'Bounded existing runtime file required')
        raw=os.read(fd,MAX_BYTES+1)
        require(len(raw)==info.st_size and hashlib.sha256(raw).hexdigest()==sha256,'Runtime source/config hash mismatch')
        return raw
    finally: os.close(fd)


def file_identity(info):
    return tuple(getattr(info,key) for key in ('st_dev','st_ino','st_mode','st_uid','st_gid',
        'st_size','st_nlink','st_mtime_ns','st_ctime_ns'))


def projected_config_bytes(path,sha256):
    require(path=='/config/runtime.json','Exact projected gateway config path required')
    directory_flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    config_fd=os.open('/config',directory_flags)
    timestamp_fd=None; file_fd=None
    try:
        config_info=os.fstat(config_fd)
        require(os.fstatvfs(config_fd).f_flag & os.ST_RDONLY,'Readonly Secret filesystem required')
        require(file_identity(os.stat('/config',follow_symlinks=False))==file_identity(config_info),
            'Actual config directory identity required')
        runtime_link=os.stat('runtime.json',dir_fd=config_fd,follow_symlinks=False)
        require(stat.S_ISLNK(runtime_link.st_mode) and
            os.readlink('runtime.json',dir_fd=config_fd)=='..data/runtime.json','Exact runtime projection link required')
        data_link=os.stat('..data',dir_fd=config_fd,follow_symlinks=False)
        require(stat.S_ISLNK(data_link.st_mode),'Exact atomic-writer data link required')
        timestamp=os.readlink('..data',dir_fd=config_fd)
        require(len(timestamp)<=64 and re.fullmatch(r'\.\.[0-9]{4}_[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{2}\.[0-9]{1,20}',timestamp),
            'Bounded atomic-writer timestamp directory required')
        timestamp_fd=os.open(timestamp,directory_flags,dir_fd=config_fd)
        timestamp_info=os.fstat(timestamp_fd)
        require(file_identity(os.stat(timestamp,dir_fd=config_fd,follow_symlinks=False))==file_identity(timestamp_info),
            'Actual timestamp directory identity required')
        file_fd=os.open('runtime.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=timestamp_fd)
        file_info=os.fstat(file_fd)
        require(stat.S_ISREG(file_info.st_mode) and 0<file_info.st_size<=MAX_BYTES,'Bounded existing runtime file required')
        chunks=[]; size=0
        while size<=MAX_BYTES:
            chunk=os.read(file_fd,min(1048576,MAX_BYTES+1-size))
            if not chunk: break
            chunks.append(chunk); size+=len(chunk)
        raw=b''.join(chunks)
        require(len(raw)==file_info.st_size and hashlib.sha256(raw).hexdigest()==sha256,'Runtime source/config hash mismatch')
        require(file_identity(os.fstat(file_fd))==file_identity(file_info) and
            file_identity(os.stat('runtime.json',dir_fd=timestamp_fd,follow_symlinks=False))==file_identity(file_info),
            'Projected runtime file changed')
        require(file_identity(os.fstat(timestamp_fd))==file_identity(timestamp_info) and
            file_identity(os.stat(timestamp,dir_fd=config_fd,follow_symlinks=False))==file_identity(timestamp_info),
            'Timestamp directory changed')
        require(file_identity(os.stat('runtime.json',dir_fd=config_fd,follow_symlinks=False))==file_identity(runtime_link) and
            os.readlink('runtime.json',dir_fd=config_fd)=='..data/runtime.json' and
            file_identity(os.stat('..data',dir_fd=config_fd,follow_symlinks=False))==file_identity(data_link) and
            os.readlink('..data',dir_fd=config_fd)==timestamp,'Runtime projection rotated')
        require(file_identity(os.fstat(config_fd))==file_identity(config_info) and
            file_identity(os.stat('/config',follow_symlinks=False))==file_identity(config_info) and
            os.fstatvfs(config_fd).f_flag & os.ST_RDONLY,'Config directory or readonly mount changed')
        return raw
    finally:
        if file_fd is not None: os.close(file_fd)
        if timestamp_fd is not None: os.close(timestamp_fd)
        os.close(config_fd)


def read_registration(request):
    require(type(request) is dict and set(request)=={'source','workspace','config_path','config_sha256',
        'internal_sha256','runtime_sha256','database_path','database_device','database_inode','database_uid'},'Closed readonly request required')
    require(request['source']+':'+request['workspace'] in {'cps:native-group-b','cit:native-group-a'},'Exact approved source workspace required')
    require(os.environ.get('CPS_COMPUTE_CONFIG')==request['config_path'],'Actual configured gateway path required')
    import cps_compute.internal as internal
    import cps_compute.runtime as runtime
    file_bytes(internal.__file__,request['internal_sha256']); file_bytes(runtime.__file__,request['runtime_sha256'])
    config=json.loads(projected_config_bytes(request['config_path'],request['config_sha256']))
    path=Path(config['state_directory'])/'control.sqlite'
    require(str(path)==request['database_path'] and path.is_absolute(),'Actual configured state directory required')
    require(all(type(request[k]) is int and request[k]>=0 for k in ('database_device','database_inode','database_uid'))
        and request['database_inode']>0,'Typed actual database identity required')
    info=os.lstat(path)
    require(stat.S_ISREG(info.st_mode) and info.st_size>0 and
        (info.st_dev,info.st_ino,info.st_uid)==(request['database_device'],request['database_inode'],request['database_uid']),
        'Existing configured control database identity required')
    # Preserve every released SQL statement and model method. Only connection
    # mode changes in this standalone single-threaded child: readonly URI means
    # normal CREATE IF NOT EXISTS succeeds for existing schema, but missing
    # schema, any mutation or a different database fails. No SQL is authored here.
    original_connect=internal.sqlite3.connect
    def readonly_connect(filename,*args,**kwargs):
        require(str(filename)==str(path) and not args and not kwargs.get('uri'),'Different database connection forbidden')
        return original_connect('file:'+quote(str(path),safe='/')+'?mode=ro',uri=True,**kwargs)
    internal.sqlite3.connect=readonly_connect
    try:
        store=internal.ControlStore(path)
        require(type(store) is internal.ControlStore and store.path==str(path),'Released configured ControlStore required')
        result=store.workspace(request['source'],request['workspace'])
    finally: internal.sqlite3.connect=original_connect
    after=os.lstat(path)
    require((after.st_dev,after.st_ino,after.st_uid)==(info.st_dev,info.st_ino,info.st_uid),'Database identity changed')
    require(type(result) is dict,'Existing source-owned registration required')
    return result


if __name__=='__main__':
    # No standalone default read. Parent streams the closed request over stdin
    # as a trusted literal sys.argv prefix; no bulky request in exec argv.
    if len(sys.argv)!=2: raise SystemExit('inert: explicit pinned Root request required')
    print(json.dumps(read_registration(json.loads(sys.argv[1])),sort_keys=True,separators=(',',':'),allow_nan=False))
