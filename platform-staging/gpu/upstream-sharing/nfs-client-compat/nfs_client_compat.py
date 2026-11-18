"""Default inspect; explicitly released persistence of ONE standard module option.

Run in the selected host namespaces using existing operator transport. No daemon,
runtime parameter writes, module reload, initramfs regeneration or reboot.
"""
import argparse,base64,hashlib,json,os,pathlib,re,shlex,shutil,socket,stat,subprocess,tempfile,uuid

TARGET='etc/modprobe.d/90-cps-nfs-directory-delegations.conf'
STATE='var/lib/cps-nfs-client-compat'
PARAM='sys/module/nfsv4/parameters/directory_delegations'
LINE=b'options nfsv4 directory_delegations=N\n'

def require(condition,message):
 if not condition:raise ValueError(message)

def digest(value):return hashlib.sha256(value).hexdigest()

def preimage(path):
 require(not path.is_symlink(),'symlink configuration refused')
 if not path.exists():return {'exists':False}
 s=path.stat();require(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'single regular configuration file required')
 require(s.st_uid==os.geteuid()and not s.st_mode&0o022,'configuration ownership/permissions unsafe')
 return {'exists':True,'sha256':digest(path.read_bytes()),'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'inode':s.st_ino}

def validate_identity(selection,node,observed,root):
 for field in ['node','node_uid','boot_id','kernel']:require(isinstance(selection.get(field),str)and selection[field], 'selected '+field+' required')
 require(re.fullmatch(r'k3s-wk-gpu[1-4]',selection['node']),'selected worker required')
 for field in ['node_uid','boot_id']:require(str(uuid.UUID(selection[field]))==selection[field],'canonical selected identity required')
 require(re.fullmatch(r'7\.[0-9A-Za-z.+_-]+',selection['kernel']),'reviewed kernel7 required')
 info=node['status']['nodeInfo'];meta=node['metadata']
 require(meta['name']==selection['node']and meta['uid']==selection['node_uid']and not meta.get('deletionTimestamp'),'Node UID/name changed')
 require(info['bootID']==selection['boot_id']and info['kernelVersion']==selection['kernel'],'Node boot/kernel changed')
 require(info['osImage']=='Ubuntu 26.04.1 LTS','reviewed Ubuntu26.04.1 required')
 require(any(c.get('type')=='Ready'and c.get('status')=='True'for c in node['status'].get('conditions',[])),'Ready Node required')
 require(observed['hostname']==selection['node']and observed['kernel']==selection['kernel'],'host name/kernel mismatch')
 require((root/'proc/sys/kernel/random/boot_id').read_text().strip()==selection['boot_id'],'host boot mismatch')

def option_values(config):
 values=[]
 for line in config.splitlines():
  tokens=shlex.split(line,comments=True)
  # Alias options are combined by kmod too. Refuse a contradictory spelling
  # anywhere, rather than relying on duplicate-argument order at module load.
  if len(tokens)>2 and tokens[0]=='options':
   for token in tokens[2:]:
    key,separator,value=token.partition('=')
    if separator and key.replace('-','_')=='directory_delegations':values.append(value)
 return values

def inspect_host(root,observed,command):
 config=command(['modprobe','--showconfig']);module=command(['modinfo','-k',observed['kernel'],'-F','filename','nfsv4']).strip()
 image=root/('boot/initrd.img-'+observed['kernel']);require(image.is_file(),'selected kernel initramfs unavailable: inspect before persistence')
 lister=observed.get('initramfs_lister','lsinitramfs');require(lister in['lsinitramfs','lsinitrd'],'supported native initramfs listing utility required')
 listing=command([lister,str(image)]).splitlines()
 files=listing if lister=='lsinitramfs'else[line.split()[-1]for line in listing if line.split()]
 in_image=any(re.search(r'(^|/)nfsv4\.ko(\.(xz|gz|zst))?$',name)for name in files)
 config_entry=any(name.lstrip('/')==TARGET or name.endswith('/'+TARGET)for name in files)
 params=[t.split('=',1)[1]for t in shlex.split((root/'proc/cmdline').read_text())if t.partition('=')[0].replace('-','_')=='nfsv4.directory_delegations'and'='in t]
 return {'hostname':observed['hostname'],'kernel':observed['kernel'],'boot_id':(root/'proc/sys/kernel/random/boot_id').read_text().strip(),
  'preimage':preimage(root/TARGET),'runtime_value':(root/PARAM).read_text().strip()if(root/PARAM).exists()else None,
  'module_filename':module,'effective_option_values':option_values(config),'modprobe_config_sha256':digest(config.encode()),
  'install_override':any(len(t)>1 and t[0]=='install'and t[1]in['nfsv4','nfs4','fs-nfs4']for t in(shlex.split(l,comments=True)for l in config.splitlines())),
  'kernel_cmdline_option_values':params,
  'initramfs':{'path':str(image),'listing_utility':lister,'sha256':digest(image.read_bytes()),'nfsv4_module_present':in_image,
   'config_entry_present':config_entry,'refresh_required_before_boot_qualification':in_image and not config_entry,
   'embedded_config_content_verification_required':in_image,'embedded_config_content_verified':False},'mutation':False}

def protected_parents(root,path):
 for p in path.parents:
  if p==root:break
  require(not p.is_symlink(),'symlink parent refused')
  if p.exists():
   s=p.stat();require(stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()and not s.st_mode&0o022,'unsafe parent ownership/permissions')

def sync_directory(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

def atomic_write(path,data,mode,uid=None,gid=None):
 fd,name=tempfile.mkstemp(prefix='.cps-nfs-',suffix='.tmp',dir=path.parent)
 try:
  with os.fdopen(fd,'wb')as stream:
   if uid is not None:os.fchown(stream.fileno(),uid,gid)
   os.fchmod(stream.fileno(),mode);stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(name,path)
  directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(directory)
  finally:os.close(directory)
 finally:
  if os.path.exists(name):os.unlink(name)

def persist(root,selection,node_reader,observed,command):
 require(isinstance(selection.get('root_release'),str)and selection['root_release'].strip(),'UNARMED Root release required')
 for field in ['canary_sha256','peer_sha256']:require(isinstance(selection.get(field),str)and re.fullmatch('[0-9a-f]{64}',selection[field]),'physical canary + peer receipt required')
 operation=selection.get('operation_id');require(isinstance(operation,str)and str(uuid.UUID(operation))==operation,'unique operation UUID required')
 validate_identity(selection,node_reader(),observed,root)
 target=root/TARGET;state=root/STATE/operation
 require(not state.exists()and not state.is_symlink(),'prior operation: reconcile; never replay')
 protected_parents(root,target);protected_parents(root,state)
 before=inspect_host(root,observed,command)
 require(before['preimage']==selection.get('expected_preimage'),'configuration preimage changed')
 require(before['runtime_value']=='N','reviewed runtime canary N must already be active; this helper never changes runtime')
 require(before['module_filename']and before['module_filename']!='(builtin)','loadable nfsv4 required; built-in module needs separate kernel-command-line review')
 require(not before['install_override'],'custom nfsv4 install override: reconcile before configuration')
 require(all(v=='N'for v in before['effective_option_values']+before['kernel_cmdline_option_values']),'conflicting directory_delegations option: reconcile')
 original=target.read_bytes()if before['preimage']['exists']else b''
 # Keep exact existing bytes/mode; do not rewrite a matching option.
 own_option=any(t[:2]==['options','nfsv4']and any(v.replace('-','_')=='directory_delegations=N'for v in t[2:])for t in(shlex.split(l,comments=True)for l in original.decode().splitlines()))
 desired=original if own_option else original+(b''if not original or original.endswith(b'\n')else b'\n')+LINE
 (root/STATE).mkdir(mode=0o700,exist_ok=True)
 sync_directory((root/STATE).parent)
 state.mkdir(mode=0o700)
 sync_directory(state.parent)
 backup={**before['preimage'],'content_base64':base64.b64encode(original).decode()}
 atomic_write(state/'preimage.json',json.dumps(backup,indent=2).encode()+b'\n',0o600)
 journal={'selection':selection,'status':'intent-config-persist','before':before,'desired_sha256':digest(desired),
  'runtime_parameter_written':False,'initramfs_regenerated':False,'reboot_performed':False,'coldboot_qualified':False,'config_file_written':False,'file_contents_changed':original!=desired}
 def save():atomic_write(state/'operation.json',json.dumps(journal,indent=2).encode()+b'\n',0o600)
 save()
 try:
  validate_identity(selection,node_reader(),observed,root)
  require(preimage(target)==before['preimage'],'configuration preimage changed before replace')
  require(digest(command(['modprobe','--showconfig']).encode())==before['modprobe_config_sha256'],'effective module configuration changed before replace')
  meta=before['preimage'];atomic_write(target,desired,meta.get('mode',0o644),meta.get('uid',os.geteuid()),meta.get('gid',os.getegid()))
  journal['config_file_written']=True
  after=inspect_host(root,observed,command)
  require(after['effective_option_values']and all(v=='N'for v in after['effective_option_values']),'effective modprobe option verification failed')
  require(after['runtime_value']=='N','runtime canary changed during persistence')
  validate_identity(selection,node_reader(),observed,root)
  journal.update(status='rootfs-configured-initramfs-review-pending'if after['initramfs']['nfsv4_module_present']else'rootfs-configured-coldboot-pending',after=after,effective_option_verified=True,initramfs=after['initramfs'])
  save();return journal
 except BaseException:
  journal['status']='HOLD-reconcile';save();raise

def run_command(args):
 env=dict(os.environ);env.pop('MODPROBE_OPTIONS',None)
 return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=30,env=env)

def own_node(name):
 return json.loads(run_command(['/usr/local/bin/k3s','kubectl','--kubeconfig','/var/lib/rancher/k3s/agent/kubelet.kubeconfig','--request-timeout=10s','get','--raw','/api/v1/nodes/'+name]))

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--selection',required=True,type=pathlib.Path);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 selection=json.loads(args.selection.read_text());root=pathlib.Path('/');lister=next((n for n in['lsinitramfs','lsinitrd']if shutil.which(n)),None)
 require(lister is not None,'native lsinitramfs/lsinitrd unavailable: inspect installed boot tooling before persistence')
 observed={'hostname':socket.gethostname(),'kernel':os.uname().release,'initramfs_lister':lister}
 validate_identity(selection,own_node(observed['hostname']),observed,root)
 if args.apply:
  require(os.geteuid()==0,'host root required for explicitly released persistence')
  result=persist(root,selection,lambda:own_node(observed['hostname']),observed,run_command)
 else:result=inspect_host(root,observed,run_command)
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
