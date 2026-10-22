#!/usr/bin/env python3
"""Offline source reconstruction and ELF checks; never builds/loads a module."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

KERNEL='6.8.0-147-generic'
VERSION='615.71.09'
ARCHIVE='45bcef6e82bef0dccdb40d5f0751c86af0fd5e0276b60d407d7b96eadd2ebfdf'
PATCH='89c96c231286b60eb72421ec2a2f0f9d8dd6aa7d90ef68eadf735d1216f949ef'
GUARD='70e6719709c8f5e5eb33a02a7323473e48dede3e4c74021b8992ea8ee0605114'
UVM_BEFORE='cf8d21c77f7db22f11b1a9c80f4197644d736d145afc2ea01bf057f83faaf8af'
UVM_AFTER='e49447593565bef4ff899ab65283169387a9992f941598a978bb939aca6a2871'
SOURCE_AFTER='420396405d625521a602cad514e0ba37d1c409dd26f59807f21fa0058e5e775f'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_name(name):
    p=PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts,'Unsafe source archive path')
    return str(p)


def require_same(expected,actual,label):require(expected==actual,label+' changed')


def verify_symbols(kernel,driver,imports):
    for name,crc in imports.items():
        require(name in kernel or name in driver,'Unresolved module import')
        require((driver if name in driver else kernel)[name]==crc,'Module import CRC changed')
    require(bool(imports),'Missing module symbol versions')
    return len(imports)


def prepare(archive,patch,guard,source_after,output):
    for path,digest in ((archive,ARCHIVE),(patch,PATCH),(guard,GUARD),(source_after,SOURCE_AFTER)):
        require(sha(path)==digest,'Pinned source input changed')
    require(not output.exists(),'Fresh output directory required')
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        require(len(members)<=10000 and sum(m.size for m in members)<=256*1024*1024,'Source archive exceeds bounds')
        names=[]
        for member in members:
            name=safe_name(member.name);names.append(name)
            require(member.isdir() or member.isfile(),'Source links/special files forbidden')
        require(len(names)==len(set(names)),'Duplicate source archive paths')
        output.mkdir(mode=0o700,parents=False)
        for member,name in zip(members,names):
            target=output/name
            if member.isdir():target.mkdir(mode=0o700,exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with target.open('xb') as handle:handle.write(tar.extractfile(member).read())
                target.chmod(0o700 if member.mode&0o111 else 0o600)
    subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch.resolve())],cwd=output,check=True,
                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    for line in source_after.read_text().splitlines():
        digest,name=line.split(None,1);require(sha(output/safe_name(name))==digest,'Final core source mismatch')
    # Parse only literal strings from the pinned historical generator; execute no code.
    constants={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(guard.read_text()).body
               if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)
               and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)}
    target=output/'kernel-open/nvidia-uvm/uvm_va_range.c'
    require(sha(target)==UVM_BEFORE,'Original UVM source changed')
    text=target.read_text();include='#include <linux/sched.h>\n'
    anchor='    uvm_va_range_managed_t *managed_range = NULL;\n\n    // Check for no overlap with HMM blocks.\n'
    require(text.count(include)==1 and text.count(anchor)==1,'UVM patch anchors changed')
    text=text.replace(include,include+constants['PARAMETER'],1)
    text=text.replace(anchor,'    uvm_va_range_managed_t *managed_range = NULL;\n\n'+constants['GUARD']+'    // Check for no overlap with HMM blocks.\n',1)
    target.write_text(text);require(sha(target)==UVM_AFTER,'Guarded UVM source mismatch')
    proof={'kind':'offline-source-only','archive_sha256':ARCHIVE,'core_patch_sha256':PATCH,
           'core_source_manifest_sha256':SOURCE_AFTER,'uvm_generator_sha256':GUARD,'uvm_source_sha256':UVM_AFTER,
           'target_kernel':KERNEL,'built':False,'loaded':False,'qualified':False}
    (output/'source-proof.json').write_text(json.dumps(proof,sort_keys=True,indent=2)+'\n')
    return proof


def query(*args):return subprocess.check_output(args,text=True).strip()


def symbols(flag,path,*,allow_empty=False):
    result={}
    try:output=query('modprobe',flag,str(path))
    except subprocess.CalledProcessError:
        if not (allow_empty and flag=='--show-exports'):raise
        # kmod reports ENODATA for a valid UVM ELF with no export section.
        sections=query('readelf','--wide','--sections',str(path))
        require('__ksymtab' not in sections,'Unparsed module exports present')
        return {}
    for line in output.splitlines():
        fields=line.split();require(len(fields)==2 and fields[1] not in result,'Malformed/duplicate module symbols')
        result[fields[1]]=int(fields[0],16)
    require(bool(result) or (allow_empty and flag=='--show-exports'),'Empty module symbol table')
    return result


def verify(headers,stock_core,stock_uvm,core,uvm):
    release=(headers/'include/generated/utsrelease.h').read_text()
    require(release.strip()=='#define UTS_RELEASE "'+KERNEL+'"','Actual target headers required')
    kernel={}
    for line in (headers/'Module.symvers').read_text().splitlines():
        fields=line.split();require(len(fields)>=4 and fields[1] not in kernel,'Malformed kernel symvers')
        kernel[fields[1]]=int(fields[0],16)
    paths=(stock_core,stock_uvm,core,uvm)
    metadata=[{key:query('modinfo','-F',key,str(p)) for key in ('version','vermagic','srcversion')} for p in paths]
    require(all(m['version']==VERSION and m['vermagic'].startswith(KERNEL+' ') and m['srcversion'] for m in metadata),
            'Stock/candidate driver version/kernel mismatch')
    require(len({m['vermagic'] for m in metadata})==1,'Stock/candidate vermagic differs')
    exports=[symbols('--show-exports',p,allow_empty=index in (1,3)) for index,p in enumerate(paths)]
    require_same(exports[0],exports[2],'Stock NVIDIA core exports')
    require_same(exports[1],exports[3],'Stock NVIDIA UVM exports')
    core_imports=symbols('--show-modversions',core);uvm_imports=symbols('--show-modversions',uvm)
    verify_symbols(kernel,{},core_imports);verify_symbols(kernel,exports[2],uvm_imports)
    # UVM guard adds no symbol dependency; core inventory legitimately adds cgrp_dfl_root.
    require_same(symbols('--show-modversions',stock_uvm),uvm_imports,'Stock UVM imports')
    stock_imports=symbols('--show-modversions',stock_core)
    require(all(core_imports.get(k)==v for k,v in stock_imports.items()),'Stock core import removed/changed')
    require(set(core_imports)-set(stock_imports)<={'cgrp_dfl_root'},'Unexpected extra core import')
    return {'kind':'offline-abi-only','target_kernel':KERNEL,'sha256':[sha(p) for p in paths],
            'module_info':metadata,'core_imports':len(core_imports),'uvm_imports':len(uvm_imports),
            'loaded':False,'qualified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation')
    prep=sub.add_parser('prepare-source')
    for arg in ('archive','patch','guard','source-after','output'):prep.add_argument('--'+arg,type=Path,required=True)
    check=sub.add_parser('verify-build')
    for arg in ('headers','stock-core','stock-uvm','core','uvm'):check.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args()
    if args.operation=='prepare-source':result=prepare(args.archive,args.patch,args.guard,args.source_after,args.output)
    elif args.operation=='verify-build':result=verify(args.headers,args.stock_core,args.stock_uvm,args.core,args.uvm)
    else:result={'state':'inert','built':False,'loaded':False}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
