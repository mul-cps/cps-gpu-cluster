/* The caller already holds the cap-map mutex and its retained cgroup pin.
 * A dead group's CSS and kernfs node remain valid until that pin is released.
 * This is a read, not cgroup_get_from_fd (which requires an online CSS). */
NvBool NV_API_CALL os_cps_readonly_cgroup(void *cgroup, CpsNativeCapRow *row)
{
#if defined(NV_MISC_CGROUP_PRESENT)
    struct cgroup *group = cgroup;
    if (group == NULL || row == NULL || sizeof(ino_t) < sizeof(NvU64)
        || group->root != &cgrp_dfl_root || group->kn == NULL)
        return NV_FALSE;
    row->cgroupId = cgroup_id(group);
    row->kernfsId = READ_ONCE(group->kn->id);
    row->inode = kernfs_ino(group->kn);
    row->offline = (READ_ONCE(group->self.flags) & CSS_ONLINE) == 0;
    row->defaultHierarchy = 1;
    return row->cgroupId != 0 && row->cgroupId == row->kernfsId
        && row->kernfsId == row->inode;
#else
    (void)cgroup;
    (void)row;
    return NV_FALSE;
#endif
}
