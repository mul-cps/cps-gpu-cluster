/* Read-only complete snapshot. The retained map entry and cgroup are untouched.
 * Used bytes remain charged until the last MemoryCharge reference is released.
 * Zero-size handles are not enumerated; preserving the pin makes them safe. */
NV_STATUS NV_API_CALL memacctGetCpsReadonlyCapSnapshot(NvU32 gpuId,
    CpsNativeCapRow *rows, NvU32 capacity, NvU32 *count)
{
    NV_STATUS status = NV_ERR_INVALID_STATE;
    GpuRegion *region;
    ClientGroupMapTypeIter iter;
    NvU32 written = 0;
    if (count == NULL)
        return NV_ERR_INVALID_ARGUMENT;
    *count = 0;
    if (rows == NULL || capacity == 0 || capacity > CPS_NATIVE_CAP_MAX_ROWS)
        return NV_ERR_INVALID_ARGUMENT;
    if (!os_cps_native_import_guard_enabled()
        || g_memacct.impl != CGROUP_IMPL_FALLBACK || g_memacct.mutex == NULL)
        return NV_ERR_NOT_SUPPORTED;
    portSyncMutexAcquire(g_memacct.mutex);
    region = mapFind(&g_memacct.GpuRegionMap, gpuId);
    if (region == NULL)
    {
        status = NV_ERR_OBJECT_NOT_FOUND;
        goto done;
    }
    iter = mapIterAll(&region->clientGroupMap);
    while (mapIterNext(&iter))
    {
        ClientGroupLimits *limits = iter.pValue;
        CpsNativeCapRow *row;
        if (written == capacity)
        {
            status = NV_ERR_BUFFER_TOO_SMALL;
            goto done;
        }
        if (limits->cpsPinnedGroup == NULL
            || mapKey(&region->clientGroupMap, limits) != (NvU64)limits->cpsPinnedGroup
            || limits->Available > limits->HardLimit
            || limits->SoftLimit > limits->HardLimit)
            goto done;
        row = &rows[written];
        if (!os_cps_readonly_cgroup(limits->cpsPinnedGroup, row))
            goto done;
        row->pinned = 1;
        row->softLimit = limits->SoftLimit;
        row->hardLimit = limits->HardLimit;
        row->currentUsed = limits->HardLimit - limits->Available;
        written++;
    }
    *count = written;
    status = NV_OK;
done:
    portSyncMutexRelease(g_memacct.mutex);
    return status;
}
