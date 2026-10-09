/* This file is called only for the fresh private rmobjexportimport kernel client.
 * The caller already owns the RM API lock; never reacquire it here. */
static NV_STATUS RmMarkProtectedObjExportClient(NvHandle hClient)
{
    CLIENT_ENTRY *pEntry = NULL;
    RmClient *pClient;
    NV_STATUS status;
    if (!os_cps_native_import_guard_enabled())
        return NV_OK;
    if (!rmapiLockIsOwner())
        return NV_ERR_INVALID_LOCK_STATE;
    status = serverAcquireClient(&g_resServ, hClient, LOCK_ACCESS_WRITE, &pEntry);
    if (status != NV_OK)
        return status;
    pClient = dynamicCast(pEntry->pClient, RmClient);
    if (pClient == NULL || pClient->pOsPidInfo != NULL ||
        pClient->cachedPrivilege < RS_PRIV_LEVEL_KERNEL)
        status = NV_ERR_INSUFFICIENT_PERMISSIONS;
    else
        pClient->bCpsObjExportClient = NV_TRUE;
    serverReleaseClient(&g_resServ, LOCK_ACCESS_WRITE, pEntry);
    return status;
}
