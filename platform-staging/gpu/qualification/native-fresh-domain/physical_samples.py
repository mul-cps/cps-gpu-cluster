#!/usr/bin/env python3
"""Default-inert, Root-only four read-only physical GPU memory samples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT='a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION='4ebffc96-e25e-4583-a3b8-0d853fd90efd'
AUTHORITY=Path('/var/lib/cps-native-gpu/domains/100876ac-14e6-4292-bf52-7d129f7f08f0/custody/authority')

def require(value,message):
    if not value:raise ValueError(message)

def checked_file(path,pin):
    path=Path(path)
    require(path.is_absolute() and re.fullmatch('[a-f0-9]{64}',pin or ''),'Absolute independently pinned file required')
    require(not path.is_symlink(),'Symlink binary/library denied')
    for parent in path.parents:
        info=parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'Protected root-owned binary/library ancestry required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and before.st_gid==0
                and not before.st_mode&0o022 and before.st_nlink==1 and before.st_size<=128*1024*1024,
                'Root-owned nonwritable bounded binary/library required')
        h=hashlib.sha256()
        while block:=os.read(fd,1024*1024):h.update(block)
        after=os.fstat(fd)
        require(all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
                and h.hexdigest()==pin,'Reviewed binary/library bytes changed')
    finally:os.close(fd)

def loader_link(library):
    require((library.parent/'libnvidia-ml.so.1').resolve(strict=True)==library,
            'Pinned NVML must be the actual loader SONAME target')

def epoch():
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Actual selected boot changed')
    info=AUTHORITY.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o700,'Protected authority directory required')
    fd=os.open(AUTHORITY/'driver-generation',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and info.st_nlink==1
                and stat.S_IMODE(info.st_mode)==0o600,'Protected epoch file required')
        require(os.read(fd,128).decode().strip()==GENERATION,'Actual selected driver generation changed')
    finally:os.close(fd)

def parse(raw):
    rows=raw.strip().splitlines()
    require(len(rows)==1,'Exactly one complete GPU sample required')
    row=[s.strip() for s in rows[0].split(',')]
    require(len(row)==3 and row[0]==GPU and all(re.fullmatch('[0-9]+',s) for s in row[1:]),'Exact typed physical GPU sample required')
    free,total=map(int,row[1:]);require(0<=free<=total<=1024*1024 and total>0,'Bounded physical GPU memory required')
    return {'gpu_uuid':GPU,'free_bytes':free*1048576,'total_bytes':total*1048576}

def sample(binary,binary_sha,library,library_sha):
    require(os.geteuid()==0,'Explicit Root execution required')
    checked_file(binary,binary_sha);checked_file(library,library_sha);loader_link(library)
    rows=[]
    for n in range(4):
        epoch()
        value=subprocess.run([str(binary),'--id='+GPU,'--query-gpu=uuid,memory.free,memory.total','--format=csv,noheader,nounits'],
            check=False,capture_output=True,text=True,timeout=5,
            env={'LD_LIBRARY_PATH':str(library.parent),'LC_ALL':'C','PATH':'/usr/sbin:/usr/bin:/sbin:/bin'})
        require(value.returncode==0 and len(value.stdout)<=4096,'Physical GPU query failed')
        row=parse(value.stdout);row['observed_monotonic_ns']=time.monotonic_ns();epoch();rows.append(row)
        if n<3:time.sleep(.5)
    return rows

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--nvidia-smi',type=Path);p.add_argument('--nvidia-smi-sha256')
    p.add_argument('--nvml-library',type=Path);p.add_argument('--nvml-library-sha256')
    a=p.parse_args(argv)
    if not a.execute:print(json.dumps({'state':'inert','gpu_calls':False}));return
    require(a.nvidia_smi is not None and a.nvml_library is not None,'Explicit pinned binary/library paths required')
    rows=sample(a.nvidia_smi,a.nvidia_smi_sha256,a.nvml_library,a.nvml_library_sha256)
    print(json.dumps({'version':1,'samples':rows,'hardware_qualified':False,'production_qualified':False}),flush=True)

if __name__=='__main__':main()
