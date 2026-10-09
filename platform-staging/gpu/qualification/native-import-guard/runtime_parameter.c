/* Qualification opt-in. Read-only sysfs and post-init read-only storage.
 * Deliberately excluded from NVIDIA's mutable registry parameter table. */
static unsigned int nv_cps_native_import_guard __ro_after_init = 0;
static int nv_cps_native_import_guard_set(const char *val, const struct kernel_param *kp)
{
    unsigned int value = 0;
    struct kernel_param temporary = *kp;
    int status;
    temporary.arg = &value;
    status = param_ops_uint.set(val, &temporary);
    if (status != 0)
        return status;
    if (value > 1)
        return -EINVAL;
    *(unsigned int *)kp->arg = value;
    return 0;
}
static int nv_cps_native_import_guard_get(char *buffer, const struct kernel_param *kp)
{
    return param_ops_uint.get(buffer, kp);
}
static const struct kernel_param_ops nv_cps_native_import_guard_ops = {
    .set = nv_cps_native_import_guard_set,
    .get = nv_cps_native_import_guard_get,
};
module_param_cb(NVreg_CpsNativeImportGuard, &nv_cps_native_import_guard_ops,
                &nv_cps_native_import_guard, 0400);
__MODULE_PARM_TYPE(NVreg_CpsNativeImportGuard, "uint");
MODULE_PARM_DESC(NVreg_CpsNativeImportGuard,
                "CPS qualification-only native import guard (0=off, 1=on; load-time only)");
NvBool NV_API_CALL os_cps_native_import_guard_enabled(void)
{
    return nv_cps_native_import_guard == 1;
}
