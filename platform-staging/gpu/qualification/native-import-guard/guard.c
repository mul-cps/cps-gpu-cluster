/* CPS qualification-only R615.71.09 import guard. Not deployed/qualified.
 * Requires fallback/misc native accounting; no MPS delegation is authorized.
 * Incorporated into NVIDIA MIT-licensed memacct.c by render_patch.py. */
NV_STATUS memacctValidateMemoryImport(MemoryCharge *pCharge, NvU32 gpuId,
                                     RmClient *pDestination)
{
    NV_STATUS status = NV_ERR_INSUFFICIENT_PERMISSIONS;
    GpuRegion *pRegion;
    ClientGroupID actorGroup, destinationGroup;
    ClientGroupID actorLeaf = NULL, destinationLeaf = NULL;
    void *pidInfo;

    /* Immutable load-time opt-in; default-off preserves unmodified behavior. */
    if (!os_cps_native_import_guard_enabled())
        return NV_OK;

    /* Enabled mode requires native accounting; absence cannot authorize imports. */
    if (g_memacct.impl == CGROUP_IMPL_NONE)
        return NV_ERR_NOT_SUPPORTED;
    /* dmem's charge has no fallback cligrp; reject rather than reinterpret it. */
    if (g_memacct.impl != CGROUP_IMPL_FALLBACK || g_memacct.mutex == NULL)
        return NV_ERR_NOT_SUPPORTED;

    /* Preserve the real PID reference: find_vpid(host-tgid) is namespace-relative. */
    pidInfo = osGetPidInfo();
    if (pidInfo == NULL)
        return NV_ERR_INSUFFICIENT_PERMISSIONS;
    actorLeaf = os_cps_cgroup_get_from_pid_info(pidInfo, OS_CGROUP_IMPL_MISC);
    actorGroup = actorLeaf;

    portSyncMutexAcquire(g_memacct.mutex);
    pRegion = mapFind(&g_memacct.GpuRegionMap, gpuId);
    if (pRegion == NULL)
    {
        status = NV_ERR_OBJECT_NOT_FOUND;
        goto done;
    }
    /* Before any GPU caps exist, retain normal driver boot/internal behavior.
     * This is NOT a protected state. No CUDA workload may start before its cap. */
    if (mapCount(&pRegion->clientGroupMap) == 0)
    {
        status = NV_OK;
        goto done;
    }
    /* Once caps exist, uncharged/foreign/ambiguous backing is never authorized. */
    if (pCharge == NULL || pCharge->cligrp == NULL || pCharge->gpuId != gpuId ||
        actorGroup == NULL ||
        memacctLimitsForGroupLocked(pRegion, &actorGroup) == NULL ||
        actorGroup != pCharge->cligrp)
        goto done;

    if (pDestination == NULL)
        goto done;
    if (pDestination->pOsPidInfo != NULL)
    {
        destinationLeaf = os_cps_cgroup_get_from_pid_info(pDestination->pOsPidInfo, OS_CGROUP_IMPL_MISC);
        destinationGroup = destinationLeaf;
        if (destinationGroup == NULL ||
            memacctLimitsForGroupLocked(pRegion, &destinationGroup) == NULL ||
            destinationGroup != actorGroup)
            goto done;
    }
    else if (pDestination->cachedPrivilege < RS_PRIV_LEVEL_KERNEL)
    {
        /* Missing user identity is not equivalent to a trusted kernel client. */
        goto done;
    }
    /* A kernel intermediary has no independent user authority. It is allowed
     * only with an actual capped actor matching the original charged backing.
     * Uncapped MPS/worker delegation fails closed, including retained handles. */
    status = NV_OK;
done:
    portSyncMutexRelease(g_memacct.mutex);
    if (destinationLeaf != NULL)
        os_cgroup_put(destinationLeaf);
    if (actorLeaf != NULL)
        os_cgroup_put(actorLeaf);
    osPutPidInfo(pidInfo);
    return status;
}
