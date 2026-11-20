/* Real CPU-only Unix transport tests. No CUDA library is loaded or called. */
#define main qualification_main
#include "native_imports.c"
#undef main
#include <fcntl.h>
#include <sys/mman.h>
#include <assert.h>
#include <grp.h>
#include <sys/wait.h>
static struct Wire frame(void){struct Wire w={.magic=0x43505349,.version=1,.kind=2,.bytes=PAYLOAD};return w;}
static void secure_socket_checks(const char *directory){
 char path[108];assert(snprintf(path,sizeof(path),"%s/import.sock",directory)>0);
 struct stat bound={0},now;
 int listener=secure_socket(path,1,&bound);assert(listener>=0);
 assert(lstat(path,&now)==0 && S_ISSOCK(now.st_mode) && now.st_uid==1000 && (now.st_mode&0777)==0600);
 assert(now.st_dev==bound.st_dev && now.st_ino==bound.st_ino);
 int importer=secure_socket(path,0,&now);assert(importer>=0);
 int peer=accept4(listener,NULL,NULL,SOCK_CLOEXEC);assert(peer>=0);
 assert(write(importer,"C",1)==1);char byte=0;assert(read(peer,&byte,1)==1 && byte=='C');
 assert(secure_socket(path,1,&now)==-1); /* never replace an existing owned socket */
 assert(chmod(path,0700)==0);assert(secure_socket(path,0,&now)==-1);assert(chmod(path,0600)==0);
 close(peer);close(importer);close(listener);assert(unlink(path)==0);
 assert(symlink("unrelated-target",path)==0);assert(secure_socket(path,1,&now)==-1);assert(secure_socket(path,0,&now)==-1);assert(unlink(path)==0);
 assert(chmod(directory,0750)==0);assert(secure_socket(path,1,&now)==-1);assert(chmod(directory,0700)==0);
}
static void real_secure_socket_test(void){
 char directory[]="/tmp/cps-native-socket-XXXXXX";assert(mkdtemp(directory)!=NULL);
 if(geteuid()==0){
  assert(chown(directory,1000,100)==0);pid_t child=fork();assert(child>=0);
  if(child==0){assert(setgroups(0,NULL)==0 && setgid(100)==0 && setuid(1000)==0);secure_socket_checks(directory);_exit(0);}
  int status=0;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
 }else{assert(geteuid()==1000);secure_socket_checks(directory);}
 assert(rmdir(directory)==0);
}
int main(void){
 unsetenv("LD_PRELOAD");assert(!preload_is_set());setenv("LD_PRELOAD","",1);assert(!preload_is_set());setenv("LD_PRELOAD","/untrusted/shim.so",1);assert(preload_is_set());unsetenv("LD_PRELOAD");
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
 close(pair[0]);close(pair[1]);real_secure_socket_test();puts("CPU transport/ABI/real secure_socket checks passed; GPU calls=0");return 0;
}
