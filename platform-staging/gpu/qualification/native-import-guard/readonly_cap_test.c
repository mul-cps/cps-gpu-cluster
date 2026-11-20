/* CPU fake maps exercise the actual read-only snapshot and OS shim. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t NvU32;
typedef uint64_t NvU64;
typedef int NvBool;
typedef int NV_STATUS;
#define NV_API_CALL
#define NV_TRUE 1
#define NV_FALSE 0
#define NV_OK 0
#define NV_ERR_INVALID_ARGUMENT 1
#define NV_ERR_NOT_SUPPORTED 2
#define NV_ERR_OBJECT_NOT_FOUND 3
#define NV_ERR_INVALID_STATE 4
#define NV_ERR_BUFFER_TOO_SMALL 5
#define CGROUP_IMPL_FALLBACK 1
#define NV_MISC_CGROUP_PRESENT
#define CSS_ONLINE 2
#define READ_ONCE(value) (value)
#include "readonly_cap.h"
struct kernfs_node { NvU64 id; };
static int cgrp_dfl_root;
struct cgroup { struct kernfs_node *kn; struct { unsigned flags; } self; int *root; };
static NvU64 cgroup_id(struct cgroup *group) { return group->kn->id; }
static NvU64 kernfs_ino(struct kernfs_node *kn) { return kn->id; }
#include "readonly_cap_os.c"
typedef struct ClientGroupLimits {
    NvU64 SoftLimit, HardLimit, Available;
    void *cpsPinnedGroup;
    NvU64 key;
} ClientGroupLimits;
typedef struct ClientGroupMap {
    ClientGroupLimits entries[CPS_NATIVE_CAP_MAX_ROWS + 1];
    NvU32 count;
} ClientGroupMap;
typedef struct GpuRegion { ClientGroupMap clientGroupMap; } GpuRegion;
typedef struct ClientGroupMapTypeIter {
    ClientGroupMap *map;
    NvU32 index;
    ClientGroupLimits *pValue;
} ClientGroupMapTypeIter;
static struct { int GpuRegionMap, impl; void *mutex; } g_memacct;
static GpuRegion region;
static int enabled, exists, acquired, released, locked;
static int os_cps_native_import_guard_enabled(void) { return enabled; }
static void portSyncMutexAcquire(void *mutex) { assert(mutex); assert(!locked); locked=1; acquired++; }
static void portSyncMutexRelease(void *mutex) { assert(mutex); assert(locked); locked=0; released++; }
static GpuRegion *mapFind(int *map, NvU32 gpu) { assert(map==&g_memacct.GpuRegionMap); assert(locked); return exists && gpu==123 ? &region : NULL; }
static ClientGroupMapTypeIter mapIterAll(ClientGroupMap *map) {
    ClientGroupMapTypeIter it = {map, 0, NULL}; assert(locked); return it;
}
static int mapIterNext(ClientGroupMapTypeIter *it) {
    assert(locked);
    if (it->index == it->map->count) return 0;
    it->pValue = &it->map->entries[it->index++]; return 1;
}
static NvU64 mapKey(ClientGroupMap *map, ClientGroupLimits *entry) {
    assert(map==&region.clientGroupMap); assert(locked); return entry->key;
}
#include "readonly_cap.c"
typedef struct { int dummy; } nvidia_stack_t;
typedef struct { int dummy; } THREAD_STATE_NODE;
#define THREAD_STATE_FLAGS_NONE 0
#define API_LOCK_FLAGS_NONE 0
#define RM_LOCK_MODULES_OSAPI 0
static int api_locked, api_error, enters, exits, inits, frees, altstack=1;
static NvBool rm_is_altstack_in_use(void) { return altstack; }
#define NV_ENTER_RM_RUNTIME(sp, fp) do { assert(!rm_is_altstack_in_use() || (sp)); (fp)=(sp); enters++; } while(0)
#define NV_EXIT_RM_RUNTIME(sp, fp) do { assert((fp)==(sp)); exits++; } while(0)
static void threadStateInit(THREAD_STATE_NODE *node, int flags) { (void)node; assert(flags==0); inits++; }
static void threadStateFree(THREAD_STATE_NODE *node, int flags) { (void)node; assert(flags==0); frees++; }
static int rmapiLockAcquire(int flags, int module) { assert(flags==0 && module==0); if (api_error) return api_error; assert(!api_locked); api_locked=1; return NV_OK; }
static void rmapiLockRelease(void) { assert(api_locked && !locked); api_locked=0; }
#include "readonly_cap_rm.c"

static void reset(struct cgroup *group) {
    memset(&region, 0, sizeof(region));
    enabled=exists=1; g_memacct.impl=CGROUP_IMPL_FALLBACK;
    g_memacct.mutex=&region; acquired=released=locked=0;
    region.clientGroupMap.count=1;
    region.clientGroupMap.entries[0]=(ClientGroupLimits){5120,5120,5120,group,(NvU64)group};
}

int main(void) {
    struct kernfs_node node = {UINT64_C(0x100000011)};
    struct cgroup group = {&node, {CSS_ONLINE}, &cgrp_dfl_root};
    CpsNativeCapRow rows[CPS_NATIVE_CAP_MAX_ROWS];
    NvU32 count;
    GpuRegion before;
    assert(sizeof(ino_t)==8);
    assert(sizeof(CpsNativeCapRow)==64);
    reset(&group); before=region;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_OK && count==1);
    assert(rows[0].offline==0 && rows[0].pinned==1 && rows[0].defaultHierarchy==1);
    assert(rows[0].inode==node.id && rows[0].kernfsId==node.id && rows[0].cgroupId==node.id);
    assert(rows[0].softLimit==5120 && rows[0].hardLimit==5120 && rows[0].currentUsed==0);
    assert(memcmp(&region,&before,sizeof(region))==0 && acquired==released && !locked);
    group.self.flags=0; /* removed path: retained pointer is still inspectable */
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_OK);
    assert(rows[0].offline==1 && rows[0].inode==node.id);
    region.clientGroupMap.entries[0].Available=5000;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_OK && rows[0].currentUsed==120);
    /* A retained backing reference keeps its bytes charged. The query must
     * report that fact, never turn offline into zero or unlimited. */
    assert(rows[0].offline && rows[0].softLimit==5120 && rows[0].hardLimit==5120);
    enabled=0;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_NOT_SUPPORTED && count==0);
    reset(&group); g_memacct.impl=0;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_NOT_SUPPORTED && count==0);
    reset(&group); g_memacct.mutex=NULL;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_NOT_SUPPORTED && count==0);
    reset(&group); exists=0;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_OBJECT_NOT_FOUND && count==0);
    reset(&group);
    assert(memacctGetCpsReadonlyCapSnapshot(124,rows,256,&count)==NV_ERR_OBJECT_NOT_FOUND && count==0);
    assert(memacctGetCpsReadonlyCapSnapshot(123,NULL,256,&count)==NV_ERR_INVALID_ARGUMENT && count==0);
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,0,&count)==NV_ERR_INVALID_ARGUMENT && count==0);
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,257,&count)==NV_ERR_INVALID_ARGUMENT && count==0);
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,NULL)==NV_ERR_INVALID_ARGUMENT);
    reset(&group); region.clientGroupMap.entries[0].cpsPinnedGroup=NULL;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    reset(&group); region.clientGroupMap.entries[0].key++;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    reset(&group); region.clientGroupMap.entries[0].Available=5121;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    reset(&group); region.clientGroupMap.entries[0].SoftLimit=5121;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    reset(&group); group.root=NULL;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    group.root=&cgrp_dfl_root; node.id=0;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_INVALID_STATE && count==0);
    node.id=17; reset(&group); region.clientGroupMap.count=0;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_OK && count==0);
    reset(&group);
    for (unsigned i=1; i<=256; i++) region.clientGroupMap.entries[i]=region.clientGroupMap.entries[0];
    region.clientGroupMap.count=256;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_OK && count==256);
    region.clientGroupMap.count=257; before=region;
    assert(memacctGetCpsReadonlyCapSnapshot(123,rows,256,&count)==NV_ERR_BUFFER_TOO_SMALL && count==0);
    assert(memcmp(&region,&before,sizeof(region))==0);
    assert(acquired==released && !locked);
    reset(&group); nvidia_stack_t stack={0};
    assert(rm_cps_get_readonly_caps(&stack,123,rows,256,&count)==NV_OK && count==1);
    assert(!api_locked && !locked && enters==exits && inits==frees);
    api_error=NV_ERR_INVALID_STATE; count=99;
    assert(rm_cps_get_readonly_caps(&stack,123,rows,256,&count)==api_error && count==0);
    assert(!api_locked && !locked && enters==exits && inits==frees);
    assert(rm_cps_get_readonly_caps(NULL,123,rows,256,&count)==NV_ERR_INVALID_ARGUMENT);
    /* Linux stack allocation returns success with NULL when NVIDIA's optional
     * alternate stack is disabled. The real RM wrapper must accept this. */
    api_error=0; altstack=0; count=99;
    assert(rm_cps_get_readonly_caps(NULL,123,rows,256,&count)==NV_OK && count==1);
    assert(!api_locked && !locked && enters==exits && inits==frees);
    assert(rm_cps_get_readonly_caps(NULL,123,rows,256,NULL)==NV_ERR_INVALID_ARGUMENT);
    altstack=1;
    api_error=0; exists=0;
    assert(rm_cps_get_readonly_caps(&stack,123,rows,256,&count)==NV_ERR_OBJECT_NOT_FOUND && count==0);
    assert(!api_locked && !locked && enters==exits && inits==frees);
    return 0;
}
