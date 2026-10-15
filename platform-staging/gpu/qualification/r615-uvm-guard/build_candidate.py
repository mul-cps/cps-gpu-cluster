#!/usr/bin/env python3
"""Pinned compile-only candidate in a fresh owned copy. Never install or load."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
import guard

KERNEL='6.8.0-134-generic'
ORIGINAL_UVM_SHA='05c2e1319dacdca062bfddc4368be02b66307e0cda31abcd7d28fb37eeefff01'
ORIGINAL_CORE_SHA='94df0cd9b062ef42091a4f2639438b3596c6a49bcb1b56640ac6ef0f792f2020'
ORIGINAL_UVM_VERSIONS='0054b45bf40416a31ae6e77554935731d29b0235c5a49452590408ebb0f5184a'
EXPECTED={'nvidia-uvm/uvm_va_range.c':guard.SOURCE_SHA256,'nvidia-uvm/uvm.c':guard.CALLER_SHA256,
          'common/inc/nvstatuscodes.h':guard.STATUS_SHA256,'Makefile':guard.MAKEFILE_SHA256,
          'nvidia/nv-kernel.o_binary':guard.CORE_BINARY_SHA256}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def versions_digest(text):
    fields=[]
    for line in text.splitlines():
        if not re.match(r'^\s+0x[0-9a-fA-F]+\s',line):continue
        for field in line.split()[1:5]:
            if re.fullmatch(r'(?:[0-9a-fA-F]{2}){1,4}',field):fields.append(field.lower())
            else:break
    guard.require(bool(fields),'ELF __versions section required')
    return hashlib.sha256(''.join(fields).encode()).hexdigest()


def source_inventory(root,max_bytes=256*1024*1024):
    root=Path(root).resolve();total=0;count=0
    for item in root.rglob('*'):
        guard.require(not item.is_symlink() or item.resolve().is_relative_to(root),'External source symlink refused')
        if item.is_file():
            total+=item.stat().st_size;count+=1
            guard.require(total<=max_bytes and count<=10000,'Source copy bound exceeded')
        else:guard.require(item.is_dir(),'Source special file refused')
    return {'bytes':total,'files':count}


def validate_output(output,source):
    output=Path(output).resolve();source=Path(source).resolve()
    guard.require(not output.exists(),'Fresh output path required')
    guard.require(not output.is_relative_to(source) and not source.is_relative_to(output),'Output/source overlap refused')
    guard.require(output.name.startswith('cps-r615-uvm-guard-'),'Owned output basename required')


def make_command(headers,jobs):
    guard.require(jobs in (1,2),'Only one or two build CPUs allowed')
    return ['make',f'-j{jobs}','NV_KERNEL_MODULES=nvidia nvidia-uvm',f'KERNEL_UNAME={KERNEL}',
            f'SYSSRC={headers}','modules']


def run(command):return subprocess.check_output(command,text=True,stderr=subprocess.STDOUT).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('/usr/src/nvidia-615.71.09'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--jobs',type=int,choices=(1,2),default=1)
    parser.add_argument('--compile',action='store_true',help='Explicit compile-only operator execution')
    args=parser.parse_args();source=args.source.resolve();output=args.output.resolve()
    validate_output(output,source)
    for relative,expected in EXPECTED.items():guard.verify((source/relative).read_bytes(),expected)
    inventory=source_inventory(source)
    headers=Path(f'/lib/modules/{KERNEL}/build').resolve()
    guard.require(headers.is_dir() and (headers/'Module.symvers').is_file(),'Pinned kernel headers/symvers required')
    guard.require(os.uname().release==KERNEL,'Execute only against the pinned running kernel')
    uvm=Path(run(['modinfo','-n','nvidia_uvm']));core=Path(run(['modinfo','-n','nvidia']))
    guard.require(sha(uvm)==ORIGINAL_UVM_SHA and sha(core)==ORIGINAL_CORE_SHA,'Installed module baseline mismatch')
    original_vermagic=run(['modinfo','-F','vermagic',str(uvm)])
    original_versions=versions_digest(run(['readelf','-x','__versions',str(uvm)]))
    guard.require(original_versions==ORIGINAL_UVM_VERSIONS,'Installed UVM CRC baseline mismatch')
    command=make_command(headers,args.jobs)
    receipt={'schemaVersion':1,'experimental':True,'compileOnly':True,'hardwareQualified':False,
             'source':str(source),'output':str(output),'sourceInventory':inventory,'sourceHashes':EXPECTED,
             'command':command,'originalUvmSha256':ORIGINAL_UVM_SHA,'originalCoreSha256':ORIGINAL_CORE_SHA,
             'originalUvmVersionsSha256':original_versions,'originalVermagic':original_vermagic,
             'coreCandidateMustNeverBeInstalledOrLoaded':True}
    if not args.compile:
        print(json.dumps(receipt,indent=2));return
    os.umask(0o077);output.mkdir(mode=0o700)
    copied=output/'source';shutil.copytree(source,copied,symlinks=False)
    target=copied/'nvidia-uvm/uvm_va_range.c';target.write_bytes(guard.patched(target.read_bytes()))
    receipt['patchedSourceSha256']=sha(target)
    with (output/'compile.log').open('wb') as log:
        completed=subprocess.run(command,cwd=copied,stdout=log,stderr=subprocess.STDOUT,timeout=900,check=False)
    receipt['compileExitCode']=completed.returncode
    guard.require(sha(uvm)==ORIGINAL_UVM_SHA and sha(core)==ORIGINAL_CORE_SHA,'Installed module changed during compile')
    for relative,expected in EXPECTED.items():guard.verify((source/relative).read_bytes(),expected)
    if completed.returncode==0:
        candidate=copied/'nvidia-uvm.ko'
        receipt['candidateUvmPath']=str(candidate);receipt['candidateUvmSha256']=sha(candidate)
        receipt['candidateVermagic']=run(['modinfo','-F','vermagic',str(candidate)])
        receipt['candidateVersion']=run(['modinfo','-F','version',str(candidate)])
        receipt['candidateUvmVersionsSha256']=versions_digest(run(['readelf','-x','__versions',str(candidate)]))
        receipt['crcAndVermagicMatch']=(receipt['candidateUvmVersionsSha256']==original_versions and
                                        receipt['candidateVermagic']==original_vermagic and
                                        receipt['candidateVersion']==guard.VERSION)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    guard.require(completed.returncode==0,'Compile failed; private compile.log retained')
    guard.require(receipt['crcAndVermagicMatch'],'Candidate CRC/version/vermagic mismatch; never load')


if __name__=='__main__':main()
