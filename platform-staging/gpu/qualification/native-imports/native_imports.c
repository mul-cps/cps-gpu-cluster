/* Trusted bounded qualification, not a policy enforcer. Official CUDA13.4.92 ABI. */
#define _GNU_SOURCE
#include <cuda.h>
#include <dlfcn.h>
#include <errno.h>
#include <poll.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define MIB ((size_t)1048576)
#define PAYLOAD (64*MIB)
#define S_(x) #x
#define S(x) S_(x)
#define FUNCTIONS(X) \
 X(cuInit) X(cuDriverGetVersion) X(cuDeviceGetCount) X(cuDeviceGet) X(cuDeviceGetUuid) \
 X(cuCtxCreate) X(cuCtxDestroy) X(cuCtxSynchronize) X(cuDeviceGetAttribute) \
 X(cuMemAlloc) X(cuMemFree) X(cuMemGetInfo) X(cuMemsetD8) X(cuMemcpyDtoH) \
 X(cuIpcGetMemHandle) X(cuIpcOpenMemHandle) X(cuIpcCloseMemHandle) \
 X(cuMemGetAllocationGranularity) X(cuMemCreate) X(cuMemRelease) \
 X(cuMemAddressReserve) X(cuMemAddressFree) X(cuMemMap) X(cuMemUnmap) X(cuMemSetAccess) \
 X(cuMemExportToShareableHandle) X(cuMemImportFromShareableHandle)
struct Api {
 void *library;
#define DECL(f) __typeof__(&f) f;
 FUNCTIONS(DECL)
#undef DECL
};
struct Allocation { CUdeviceptr address; CUmemGenericAllocationHandle handle; int reserved,mapped,ipc,ordinary,fd; };
struct Wire { uint32_t magic,version,kind; uint64_t bytes; unsigned char gpu[16]; CUipcMemHandle ipc; };
_Static_assert(CUDA_VERSION==13040,"Pinned CUDA13.4 ABI required");
_Static_assert(sizeof(CUdeviceptr)==8 && sizeof(CUmemGenericAllocationHandle)==8,"64-bit CUDA ABI required");
_Static_assert(sizeof(CUipcMemHandle)==64,"Official opaque IPC ABI required");
_Static_assert(sizeof(CUmemAllocationProp)==32 && sizeof(CUmemAccessDesc)==12,"Pinned x86_64 official VMM ABI required");
static struct Api api;
static int failed;
static void event(const char *phase,int result) {
 struct timespec now;clock_gettime(CLOCK_REALTIME,&now);
 printf("{\"kind\":\"cuda\",\"phase\":\"%s\",\"result\":%d,\"pid\":%ld,\"time_ns\":%lld,\"production_qualified\":false}\n",phase,result,(long)getpid(),(long long)now.tv_sec*1000000000+now.tv_nsec);fflush(stdout);
}
static int checked(const char *phase,CUresult r) {event(phase,r);if(r!=CUDA_SUCCESS){failed=1;return -1;}return 0;}
static int wait_fd(int fd,short events) {
 struct pollfd p={fd,events,0};int r;
 do {r=poll(&p,1,120000);} while(r<0 && errno==EINTR);
 return r==1 && (p.revents&events) ? 0:-1;
}
/* One complete local SEQPACKET frame; no stream short-read ambiguity. */
static int send_wire(int fd,const struct Wire *w,int exported_fd) {
 char control[CMSG_SPACE(sizeof(int))]={0};struct iovec iov={(void*)w,sizeof(*w)};
 struct msghdr message={0};message.msg_iov=&iov;message.msg_iovlen=1;
 if(exported_fd>=0){message.msg_control=control;message.msg_controllen=sizeof(control);struct cmsghdr *c=CMSG_FIRSTHDR(&message);c->cmsg_level=SOL_SOCKET;c->cmsg_type=SCM_RIGHTS;c->cmsg_len=CMSG_LEN(sizeof(int));memcpy(CMSG_DATA(c),&exported_fd,sizeof(int));}
 if(wait_fd(fd,POLLOUT))return -1;
 return sendmsg(fd,&message,MSG_NOSIGNAL)==(ssize_t)sizeof(*w)?0:-1;
}
static int recv_wire(int fd,struct Wire *w,int want_fd,int *received_fd) {
 char control[CMSG_SPACE(8*sizeof(int))]={0};struct iovec iov={w,sizeof(*w)};struct msghdr message={0};
 message.msg_iov=&iov;message.msg_iovlen=1;message.msg_control=control;message.msg_controllen=sizeof(control);*received_fd=-1;
 if(wait_fd(fd,POLLIN))return -1;
 ssize_t n=recvmsg(fd,&message,MSG_CMSG_CLOEXEC);int count=0,bad=0;
 for(struct cmsghdr *c=CMSG_FIRSTHDR(&message);c;c=CMSG_NXTHDR(&message,c)){
  if(c->cmsg_level!=SOL_SOCKET || c->cmsg_type!=SCM_RIGHTS){bad=1;continue;}
  size_t bytes=c->cmsg_len>=CMSG_LEN(0)?c->cmsg_len-CMSG_LEN(0):0;if(bytes%sizeof(int)){bad=1;continue;}
  for(size_t offset=0;offset<bytes;offset+=sizeof(int)){int found;memcpy(&found,(char*)CMSG_DATA(c)+offset,sizeof(int));if(count++==0)*received_fd=found;else close(found);}
 }
 if(n!=(ssize_t)sizeof(*w)||(message.msg_flags&(MSG_TRUNC|MSG_CTRUNC))||bad||count!=want_fd||w->magic!=0x43505349||w->version!=1||w->bytes!=PAYLOAD){if(*received_fd>=0)close(*received_fd);*received_fd=-1;return -1;}
 return 0;
}
static int token(int fd,char value,int sending) {
 if(wait_fd(fd,sending?POLLOUT:POLLIN))return -1;
 if(sending)return send(fd,&value,1,MSG_NOSIGNAL)==1?0:-1;
 char b[2];return recv(fd,b,sizeof(b),0)==1 && b[0]==value?0:-1;
}
static int preload_is_set(void) {const char *value=getenv("LD_PRELOAD");return value && *value;}
static int parse_uuid(const char *s,unsigned char bytes[16]) {
 if(!s||strlen(s)!=40||strncmp(s,"GPU-",4))return -1;
 int k=0;for(int i=4;i<40;){if(i==12||i==17||i==22||i==27){if(s[i++]!='-')return -1;continue;}
  unsigned n=0;for(int j=0;j<2;j++){char c=s[i++];int d=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;if(d<0)return -1;n=n*16+(unsigned)d;}bytes[k++]=(unsigned char)n;}
 return k==16?0:-1;
}
static int load_api(void) {
 api.library=dlopen("libcuda.so.1",RTLD_NOW|RTLD_LOCAL);if(!api.library){fprintf(stderr,"CUDA driver library unavailable\n");return -1;}
#define LOAD(f) do{*(void **)(&api.f)=dlsym(api.library,S(f));if(!api.f){fprintf(stderr,"Required official CUDA symbol missing: %s\n",S(f));return -1;}}while(0);
 FUNCTIONS(LOAD)
#undef LOAD
 return 0;
}
static int cleanup(struct Allocation *a) {
 int rc=0;
 if(a->ipc){if(checked("ipc-close",api.cuIpcCloseMemHandle(a->address)))rc=-1;a->ipc=0;}
 if(a->mapped){if(checked("vmm-unmap",api.cuMemUnmap(a->address,PAYLOAD)))rc=-1;a->mapped=0;}
 if(a->handle){if(checked("vmm-release",api.cuMemRelease(a->handle)))rc=-1;a->handle=0;}
 if(a->reserved){if(checked("vmm-address-free",api.cuMemAddressFree(a->address,PAYLOAD)))rc=-1;a->reserved=0;}
 if(a->ordinary){if(checked("ordinary-free",api.cuMemFree(a->address)))rc=-1;a->ordinary=0;}
 if(a->fd>=0){if(close(a->fd))rc=-1;a->fd=-1;}
 return rc;
}
static CUmemAllocationProp properties(CUdevice device) {
 CUmemAllocationProp p={0};p.type=CU_MEM_ALLOCATION_TYPE_PINNED;p.requestedHandleTypes=CU_MEM_HANDLE_TYPE_POSIX_FILE_DESCRIPTOR;p.location.type=CU_MEM_LOCATION_TYPE_DEVICE;p.location.id=device;return p;
}
static int map_vmm(struct Allocation *a,CUdevice device) {
 if(checked("vmm-reserve",api.cuMemAddressReserve(&a->address,PAYLOAD,0,0,0)))return -1;
 a->reserved=1;
 if(checked("vmm-map",api.cuMemMap(a->address,PAYLOAD,0,a->handle,0)))return -1;
 a->mapped=1;
 CUmemAccessDesc access={0};access.location.type=CU_MEM_LOCATION_TYPE_DEVICE;access.location.id=device;access.flags=CU_MEM_ACCESS_FLAGS_PROT_READWRITE;
 return checked("vmm-set-access",api.cuMemSetAccess(a->address,PAYLOAD,&access,1));
}
static int allocate_vmm(struct Allocation *a,CUdevice device) {
 CUmemAllocationProp p=properties(device);size_t granularity=0;
 if(checked("vmm-granularity",api.cuMemGetAllocationGranularity(&granularity,&p,CU_MEM_ALLOC_GRANULARITY_MINIMUM)))return -1;
 if(!granularity||PAYLOAD%granularity){fprintf(stderr,"Fixed64MiB not divisible by device granularity\n");return -1;}
 if(checked("vmm-create-64",api.cuMemCreate(&a->handle,PAYLOAD,&p,0)))return -1;
 return map_vmm(a,device);
}
static int touch(CUdeviceptr address,unsigned char byte) {
 unsigned char got=0;
 if(checked("fill-64",api.cuMemsetD8(address,byte,PAYLOAD))||checked("synchronize",api.cuCtxSynchronize())||checked("readback",api.cuMemcpyDtoH(&got,address,1)))return -1;
 if(got!=byte){fprintf(stderr,"GPU readback mismatch\n");return -1;}return 0;
}
static int direct_vmm(CUdevice device,size_t cap) {
 struct Allocation a={.fd=-1},recovery={.fd=-1};CUmemGenericAllocationHandle over=0;int rc=-1;
 if(allocate_vmm(&a,device)||touch(a.address,19)||cleanup(&a))goto done;
 size_t free_bytes=0,total=0;
 if(checked("cap-memory-info",api.cuMemGetInfo(&free_bytes,&total)))goto done;
 printf("{\"kind\":\"cap-info\",\"free_bytes\":%zu,\"total_bytes\":%zu,\"requested_over_bytes\":%zu}\n",free_bytes,total,cap);fflush(stdout);
 if(total!=cap || free_bytes>=total){fprintf(stderr,"Exact cap and positive charged baseline required\n");goto done;}
 CUmemAllocationProp p=properties(device);CUresult r=api.cuMemCreate(&over,cap,&p,0);event("vmm-over-cap-never-touch",r);
 if(r==CUDA_SUCCESS){checked("unexpected-over-release",api.cuMemRelease(over));over=0;fprintf(stderr,"Over-cap allocation unexpectedly succeeded; not mapped or touched\n");goto done;}
 if(r!=CUDA_ERROR_OUT_OF_MEMORY){fprintf(stderr,"Over-cap result is not typed CUDA OOM\n");goto done;}
 if(allocate_vmm(&recovery,device)||touch(recovery.address,37))goto done;
 rc=0;
 done:if(over)checked("over-release",api.cuMemRelease(over));int a_rc=cleanup(&a),recovery_rc=cleanup(&recovery);if(a_rc||recovery_rc)rc=-1;return rc;
}
static int secure_socket(const char *path,int exporter,struct stat *bound) {
 if(!path||strlen(path)>=sizeof(((struct sockaddr_un*)0)->sun_path))return -1;
 char parent[108];strcpy(parent,path);char *slash=strrchr(parent,'/');if(!slash||slash==parent)return -1;*slash=0;
 struct stat st;if(lstat(parent,&st)||!S_ISDIR(st.st_mode)||st.st_uid!=1000||(st.st_mode&0777)!=0700)return -1;
 int exists=lstat(path,&st)==0;if(exporter?(exists||errno!=ENOENT):(!exists||!S_ISSOCK(st.st_mode)||st.st_uid!=1000||(st.st_mode&0777)!=0600))return -1;
 int fd=socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0);if(fd<0)return -1;
 struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path,path);
 if(exporter){
  mode_t mask=umask(0077);int r=bind(fd,(struct sockaddr*)&address,sizeof(address));umask(mask);
  struct stat created,ready;
  if(r||lstat(path,&created)||!S_ISSOCK(created.st_mode)||created.st_uid!=1000){close(fd);return -1;}
  /* Unix bind creates0700 under umask077; the importer deliberately requires0600. */
  if(chmod(path,0600)||lstat(path,&ready)||!S_ISSOCK(ready.st_mode)||ready.st_uid!=1000||
     ready.st_dev!=created.st_dev||ready.st_ino!=created.st_ino||(ready.st_mode&0777)!=0600){close(fd);return -1;}
  *bound=ready;if(listen(fd,1)){close(fd);return -1;}
 }
 else if(connect(fd,(struct sockaddr*)&address,sizeof(address))){close(fd);return -1;}
 return fd;
}
static int authenticate(int fd) {struct ucred p;socklen_t n=sizeof(p);return getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&p,&n)||n!=sizeof(p)||p.uid!=1000||p.gid!=100?-1:0;}
static int exchange(const char *mode,const char *path,CUdevice device,const unsigned char gpu[16],int retained_seconds,int importer_fill) {
 int exporter=strstr(mode,"export")!=NULL,vmm=strncmp(mode,"vmm",3)==0;struct stat bound={0},now;struct Allocation a={.fd=-1},fill={.fd=-1};struct Wire w={.magic=0x43505349,.version=1,.kind=vmm?2u:1u,.bytes=PAYLOAD};memcpy(w.gpu,gpu,16);
 int listener=-1,fd=-1,rc=-1;listener=secure_socket(path,exporter,&bound);if(listener<0){fprintf(stderr,"Approved private socket unavailable\n");return -1;}
 if(exporter){if(wait_fd(listener,POLLIN))goto done;fd=accept4(listener,NULL,NULL,SOCK_CLOEXEC);}else{fd=listener;listener=-1;}
 if(fd<0||authenticate(fd)){fprintf(stderr,"Exact UID1000/GID100 peer required\n");goto done;}
 if(exporter){
  if(vmm){if(allocate_vmm(&a,device)||touch(a.address,19)||checked("vmm-export",api.cuMemExportToShareableHandle(&a.fd,a.handle,CU_MEM_HANDLE_TYPE_POSIX_FILE_DESCRIPTOR,0)))goto done;}
  else{if(checked("ipc-allocate",api.cuMemAlloc(&a.address,PAYLOAD)))goto done;a.ordinary=1;if(touch(a.address,19)||checked("ipc-export",api.cuIpcGetMemHandle(&w.ipc,a.address)))goto done;}
  if(send_wire(fd,&w,vmm?a.fd:-1)||token(fd,'I',0))goto done;
  if(vmm){if(cleanup(&a))goto done;event("exporter-references-released-importer-retains",0);if(token(fd,'R',1))goto done;}
  if(token(fd,'D',0))goto done;
 }else{
  if(importer_fill){if(checked("importer-own-fill-allocate",api.cuMemAlloc(&fill.address,PAYLOAD)))goto done;fill.ordinary=1;if(touch(fill.address,11))goto done;}
  struct Wire incoming={0};if(recv_wire(fd,&incoming,vmm?1:0,&a.fd)||incoming.kind!=w.kind||memcmp(incoming.gpu,gpu,16)){fprintf(stderr,"Exact allocation/GPU wire identity required\n");goto done;}
  if(vmm){if(checked("vmm-import",api.cuMemImportFromShareableHandle(&a.handle,(void*)(intptr_t)a.fd,CU_MEM_HANDLE_TYPE_POSIX_FILE_DESCRIPTOR))||map_vmm(&a,device))goto done;}
  else{if(checked("ipc-import",api.cuIpcOpenMemHandle(&a.address,incoming.ipc,CU_IPC_MEM_LAZY_ENABLE_PEER_ACCESS)))goto done;a.ipc=1;}
  unsigned char got=0;if(checked("import-readback",api.cuMemcpyDtoH(&got,a.address,1))||got!=19||touch(a.address,37)||token(fd,'I',1))goto done;
  if(vmm){if(token(fd,'R',0))goto done;event("importer-retained-backing-start",0);sleep((unsigned)retained_seconds);if(touch(a.address,37))goto done;event("importer-retained-backing-end",0);}
  if(cleanup(&a)||token(fd,'D',1))goto done;
 }
 rc=0;
 done:
 int a_rc=cleanup(&a),fill_rc=cleanup(&fill);if(a_rc||fill_rc)rc=-1;
 /* Error acknowledgement follows local cleanup, never before IPC close. */
 if(rc&&fd>=0){char error='E';send(fd,&error,1,MSG_NOSIGNAL|MSG_DONTWAIT);}
 if(fd>=0)close(fd);
 if(listener>=0)close(listener);
 if(exporter&&bound.st_ino&&lstat(path,&now)==0&&now.st_ino==bound.st_ino&&now.st_dev==bound.st_dev)unlink(path);
 return rc;
}
int main(int argc,char **argv) {
 const char *mode="vmm-direct",*gpu_uuid=NULL,*socket_path=NULL;int execute=0,cap_mib=512,hold=3,importer_fill=0;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--execute"))execute=1;
  else if(!strcmp(argv[i],"--mode")&&i+1<argc)mode=argv[++i];
  else if(!strcmp(argv[i],"--gpu-uuid")&&i+1<argc)gpu_uuid=argv[++i];
  else if(!strcmp(argv[i],"--socket")&&i+1<argc)socket_path=argv[++i];
  else if(!strcmp(argv[i],"--cap-mib")&&i+1<argc){const char *n=argv[++i];if(!strcmp(n,"512"))cap_mib=512;else if(!strcmp(n,"5120"))cap_mib=5120;else return 2;}
  else if(!strcmp(argv[i],"--importer-fill-mib")&&i+1<argc){const char *n=argv[++i];if(!strcmp(n,"64"))importer_fill=1;else if(strcmp(n,"0"))return 2;}
  else if(!strcmp(argv[i],"--retain-seconds")&&i+1<argc){const char *n=argv[++i];if(strlen(n)!=1||n[0]<'1'||n[0]>'9')return 2;hold=n[0]-'0';}
  else return 2;
 }
 if(strcmp(mode,"vmm-direct")&&strcmp(mode,"ipc-export")&&strcmp(mode,"ipc-import")&&strcmp(mode,"vmm-export")&&strcmp(mode,"vmm-import"))return 2;
 if(importer_fill&&strcmp(mode,"ipc-import")&&strcmp(mode,"vmm-import"))return 2;
 if(!execute){puts("{\"state\":\"inert\",\"gpu_calls\":false,\"payload_mib\":64,\"production_qualified\":false}");return 0;}
 unsigned char wanted[16];if(parse_uuid(gpu_uuid,wanted)||getuid()!=1000||getgid()!=100||preload_is_set()||(!socket_path&&strcmp(mode,"vmm-direct"))){fprintf(stderr,"Explicit exact GPU/UID1000/GID100/no-preload/socket identity required\n");return 2;}
 int rc=-1,driver=0,count=0;CUdevice device=-1;CUcontext context=NULL;
 if(load_api())goto done;
 if(checked("initialize",api.cuInit(0))||checked("driver-version",api.cuDriverGetVersion(&driver))||driver<13040||checked("device-count",api.cuDeviceGetCount(&count)))goto done;
 for(int i=0;i<count;i++){CUdevice d;CUuuid u;if(checked("enumerate-device",api.cuDeviceGet(&d,i))||checked("device-uuid",api.cuDeviceGetUuid(&u,d)))goto done;if(!memcmp(u.bytes,wanted,16)){device=d;break;}}
 if(device<0){fprintf(stderr,"Exact physical GPU absent\n");goto done;}
 printf("{\"kind\":\"identity\",\"gpu_uuid\":\"%s\",\"driver_api_version\":%d,\"uid\":%ld,\"gid\":%ld,\"device_ordinal\":%d}\n",gpu_uuid,driver,(long)getuid(),(long)getgid(),device);fflush(stdout);
 for(int a=0;a<2;a++){int value=-1;CUdevice_attribute attribute=a?CU_DEVICE_ATTRIBUTE_PAGEABLE_MEMORY_ACCESS_USES_HOST_PAGE_TABLES:CU_DEVICE_ATTRIBUTE_PAGEABLE_MEMORY_ACCESS;if(checked("pageable-attribute",api.cuDeviceGetAttribute(&value,attribute,device))||value!=0){fprintf(stderr,"HMM/ATS disabled attributes required\n");goto done;}}
 if(checked("context-create",api.cuCtxCreate(&context,NULL,0,device)))goto done;
 size_t cap_free=0,cap_total=0;if(checked("initial-cap-memory-info",api.cuMemGetInfo(&cap_free,&cap_total))||cap_total!=(size_t)cap_mib*MIB||cap_free>=cap_total){fprintf(stderr,"Exact capped client and positive charged baseline required\n");goto done;}
 printf("{\"kind\":\"initial-cap-info\",\"total_bytes\":%zu,\"free_bytes\":%zu}\n",cap_total,cap_free);fflush(stdout);
 if(!strcmp(mode,"vmm-direct"))rc=direct_vmm(device,(size_t)cap_mib*MIB);else rc=exchange(mode,socket_path,device,wanted,hold,importer_fill);
 done:if(context){checked("final-synchronize",api.cuCtxSynchronize());checked("context-destroy",api.cuCtxDestroy(context));}if(api.library)dlclose(api.library);
 printf("{\"kind\":\"final\",\"status\":\"%s\",\"production_qualified\":false,\"managed_imports_qualified\":false,\"automatic_caps_qualified\":false}\n",rc==0&&!failed?"bounded-measurement-completed":"inconclusive");return rc==0&&!failed?0:1;
}
