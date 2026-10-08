#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint32_t NV_STATUS;
// STATUS_DEFINITIONS
enum { UVM_VA_RANGE_TYPE_MANAGED, UVM_VA_RANGE_TYPE_SEMAPHORE_POOL, UVM_VA_RANGE_TYPE_DEVICE_P2P };
typedef struct { uint64_t start,end; } node_t;
typedef struct { node_t node; int type; } uvm_va_range_t;
typedef struct { int mem; } pool_t;
typedef struct { uvm_va_range_t existing; bool collision; } tree_t;
typedef struct { tree_t va_range_tree; } uvm_va_space_t;
struct mm_struct { int unused; };
struct vm_area_struct { uint64_t vm_start,vm_end; void *vm_private_data,*vm_ops; };
typedef struct { struct vm_area_struct *vma; } uvm_vma_wrapper_t;
typedef struct { uvm_va_range_t va_range; uvm_vma_wrapper_t *vma_wrapper; } uvm_va_range_managed_t;
static int reclaim_calls,allocation_calls,add_calls,destroy_calls,fallback_calls;
static NV_STATUS hmm_status,add_status;
static bool allocation_fails;
static uint64_t checked_start,checked_end;
static uvm_va_range_managed_t allocated;
static pool_t pool;
static int uvm_vm_ops_semaphore_pool,uvm_vm_ops_device_p2p;
#define module_param(name,type,permissions)
#define MODULE_PARM_DESC(name,description)
#define UVM_ASSERT(value) do { if (!(value)) return NV_ERR_INVALID_ADDRESS; } while (0)
// PARAMETER_DEFINITION
static void *uvm_range_tree_iter_first(tree_t *tree,uint64_t start,uint64_t end) {
    checked_start=start;checked_end=end;
    return tree->collision && tree->existing.node.start<=end && tree->existing.node.end>=start ? &tree->existing : NULL;
}
static NV_STATUS uvm_hmm_va_block_reclaim(uvm_va_space_t *space,struct mm_struct *mm,uint64_t start,uint64_t end) {
    (void)space;(void)mm;(void)start;(void)end;reclaim_calls++;return hmm_status;
}
static uvm_va_range_managed_t *uvm_va_range_alloc_managed(uvm_va_space_t *space,uint64_t start,uint64_t end) {
    (void)space;allocation_calls++;allocated.va_range.node=(node_t){start,end};return allocation_fails ? NULL : &allocated;
}
static NV_STATUS uvm_range_tree_add(tree_t *tree,node_t *node) {
    (void)node;add_calls++;return tree->collision ? NV_ERR_UVM_ADDRESS_IN_USE : add_status;
}
static void uvm_va_range_destroy(uvm_va_range_t *range,void *mm) {(void)range;(void)mm;destroy_calls++;}
// ORIGINAL_PATCHED_FUNCTION
static uvm_va_range_t *uvm_va_range_find(uvm_va_space_t *space,uint64_t start) {
    tree_t *tree=&space->va_range_tree;
    return tree->collision && tree->existing.node.start<=start && tree->existing.node.end>=start ? &tree->existing : NULL;
}
static bool va_range_type_expects_mmap(int type) { return type==UVM_VA_RANGE_TYPE_SEMAPHORE_POOL || type==UVM_VA_RANGE_TYPE_DEVICE_P2P; }
static void uvm_vma_wrapper_destroy(void *wrapper) {(void)wrapper;}
static pool_t *uvm_va_range_to_semaphore_pool(uvm_va_range_t *range) {(void)range;return &pool;}
static NV_STATUS uvm_mem_map_cpu_user(int mem,uvm_va_space_t *space,struct vm_area_struct *vma) {
    (void)mem;(void)space;(void)vma;fallback_calls=1;return NV_OK;
}
static uvm_va_range_t *uvm_va_range_to_device_p2p(uvm_va_range_t *range) {return range;}
static NV_STATUS uvm_va_range_device_p2p_map_cpu(uvm_va_space_t *space,struct vm_area_struct *vma,uvm_va_range_t *range) {
    (void)space;(void)vma;(void)range;fallback_calls=2;return NV_OK;
}
NV_STATUS run_case(int enabled,int collision_mode,int reclaim_error,int fail_alloc,int insertion_error) {
    uvm_va_space_t storage={0},*va_space=&storage;
    struct vm_area_struct area={4096,8192,NULL,NULL},*vma=&area;
    uvm_vma_wrapper_t wrapper={vma};uvm_va_range_managed_t *out=(void*)1;
    bool vma_wrapper_allocated=true;
    (void)vma_wrapper_allocated;
    uvm_deny_managed_mmap=enabled;reclaim_calls=allocation_calls=add_calls=destroy_calls=fallback_calls=0;
    checked_start=checked_end=0;hmm_status=reclaim_error;allocation_fails=fail_alloc;add_status=insertion_error;
    storage.va_range_tree.collision=collision_mode!=0;
    storage.va_range_tree.existing=(uvm_va_range_t){{4096,8191},collision_mode==2 ? UVM_VA_RANGE_TYPE_DEVICE_P2P : UVM_VA_RANGE_TYPE_SEMAPHORE_POOL};
    if(collision_mode==3)storage.va_range_tree.existing.type=UVM_VA_RANGE_TYPE_MANAGED;
    if(collision_mode==4)storage.va_range_tree.existing.node.start=4112;
    if(collision_mode==5)storage.va_range_tree.existing.node=(node_t){8192,12287};
    if(collision_mode==6)storage.va_range_tree.existing.node=(node_t){4080,8207};
    NV_STATUS status=uvm_va_range_create_mmap(va_space,NULL,&wrapper,&out);
    // ORIGINAL_CALLER_COLLISION_BLOCK
    return status;
}
int counter(int index) { int values[]={reclaim_calls,allocation_calls,add_calls,destroy_calls,fallback_calls};return values[index]; }
uint64_t checked_bound(int end) {return end ? checked_end : checked_start;}
