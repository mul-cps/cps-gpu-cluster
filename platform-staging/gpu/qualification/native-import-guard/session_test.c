/* CPU-only fixture: trusted session marker and lock release paths. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef int NV_STATUS,NvBool;typedef unsigned NvHandle;
enum {NV_OK,NV_ERR_INSUFFICIENT_PERMISSIONS,NV_ERR_INVALID_STATE,RS_PRIV_LEVEL_KERNEL=10,RMAPI_LOCK_FLAGS_NONE=0,NV_TRUE=1};
typedef struct {void *pOsPidInfo;int cachedPrivilege;NvBool bCpsGpuOpsSession;} RmClient;
typedef RmClient RsClient;typedef int nvGpuOpsLockSet;
static RmClient client;static int enabled,locked,lock_status,cast_ok;
static int os_cps_native_import_guard_enabled(void){return enabled;}
static NV_STATUS _nvGpuOpsLocksAcquire(int flags,NvHandle h,RsClient **out,int n,int a,int b,nvGpuOpsLockSet *locks){assert(flags==RMAPI_LOCK_FLAGS_NONE&&h==42&&!n&&!a&&!b&&locks&&!locked);if(lock_status)return lock_status;locked=1;*out=&client;return NV_OK;}
static void _nvGpuOpsLocksRelease(nvGpuOpsLockSet *locks){assert(locks&&locked);locked=0;}
#define dynamicCast(p,t) (cast_ok?(p):NULL)
#include "gpu_ops_session.c"
static void reset(void){client=(RmClient){NULL,RS_PRIV_LEVEL_KERNEL,0};enabled=cast_ok=1;locked=lock_status=0;}
int main(void){
 reset();assert(nvGpuOpsMarkProtectedSession(42)==NV_OK&&client.bCpsGpuOpsSession&&!locked);
 reset();enabled=0;assert(nvGpuOpsMarkProtectedSession(42)==NV_OK&&!client.bCpsGpuOpsSession&&!locked);
 reset();client.pOsPidInfo=(void*)1;assert(nvGpuOpsMarkProtectedSession(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!client.bCpsGpuOpsSession&&!locked);
 reset();client.cachedPrivilege=0;assert(nvGpuOpsMarkProtectedSession(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!client.bCpsGpuOpsSession&&!locked);
 reset();cast_ok=0;assert(nvGpuOpsMarkProtectedSession(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!locked);
 reset();lock_status=NV_ERR_INVALID_STATE;assert(nvGpuOpsMarkProtectedSession(42)==lock_status&&!client.bCpsGpuOpsSession&&!locked);
 puts("Synthetic trusted-session marker checks passed; no RM/GPU calls");return 0;}
