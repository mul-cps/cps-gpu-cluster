/* Mark only the private GPU-ops session client created by this kernel entry.
 * No user allocation parameter or cached privilege grants this authority. */
static NV_STATUS nvGpuOpsMarkProtectedSession(NvHandle hClient)
{
    nvGpuOpsLockSet acquiredLocks;
    RsClient *pClient = NULL;
    RmClient *pRmClient;
    NV_STATUS status;
    if (!os_cps_native_import_guard_enabled())
        return NV_OK;
    status = _nvGpuOpsLocksAcquire(RMAPI_LOCK_FLAGS_NONE, hClient, &pClient,
                                   0, 0, 0, &acquiredLocks);
    if (status != NV_OK)
        return status;
    pRmClient = dynamicCast(pClient, RmClient);
    if (pRmClient == NULL || pRmClient->pOsPidInfo != NULL ||
        pRmClient->cachedPrivilege < RS_PRIV_LEVEL_KERNEL)
        status = NV_ERR_INSUFFICIENT_PERMISSIONS;
    else
        pRmClient->bCpsGpuOpsSession = NV_TRUE;
    _nvGpuOpsLocksRelease(&acquiredLocks);
    return status;
}
