/* CPS qualification-only retained lookup for the Linux 6.8 misc backend.
 * Paste into kernel-open/nvidia/os-interface.c; add <linux/sched/task.h>.
 * The caller owns pidInfo's struct-pid reference and must hold it throughout.
 * A non-NULL result owns ONE cgroup reference, released by os_cgroup_put().
 * Numeric PID lookup is deliberately absent: host and container PID namespaces
 * cannot substitute an unrelated task with the same integer identifier.
 */
void *NV_API_CALL os_cps_cgroup_get_from_pid_info(void *pidInfo, int impl)
{
#if defined(NV_MISC_CGROUP_PRESENT)
    struct task_struct *task;
    struct cgroup *group = NULL;

    if (pidInfo == NULL || impl != OS_CGROUP_IMPL_MISC)
        return NULL;

    rcu_read_lock();
    task = pid_task((struct pid *)pidInfo, PIDTYPE_PID);
    if (task != NULL)
    {
        /* Equivalent to get_pid_task's retained-task sequence, reusing the
         * already imported pid_task symbol. RCU protects both task lookup
         * and the css_set snapshot until the cgroup reference is acquired. */
        get_task_struct(task);
        group = task_cgroup(task, misc_cgrp_id);
        if (group != NULL && !cgroup_tryget(group))
            group = NULL;
    }
    rcu_read_unlock();

    if (task != NULL)
        put_task_struct(task);
    return group;
#else
    (void)pidInfo;
    (void)impl;
    return NULL;
#endif
}
