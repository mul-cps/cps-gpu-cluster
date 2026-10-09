/* Kernel entry follows the existing RM runtime/stack discipline. The API lock
 * protects g_memacct.mutex lifetime against memacctRemoveGpu's last-GPU destroy.
 * The inner snapshot acquires the accounting mutex in the normal RM order. */
NV_STATUS NV_API_CALL rm_cps_get_readonly_caps(void *stack, NvU32 gpuId,
    CpsNativeCapRow *rows, NvU32 capacity, NvU32 *count)
{
    nvidia_stack_t *sp = stack;
    THREAD_STATE_NODE threadState;
    NV_STATUS status;
    void *fp;
    /* Vendor stack allocation deliberately returns NULL when the optional RM
     * alternate stack is disabled; NV_ENTER_RM_RUNTIME is then a no-op. */
    if ((sp == NULL && rm_is_altstack_in_use()) || count == NULL)
        return NV_ERR_INVALID_ARGUMENT;
    *count = 0;
    NV_ENTER_RM_RUNTIME(sp, fp);
    threadStateInit(&threadState, THREAD_STATE_FLAGS_NONE);
    status = rmapiLockAcquire(API_LOCK_FLAGS_NONE, RM_LOCK_MODULES_OSAPI);
    if (status == NV_OK)
    {
        status = memacctGetCpsReadonlyCapSnapshot(gpuId, rows, capacity, count);
        rmapiLockRelease();
    }
    threadStateFree(&threadState, THREAD_STATE_FLAGS_NONE);
    NV_EXIT_RM_RUNTIME(sp, fp);
    return status;
}
