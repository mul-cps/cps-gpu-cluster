import os,signal,sys,time,json,pathlib
pid=int(sys.argv[1]);expected=sys.argv[2]
fd=os.pidfd_open(pid)
actual=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
assert actual==expected,(actual,expected)
signal.pidfd_send_signal(fd,signal.SIGCONT)
os.close(fd)
print(json.dumps({'action':'CONT','pid':pid,'starttime':actual,'time':time.time()}),flush=True)
