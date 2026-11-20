/* Explicit synthetic Linux ABI; compiles the actual retained helper. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#define NV_API_CALL
#define NV_MISC_CGROUP_PRESENT 1
#define OS_CGROUP_IMPL_NONE 0
#define OS_CGROUP_IMPL_MISC 1
#define OS_CGROUP_IMPL_DMEM 2
#define PIDTYPE_PID 0
static const int misc_cgrp_id = 9;
struct cgroup { int refs, can_get; };
struct task_struct { int refs; struct cgroup *group; };
struct pid { int namespace_id, visible_pid; struct task_struct *task; };
static int rcu_depth, lookups, task_gets, task_puts, group_gets, group_puts;
static int exit_after_lookup, migrate_after_snapshot;
static struct cgroup other_group;
static struct task_struct *deferred_exit;
static void rcu_read_lock(void) { assert(!rcu_depth); rcu_depth++; }
static void rcu_read_unlock(void) {
    assert(rcu_depth == 1); rcu_depth--;
    if (deferred_exit) { assert(deferred_exit->refs > 1); deferred_exit->refs--; deferred_exit = NULL; }
}
static struct task_struct *pid_task(struct pid *pid, int type) {
    assert(rcu_depth && pid && type == PIDTYPE_PID); lookups++;
    struct task_struct *task = pid->task;
    if (exit_after_lookup && task) { pid->task = NULL; deferred_exit = task; }
    /* Even a last task reference cannot free the task while RCU is held. */
    return task;
}
static struct task_struct *get_task_struct(struct task_struct *task) {
    assert(rcu_depth && task && task->refs > 0); task->refs++; task_gets++; return task;
}
static void put_task_struct(struct task_struct *task) {
    assert(!rcu_depth && task && task->refs > 0); task->refs--; task_puts++;
}
static struct cgroup *task_cgroup(struct task_struct *task, int id) {
    assert(rcu_depth && task && task->refs > 0 && id == misc_cgrp_id);
    struct cgroup *group = task->group;
    if (migrate_after_snapshot) task->group = &other_group;
    return group;
}
static int cgroup_tryget(struct cgroup *group) {
    assert(rcu_depth && group);
    if (!group->can_get) return 0;
    group->refs++; group_gets++; return 1;
}
static void os_cgroup_put(struct cgroup *group) {
    assert(!rcu_depth && group && group->refs > 0); group->refs--; group_puts++;
}
#include "task_cgroup_get.c"
static void reset(void) {
    rcu_depth = lookups = task_gets = task_puts = group_gets = group_puts = 0;
    exit_after_lookup = migrate_after_snapshot = 0;
    deferred_exit = NULL;
    other_group = (struct cgroup){ .refs = 1, .can_get = 1 };
}
int main(void) {
    struct cgroup group = { .refs = 1, .can_get = 1 };
    struct task_struct task = { .refs = 1, .group = &group };
    struct pid host = { .namespace_id = 0, .visible_pid = 123, .task = &task };
    struct pid container = { .namespace_id = 44, .visible_pid = 123, .task = NULL };
    void *result;
    reset(); assert(os_cps_cgroup_get_from_pid_info(NULL, OS_CGROUP_IMPL_MISC) == NULL);
    assert(!lookups && !rcu_depth);
    assert(os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_NONE) == NULL);
    assert(os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_DMEM) == NULL);
    assert(!lookups && !task_gets && !group_gets);
    reset(); result = os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_MISC);
    assert(result == &group && group.refs == 2 && task.refs == 1);
    assert(task_gets == 1 && task_puts == 1 && !rcu_depth);
    os_cgroup_put(result); assert(group.refs == 1 && group_gets == group_puts);
    /* Identical numeric PIDs in two namespaces never substitute identities. */
    reset(); assert(os_cps_cgroup_get_from_pid_info(&container, OS_CGROUP_IMPL_MISC) == NULL);
    assert(lookups == 1 && !task_gets && !task_puts && !group_gets);
    reset(); group.can_get = 0;
    assert(os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_MISC) == NULL);
    assert(task.refs == 1 && task_gets == task_puts && !group_gets && !rcu_depth);
    group.can_get = 1;
    /* Concurrent creator exit cannot free a task observed under RCU. */
    reset(); exit_after_lookup = 1;
    result = os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_MISC);
    assert(result == &group && !host.task && task.refs == 0 && group.refs == 2);
    os_cgroup_put(result); assert(group.refs == 1);
    host.task = &task; task.refs = 1;
    /* Migration after the snapshot cannot invalidate the retained old leaf. */
    reset(); migrate_after_snapshot = 1;
    result = os_cps_cgroup_get_from_pid_info(&host, OS_CGROUP_IMPL_MISC);
    assert(result == &group && task.group == &other_group && group.refs == 2);
    os_cgroup_put(result); assert(group.refs == 1 && other_group.refs == 1);
    puts("Retained task/cgroup CPU checks passed; no kernel or GPU calls");
    return 0;
}
