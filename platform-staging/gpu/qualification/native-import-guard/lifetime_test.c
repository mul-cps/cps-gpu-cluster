/* CPU synthetic map/cgroup ABI: compiles actual pin/unpin helpers. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef void *ClientGroupID;
typedef struct {ClientGroupID cpsPinnedGroup;} ClientGroupLimits;
typedef struct {ClientGroupLimits *entries;size_t count;} ClientGroupMap;
typedef struct {ClientGroupMap clientGroupMap;} GpuRegion;
typedef struct {ClientGroupMap *map;size_t pos;ClientGroupLimits *pValue;} ClientGroupMapTypeIter;
static int enabled,gets,puts_count;
static int os_cps_native_import_guard_enabled(void){return enabled;}
static void os_cgroup_get(ClientGroupID g){assert(g);gets++;}
static void os_cgroup_put(ClientGroupID g){assert(g);puts_count++;}
static ClientGroupMapTypeIter mapIterAll(ClientGroupMap *map){return (ClientGroupMapTypeIter){.map=map};}
static int mapIterNext(ClientGroupMapTypeIter *iter){if(iter->pos==iter->map->count)return 0;iter->pValue=&iter->map->entries[iter->pos++];return 1;}
#include "limits_lifetime.c"
int main(void){ClientGroupLimits entries[3];GpuRegion r={.clientGroupMap={entries,3}};
 enabled=1;memacctPinLimitGroup(&entries[0],(void*)1);memacctPinLimitGroup(&entries[1],(void*)2);assert(gets==2);
 enabled=0;memacctPinLimitGroup(&entries[2],(void*)3);assert(gets==2&&entries[2].cpsPinnedGroup==NULL);
 memacctUnpinLimitGroups(&r);assert(puts_count==2);for(unsigned i=0;i<3;i++)assert(entries[i].cpsPinnedGroup==NULL);
 memacctUnpinLimitGroups(&r);assert(puts_count==2);puts("Synthetic lifetime checks passed; no real cgroups touched");return 0;}
