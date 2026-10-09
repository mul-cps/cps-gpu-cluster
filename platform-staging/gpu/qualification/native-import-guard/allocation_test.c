/* CPU synthetic fixture for actual protected allocator; never GPU calls. */
#include <assert.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
#include <stdint.h>
typedef int NV_STATUS,NvBool;typedef unsigned NvU32;typedef size_t NvLength;typedef void *ClientGroupID;
#define G(n) ((ClientGroupID)(uintptr_t)(n))
enum {NV_OK,NV_ERR_INSUFFICIENT_PERMISSIONS,NV_ERR_NOT_SUPPORTED,NV_ERR_OBJECT_NOT_FOUND,NV_ERR_NO_MEMORY,NV_WARN_RESOURCE_ACCOUNTING_SOFT_LIMIT_EXCEEDED,NV_ERR_RESOURCE_ACCOUNTING_HARD_LIMIT_EXCEEDED};
enum {CGROUP_IMPL_NONE,CGROUP_IMPL_FALLBACK,CGROUP_IMPL_OS,OS_CGROUP_IMPL_MISC=1,NV_FALSE=0,NV_TRUE=1,NV2080_NOTIFIERS_MEMACCT_SOFT_LIMIT_EXCEEDED=2};
typedef struct {NvU32 gpuId,pid;ClientGroupID cligrp;} MemoryCharge;
typedef struct {void *pOsPidInfo;NvU32 ProcID;NvBool bCpsGpuOpsSession;int bCpsObjExportClient;} RmClient;
typedef struct {NvLength HardLimit;} ClientGroupLimits;static ClientGroupLimits limits;typedef struct {int clientGroupMap;} GpuRegion;
static struct {int impl,GpuRegionMap;void *mutex;} g_memacct;
static GpuRegion region;static ClientGroupID actor,creator;static int locks,gets,puts_count,pid_puts,allocs,frees,notifies,charges,admin,have_region,have_pid,fail_alloc,charge_status;
static NvU32 osGetCurrentProcess(void){return 29;}
static void *osGetPidInfo(void){return have_pid?(void*)1:NULL;}
static void osPutPidInfo(void *p){assert(p==(void*)1);pid_puts++;}
static void *os_cps_cgroup_get_from_pid_info(void *p,int impl){assert(p&&impl==OS_CGROUP_IMPL_MISC);void *g=p==(void*)1?actor:creator;if(g)gets++;return g;}
static void os_cgroup_put(void *p){assert(p);puts_count++;}
static void *portMemAllocNonPaged(size_t n){if(fail_alloc)return NULL;allocs++;return malloc(n);}
static void portMemFree(void *p){if(p){frees++;free(p);}}
static void portSyncMutexAcquire(void *p){assert(p&&!locks);locks++;}
static void portSyncMutexRelease(void *p){assert(p&&locks==1);locks--;}
static GpuRegion *mapFind(int *p,NvU32 gpu){assert(p==&g_memacct.GpuRegionMap&&gpu==7);return have_region?&region:NULL;}
static int mapCount(int *p){return *p;}
static ClientGroupLimits *memacctLimitsForGroupLocked(GpuRegion *r,ClientGroupID *g){assert(r==&region&&locks);if(*g==G(101)||*g==G(102))*g=G(100);if(*g==G(201))*g=G(200);return *g==G(100)||*g==G(200)?&limits:NULL;}
static NV_STATUS memacctTryChargeInternalLocked(GpuRegion *r,ClientGroupID g,NvU32 gpu,NvLength size,MemoryCharge *c){assert(r==&region&&locks&&gpu==7&&size==64);charges++;c->cligrp=g;return charge_status;}
static int osIsAdministrator(void){return admin;}
static void *gpumgrGetGpuFromId(NvU32 gpu){assert(gpu==7);return (void*)1;}
static void gpuNotifySubDeviceEvent(void *gpu,int which,void *data,int a,int pid,int b){assert(gpu&&which==2&&!data&&!a&&pid==19&&!b);notifies++;}
#include "allocation_guard.c"
static void reset(void){limits.HardLimit=512;g_memacct.impl=CGROUP_IMPL_FALLBACK;g_memacct.mutex=(void*)1;region.clientGroupMap=2;actor=G(101);creator=G(102);locks=gets=puts_count=pid_puts=allocs=frees=notifies=charges=admin=fail_alloc=0;have_region=have_pid=1;charge_status=NV_OK;}
static NV_STATUS run(RmClient *client,MemoryCharge **out){NV_STATUS s=memacctTryChargeProtected(client,7,64,out);assert(!locks&&gets==puts_count);assert(pid_puts==(have_pid&&client&&(client->pOsPidInfo||client->bCpsGpuOpsSession)?1:0));assert(allocs-frees==(*out?1:0));return s;}
int main(void){RmClient c={(void*)2,19,NV_FALSE,0};MemoryCharge *out;
 reset();assert(run(&c,&out)==NV_OK&&out&&out->cligrp==G(100)&&out->gpuId==7&&out->pid==19);free(out);
 reset();creator=G(201);assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out&&!charges);
 reset();creator=NULL;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();actor=NULL;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();charge_status=NV_ERR_RESOURCE_ACCOUNTING_HARD_LIMIT_EXCEEDED;assert(run(&c,&out)==charge_status&&!out);
 reset();charge_status=NV_WARN_RESOURCE_ACCOUNTING_SOFT_LIMIT_EXCEEDED;assert(run(&c,&out)==NV_OK&&out&&notifies==1);free(out);
 reset();actor=creator=G(1);admin=1;assert(run(&c,&out)==NV_OK&&!out&&!charges);
 reset();actor=creator=G(1);assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();actor=G(1);creator=G(2);admin=1;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();actor=G(1);admin=1;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();c.pOsPidInfo=NULL;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);c.pOsPidInfo=(void*)2;
 reset();c.pOsPidInfo=NULL;c.bCpsObjExportClient=1;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out&&!charges);c.pOsPidInfo=(void*)2;c.bCpsObjExportClient=0;
 reset();fail_alloc=1;assert(run(&c,&out)==NV_ERR_NO_MEMORY&&!out);
 reset();have_pid=0;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();g_memacct.impl=CGROUP_IMPL_NONE;assert(memacctTryChargeProtected(&c,7,64,&out)==NV_ERR_NOT_SUPPORTED&&!out&&!gets);
 reset();region.clientGroupMap=0;assert(memacctTryChargeProtected(NULL,7,64,&out)==NV_OK&&!out&&!gets); /* boot not protected */
 reset();c.pOsPidInfo=NULL;c.bCpsGpuOpsSession=NV_TRUE;assert(run(&c,&out)==NV_OK&&out&&out->cligrp==G(100)&&out->pid==29);free(out);
 reset();limits.HardLimit=(NvLength)-1;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out&&!charges);
 reset();limits.HardLimit=0;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out&&!charges);
 reset();actor=G(1);admin=1;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out&&!charges); /* marked session never operator bypass */
 reset();actor=NULL;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out);
 reset();c.pOsPidInfo=(void*)2;creator=NULL;assert(run(&c,&out)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!out); /* marker cannot rescue dead user creator */
 puts("Synthetic allocator checks passed; no GPU allocations");return 0;}
