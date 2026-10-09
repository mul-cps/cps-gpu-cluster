/* Qualification-only ABI shared by the OS shim and memacct.
 * No pointer or writable control is exposed to user space. */
#ifndef CPS_NATIVE_READONLY_CAP_H
#define CPS_NATIVE_READONLY_CAP_H
#define CPS_NATIVE_CAP_MAX_ROWS 256U
typedef struct CpsNativeCapRow
{
    NvU64 cgroupId;
    NvU64 kernfsId;
    NvU64 inode;
    NvU64 softLimit;
    NvU64 hardLimit;
    NvU64 currentUsed;
    NvU32 offline;
    NvU32 pinned;
    NvU32 defaultHierarchy;
} CpsNativeCapRow;
NvBool NV_API_CALL os_cps_readonly_cgroup(void *cgroup, CpsNativeCapRow *row);
NV_STATUS NV_API_CALL memacctGetCpsReadonlyCapSnapshot(NvU32 gpuId,
    CpsNativeCapRow *rows, NvU32 capacity, NvU32 *count);
NV_STATUS NV_API_CALL rm_cps_get_readonly_caps(void *stack, NvU32 gpuId,
    CpsNativeCapRow *rows, NvU32 capacity, NvU32 *count);
#endif
