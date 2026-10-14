"""Read-only, explicit root witness inside the pinned507 node Pod. Default is inert."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

NODE_CODE_SHA = 'f01b24bc984a153e9995549ef09f73167500f375d79e078a7e7aa9e1171c3664'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GENERATION = 'b10498fc-9153-4394-875a-ea7cfb498625'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'


def need(ok, msg):
    if not ok: raise ValueError(msg)


def checksum(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observer(na, uid, binding_id, phase, crictl):
    adapter, q, modules = na.load_bundle('/opt/native')
    m, manual, health = modules['models'], modules['manual'], modules['health']
    state = Path('/run/cps-native-gpu')
    envelope = adapter.private_read(state/'enrollments'/(uid+'.json'), 0)
    enrollment = envelope['enrollment']; need(enrollment['binding_id']==binding_id
        and enrollment['source']=='cit' and enrollment['workspace']=='native-group-a'
        and enrollment['profile']=='interactive-native-qualification-10' and enrollment['cap_mib']==10240,
        'Exact signed10 enrollment required')
    intent=m.CapIntent(**enrollment['intent'])
    need(intent.pod_uid==uid and intent.node_uid==NODE_UID and intent.gpu_uuid==GPU, 'Exact Pod/node/device required')
    kube=na.api_class(q)(Path('/var/run/secrets/kubernetes.io/serviceaccount'))
    driver=manual.Nvml()
    try:
        def epoch(): return na.abort_current_epoch({'pool': {'node_uid': NODE_UID, 'gpu_uuid': GPU}},state,driver,health,m)
        first=epoch(); need(first.boot_id==BOOT and first.driver_generation==GENERATION, 'Current physical epoch required')
        config=na.read_config(Path('/config/config.json'))
        need(config['version']==2 and config['mode']=='operator-qualification'
             and config['workspaces']=={'cit:native-group-a':{'profile':'interactive-native-qualification-10','cap_mib':10240}},'Actual node mode/scope changed')
        actual=kube.configmap(envelope['authority_namespace'],envelope['configmap_name'])
        need(na.validate_enrollment(actual,config,m)==envelope,'Current immutable enrollment differs from protected mirror')
        node=kube.node(intent.node); need(node['metadata']['uid']==NODE_UID, 'Actual post-Bind Node UID changed')
        backend=adapter.QualificationNodeBackend(m,manual,intents=[intent],driver=driver,
            get_pod=kube.pod,get_node=kube.node,get_cri=q.cri_reader(crictl,'unix:///host/run/k3s/containerd/containerd.sock'),
            delete_pod=lambda *a: (_ for _ in ()).throw(ValueError('observer cannot delete')),
            gpu_clients=q.gpu_clients,health=lambda:q.health(driver,health,authority_directory=str(state/'authority')),state_root=state)
        journal=m.PrivateJournal.__new__(m.PrivateJournal);journal.directory=state/'journal'
        record=journal.read(uid)
        pod=kube.pod(intent)
        out={'phase':phase,'pod_uid':uid,'binding_id':binding_id,'epoch':first.__dict__,
             'actual_node':{'uid':node['metadata']['uid'],'resourceVersion':node['metadata']['resourceVersion']},
             'native_writes':False,'hardware_qualified':False}
        if phase=='before-cuda':
            need(pod is not None, 'Actual bound first-gate Pod required')
            na.validate_actual_pod(pod,enrollment);na.validate_device_identity_barrier(pod,intent)
            obs=backend.observe(intent)
            out.update(identity=obs.identity.to_dict(),actual_spec_sha256=checksum(pod['spec']),
                no_user_init_started=True, gate_receipt_present=backend.read_gate(obs.identity) is not None,
                native_readback=backend._raw(obs.identity))
        elif phase=='running':
            need(pod is not None and record is not None and record.state=='sealed', 'Actual sealed running journal required')
            na.validate_actual_pod(pod,enrollment);na.validate_device_identity_barrier(pod,intent)
            backend._current(record.identity);need(record.identity.epoch==first, 'Actual sealed epoch required')
            need(backend.read_gate(record.identity)==record.receipt(), 'Exact sealed-before-user-init receipt required')
            cap=backend._raw(record.identity);need(cap['soft']==cap['hard']==10240*1048576, 'Actual10GiB cap readback required')
            cdi=na.validate_cdi_binding(intent,state,driver,health,modules['cdi'],m)
            status=next(s for s in pod['status']['containerStatuses'] if s['name']=='notebook')
            cid=status['containerID'];need(cid.startswith('containerd://'),'Actual containerd identity required')
            # q.cri_reader intentionally resolves the first gate. Running notebook
            # identity requires its actual CRI ID independently, never its name.
            import subprocess
            cri=json.loads(subprocess.check_output([str(crictl),'--runtime-endpoint','unix:///host/run/k3s/containerd/containerd.sock','inspect',cid.split('://',1)[1]],timeout=10))
            labels=cri['status']['labels'];need(cri['status']['state']=='CONTAINER_RUNNING'
                and all(labels.get(k)==v for k,v in {'io.kubernetes.pod.uid':uid,
                    'io.kubernetes.pod.namespace':intent.namespace,'io.kubernetes.pod.name':intent.name,
                    'io.kubernetes.container.name':'notebook'}.items()),'Actual own notebook CRI identity required')
            pid=cri['info']['pid'];need(type(pid) is int and pid>0,'Actual hostPID required')
            proc=Path('/proc')/str(pid);before=proc.joinpath('stat').read_text();ticks=int(before.rsplit(') ',1)[1].split()[19])
            relative=proc.joinpath('cgroup').read_text().strip();need(relative.startswith('0::/'),'Unified CRI cgroup required')
            leaf=manual.safe_path(Path('/sys/fs/cgroup'),relative[3:]);parent=leaf.parent;info=parent.stat()
            need(parent==Path(record.identity.cgroup_path)
                and (info.st_dev,info.st_ino)==(record.identity.cgroup_device,record.identity.cgroup_inode), 'Actual notebook is outside original capped parent')
            need(int(proc.joinpath('stat').read_text().rsplit(') ',1)[1].split()[19])==ticks,'Actual PID replaced during capture')
            current=kube.pod(intent);need(current['metadata']['uid']==uid and checksum(current['spec'])==intent.spec_sha256,'Current full Pod changed')
            out.update(identity=record.identity.to_dict(),seal=record.receipt(),native_readback=cap,cdi=cdi,
                cri={'container_id':cid,'host_pid':pid,'pid_start_ticks':ticks,'cgroup_relative':relative[3:],
                     'parent_inode':info.st_ino,'parent_device':info.st_dev},init_statuses=pod['status'].get('initContainerStatuses',[]))
        else:
            need(pod is None and record is not None,'Exact Pod absence and durable original journal required')
            receipt=na.cleanup_receipt(envelope,record,backend,pod,m)
            actual=kube.configmap(envelope['authority_namespace'],'cps-native-cleanup-'+binding_id[:40])
            need(actual is not None and actual.get('immutable') is True,
                 'Actual immutable cleanup publication required')
            # Canonical full expected object validation uses the installed node validator.
            na.validate_cleanup(actual,receipt)
            out.update(cleanup=actual,journal_state=record.state,native_zero=True)
        need(epoch()==first and kube.node(intent.node)['metadata']['uid']==NODE_UID, 'Epoch/node changed across witness')
        return out
    finally: driver.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--phase',choices=['before-cuda','running','terminal']);p.add_argument('--pod-uid');p.add_argument('--binding-id');p.add_argument('--crictl')
    a=p.parse_args()
    if not a.execute: print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False}));return
    need(os.geteuid()==0 and a.phase and a.pod_uid and re.fullmatch('[a-f0-9]{60}',a.binding_id or '')
         and a.crictl and a.crictl.startswith('/host/var/lib/rancher/k3s/data/'),'Explicit bounded root witness required')
    source=Path('/opt/native/node_agent.py');need(hashlib.sha256(source.read_bytes()).hexdigest()==NODE_CODE_SHA,'Exact reviewed507 operator epoch patch required')
    sys.path.insert(0,'/opt/native');spec=importlib.util.spec_from_file_location('_verified_node_agent',source)
    na=importlib.util.module_from_spec(spec);sys.modules[spec.name]=na;spec.loader.exec_module(na)
    print(json.dumps(observer(na,a.pod_uid,a.binding_id,a.phase,Path(a.crictl)),sort_keys=True))

if __name__=='__main__':main()
