/* Actual proc callback against CPU stubs: every-read credentials, PM locking,
 * fail-closed snapshot, exact finite detached-row output, no write operation. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stddef.h>
#include <sys/types.h>
#include <errno.h>
typedef uint32_t NvU32;
typedef uint64_t NvU64;
typedef int NvBool;
typedef int NV_STATUS;
#define NV_API_CALL
#define NV_OK 0
#define NV_ERR_BUFFER_TOO_SMALL 2
#define NV_ERR_OBJECT_NOT_FOUND 3
#define GFP_KERNEL 0
#define GLOBAL_ROOT_UID 0
#define CAP_SYS_ADMIN 21
#define __user
#define NV_PROC_OPS_SET_OWNER()
#define NV_PROC_OPS_OPEN open
#define NV_PROC_OPS_READ read
#define NV_PROC_OPS_LSEEK lseek
#define NV_PROC_OPS_RELEASE release
#define NV_PDE_DATA(inode) ((inode)->data)
#include "readonly_cap.h"
typedef struct { int dummy; } nvidia_stack_t;
typedef struct { NvU32 gpu_id; struct { int valid; } nv_uuid_cache; } nv_state_t;
struct seq_file { void *private; char data[2048]; size_t used; };
struct inode { void *data; };
struct file { struct seq_file seq; int (*show)(struct seq_file *,void *); };
typedef struct {
    int (*open)(struct inode *,struct file *);
    ssize_t (*read)(struct file *,char *,size_t,loff_t *);
    loff_t (*lseek)(struct file *,loff_t,int);
    int (*release)(struct inode *,struct file *);
} nv_proc_ops_t;
static int uid, cap, enabled=1, init_user_ns, nv_system_pm_lock;
static int pm_locked, pm_error, snapshots, snapshot_error, stack_error, uuid_error;
static int current_euid(void) { return uid; }
static int uid_eq(int a,int b) { return a==b; }
static int ns_capable(int *ns,int which) { assert(ns==&init_user_ns && which==CAP_SYS_ADMIN); return cap; }
static int os_cps_native_import_guard_enabled(void) { return enabled; }
static void *kcalloc(size_t n,size_t size,int flags) { assert(flags==0); return calloc(n,size); }
static void kfree(void *p) { free(p); }
static int nv_kmem_cache_alloc_stack(nvidia_stack_t **sp) { if(stack_error) return -1; *sp=malloc(sizeof(**sp)); assert(*sp); return 0; }
static void nv_kmem_cache_free_stack(nvidia_stack_t *sp) { free(sp); }
static char *rm_get_gpu_uuid(nvidia_stack_t *sp,nv_state_t *nv) {
    char *s; assert(sp && nv->gpu_id==123); if(uuid_error) return NULL;
    s=malloc(41); strcpy(s,"GPU-16128952-b438-556a-00bb-93039ee24e56"); return s;
}
static void os_free_mem(void *p) { free(p); }
NV_STATUS NV_API_CALL rm_cps_get_readonly_caps(void *stack,NvU32 gpuId,CpsNativeCapRow *rows,NvU32 capacity,NvU32 *count) {
    assert(stack && gpuId==123 && capacity==256 && pm_locked);
    snapshots++; if(snapshot_error) return snapshot_error;
    *count=1; rows[0]=(CpsNativeCapRow){4294967313ULL,4294967313ULL,4294967313ULL,5368709120ULL,5368709120ULL,0,1,1,1}; return NV_OK;
}
static void seq_printf(struct seq_file *s,const char *format,...) {
    va_list args; va_start(args,format);
    int written=vsnprintf(s->data+s->used,sizeof(s->data)-s->used,format,args);
    va_end(args); assert(written>=0 && (size_t)written<sizeof(s->data)-s->used); s->used+=(size_t)written;
}
static void seq_puts(struct seq_file *s,const char *value) { seq_printf(s,"%s",value); }
static int single_open(struct file *f,int (*show)(struct seq_file *,void *),void *data) {
    f->seq.private=data; f->seq.used=0; f->show=show; return 0;
}
static int nv_down_read_interruptible(int *lock) { assert(lock==&nv_system_pm_lock); if(pm_error) return pm_error; assert(!pm_locked); pm_locked=1; return 0; }
static void up_read(int *lock) { assert(lock==&nv_system_pm_lock && pm_locked); pm_locked=0; }
static ssize_t seq_read(struct file *f,char *buffer,size_t size,loff_t *position) {
    int rc; assert(pm_locked); f->seq.used=0; rc=f->show(&f->seq,NULL);
    if(rc) return rc;
    assert(size>f->seq.used);
    memcpy(buffer,f->seq.data,f->seq.used+1);
    *position+=(loff_t)f->seq.used; return (ssize_t)f->seq.used;
}
static int single_release(struct inode *inode,struct file *file) { (void)inode;(void)file;return 0; }
#include "readonly_cap_proc.c"

int main(void) {
    nv_state_t nv={123,{1}}; struct inode inode={&nv}; struct file file;
    char output[2048]; loff_t position=0;
    cap=1; uid=1000;
    assert(nv_procfs_cps_native_caps_fops.lseek==NULL); /* no unlocked seq_lseek->show path */
    assert(nv_procfs_cps_native_caps_fops.open(&inode,&file)==-EPERM && snapshots==0);
    uid=0; cap=0;
    assert(nv_procfs_cps_native_caps_fops.open(&inode,&file)==-EPERM && snapshots==0);
    cap=1; enabled=0;
    assert(nv_procfs_cps_native_caps_fops.open(&inode,&file)==-EPERM && snapshots==0);
    enabled=1;
    assert(nv_procfs_cps_native_caps_fops.open(&inode,&file)==0);
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)>0);
    assert(strstr(output,"\"offline\":true") && strstr(output,"\"inode\":4294967313"));
    assert(strstr(output,"\"hard\":5368709120,\"used\":0") && !pm_locked && snapshots==1);
    uid=1000; /* already-open descriptor passed to an untrusted account */
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EPERM && snapshots==1);
    uid=0; cap=0;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EPERM && snapshots==1);
    cap=1; snapshot_error=NV_ERR_BUFFER_TOO_SMALL;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EOVERFLOW && file.seq.used==0 && !pm_locked);
    snapshot_error=NV_ERR_OBJECT_NOT_FOUND;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EIO && file.seq.used==0 && !pm_locked);
    snapshot_error=0; pm_error=-EINTR; int previous=snapshots;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EINTR && snapshots==previous && !pm_locked);
    pm_error=0; stack_error=1;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EIO && file.seq.used==0 && !pm_locked);
    stack_error=0; uuid_error=1;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EIO && file.seq.used==0 && !pm_locked);
    uuid_error=0; nv.nv_uuid_cache.valid=0;
    assert(nv_procfs_cps_native_caps_fops.read(&file,output,sizeof(output),&position)==-EIO && file.seq.used==0 && !pm_locked);
    assert(nv_procfs_cps_native_caps_fops.release(&inode,&file)==0);
    return 0;
}
