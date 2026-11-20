#!/usr/bin/env python3
"""Render an OFFLINE guard patch; never edits source or builds/loads a module."""
import argparse, difflib, hashlib, json
from pathlib import Path
HERE=Path(__file__).parent
HASHES={
 'src/nvidia/src/kernel/mem_mgr/video_mem.c':'92248044cb241097cb03e6b5151df2eaffc7aad765d35506039f14e48217401c',
 'src/nvidia/src/kernel/rmapi/nv_gpu_ops.c':'884af61d0fbb6b4e7d97920fbfc96dd30575c6350ae1ef2c97126cf89c2afc99',
 'src/nvidia/src/kernel/mem_mgr/memacct.c':'bb33f008cafa41842e393edb7571d0f61c3e6f690b4a41235d45e42676683a58',
 'src/nvidia/inc/kernel/mem_mgr/memacct.h':'2079f73e5452744848a96686e6401d78d0cc088364c07b371d118887f325a923',
 'kernel-open/nvidia/os-interface.c':'ef23dfe456481ea07c926d5929991807666e6796ac07b72e9c4ea96e224adf62',
 'kernel-open/common/inc/os-interface.h':'531c2d9f21f63de576c24047a9c01081aa4124740346351e9efdcfe867c3204f',
 'src/nvidia/arch/nvalloc/unix/include/os-interface.h':'bd281e48ff06b481033fc2fb29a891710a2b4d66fb009cc2b752ab6e90f2113b',
 'kernel-open/nvidia/nvidia.Kbuild':'6b2803664c904934bf92a24d55e5668aa82049b082972bce97d13b0ef390735b',
 'src/nvidia/generated/g_client_nvoc.h':'1cc654687a59b1635672761670f6521579fb24cb361661329996f3d463e02243',
 'src/nvidia/src/kernel/rmapi/client.c':'9b318cf1cb287b927b25a6732f4458801d9f813cf9c2a8e30f141f91b77cda03',
 'src/nvidia/arch/nvalloc/unix/src/rmobjexportimport.c':'053d04e6cdc34229700447a2fc5104717c439a74d5d9cea4dbf90410cdd3d9dd',
 'src/nvidia/arch/nvalloc/unix/src/os.c':'057b50fcb738be90a073b60f63e70559706864ddcec3bf703282563173e3dce4'}
def replace_once(data,old,new):
 if data.count(old)!=1:raise ValueError('Pinned source anchor absent or ambiguous')
 return data.replace(old,new,1)
READONLY_HASHES={'kernel-open/nvidia/nv-procfs.c':'3e5dde885bcba7890439f57e0d51c670f81bd340df151c38ab2f2ee32eddc006',
 'src/nvidia/arch/nvalloc/unix/src/osapi.c':'43017499b404600beac7f5c2b5f09f39774b71f50ba15fd3317399fa29c02b7e',
 'src/nvidia/exports_link_command.txt':'b3312b233ce8658452b9f91799d78ca894d7ce7233542caaa0cbe4cbc4f5daf1'}
def render(source, *, readonly_cap_inventory=False):
 original={}
 hashes={**HASHES,**(READONLY_HASHES if readonly_cap_inventory else {})}
 for name,sha in hashes.items():
  path=source/name
  if path.is_symlink():raise ValueError('Symlink source rejected')
  data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Pristine pinned615.71.09 source required: '+name)
  original[name]=data.decode()
 changed=original.copy()
 name='src/nvidia/generated/g_client_nvoc.h'
 changed[name]=replace_once(changed[name],'    NvS32 lockStressCounter;','    NvS32 lockStressCounter;\n    NvBool bCpsGpuOpsSession; /* Source-owned qualification marker, not a user parameter. */\n    NvBool bCpsObjExportClient; /* Destination-copy authority only, never allocation. */')
 name='src/nvidia/src/kernel/rmapi/client.c'
 changed[name]=replace_once(changed[name],'    pClient->bIsRootNonPriv  =','    pClient->bCpsGpuOpsSession = NV_FALSE;\n    pClient->bCpsObjExportClient = NV_FALSE;\n    pClient->bIsRootNonPriv  =')
 name='kernel-open/nvidia/nvidia.Kbuild'
 changed[name]=replace_once(changed[name],'NV_CONFTEST_FUNCTION_COMPILE_TESTS += get_dev_pagemap_has_pgmap_arg','NV_CONFTEST_TYPE_COMPILE_TESTS += memory_device_coherent_present\nNV_CONFTEST_FUNCTION_COMPILE_TESTS += get_dev_pagemap_has_pgmap_arg')
 name='kernel-open/nvidia/os-interface.c'
 changed[name]=replace_once(changed[name],'#include <linux/pid.h>','#include <linux/pid.h>\n#include <linux/sched/task.h>\n#include <linux/ratelimit.h>')
 changed[name]=replace_once(changed[name],'void* NV_API_CALL os_get_pid_info(void)',(HERE/'task_cgroup_get.c').read_text()+'\nvoid* NV_API_CALL os_get_pid_info(void)')
 changed[name]=replace_once(changed[name],'extern char *NVreg_TemporaryFilePath;',(HERE/'runtime_parameter.c').read_text()+'\n'+(HERE/'import_diagnostic.c').read_text()+'\nextern char *NVreg_TemporaryFilePath;')
 for name in ['kernel-open/common/inc/os-interface.h','src/nvidia/arch/nvalloc/unix/include/os-interface.h']:
  changed[name]=replace_once(changed[name],'void*       NV_API_CALL  os_get_pid_info(void);','void        NV_API_CALL  os_cps_native_import_denied(NvU32 gpuId, NvU32 reason, NvU32 clientKind, NvU32 status);\nNvBool      NV_API_CALL  os_cps_native_import_guard_enabled(void);\nvoid*       NV_API_CALL  os_cps_cgroup_get_from_pid_info(void *pidInfo, int impl);\nvoid*       NV_API_CALL  os_get_pid_info(void);')
 name='src/nvidia/arch/nvalloc/unix/src/rmobjexportimport.c'
 changed[name]=replace_once(changed[name],'#include "rmapi/rmapi.h"','#include "os-interface.h"\n#include "rmapi/client.h"\n#include "rmapi/rmapi.h"')
 changed[name]=replace_once(changed[name],'static NV_STATUS RmRefObjExportImport(void)',(HERE/'object_export_client.c').read_text()+'\nstatic NV_STATUS RmRefObjExportImport(void)')
 changed[name]=replace_once(changed[name],'    pMemAllocator = portMemAllocatorCreateNonPaged();','    rmStatus = RmMarkProtectedObjExportClient(hObjExportRmClient);\n    if (rmStatus != NV_OK)\n        goto failed;\n\n    pMemAllocator = portMemAllocatorCreateNonPaged();')
 name='src/nvidia/src/kernel/mem_mgr/memacct.c'
 changed[name]=replace_once(changed[name],'    NvLength Available;','    NvLength Available;\n    ClientGroupID cpsPinnedGroup;')
 changed[name]=replace_once(changed[name],'static NV_STATUS memacctTryChargeOs(', (HERE/'limits_lifetime.c').read_text()+'\nstatic NV_STATUS memacctTryChargeOs(')
 changed[name]=replace_once(changed[name],'        pLimits->Available = hardlimit;','        memacctPinLimitGroup(pLimits, cligrp);\n        pLimits->Available = hardlimit;')
 changed[name]=replace_once(changed[name],'        mapClear(&pRegion->clientGroupMap);','        memacctUnpinLimitGroups(pRegion);\n        mapClear(&pRegion->clientGroupMap);')
 changed[name]=replace_once(changed[name],'#include \"mem_mgr/memacct.h\"','#include \"os-interface.h\"\n#include \"mem_mgr/memacct.h\"')
 changed[name]=replace_once(changed[name],'static NV_STATUS memacctTryChargeInternalLocked(', (HERE/'guard.c').read_text()+'\nstatic NV_STATUS memacctTryChargeInternalLocked(')
 old='NV_STATUS memacctTryCharge(RmClient *pRmClient, NvU32 gpuId, NvLength size, MemoryCharge **ppCharge)\n{'
 changed[name]=replace_once(changed[name],old,(HERE/'allocation_guard.c').read_text()+'\n'+old+'\n    if (os_cps_native_import_guard_enabled())\n        return memacctTryChargeProtected(pRmClient, gpuId, size, ppCharge);')
 name='src/nvidia/arch/nvalloc/unix/src/os.c'
 old='        cgroup = osClientGroupID(pid, pidInfo);\n        if (cgroup != NULL)\n            osCgroupGet(cgroup);'
 new='        if (os_cps_native_import_guard_enabled())\n            cgroup = os_cps_cgroup_get_from_pid_info(pidInfo, OS_CGROUP_IMPL_MISC);\n        else\n        {\n            cgroup = osClientGroupID(pid, pidInfo);\n            if (cgroup != NULL)\n                osCgroupGet(cgroup);\n        }'
 if changed[name].count(old)!=2:raise ValueError('Set/Get current-process anchors changed')
 changed[name]=changed[name].replace(old,new)
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
 changed[name]=replace_once(changed[name],'NV_STATUS nvGpuOpsCreateSession(struct gpuSession **session)',(HERE/'gpu_ops_session.c').read_text()+'\nNV_STATUS nvGpuOpsCreateSession(struct gpuSession **session)')
 changed[name]=replace_once(changed[name],'    gpuSession->devices = NULL;','    status = nvGpuOpsMarkProtectedSession(gpuSession->handle);\n    if (status != NV_OK)\n    {\n        pRmApi->Free(pRmApi, gpuSession->handle, gpuSession->handle);\n        portMemFree(gpuSession);\n        return status;\n    }\n\n    gpuSession->devices = NULL;')
 changed[name]=replace_once(changed[name],'#include <class/cl0002.h>','#include "mem_mgr/memacct.h"\n#include <class/cl0002.h>')
 old='    // RM client allocations can\'t have multiple memdesc.\n    pMemDesc = pMemory->pMemDesc;'
 new=old+'\n    if (memdescGetAddressSpace(pMemDesc) == ADDR_FBMEM)\n    {\n        status = memacctValidateMemoryImport(pMemory->pCharge, pMemDesc->pGpu->gpuId,\n                                             dynamicCast(pSessionClient, RmClient));\n        if (status != NV_OK)\n            goto done;\n    }'
 changed[name]=replace_once(changed[name],old,new)
 if readonly_cap_inventory:
  for name in ['kernel-open/common/inc/os-interface.h','src/nvidia/arch/nvalloc/unix/include/os-interface.h']:
   changed[name]=replace_once(changed[name],'void*       NV_API_CALL  os_get_pid_info(void);',(HERE/'readonly_cap.h').read_text()+'\nvoid*       NV_API_CALL  os_get_pid_info(void);')
  name='kernel-open/nvidia/os-interface.c'
  changed[name]=replace_once(changed[name],'void* NV_API_CALL os_get_pid_info(void)',(HERE/'readonly_cap_os.c').read_text()+'\nvoid* NV_API_CALL os_get_pid_info(void)')
  name='src/nvidia/src/kernel/mem_mgr/memacct.c'
  changed[name]=replace_once(changed[name],'NV_STATUS memacctGetLimits(', (HERE/'readonly_cap.c').read_text()+'\nNV_STATUS memacctGetLimits(')
  name='kernel-open/nvidia/nv-procfs.c'
  changed[name]=replace_once(changed[name],'#include "nv-reg.h"','#include "nv-reg.h"\n#include <linux/cred.h>\n#include <linux/user_namespace.h>\n#include <linux/capability.h>')
  changed[name]=replace_once(changed[name],'static int\nnv_procfs_read_gpu_info(', (HERE/'readonly_cap_proc.c').read_text()+'\nstatic int\nnv_procfs_read_gpu_info(')
  anchor='    entry = NV_CREATE_PROC_FILE("registry", proc_nvidia_gpu, registry, nv);'
  changed[name]=replace_once(changed[name],anchor,'    if (os_cps_native_import_guard_enabled())\n    {\n        entry = proc_create_data("cps_native_caps", S_IFREG | S_IRUSR,\n            proc_nvidia_gpu, &nv_procfs_cps_native_caps_fops, nv);\n        if (!entry)\n            goto failed;\n    }\n\n'+anchor)
  name='src/nvidia/arch/nvalloc/unix/src/osapi.c'
  changed[name]=replace_once(changed[name],'NV_STATUS NV_API_CALL rm_acquire_api_lock(', (HERE/'readonly_cap_rm.c').read_text()+'\nNV_STATUS NV_API_CALL rm_acquire_api_lock(')
  name='src/nvidia/exports_link_command.txt'
  changed[name]=replace_once(changed[name],'--undefined=rm_get_gpu_uuid\n','--undefined=rm_cps_get_readonly_caps\n--undefined=rm_get_gpu_uuid\n')
 return original,changed
def patch(original,changed):
 return ''.join(''.join(difflib.unified_diff(original[n].splitlines(True),changed[n].splitlines(True),fromfile='a/'+n,tofile='b/'+n)) for n in original)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);p.add_argument('--render',action='store_true');p.add_argument('--readonly-cap-inventory',action='store_true');a=p.parse_args()
 receipt={'state':'inert','gpuCalls':False,'coreBuilt':False,'coreLoaded':False,'productionQualified':False,'sourceTag':'615.71.09','inputSha256':{**HASHES,**(READONLY_HASHES if a.readonly_cap_inventory else {})},'readonlyCapInventory':a.readonly_cap_inventory}
 if a.render:
  if not a.source or not a.output:p.error('--render requires --source and NEW --output')
  original,changed=render(a.source,readonly_cap_inventory=a.readonly_cap_inventory);data=patch(original,changed).encode()
  with a.output.open('xb') as stream:stream.write(data)
  receipt.update(state='offline-patch-rendered',patchSha256=hashlib.sha256(data).hexdigest())
 print(json.dumps(receipt))
if __name__=='__main__':main()
