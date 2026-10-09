/* CPU-only exact logger argument/rate-limit gate fixture; no kernel calls. */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
typedef unsigned NvU32;
#define NV_API_CALL
#define HZ 100
#define KERN_WARNING ""
typedef struct {int interval,burst;} RateState;
#define DEFINE_RATELIMIT_STATE(n,i,b) RateState n={i,b}
static int allow,logs,current;
static int __ratelimit(RateState *state){assert(state->interval==500&&state->burst==8);return allow;}
static int task_tgid_nr(int value){assert(value==current);return 29;}
static int printk(const char *fmt,...){char result[200];va_list ap;va_start(ap,fmt);vsnprintf(result,sizeof(result),fmt,ap);va_end(ap);assert(strstr(result,"gpu=7 reason=6 clientKind=2 status=0x1b tgid=29"));assert(!strstr(fmt,"%p"));logs++;return 0;}
#include "import_diagnostic.c"
int main(void){allow=1;os_cps_native_import_denied(7,6,2,0x1b);assert(logs==1);allow=0;os_cps_native_import_denied(7,6,2,0x1b);assert(logs==1);puts("Synthetic denial logger gate passed; kernel rate limiter not exercised");return 0;}
