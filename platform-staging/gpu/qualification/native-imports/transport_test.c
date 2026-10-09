/* Real CPU-only Unix transport tests. No CUDA library is loaded or called. */
#define main qualification_main
#include "native_imports.c"
#undef main
#include <fcntl.h>
#include <sys/mman.h>
#include <assert.h>
static struct Wire frame(void){struct Wire w={.magic=0x43505349,.version=1,.kind=2,.bytes=PAYLOAD};return w;}
int main(void){
 int pair[2];assert(socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,pair)==0);
 struct Wire w=frame(),out;int got=-1;
 assert(send_wire(pair[0],&w,-1)==0);assert(recv_wire(pair[1],&out,1,&got)==-1 && got==-1);
 int fd=memfd_create("cpu-only-cps-transport",MFD_CLOEXEC);assert(fd>=0);assert(write(fd,"retained",8)==8);
 assert(send_wire(pair[0],&w,fd)==0);assert(recv_wire(pair[1],&out,1,&got)==0 && got>=0);
 assert(fcntl(got,F_GETFD)&FD_CLOEXEC);close(fd);assert(lseek(got,0,SEEK_SET)==0);char bytes[8];assert(read(got,bytes,8)==8 && memcmp(bytes,"retained",8)==0);close(got);
 w.magic=0;fd=memfd_create("bad-wire",MFD_CLOEXEC);assert(fd>=0);
 assert(send_wire(pair[0],&w,fd)==0);assert(recv_wire(pair[1],&out,1,&got)==-1 && got==-1);close(fd);
 w=frame();assert(send_wire(pair[0],&w,-1)==0);assert(recv_wire(pair[1],&out,0,&got)==0 && got==-1);
 unsigned char uuid[16];assert(parse_uuid("GPU-16128952-b438-556a-00bb-93039ee24e56",uuid)==0);assert(uuid[0]==0x16&&uuid[15]==0x56);assert(parse_uuid("GPU-16128952xb438-556a-00bb-93039ee24e56",uuid)==-1);assert(parse_uuid("GPU-16128952-b438-556a-00bb-93039ee24e5Z",uuid)==-1);
 close(pair[0]);close(pair[1]);puts("CPU transport/ABI checks passed; GPU calls=0");return 0;
}
