/* Global bounded denial-only diagnostics. No handles, pointers or secrets. */
void NV_API_CALL os_cps_native_import_denied(NvU32 gpuId, NvU32 reason,
                                            NvU32 clientKind, NvU32 status)
{
    static DEFINE_RATELIMIT_STATE(cps_import_denials, 5 * HZ, 8);
    if (__ratelimit(&cps_import_denials))
        printk(KERN_WARNING "NVRM: CPS native import denied gpu=%u reason=%u clientKind=%u status=0x%x tgid=%d\n",
               gpuId, reason, clientKind, status, task_tgid_nr(current));
}
