#!/usr/bin/env python3
"""Pinned official-header CPU build; never load or invoke CUDA."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HEADER_SHA='7a79d67ca888061b1dfbe4739b51ad64f85a2f3ad874947ce09b2c635b4c7072'
PACKAGE_URL='https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-cudart-dev-13-4_13.4.92-1_amd64.deb'
PACKAGE_SHA='71bf3d001f2560a4710bdaba9297fcd3f775a50e3b320ec1c5fcc880d458b0df'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--headers',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--compiler',default='cc');p.add_argument('--compile',action='store_true');a=p.parse_args()
 source=Path(__file__).with_name('native_imports.c');header=a.headers/'cuda.h'
 if hashlib.sha256(header.read_bytes()).hexdigest()!=HEADER_SHA:raise ValueError('Exact official CUDA13.4.92 cuda.h required')
 if a.output.exists():raise ValueError('Refuse to overwrite output')
 cmd=[a.compiler,'-std=c11','-Wall','-Wextra','-Werror','-O2','-I'+str(a.headers),str(source),'-ldl','-o',str(a.output)]
 receipt={'state':'inert','gpu_calls':False,'headerSha256':HEADER_SHA,'packageUrl':PACKAGE_URL,'packageSha256':PACKAGE_SHA,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'command':cmd}
 if a.compile:
  subprocess.run(cmd,check=True,timeout=60);receipt.update(state='cpu-compiled',binarySha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
 print(json.dumps(receipt))
if __name__=='__main__':main()
