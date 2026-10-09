/* Opt-in fallback allocator: keep actor and creator leaf refs until charge ends.
 * No charge may silently disappear for dead/foreign/uncapped RM creators. */
static NV_STATUS memacctTryChargeProtected(RmClient *pRmClient, NvU32 gpuId,
                                          NvLength size, MemoryCharge **ppCharge)
{
    NV_STATUS status = NV_ERR_INSUFFICIENT_PERMISSIONS;
    ClientGroupID actorLeaf = NULL, creatorLeaf = NULL, actorGroup, creatorGroup;
    void *pidInfo = NULL;
    MemoryCharge *pCharge = NULL;
    GpuRegion *pRegion;
    ClientGroupLimits *pActorLimits, *pCreatorLimits;
    NvBool bOperatorBypass = NV_FALSE;
    *ppCharge = NULL;
    if (g_memacct.impl != CGROUP_IMPL_FALLBACK || g_memacct.mutex == NULL)
        return NV_ERR_NOT_SUPPORTED;

    /* Boot before any cap exists is explicitly unprotected. Controller gates
     * every workload on its own cap readback before CUDA initialization. */
    portSyncMutexAcquire(g_memacct.mutex);
    pRegion = mapFind(&g_memacct.GpuRegionMap, gpuId);
    if (pRegion == NULL)
        status = NV_ERR_OBJECT_NOT_FOUND;
    else if (mapCount(&pRegion->clientGroupMap) == 0)
        status = NV_OK;
    portSyncMutexRelease(g_memacct.mutex);
    if (status != NV_ERR_INSUFFICIENT_PERMISSIONS)
        return status;

    if (pRmClient == NULL || pRmClient->pOsPidInfo == NULL)
        goto cleanup;
    pidInfo = osGetPidInfo();
    if (pidInfo == NULL)
        goto cleanup;
    actorLeaf = os_cps_cgroup_get_from_pid_info(pidInfo, OS_CGROUP_IMPL_MISC);
    creatorLeaf = os_cps_cgroup_get_from_pid_info(pRmClient->pOsPidInfo, OS_CGROUP_IMPL_MISC);
    if (actorLeaf == NULL || creatorLeaf == NULL)
        goto cleanup;
    actorGroup = actorLeaf;
    creatorGroup = creatorLeaf;
    pCharge = portMemAllocNonPaged(sizeof *pCharge);
    if (pCharge == NULL)
    {
        status = NV_ERR_NO_MEMORY;
        goto cleanup;
    }
    portSyncMutexAcquire(g_memacct.mutex);
    pRegion = mapFind(&g_memacct.GpuRegionMap, gpuId);
    if (pRegion == NULL)
        status = NV_ERR_OBJECT_NOT_FOUND;
    else
    {
        pActorLimits = memacctLimitsForGroupLocked(pRegion, &actorGroup);
        pCreatorLimits = memacctLimitsForGroupLocked(pRegion, &creatorGroup);
        if (pActorLimits == NULL && pCreatorLimits == NULL &&
            actorLeaf == creatorLeaf && osIsAdministrator())
        {
            /* Explicit trusted host-operator boundary, never cached privilege.
             * Both creators remain alive and refer to the same uncapped leaf.
             * Host MPS is excluded from the protected workload path. */
            bOperatorBypass = NV_TRUE;
            status = NV_OK;
        }
        else if (pActorLimits == NULL || pCreatorLimits == NULL || actorGroup != creatorGroup)
            status = NV_ERR_INSUFFICIENT_PERMISSIONS;
        else
            status = memacctTryChargeInternalLocked(pRegion, creatorGroup, gpuId, size, pCharge);
    }
    portSyncMutexRelease(g_memacct.mutex);

    if (!bOperatorBypass && (status == NV_OK || status == NV_WARN_RESOURCE_ACCOUNTING_SOFT_LIMIT_EXCEEDED))
    {
        pCharge->gpuId = gpuId;
        pCharge->pid = pRmClient->ProcID;
        *ppCharge = pCharge;
        pCharge = NULL;
        if (status == NV_WARN_RESOURCE_ACCOUNTING_SOFT_LIMIT_EXCEEDED)
        {
            gpuNotifySubDeviceEvent(gpumgrGetGpuFromId(gpuId), NV2080_NOTIFIERS_MEMACCT_SOFT_LIMIT_EXCEEDED,
                NULL, 0, pRmClient->ProcID, 0);
            status = NV_OK;
        }
    }
cleanup:
    portMemFree(pCharge);
    if (creatorLeaf != NULL)
        os_cgroup_put(creatorLeaf);
    if (actorLeaf != NULL)
        os_cgroup_put(actorLeaf);
    if (pidInfo != NULL)
        osPutPidInfo(pidInfo);
    return status;
}
