/* Called only after a new entry has been inserted successfully under mutex.
 * Updates never acquire another reference. Default-off retains baseline lifetime. */
static void memacctPinLimitGroup(ClientGroupLimits *pLimits, ClientGroupID cligrp)
{
    pLimits->cpsPinnedGroup = NULL;
    if (os_cps_native_import_guard_enabled())
    {
        os_cgroup_get(cligrp);
        pLimits->cpsPinnedGroup = cligrp;
    }
}
static void memacctUnpinLimitGroups(GpuRegion *pRegion)
{
    ClientGroupMapTypeIter iter = mapIterAll(&pRegion->clientGroupMap);
    while (mapIterNext(&iter))
    {
        ClientGroupLimits *pLimits = iter.pValue;
        if (pLimits->cpsPinnedGroup != NULL)
        {
            os_cgroup_put(pLimits->cpsPinnedGroup);
            pLimits->cpsPinnedGroup = NULL;
        }
    }
}
