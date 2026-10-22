#!/usr/bin/env python3
"""Cold Node startup only: derive one UUID CDI provider from a pinned source.

No allocation, driver mutation, API calls or admission changes. Installed SDK
validators and the trusted target Node configuration retain their authority.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
from cps_compute.native_node import cdi
from cps_compute import native_gpu_health as health

SOURCE='k8s.device-plugin.nvidia.com-gpu.json'
OUTPUT='cps-native-selected-147.json'
HEALTH_SHA256='fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8'


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def unique(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'Duplicate JSON key')
        result[k]=v
    return result


def document(raw):
    require(type(raw) is bytes and len(raw)<=262144,'Bounded raw JSON required')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'Nonfinite JSON'))


def render(source_raw,pins,inventory,gpu_uuid):
    require(type(pins) is cdi.CDIRuntimePins and pins.selected_filename==OUTPUT,
        'Explicit cold selected CDI filename required')
    require(hashlib.sha256(source_raw).hexdigest()==pins.other_cdi_files.get(SOURCE),
        'Pinned original device-plugin descriptor required')
    source=document(source_raw)
    require(type(source) is dict and set(source)=={'cdiVersion','kind','devices','containerEdits'}
        and source['cdiVersion']=='0.5.0' and source['kind']=='k8s.device-plugin.nvidia.com/gpu'
        and type(source['devices']) is list and 1<=len(source['devices'])<=32,
        'Exact device-plugin CDI source required')
    require(all(type(d) is dict and set(d)=={'name','containerEdits'} and cdi.valid_uuid(d['name'])
        for d in source['devices']) and len({d['name'] for d in source['devices']})==len(source['devices']),
        'Unique canonical UUID devices required; all alias refused')
    selected=[d for d in source['devices'] if d['name']==gpu_uuid]
    require(len(selected)==1,'Exactly one selected UUID required')
    result={'cdiVersion':source['cdiVersion'],'kind':'management.nvidia.com/gpu',
        'containerEdits':deepcopy(source['containerEdits']),'devices':deepcopy(selected)}
    cdi.validate_current_cdi(result,inventory,gpu_uuid,pins=pins)
    return canonical(result)


def _search_precheck(root,pins,*,staged=None,trusted_uid=0):
    try:other=cdi._directory_names(root/'etc/cdi')
    except FileNotFoundError:other=[]
    require(not other,'Alternate CDI directory refused')
    names=set(cdi._directory_names(root/'run/cdi'))
    if staged is not None:
        name,held,raw=staged
        require(type(name) is str and name.startswith('.cps-selected-')
            and str(uuid.UUID(name.removeprefix('.cps-selected-')))==name.removeprefix('.cps-selected-'),
            'Exact own temporary name required')
        current=cdi._device_stat(root/'run/cdi'/name);owned=os.fstat(held)
        require(stat.S_ISREG(owned.st_mode) and owned.st_uid==trusted_uid
            and stat.S_IMODE(owned.st_mode)==0o644 and owned.st_nlink==1
            and (current.st_dev,current.st_ino)==(owned.st_dev,owned.st_ino)
            and cdi.read_root_file(root/'run/cdi'/name,trusted_uid=trusted_uid)==raw,
            'Only held exact private staging inode may be excluded')
        require(name in names,'Own staging file disappeared');names.remove(name)
    require(names in (set(pins.other_cdi_files),set(pins.other_cdi_files)|{OUTPUT}),
        'Unreviewed CDI provider present')
    for name,pin in pins.other_cdi_files.items():
        require(hashlib.sha256(cdi.read_root_file(root/'run/cdi'/name)).hexdigest()==pin,'CDI provider changed')
    for name,pin in pins.runtime_files.items():
        require(hashlib.sha256(cdi.read_root_file(root/name)).hexdigest()==pin,'CDI runtime configuration changed')


def publish(directory,raw,*,before,after,trusted_uid=0):
    """FD-anchored exclusive publication. Existing wrong content is never replaced."""
    fd=cdi._open_directory(directory);temporary='.cps-selected-'+str(uuid.uuid4())
    try:
        info=os.fstat(fd)
        require(info.st_uid==trusted_uid and not info.st_mode&0o022,'Protected root CDI directory required')
        before()
        try:
            current=cdi.read_root_file(Path(directory)/OUTPUT,trusted_uid=trusted_uid)
        except FileNotFoundError:current=None
        require(current is None or current==raw,'Existing selected descriptor differs; explicit migration required')
        if current is None:
            out=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644,dir_fd=fd)
            try:
                with os.fdopen(out,'wb') as stream:
                    os.fchmod(stream.fileno(),0o644)
                    stream.write(raw);stream.flush();os.fsync(stream.fileno())
                    before(staged=(temporary,stream.fileno(),raw))
                    # link publishes a fully fsynced inode atomically and cannot replace a racing writer.
                    os.link(temporary,OUTPUT,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
                os.unlink(temporary,dir_fd=fd);os.fsync(fd)
            finally:
                try:os.unlink(temporary,dir_fd=fd)
                except FileNotFoundError:pass
        require(cdi.read_root_file(Path(directory)/OUTPUT,trusted_uid=trusted_uid)==raw,'Selected descriptor publication changed')
        after()
    finally:os.close(fd)


def execute(settings,*,host_root=Path('/host'),directory=Path('/cdi')):
    require(type(settings) is dict and set(settings)=={'version','node_pool','cdi_pins','authority_directory'}
        and type(settings['version']) is int and settings['version']==1,'Closed startup settings required')
    pool=settings['node_pool'];pins=cdi.CDIRuntimePins.from_dict(settings['cdi_pins'])
    require(type(pool) is dict and set(pool)=={'node_uid','boot_id','driver_generation','gpu_uuid'},'Exact epoch required')
    require(all(type(pool[k]) is str and str(uuid.UUID(pool[k]))==pool[k] and uuid.UUID(pool[k]).int!=0
        for k in ('node_uid','boot_id','driver_generation')) and cdi.valid_uuid(pool['gpu_uuid']), 'Canonical epoch required')
    authority=settings['authority_directory']
    require(type(authority) is str and authority.startswith('var/lib/cps-native-gpu/domains/')
        and authority.endswith('/custody/authority') and '..' not in Path(authority).parts,'Durable authority path required')
    token=authority.removeprefix('var/lib/cps-native-gpu/domains/').removesuffix('/custody/authority')
    require(str(uuid.UUID(token))==token and uuid.UUID(token).int!=0,'Canonical durable domain required')
    require(os.geteuid()==0 and hashlib.sha256(Path(health.__file__).read_bytes()).hexdigest()==HEALTH_SHA256,
        'Exact147 SDK health source and Root required')
    require((host_root/'proc/sys/kernel/random/boot_id').read_text().strip()==pool['boot_id'],'Actual boot changed')
    def epoch(*,staged=None):
        require((host_root/'proc/sys/kernel/random/boot_id').read_text().strip()==pool['boot_id'],'Actual boot changed')
        require(health.validate_native_driver_health(module_directory=host_root/'sys/module',
            authority_directory=host_root/authority,boot_id=pool['boot_id'])==pool['driver_generation'],
            'Fresh147 driver authority changed')
        _search_precheck(host_root,pins,staged=staged)
    epoch()
    inventory=cdi.read_inventory(host_root=host_root,proc_path=host_root/'proc/driver/nvidia/gpus')
    raw=render(cdi.read_root_file(host_root/'run/cdi'/SOURCE),pins,inventory,pool['gpu_uuid'])
    # The RW mount must refer to the same directory proved through the read-only host tree.
    a=cdi._open_directory(directory);b=cdi._open_directory(host_root/'run/cdi')
    try:require((os.fstat(a).st_dev,os.fstat(a).st_ino)==(os.fstat(b).st_dev,os.fstat(b).st_ino),'CDI mounts differ')
    finally:os.close(a);os.close(b)
    def finished():
        epoch()
        cdi.observe_current_cdi(pool['gpu_uuid'],pins=pins,host_root=host_root,
            proc_path=host_root/'proc/driver/nvidia/gpus')
    publish(directory,raw,before=epoch,after=finished)
    return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--settings',type=Path);args=parser.parse_args()
    if not args.execute:print(json.dumps({'state':'inert'}));return
    require(args.settings is not None,'Protected settings path required')
    digest=execute(document(cdi.read_root_file(args.settings)))
    print(json.dumps({'state':'selected-cdi-verified','sha256':digest}))

if __name__=='__main__':main()
