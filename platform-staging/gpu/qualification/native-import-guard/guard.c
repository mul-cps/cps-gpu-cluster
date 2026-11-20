/* CPS qualification-only R615.71.09 import guard. Not deployed/qualified.
 * Requires fallback/misc native accounting; no MPS delegation is authorized.
 * Incorporated into NVIDIA MIT-licensed memacct.c by render_patch.py. */
NV_STATUS memacctValidateMemoryImport(MemoryCharge *pCharge, NvU32 gpuId,
                                     RmClient *pDestination)
{
    NV_STATUS status = NV_ERR_INSUFFICIENT_PERMISSIONS;
    GpuRegion *pRegion;
    ClientGroupID actorGroup, destinationGroup;
    ClientGroupLimits *pActorLimits;
    ClientGroupID actorLeaf = NULL, destinationLeaf = NULL;
    void *pidInfo;
    NvU32 reason = 0, clientKind = 0;


    /* Immutable load-time opt-in; default-off preserves unmodified behavior. */
    if (!os_cps_native_import_guard_enabled())
        return NV_OK;

    if (pDestination != NULL)
        clientKind = (pDestination->bCpsGpuOpsSession ? 1U : 0U) |
                     (pDestination->bCpsObjExportClient ? 2U : 0U) |
                     (pDestination->pOsPidInfo != NULL ? 4U : 0U);

    /* Enabled mode requires native accounting; absence cannot authorize imports. */
    if (g_memacct.impl == CGROUP_IMPL_NONE)
    {
        os_cps_native_import_denied(gpuId, 11, clientKind, NV_ERR_NOT_SUPPORTED);
        return NV_ERR_NOT_SUPPORTED;
    }
    /* dmem's charge has no fallback cligrp; reject rather than reinterpret it. */
    if (g_memacct.impl != CGROUP_IMPL_FALLBACK || g_memacct.mutex == NULL)
    {
        os_cps_native_import_denied(gpuId, 11, clientKind, NV_ERR_NOT_SUPPORTED);
        return NV_ERR_NOT_SUPPORTED;
    }

    /* Preserve the real PID reference: find_vpid(host-tgid) is namespace-relative. */
    pidInfo = osGetPidInfo();
    if (pidInfo == NULL)
    {
        os_cps_native_import_denied(gpuId, 1, clientKind, status);
        return NV_ERR_INSUFFICIENT_PERMISSIONS;
    }
    actorLeaf = os_cps_cgroup_get_from_pid_info(pidInfo, OS_CGROUP_IMPL_MISC);
    actorGroup = actorLeaf;

    portSyncMutexAcquire(g_memacct.mutex);
    pRegion = mapFind(&g_memacct.GpuRegionMap, gpuId);
    if (pRegion == NULL)
    {
        status = NV_ERR_OBJECT_NOT_FOUND;
        reason = 2;
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
    if (pCharge == NULL || pCharge->cligrp == NULL || pCharge->gpuId != gpuId)
    {
        reason = 3;
        goto done;
    }
    if (actorGroup == NULL)
    {
        reason = 4;
        goto done;
    }
    pActorLimits = memacctLimitsForGroupLocked(pRegion, &actorGroup);
    if (pActorLimits == NULL || pActorLimits->HardLimit == 0 ||
        pActorLimits->HardLimit == (NvLength)-1)
    {
        reason = 5;
        goto done;
    }
    if (actorGroup != pCharge->cligrp)
    {
        reason = 6;
        goto done;
    }
    if (pDestination == NULL)
    {
        reason = 7;
        goto done;
    }
    if (pDestination->pOsPidInfo != NULL)
    {
        destinationLeaf = os_cps_cgroup_get_from_pid_info(pDestination->pOsPidInfo, OS_CGROUP_IMPL_MISC);
        destinationGroup = destinationLeaf;
        if (destinationGroup == NULL)
        {
            reason = 8;
            goto done;
        }
        if (memacctLimitsForGroupLocked(pRegion, &destinationGroup) == NULL ||
            destinationGroup != actorGroup)
        {
            reason = 9;
            goto done;
        }
    }
    else if ((!pDestination->bCpsGpuOpsSession && !pDestination->bCpsObjExportClient) ||
             pDestination->cachedPrivilege < RS_PRIV_LEVEL_KERNEL)
    {
        /* Missing user identity is not equivalent to a trusted kernel client. */
        reason = 10;
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
    if (status != NV_OK)
        os_cps_native_import_denied(gpuId, reason, clientKind, status);
    return status;
}
