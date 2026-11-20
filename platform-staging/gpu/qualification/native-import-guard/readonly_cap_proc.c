/* Root-only diagnostic. No write handler, setters, gate or map mutations.
 * Recheck credentials on every read, including reads through a passed FD. */
static NvBool nv_cps_readonly_caps_authorized(void)
{
    return uid_eq(current_euid(), GLOBAL_ROOT_UID)
        && ns_capable(&init_user_ns, CAP_SYS_ADMIN)
        && os_cps_native_import_guard_enabled();
}

static int nv_procfs_read_cps_native_caps(struct seq_file *s, void *unused)
{
    nv_state_t *nv = s->private;
    CpsNativeCapRow *rows;
    nvidia_stack_t *sp = NULL;
    char *uuid = NULL;
    NV_STATUS status;
    NvU32 count = 0, i;
    int result = -EIO;
    (void)unused;
    if (!nv_cps_readonly_caps_authorized())
        return -EPERM;
    if (nv == NULL || !nv->nv_uuid_cache.valid)
        return -EIO;
    rows = kcalloc(CPS_NATIVE_CAP_MAX_ROWS, sizeof(*rows), GFP_KERNEL);
    if (rows == NULL)
        return -ENOMEM;
    if (nv_kmem_cache_alloc_stack(&sp) != 0)
        goto done;
    uuid = rm_get_gpu_uuid(sp, nv);
    if (uuid == NULL)
        goto done;
    status = rm_cps_get_readonly_caps(sp, nv->gpu_id, rows,
        CPS_NATIVE_CAP_MAX_ROWS, &count);
    if (status != NV_OK)
    {
        if (status == NV_ERR_BUFFER_TOO_SMALL)
            result = -EOVERFLOW;
        goto done;
    }
    seq_printf(s, "{\"version\":1,\"backend\":\"misc-fallback\",\"gpu_uuid\":\"%s\","
        "\"gpu_id\":%u,\"entries\":[", uuid, nv->gpu_id);
    for (i = 0; i < count; i++)
    {
        const CpsNativeCapRow *r = &rows[i];
        seq_printf(s, "%s{\"cgroup_id\":%llu,\"kernfs_id\":%llu,\"inode\":%llu,"
            "\"offline\":%s,\"pinned\":true,\"default_hierarchy\":true,"
            "\"soft\":%llu,\"hard\":%llu,\"used\":%llu}", i ? "," : "",
            (unsigned long long)r->cgroupId, (unsigned long long)r->kernfsId,
            (unsigned long long)r->inode, r->offline ? "true" : "false",
            (unsigned long long)r->softLimit, (unsigned long long)r->hardLimit,
            (unsigned long long)r->currentUsed);
    }
    seq_puts(s, "]}\n");
    result = 0;
done:
    if (uuid != NULL)
        os_free_mem(uuid);
    if (sp != NULL)
        nv_kmem_cache_free_stack(sp);
    kfree(rows);
    return result;
}

static int nv_procfs_open_cps_native_caps(struct inode *inode, struct file *file)
{
    if (!nv_cps_readonly_caps_authorized())
        return -EPERM;
    return single_open(file, nv_procfs_read_cps_native_caps, NV_PDE_DATA(inode));
}

static ssize_t nv_procfs_read_lock_cps_native_caps(struct file *file,
    char __user *buffer, size_t size, loff_t *position)
{
    ssize_t result;
    if (!nv_cps_readonly_caps_authorized())
        return -EPERM;
    result = nv_down_read_interruptible(&nv_system_pm_lock);
    if (result < 0)
        return result;
    result = seq_read(file, buffer, size, position);
    up_read(&nv_system_pm_lock);
    return result;
}

static const nv_proc_ops_t nv_procfs_cps_native_caps_fops = {
    NV_PROC_OPS_SET_OWNER()
    .NV_PROC_OPS_OPEN = nv_procfs_open_cps_native_caps,
    .NV_PROC_OPS_READ = nv_procfs_read_lock_cps_native_caps,
    .NV_PROC_OPS_RELEASE = single_release,
};
