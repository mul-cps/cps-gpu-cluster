#!/usr/bin/env python3
"""Extract the verified embedded K3s zstd frame without executing the binary."""
import argparse
import ctypes
import ctypes.util
import hashlib
from pathlib import Path
import subprocess
import tarfile

p=argparse.ArgumentParser()
p.add_argument('binary',type=Path)
p.add_argument('archive_sha256')
p.add_argument('destination',type=Path)
a=p.parse_args()
a.destination.mkdir(parents=True,exist_ok=False)
data=a.binary.read_bytes()
lib=ctypes.CDLL(ctypes.util.find_library('zstd'))
lib.ZSTD_findFrameCompressedSize.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
lib.ZSTD_findFrameCompressedSize.restype=ctypes.c_size_t
lib.ZSTD_isError.argtypes=[ctypes.c_size_t]
buffer=ctypes.create_string_buffer(data)
pos=0
while True:
    pos=data.find(b'\x28\xb5\x2f\xfd',pos)
    if pos<0:
        raise RuntimeError('Expected archive not found in executable')
    size=lib.ZSTD_findFrameCompressedSize(ctypes.byref(buffer,pos),len(data)-pos)
    if not lib.ZSTD_isError(size):
        frame=data[pos:pos+size]
        if hashlib.sha256(frame).hexdigest()==a.archive_sha256:
            break
    pos+=4
archive=a.destination/'payload.tar.zst'
archive.write_bytes(frame)
with (a.destination/'payload.tar').open('wb') as out:
    subprocess.run(['zstd','-d','-c',str(archive)],stdout=out,check=True)
with tarfile.open(a.destination/'payload.tar') as tar:
    for member in tar:
        path=Path(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert path.parts and path.parts[0] in ('bin','etc')
    tar.extractall(a.destination,filter='data')
print(f'archive_sha256={a.archive_sha256} offset={pos} size={size}')
