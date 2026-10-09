#include <assert.h>
#include <stddef.h>
#define NV_API_CALL
#include "task_cgroup_get.c"
int main(void) {
    assert(os_cps_cgroup_get_from_pid_info((void *)1, 1) == NULL);
    assert(os_cps_cgroup_get_from_pid_info(NULL, 1) == NULL);
    return 0;
}
