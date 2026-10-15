/* CPU synthetic parameter ABI/control-flow only; real kernel compilation required. */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int NvBool;
#define NV_API_CALL
#define __ro_after_init
struct kernel_param {void *arg;};
struct kernel_param_ops {int (*set)(const char*,const struct kernel_param*);int (*get)(char*,const struct kernel_param*);};
#define module_param_cb(name,ops,value,mode) _Static_assert((mode)==0400,"Read-only mode required")
#define __MODULE_PARM_TYPE(name,type)
#define MODULE_PARM_DESC(name,desc)
static int kstrtouint(const char *v,unsigned int base,unsigned int *out){char *end;errno=0;if(!v||!*v||*v=='-')return -EINVAL;unsigned long n=strtoul(v,&end,base);if(errno||*end||n>UINT_MAX)return -EINVAL;*out=(unsigned)n;return 0;}
static int param_set_uint(const char *v,const struct kernel_param *p){return kstrtouint(v,0,p->arg);}
static int param_get_uint(char *v,const struct kernel_param *p){return sprintf(v,"%u",*(unsigned*)p->arg);}
static const struct kernel_param_ops param_ops_uint={.set=param_set_uint,.get=param_get_uint};
#include "runtime_parameter.c"
int main(void){struct kernel_param p={&nv_cps_native_import_guard};char out[20];
 assert(nv_cps_native_import_guard==0&&!os_cps_native_import_guard_enabled());
 assert(nv_cps_native_import_guard_ops.set("1",&p)==0&&os_cps_native_import_guard_enabled());
 for(unsigned i=0;i<6;i++){const char *bad[]={"2","4294967295","4294967296","-1","bad",""};assert(nv_cps_native_import_guard_ops.set(bad[i],&p)!=0);assert(nv_cps_native_import_guard==1);}
 assert(nv_cps_native_import_guard_ops.get(out,&p)==1&&!strcmp(out,"1"));
 assert(nv_cps_native_import_guard_ops.set("0",&p)==0&&!os_cps_native_import_guard_enabled());
 puts("Synthetic parameter checks passed; no kernel module loaded");return 0;}
