/* Synthetic CPU driver functions test control flow only. Never dlopen libcuda. */
#define main qualification_main
#include "native_imports.c"
#undef main
#include <assert.h>
static int allocations,releases,reserves,unmaps,touches,over_result,reserve_error,unmap_error,over_mapped;
static CUresult CUDAAPI gran(size_t *g,const CUmemAllocationProp *p,CUmemAllocationGranularity_flags f){(void)p;(void)f;*g=2*MIB;return CUDA_SUCCESS;}
static CUresult CUDAAPI create(CUmemGenericAllocationHandle *h,size_t n,const CUmemAllocationProp *p,unsigned long long f){(void)p;(void)f;if(n>PAYLOAD&&over_result!=CUDA_SUCCESS)return (CUresult)over_result;*h=(CUmemGenericAllocationHandle)++allocations;return CUDA_SUCCESS;}
static CUresult CUDAAPI release(CUmemGenericAllocationHandle h){assert(h);releases++;return CUDA_SUCCESS;}
static CUresult CUDAAPI reserve(CUdeviceptr *p,size_t n,size_t a,CUdeviceptr fixed,unsigned long long f){(void)a;(void)fixed;(void)f;assert(n==PAYLOAD);if(reserve_error)return CUDA_ERROR_OUT_OF_MEMORY;*p=0x100000+(CUdeviceptr)++reserves*PAYLOAD;return CUDA_SUCCESS;}
static CUresult CUDAAPI address_free(CUdeviceptr p,size_t n){assert(p&&n==PAYLOAD);return CUDA_SUCCESS;}
static CUresult CUDAAPI map(CUdeviceptr p,size_t n,size_t o,CUmemGenericAllocationHandle h,unsigned long long f){(void)o;(void)f;assert(p&&n==PAYLOAD&&h);if(h==2)over_mapped++;return CUDA_SUCCESS;}
static CUresult CUDAAPI unmap(CUdeviceptr p,size_t n){assert(p&&n==PAYLOAD);unmaps++;return unmap_error?CUDA_ERROR_INVALID_VALUE:CUDA_SUCCESS;}
static CUresult CUDAAPI grant_access(CUdeviceptr p,size_t n,const CUmemAccessDesc *d,size_t count){assert(p&&n==PAYLOAD&&count==1&&d->flags==CU_MEM_ACCESS_FLAGS_PROT_READWRITE);return CUDA_SUCCESS;}
static unsigned char current;
static CUresult CUDAAPI fill(CUdeviceptr p,unsigned char v,size_t n){assert(p&&n==PAYLOAD);current=v;touches++;return CUDA_SUCCESS;}
static CUresult CUDAAPI sync_context(void){return CUDA_SUCCESS;}
static CUresult CUDAAPI readback(void *out,CUdeviceptr p,size_t n){assert(p&&n==1);*(unsigned char*)out=current;return CUDA_SUCCESS;}
static CUresult CUDAAPI info(size_t *free_bytes,size_t *total){*total=512*MIB;*free_bytes=90*MIB;return CUDA_SUCCESS;}
static void reset(void){failed=allocations=releases=reserves=unmaps=touches=reserve_error=unmap_error=over_mapped=0;over_result=CUDA_ERROR_OUT_OF_MEMORY;}
int main(void){
 api.cuMemGetAllocationGranularity=gran;api.cuMemCreate=create;api.cuMemRelease=release;api.cuMemAddressReserve=reserve;api.cuMemAddressFree=address_free;api.cuMemMap=map;api.cuMemUnmap=unmap;api.cuMemSetAccess=grant_access;api.cuMemsetD8=fill;api.cuCtxSynchronize=sync_context;api.cuMemcpyDtoH=readback;api.cuMemGetInfo=info;
 reset();assert(direct_vmm(0,512*MIB)==0);assert(allocations==2&&releases==2&&touches==2&&unmaps==2&&!failed);
 reset();over_result=CUDA_SUCCESS;assert(direct_vmm(0,512*MIB)==-1);assert(allocations==2&&releases==2&&touches==1&&unmaps==1&&over_mapped==0);
 reset();over_result=CUDA_ERROR_NOT_SUPPORTED;assert(direct_vmm(0,512*MIB)==-1);assert(allocations==1&&releases==1&&touches==1);
 reset();reserve_error=1;assert(direct_vmm(0,512*MIB)==-1);assert(allocations==1&&releases==1&&touches==0);
 reset();unmap_error=1;assert(direct_vmm(0,512*MIB)==-1);assert(releases==1&&failed);
 puts("CPU allocation/cleanup regression checks passed; real GPU calls=0");return 0;
}
