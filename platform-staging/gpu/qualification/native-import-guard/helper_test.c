/* Synthetic CPU fixture compiles the actual guard helper, never NVIDIA/GPU code. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
typedef int NV_STATUS; typedef unsigned NvU32; typedef void *ClientGroupID;
#define G(n) ((ClientGroupID)(uintptr_t)(n))
enum {NV_OK, NV_ERR_INSUFFICIENT_PERMISSIONS, NV_ERR_NOT_SUPPORTED, NV_ERR_OBJECT_NOT_FOUND};
enum {CGROUP_IMPL_NONE, CGROUP_IMPL_FALLBACK, CGROUP_IMPL_OS, RS_PRIV_LEVEL_KERNEL=10};
typedef struct {ClientGroupID cligrp;NvU32 gpuId;} MemoryCharge;
typedef struct {void *pOsPidInfo;NvU32 ProcID;int cachedPrivilege;} RmClient;
typedef struct {int clientGroupMap;} GpuRegion;
static struct {int impl;void *mutex;int GpuRegionMap;} g_memacct;
static GpuRegion region;static ClientGroupID actor,destination;static int have_pid,have_region,pid_puts,locks;
static void *osGetPidInfo(void){return have_pid?(void*)1:NULL;}
static void osPutPidInfo(void *p){assert(p==(void*)1);pid_puts++;}
static NvU32 osGetCurrentProcess(void){return 17;}
static ClientGroupID osClientGroupID(NvU32 pid,void *info){assert(info);return pid==17?actor:destination;}
static void portSyncMutexAcquire(void *p){assert(p);assert(!locks);locks++;}
static void portSyncMutexRelease(void *p){assert(p);assert(locks==1);locks--;}
static GpuRegion *mapFind(int *map,NvU32 id){assert(map==&g_memacct.GpuRegionMap);assert(id==7);return have_region?&region:NULL;}
static int mapCount(int *map){return *map;}
static void *memacctLimitsForGroupLocked(GpuRegion *p,ClientGroupID *group){assert(p==&region&&locks);if(*group==G(101)||*group==G(102))*group=G(100);if(*group==G(201))*group=G(200);return *group==G(100)||*group==G(200)?(void*)1:NULL;}
#include "guard.c"
static void reset(void){g_memacct.impl=CGROUP_IMPL_FALLBACK;g_memacct.mutex=(void*)1;region.clientGroupMap=2;have_pid=have_region=1;actor=G(101);destination=G(102);pid_puts=locks=0;}
static NV_STATUS check(MemoryCharge *charge,RmClient *client){NV_STATUS s=memacctValidateMemoryImport(charge,7,client);assert(locks==0);assert(pid_puts==(have_pid?1:0));return s;}
int main(void){MemoryCharge charge={G(100),7};RmClient user={(void*)2,18,0},kernel={NULL,19,RS_PRIV_LEVEL_KERNEL};
 reset();assert(check(&charge,&user)==NV_OK); /* same capped Pod, different children */
 reset();actor=G(201);assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();destination=G(201);assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();assert(check(&charge,&kernel)==NV_OK); /* current capped actor is proven */
 reset();actor=G(1);assert(check(&charge,&kernel)==NV_ERR_INSUFFICIENT_PERMISSIONS); /* MPS/async root cannot delegate */
 reset();assert(check(NULL,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();charge.gpuId=8;assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);charge.gpuId=7;
 reset();charge.cligrp=0;assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);charge.cligrp=G(100);
 reset();assert(check(&charge,NULL)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();kernel.cachedPrivilege=0;assert(check(&charge,&kernel)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();actor=0;assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();destination=0;assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();have_region=0;assert(check(&charge,&user)==NV_ERR_OBJECT_NOT_FOUND);
 reset();have_pid=0;assert(check(&charge,&user)==NV_ERR_INSUFFICIENT_PERMISSIONS);
 reset();region.clientGroupMap=0;actor=G(1);assert(check(NULL,&kernel)==NV_OK); /* boot is explicitly unprotected */
 reset();g_memacct.impl=CGROUP_IMPL_OS;assert(memacctValidateMemoryImport(&charge,7,&user)==NV_ERR_NOT_SUPPORTED);assert(!pid_puts&&!locks);
 reset();g_memacct.impl=CGROUP_IMPL_NONE;assert(memacctValidateMemoryImport(&charge,7,&user)==NV_OK);assert(!pid_puts&&!locks);
 puts("Synthetic import guard checks passed; driver not built/loaded/qualified");return 0;}
