/* CPU-only exact export marker helper and lock ownership fixture. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef unsigned NvHandle;typedef int NV_STATUS;
enum {NV_OK,NV_ERR_INSUFFICIENT_PERMISSIONS,NV_ERR_INVALID_LOCK_STATE,NV_ERR_OBJECT_NOT_FOUND,RS_PRIV_LEVEL_KERNEL=10,LOCK_ACCESS_WRITE=1,NV_TRUE=1};
typedef struct {void *pOsPidInfo;int cachedPrivilege,bCpsObjExportClient;} RmClient;
typedef struct {RmClient *pClient;} CLIENT_ENTRY;
static RmClient client;static CLIENT_ENTRY entry;static int enabled,api_owner,locked,lock_status,cast_ok,g_resServ;
static int os_cps_native_import_guard_enabled(void){return enabled;}
static int rmapiLockIsOwner(void){return api_owner;}
static NV_STATUS serverAcquireClient(int *server,NvHandle handle,int flags,CLIENT_ENTRY **out){assert(server==&g_resServ&&handle==42&&flags==LOCK_ACCESS_WRITE&&!locked&&api_owner);if(lock_status)return lock_status;locked=1;*out=&entry;return NV_OK;}
static void serverReleaseClient(int *server,int flags,CLIENT_ENTRY *p){assert(server==&g_resServ&&flags==LOCK_ACCESS_WRITE&&p==&entry&&locked);locked=0;}
#define dynamicCast(p,t) (cast_ok?(p):NULL)
#include "object_export_client.c"
static void reset(void){client=(RmClient){NULL,RS_PRIV_LEVEL_KERNEL,0};entry.pClient=&client;enabled=api_owner=cast_ok=1;locked=lock_status=0;}
int main(void){
 reset();assert(RmMarkProtectedObjExportClient(42)==NV_OK&&client.bCpsObjExportClient&&!locked);
 reset();enabled=0;api_owner=0;assert(RmMarkProtectedObjExportClient(42)==NV_OK&&!client.bCpsObjExportClient&&!locked);
 reset();api_owner=0;assert(RmMarkProtectedObjExportClient(42)==NV_ERR_INVALID_LOCK_STATE&&!locked);
 reset();client.pOsPidInfo=(void*)1;assert(RmMarkProtectedObjExportClient(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!client.bCpsObjExportClient&&!locked);
 reset();client.cachedPrivilege=0;assert(RmMarkProtectedObjExportClient(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!locked);
 reset();cast_ok=0;assert(RmMarkProtectedObjExportClient(42)==NV_ERR_INSUFFICIENT_PERMISSIONS&&!locked);
 reset();lock_status=NV_ERR_OBJECT_NOT_FOUND;assert(RmMarkProtectedObjExportClient(42)==lock_status&&!locked);
 puts("Synthetic private export-client marker checks passed; no RM/GPU calls");return 0;}
