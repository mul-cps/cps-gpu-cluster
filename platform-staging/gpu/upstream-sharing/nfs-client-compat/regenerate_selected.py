"""Unarmed/default inspect. One native selected-kernel rebuild; no reboot or retry."""
import argparse,contextlib,fcntl,hashlib,importlib.util,json,os,pathlib,re,shutil,socket,stat,subprocess,uuid
D=pathlib.Path(__file__).parent
KERNEL='7.0.0-43-generic';LINE=b'options nfsv4 directory_delegations=N\n'
HELPER_SHA='60d0b86b7943327ead580a5fc5fe106ef02409bea3bcdea79c1cc497bb4ce149'
UPDATER_SHA='77957a324a936d6ee5d1cd51043cac9f34af7daaed5971bf1a0f6982b1c4eb30'
LOCKS=['/var/lib/dpkg/lock-frontend','/var/lib/dpkg/lock','/var/cache/apt/archives/lock','/var/lib/apt/lists/lock']
STATE=pathlib.Path('/var/lib/cps-nfs-initramfs');IMAGE=pathlib.Path('/boot/initrd.img-'+KERNEL)
CONFIG=pathlib.Path('/etc/modprobe.d/90-cps-nfs-directory-delegations.conf')
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load_helper():
 p=D/'nfs_client_compat.py';require(sha(p)==HELPER_SHA,'helper changed');s=importlib.util.spec_from_file_location('native_nfs',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def metadata(p):
 p=pathlib.Path(p);s=p.lstat();d={'path':str(p),'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'inode':s.st_ino,'size':s.st_size,'symlink':p.is_symlink()}
 if p.is_symlink():d['link']=os.readlink(p)
 elif p.is_file():d['sha256']=sha(p)
 return d
def validate_release(s):
 require(isinstance(s.get('root_release'),str)and s['root_release'].strip(),'UNARMED')
 require(str(uuid.UUID(s['operation_id']))==s['operation_id'],'operation UUID')
 require(s['kernel']==KERNEL and s['updater_sha256']==UPDATER_SHA,'selected native version')
 require(isinstance(s.get('persisted_operation'),str)and re.fullmatch(r'/var/lib/cps-nfs-client-compat/[0-9a-f-]{36}/operation.json',s['persisted_operation'])and isinstance(s.get('persisted_operation_sha256'),str)and re.fullmatch('[0-9a-f]{64}',s['persisted_operation_sha256']),'persistence proof required')
def package_operation(argv):
 if argv==['/usr/bin/python3','/usr/share/unattended-upgrades/unattended-upgrade-shutdown','--wait-for-signal']or argv==['python3','/usr/share/unattended-upgrades/unattended-upgrade-shutdown','--wait-for-signal']:return False
 names={pathlib.Path(a).name for a in argv[:2]}
 return bool(names&{'apt','apt-get','dpkg','unattended-upgrade','unattended-upgrades','update-initramfs','mkinitramfs','dracut'})
def package_processes():
 result=[]
 for p in pathlib.Path('/proc').iterdir():
  if p.name.isdigit()and int(p.name)!=os.getpid():
   try:args=[x.decode()for x in(p/'cmdline').read_bytes().split(b'\0')if x]
   except (FileNotFoundError,ProcessLookupError):continue
   if package_operation(args):result.append({'pid':int(p.name),'argv':args})
 return result
def space_requirements(size,expanded,backup_bytes=None):return {'boot':3*size+64*1024*1024,'state':(size if backup_bytes is None else backup_bytes)+2*expanded+128*1024*1024}
def check_space(size,expanded,boot_available,state_available,backup_bytes=None,same_fs=False):
 r=space_requirements(size,expanded,backup_bytes);require(boot_available>=r['boot']and state_available>=r['state'],'insufficient backup/new-image/extraction space')
 if same_fs:require(min(boot_available,state_available)>=sum(r.values()),'combined filesystem budget insufficient')
 return r
def expanded_size():
 t=subprocess.check_output(['lsinitramfs','-l',str(IMAGE)],text=True,stderr=subprocess.PIPE,timeout=60);total=0
 for line in t.splitlines():
  fields=line.split();require(len(fields)>=9 and fields[4].isdigit(),'unknown native initramfs listing format');total+=int(fields[4])
 return total
def verify_embedded(root):
 found=list(root.glob('**/etc/modprobe.d/90-cps-nfs-directory-delegations.conf'));require(bool(found),'embedded NFS option missing');receipts=[]
 for p in found:
  require(not p.is_symlink()and p.resolve().is_relative_to(root.resolve())and p.is_file(),'unsafe embedded config path')
  require(p.read_bytes()==LINE,'embedded option bytes differ');receipts.append({'relativePath':str(p.relative_to(root)),'sha256':sha(p)})
 return receipts
@contextlib.contextmanager
def locks():
 handles=[]
 try:
  # Operator flock serializes this operation; native apt/dpkg use POSIX locks.
  fd=os.open('/run/cps-nfs-initramfs.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);handles.append(fd);meta=os.fstat(fd);require(stat.S_ISREG(meta.st_mode)and meta.st_uid==0 and meta.st_nlink==1,'unsafe operator lock');fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for p in LOCKS:
   fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW);handles.append(fd);s=os.fstat(fd);require(stat.S_ISREG(s.st_mode)and s.st_uid==0,'unsafe package lock');fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  require(not package_processes(),'active package/initramfs operation')
  require(not any(p.name.isdigit()for p in pathlib.Path('/var/lib/dpkg/updates').iterdir()),'pending dpkg updates')
  yield
 finally:
  for fd in reversed(handles):os.close(fd)
def inventory_guard(s,h):
 observed={'hostname':socket.gethostname(),'kernel':os.uname().release,'initramfs_lister':'lsinitramfs'}
 h.validate_identity(s,h.own_node(s['node']),observed,pathlib.Path('/'))
 require(pathlib.Path('/sys/module/nfsv4/parameters/directory_delegations').read_text().strip()=='N','runtime N changed')
 require(metadata(IMAGE)==s['expected_initrd'],'initrd preimage changed')
 require(sha('/usr/sbin/update-initramfs')==UPDATER_SHA,'native updater changed')
 for p,want in s['expected_tools'].items():require(sha(p)==want,'native tool changed')
 for entry in s['preserved_boot_metadata']:require(metadata(entry['path'])==entry,'boot config changed')
 for base,expected in s['post_update_entries'].items():require((sorted(p.name for p in pathlib.Path(base).iterdir())if pathlib.Path(base).is_dir()else None)==expected,'post-update hook inventory changed')
 require(not CONFIG.is_symlink()and CONFIG.read_bytes()==LINE,'persisted exact option required')
 require(sha(s['persisted_operation'])==s['persisted_operation_sha256'],'persistence journal changed')
 journal=json.loads(pathlib.Path(s['persisted_operation']).read_text());require(journal.get('effective_option_verified')is True and journal['selection']['node_uid']==s['node_uid']and journal['selection']['boot_id']==s['boot_id'],'persistence proof identity')
 require(hashlib.sha256(h.run_command(['modprobe','--showconfig']).encode()).hexdigest()==journal['after']['modprobe_config_sha256'],'effective module configuration drift')
 require(not any(IMAGE.with_name(IMAGE.name+suffix).exists()for suffix in ['.new','.dpkg-bak','.bak']),'preexisting updater sidefile: review before rebuild')
 return observed
def execute(s):
 validate_release(s);require(os.geteuid()==0 and os.environ.get('INVOCATION_ID'),'Root durable systemd invocation required');h=load_helper()
 with locks():
  observed=inventory_guard(s,h);expanded=expanded_size();space=check_space(IMAGE.stat().st_size,expanded,shutil.disk_usage('/boot').free,shutil.disk_usage('/var/lib').free,sum(x['size']for x in [s['expected_initrd'],*s['preserved_boot_metadata']]if 'sha256'in x),same_fs=os.stat('/boot').st_dev==os.stat('/var/lib').st_dev)
  state=STATE/s['operation_id'];require(not state.exists()and not state.is_symlink(),'existing operation: reconcile, never replay');h.protected_parents(pathlib.Path('/'),state)
  STATE.mkdir(mode=0o700,exist_ok=True);h.sync_directory(STATE.parent);state.mkdir(mode=0o700);h.sync_directory(STATE)
  before={'selection':s,'status':'backup-intent','space':space,'coldbootQualified':False,'rebootPerformed':False,'runtimeParameterWritten':False}
  def save():h.atomic_write(state/'operation.json',(json.dumps(before,indent=2)+'\n').encode(),0o600)
  save()
  try:
   # Originals remain untouched; backup file mode is intentionally root0600.
   backups=[]
   for i,entry in enumerate([s['expected_initrd'],*s['preserved_boot_metadata']]):
    if entry.get('symlink')or 'sha256'not in entry:continue
    src=pathlib.Path(entry['path']);dest=state/('preimage-'+str(i));require(metadata(src)==entry,'backup source changed')
    with src.open('rb')as read,dest.open('xb')as write:
     os.fchmod(write.fileno(),0o600);shutil.copyfileobj(read,write,1024*1024);write.flush();os.fsync(write.fileno())
    h.sync_directory(state);require(sha(dest)==entry['sha256']and metadata(src)==entry,'backup not exact');backups.append({'file':dest.name,'original':entry,'sha256':sha(dest)})
   before.update(status='backup-verified',backups=backups);save();inventory_guard(s,h)
   # Exactly one stock selected-kernel update. The systemd service controls the
   # whole process group on timeout; a killed unit leaves this durable intent.
   before['status']='native-update-running';save()
   tmp=state/'native-tmp';tmp.mkdir(mode=0o700);h.sync_directory(state)
   log=state/'native-update.log';fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);h.sync_directory(state)
   with os.fdopen(fd,'wb')as output:
    result=subprocess.run(['/usr/sbin/update-initramfs','-u','-k',KERNEL],stdout=output,stderr=subprocess.STDOUT,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TMPDIR':str(tmp)});output.flush();os.fsync(output.fileno())
   before.update(nativeReturnCode=result.returncode,updateLogSHA256=sha(log));save();require(result.returncode==0,'native updater failed; no retry')
   require(IMAGE.is_file()and not IMAGE.is_symlink(),'new image missing/unsafe');h.sync_directory(IMAGE.parent)
   before.update(status='native-updated-validation-pending',newInitrd=metadata(IMAGE));save()
   require(all(before['newInitrd'][k]==s['expected_initrd'][k]for k in ['uid','gid','mode']),'new initrd ownership/mode differs')
   require('nfsv4.ko' in subprocess.check_output(['lsinitramfs',str(IMAGE)],text=True,stderr=subprocess.PIPE,timeout=60),'nfsv4 missing from regenerated image')
   for entry in s['preserved_boot_metadata']:require(metadata(entry['path'])==entry,'boot config drift after update')
   require(CONFIG.read_bytes()==LINE and pathlib.Path('/sys/module/nfsv4/parameters/directory_delegations').read_text().strip()=='N','N configuration/runtime changed')
   extract=state/'extracted';r=subprocess.run(['unmkinitramfs',str(IMAGE),str(extract)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);require(r.returncode==0,'embedded extraction failed')
   embedded=verify_embedded(extract);h.validate_identity(s,h.own_node(s['node']),observed,pathlib.Path('/'))
   before.update(status='regenerated-embedded-config-verified-coldboot-pending',embeddedConfig=embedded);save();print(json.dumps({'operation':str(state),'status':before['status'],'newInitrdSHA256':before['newInitrd']['sha256'],'coldbootQualified':False}))
  except BaseException as exc:
   before.update(status='HOLD-reconcile',failureType=type(exc).__name__);save();raise
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selection',type=pathlib.Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();s=json.loads(a.selection.read_text())
 if a.execute:execute(s)
 else:print(json.dumps({'mutation':False,'selectedNode':s.get('node'),'kernel':KERNEL,'rootRelease':s.get('root_release'),'command':['/usr/sbin/update-initramfs','-u','-k',KERNEL],'coldbootQualified':False}))
