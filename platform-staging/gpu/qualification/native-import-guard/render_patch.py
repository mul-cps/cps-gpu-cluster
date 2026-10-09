#!/usr/bin/env python3
"""Render an OFFLINE guard patch; never edits source or builds/loads a module."""
import argparse, difflib, hashlib, json
from pathlib import Path
HERE=Path(__file__).parent
HASHES={
 'src/nvidia/src/kernel/mem_mgr/video_mem.c':'92248044cb241097cb03e6b5151df2eaffc7aad765d35506039f14e48217401c',
 'src/nvidia/src/kernel/rmapi/nv_gpu_ops.c':'884af61d0fbb6b4e7d97920fbfc96dd30575c6350ae1ef2c97126cf89c2afc99',
 'src/nvidia/src/kernel/mem_mgr/memacct.c':'bb33f008cafa41842e393edb7571d0f61c3e6f690b4a41235d45e42676683a58',
 'src/nvidia/inc/kernel/mem_mgr/memacct.h':'2079f73e5452744848a96686e6401d78d0cc088364c07b371d118887f325a923'}
def replace_once(data,old,new):
 if data.count(old)!=1:raise ValueError('Pinned source anchor absent or ambiguous')
 return data.replace(old,new,1)
def render(source):
 original={}
 for name,sha in HASHES.items():
  path=source/name
  if path.is_symlink():raise ValueError('Symlink source rejected')
  data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Pristine pinned615.71.09 source required: '+name)
  original[name]=data.decode()
 changed=original.copy()
 name='src/nvidia/src/kernel/mem_mgr/memacct.c'
 changed[name]=replace_once(changed[name],'static NV_STATUS memacctTryChargeInternalLocked(', (HERE/'guard.c').read_text()+'\nstatic NV_STATUS memacctTryChargeInternalLocked(')
 name='src/nvidia/inc/kernel/mem_mgr/memacct.h'
 changed[name]=replace_once(changed[name],'void memacctIncrementChargeRefCount(MemoryCharge *pCharge);','NV_STATUS memacctValidateMemoryImport(MemoryCharge *pCharge, NvU32 gpuId, RmClient *pDestination);\nvoid memacctIncrementChargeRefCount(MemoryCharge *pCharge);')
 name='src/nvidia/src/kernel/mem_mgr/video_mem.c'
 # Early: no BAR1/heap refcount has been acquired yet.
 old='    NvBool             bSrcLockAcquired = NV_FALSE;\n\n    if (!rmDeviceGpuLockIsOwner(pGpu->gpuInstance) && !rmGpuLockIsOwner())\n'
 new='    NvBool             bSrcLockAcquired = NV_FALSE;\n\n    status = memacctValidateMemoryImport(pMemorySrc->pCharge, pGpu->gpuId,\n                                        dynamicCast(pCallContext->pClient, RmClient));\n    if (status != NV_OK)\n        return status;\n\n    if (!rmDeviceGpuLockIsOwner(pGpu->gpuInstance) && !rmGpuLockIsOwner())\n'
 changed[name]=replace_once(changed[name],old,new)
 # Explicit include avoids dependence on transitive generated class headers.
 changed[name]=replace_once(changed[name],'#include "gpu/mem_mgr/mem_desc.h"','#include "mem_mgr/memacct.h"\n#include "gpu/mem_mgr/mem_desc.h"')
 name='src/nvidia/src/kernel/rmapi/nv_gpu_ops.c'
 changed[name]=replace_once(changed[name],'#include <class/cl0002.h>','#include "mem_mgr/memacct.h"\n#include <class/cl0002.h>')
 old='    // RM client allocations can\'t have multiple memdesc.\n    pMemDesc = pMemory->pMemDesc;'
 new=old+'\n    if (memdescGetAddressSpace(pMemDesc) == ADDR_FBMEM)\n    {\n        status = memacctValidateMemoryImport(pMemory->pCharge, pMemDesc->pGpu->gpuId,\n                                             dynamicCast(pSessionClient, RmClient));\n        if (status != NV_OK)\n            goto done;\n    }'
 changed[name]=replace_once(changed[name],old,new)
 return original,changed
def patch(original,changed):
 return ''.join(''.join(difflib.unified_diff(original[n].splitlines(True),changed[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in HASHES)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);p.add_argument('--render',action='store_true');a=p.parse_args()
 receipt={'state':'inert','gpuCalls':False,'coreBuilt':False,'coreLoaded':False,'productionQualified':False,'sourceTag':'615.71.09','inputSha256':HASHES}
 if a.render:
  if not a.source or not a.output:p.error('--render requires --source and NEW --output')
  original,changed=render(a.source);data=patch(original,changed).encode()
  with a.output.open('xb') as stream:stream.write(data)
  receipt.update(state='offline-patch-rendered',patchSha256=hashlib.sha256(data).hexdigest())
 print(json.dumps(receipt))
if __name__=='__main__':main()
