#!/usr/bin/env python3
"""Default-inert preparation for actual current normal-lifecycle CPS5/CIT20.

No Kubernetes, GPU, Start/Stop, source handover or passed-evidence operations.
The original25 protocols, current630 host guards and trusted20 ELF are reused.
"""
import argparse
import ast
import base64
import copy
import json
from pathlib import Path
import types
import prepare_harness as legacy
import prepare_current_group_harness as current

HERE=Path(__file__).parent
HARNESS_SHA='c53e536718edc3c4e5daff9c64ddf77ab28847a28457065afbbcf4ce3025c9a3'
CURRENT_SHA='caddf91ed0f0ab9b3190349e64bdcc85884473dc260cbc916cf2ee68b2773c71'
PROFILE20_SOURCE=Path('/home/bjoern/.local/state/cps-platform-completion-20261011/native20-probes-source-prepared-20261012/source-v3/prepare_profile20.py')
PROFILE20_SHA='5d78371154dd0fa4a3564a5ff39b04f2fc7373fc39b4f60403a7ac0033cfd6e8'
CAPTURE_TEMPLATE=Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012/capture-actual-v3/read-only-host-capture.py')
TERMINAL_SOURCE=Path('/home/bjoern/git/cps-gpu-cluster-worktrees/current-groups-to-profile20-20261012/platform-staging/gpu/native-group-pilot/terminal_policy_proposal.py')
TERMINAL_SHA='d2290c2172cd50ff861f13ff274864344c261edbc3bd28c9b81bcb55a597a43c'
POLICY_HASH='sha256:39ef15d3b5a76f96d135beb1afcd538775c64301cb51751086b44d68c54f8012'
PROFILE_CAPS={'interactive-native-qualification-5':5120,'interactive-native-qualification-20':20480}


def module(name,raw,path):
    result=types.ModuleType(name);result.__file__=str(path)
    exec(compile(raw,str(path),'exec'),result.__dict__)
    return result


def loaders():
    """Exact siblings only; legacy source files are never modified."""
    hraw=legacy.read_pinned(HERE/'prepare_harness.py',HARNESS_SHA)
    craw=legacy.read_pinned(HERE/'prepare_current_group_harness.py',CURRENT_SHA)
    p=module('fixed20_protocol',legacy.read_pinned(PROFILE20_SOURCE,PROFILE20_SHA,private=True),PROFILE20_SOURCE)
    code=hraw.decode()
    for old,new,count in [
        ("'jupyter-citnativegroupa--rtc', 10240)","'jupyter-citnativegroupa--rtc', 20480)",1),
        ("p['budget_mib'] == 15360","p['budget_mib'] == 25600",1),
        ("p['headroom_bytes'] > 0","p['headroom_bytes'] == 1073741824",1),
        ('cover15GiB','cover25GiB',1),('CIT A10','CIT A20',1),
        ('cap_mib in (5120, 10240)','cap_mib in (5120, 10240, 20480)',1),
        ('else if(!strcmp(n,"10240"))cap_mib=10240;else return 2;',
         'else if(!strcmp(n,"10240"))cap_mib=10240;else if(!strcmp(n,"20480"))cap_mib=20480;else return 2;',1),
        ('native-imports-10','native-imports-20',3)]:code=p.replace(code,old,new,count)
    h=module('current_operator20_harness',code.encode(),HERE/'prepare_harness.py')
    ccode=p.replace(craw.decode(),"h._validate_binding(binding, 'interactive-shared-')",
        "h._validate_binding(binding, 'interactive-native-qualification-')")
    c=module('current_operator20_host',ccode.encode(),HERE/'prepare_current_group_harness.py');c.h=h
    original=h._render_validated_sources
    def render(*args,**kw):
        out=original(*args,**kw);old_pre=out['run_group_acceptance.py'];pre=old_pre.decode()
        pre=p.replace(pre,'BUDGET_BYTES = 16106127360','BUDGET_BYTES = 26843545600')
        for old,new in [('(10240 if aggregate else 5120)','(20480 if aggregate else 5120)'),
            ("failure.get('cap_mib')==10240","failure.get('cap_mib')==20480"),
            ("failure.get('maximum_attempted_tensor_mib')==10496","failure.get('maximum_attempted_tensor_mib')==20736"),
            ('(6656 if aggregate else 9216)','(16896 if aggregate else 19456)'),
            ('(7936 if aggregate else 10240)','(18176 if aggregate else 20480)'),
            ('(8704 if aggregate else 9216)','(18944 if aggregate else 19456)'),
            ('Exact10GiB','Exact20GiB')]:pre=p.replace(pre,old,new)
        out['run_group_acceptance.py']=pre.encode()
        old_helper=out['imports/same_pod_imports.py'];helper=old_helper.decode()
        helper=p.replace(helper,'CAP = 10737418240','CAP = 21474836480')
        helper=p.replace(helper,"'--cap-mib', '10240'","'--cap-mib', '20480'")
        out['imports/same_pod_imports.py']=helper.encode()
        old_group=out['group_probe.py'];out['group_probe.py']=p.replace(old_group.decode(),
            'choices=(5120,10240)','choices=(5120,10240,20480)').encode()
        for name,value in list(out.items()):
            if name.endswith('.py') and name not in ('run_group_acceptance.py','imports/same_pod_imports.py','group_probe.py'):
                for before,after in [(old_pre,out['run_group_acceptance.py']),(old_helper,out['imports/same_pod_imports.py']),(old_group,out['group_probe.py'])]:
                    value=value.replace(h.sha(before).encode(),h.sha(after).encode())
                out[name]=value
        return out
    h._render_validated_sources=render
    return h,c,p


def capture_source(actual_uids):
    """Reviewed read-only capture, varying only the actual two ordered Pod UIDs."""
    legacy.require(isinstance(actual_uids,list) and len(actual_uids)==2 and len(set(actual_uids))==2,
        'Two actual ordered distinct Pod UIDs required')
    for uid in actual_uids:legacy.valid_uuid(uid)
    raw=legacy.read_pinned(CAPTURE_TEMPLATE,current.INVENTORY_CAPTURE_SOURCE_SHA256,private=True)
    tree=ast.parse(raw);found=[n for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='targets' for t in n.targets)]
    legacy.require(len(found)==1,'Exact reviewed capture target assignment required')
    n=found[0];lines=raw.decode().splitlines(keepends=True)
    lines[n.lineno-1:n.end_lineno]=['targets = '+repr(actual_uids)+'\n']
    result=''.join(lines).encode();compile(result,'current-operator20-read-only-capture','exec')
    return result


def validate_inputs(manifest,h,c,p):
    from cps_compute import native_gpu_controller as models
    from cps_compute.native_gpu_control import MeasuredNativeAuthority
    from cps_compute.native_gpu_runtime import validate_native_cap_receipt,validate_native_pod_intent
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.policy import Policy
    # Use the existing source-only custody mapper; no backend is constructed.
    import sys
    pilot=HERE.parents[1]/'native-group-pilot'
    if str(pilot) not in sys.path:sys.path.insert(0,str(pilot))
    import node_agent as agent
    terminal=module("operator20_terminal_mapper",legacy.read_pinned(TERMINAL_SOURCE,TERMINAL_SHA),TERMINAL_SOURCE)
    fields={'version','state','binding','policy','native_qualification','node_config','baseline_terminal_snapshot',
        'ledger_after','authority_after','sealed_targets','inventory_capture'}
    legacy.require(isinstance(manifest,dict) and set(manifest)==fields and type(manifest['version']) is int
        and manifest['version']==1 and manifest['state']=='Root-reviewed-current-operator20-plan',
        'Closed separate actual current operator20 manifest required')
    read=p.input_json
    binding=h.validate_binding(read(manifest['binding']));policy=Policy(read(manifest['policy']))
    config=read(manifest['native_qualification']);mode=NativeGroupQualification.from_config(config,policy)
    legacy.require(mode is not None and mode.policy_hash==binding['policy_hash']==policy.hash==POLICY_HASH
        and config['profile_caps']==PROFILE_CAPS and mode.gate_image==current.GATE_IMAGE,
        'Exact actual operator-only CPS5/CIT20 policy/mode/caps required')
    original=copy.deepcopy(mode.workspaces)
    for scope,size in [('cps:native-group-b',5),('cit:native-group-a',10)]:
        original[scope]['profiles']=['interactive-shared-'+str(size)]
        original[scope]['ceiling']={'cpu':'4','memory':'16Gi','gpuMemoryGiB':size}
    legacy.require(agent.canonical_sha256(original)=='sha256:'+current.APPROVALS_SHA256,
        'Only unchanged reviewed identities/storage/two source scopes are permitted')
    pool=mode.node_pool
    legacy.require(pool['max_workspaces']==2 and pool['memory_budget_mib']==25600 and pool['headroom_mib']==1024
        and all(pool[k]==binding['pool'][k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')),
        'Exact current25GiB two-lifetime pool/epoch required')
    node=read(manifest['node_config']);agent.validate_config(node)
    baseline=read(manifest['baseline_terminal_snapshot'])
    legacy.require(set(baseline)=={'ledger','previous_node','authority_maps','host_snapshot'},
        'Complete unchanged pre-Start released custody snapshot required')
    history=terminal.map_history({k:baseline[k] for k in ('authority_maps','host_snapshot')},baseline['ledger'],baseline['previous_node'])
    legacy.require(node['mode']=='operator-qualification' and node['enabled'] is True and node['policy_hash']==policy.hash
        and node['pool']==pool and node['terminal_history']==history
        and node['workspaces']=={s:{'profile':v['profiles'][0],'cap_mib':v['ceiling']['gpuMemoryGiB']*1024} for s,v in mode.workspaces.items()},
        'Actual operator node must preserve the entire independently validated terminal map')
    seals=manifest['sealed_targets'];legacy.require(isinstance(seals,list) and len(seals)==2,'Both actual sealed Pod lifetimes required')
    records=[];seen=set()
    for target,seal in zip(binding['targets'],seals):
        legacy.require(set(seal)=={'pod_uid','journal','gate_receipt'} and seal['pod_uid']==target['pod_uid'],
            'Actual ordered5/20 PodUID seals required')
        approval=mode.approval(target['source'],target['workspace'])
        legacy.require(approval is not None and approval['profiles']==[target['profile']]
            and approval['namespace']==target['namespace'] and approval['pod']==target['name']
            and mode.cap_mib(target['profile'])==target['cap_mib'],'Exact source-owned operator target required')
        record=models.CapRecord.from_dict(read(seal['journal']));gate=read(seal['gate_receipt'])
        intent={k:target[k] for k in ('namespace','name','pod_uid','spec_sha256','cap_mib')}
        intent.update({k:pool[k] for k in ('node','node_uid','gpu_uuid')},policy_hash=policy.hash)
        legacy.require(record.state=='sealed' and record.intent.to_dict()==intent and gate==record.receipt()
            and record.identity.epoch==models.DriverEpoch(pool['node_uid'],pool['boot_id'],pool['driver_generation'],pool['gpu_uuid'])
            and (record.identity.cgroup_device,record.identity.cgroup_inode) not in seen,'Exact distinct sealed current operator caps/epoch required')
        seen.add((record.identity.cgroup_device,record.identity.cgroup_inode));records.append(record)
        validate_native_cap_receipt(gate,intent,boot_id=pool['boot_id'],pid_start_ticks=record.identity.pid_start_ticks,driver_generation=pool['driver_generation'])
        validate_native_pod_intent(read(target['pod_capture']),intent)
    before=baseline['ledger'];after=read(manifest['ledger_after'])
    legacy.require(after.get('apiVersion')=='v1' and after.get('kind')=='ConfigMap'
        and all(after['metadata'][k]==before['metadata'][k] for k in ('name','namespace','uid'))
        and after['metadata'].get('resourceVersion'),'Exact full current allocation ConfigMap identity required')
    old=agent.parse(before['data']['state.json']);new=agent.parse(after['data']['state.json'])
    validator=MeasuredNativeAuthority.__new__(MeasuredNativeAuthority);validator.pool=pool;validator._validate_allocations(new['allocations'])
    extra=set(new['allocations'])-set(old['allocations'])
    legacy.require(len(extra)==2 and all(new['allocations'].get(k)==v for k,v in old['allocations'].items()),
        'Every previous allocation must remain identical plus exactly two current claims')
    active={row['intent']['pod_uid']:row for k,row in new['allocations'].items() if k in extra and row.get('intent')}
    legacy.require(set(active)=={t['pod_uid'] for t in binding['targets']},'Only actual sealed current Pod intents may join ledger')
    for record in records:
        row=active[record.intent.pod_uid]
        approved=mode.approval(row['source'],row['workspace'])
        legacy.require(approved is not None and row['members']==approved['members']
            and row['group_id']==approved['group_id'] and row['ceiling']==approved['ceiling']
            and row['state']=='enrolled' and row['intent']==record.intent.to_dict()
            and row['profile']=='interactive-native-qualification-'+str(record.intent.cap_mib//1024),
            'Actual current claim must bind exact enrolled operator intent/profile')
    capture=manifest['inventory_capture'];legacy.require(set(capture)=={'inventory','host_records','host_snapshot'},'Full actual capture pins required')
    inventory=read(capture['inventory']);host=read(capture['host_records']);snapshot=read(capture['host_snapshot'])
    source=snapshot['captureSource'];legacy.require(p.input_read(source)==capture_source([t['pod_uid'] for t in binding['targets']]),
        'Exact reviewed read-only capture with only actual UID substitution required')
    legacy.require(type(snapshot['version']) is int and snapshot['version']==1 and snapshot['observerPodUid']==binding['observer_uid']
        and all(snapshot[k]==pool[v] for k,v in [('node','node'),('nodeUid','node_uid'),('bootId','boot_id'),('driverGeneration','driver_generation')])
        and host['healthPassed'] is True and host['sourceSha256']==snapshot['healthSourceSha256']
        =='52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67'
        and host['bootId']==pool['boot_id'] and host['driverGeneration']==pool['driver_generation']
        and host['finiteCaps']==inventory and host['finiteCapsRawSha256']=='sha256:'+capture['inventory']['sha256']
        and legacy.sha(base64.b64decode(host['finiteCapsRawBase64'],validate=True))==capture['inventory']['sha256'],
        'Complete actual raw inventory/current healthy observer epoch required')
    # Re-read all old custody from the actual post-Start capture; remove only
    # the two independently authenticated active lifetimes for the pure mapper.
    authority=read(manifest['authority_after']);old_authority=copy.deepcopy(authority)
    enrollment_names={'cps-native-enrollment-'+k[:40] for k in extra}
    by_name={cm['metadata']['name']:cm for cm in authority['items']}
    legacy.require(len(by_name)==len(authority['items']),'Distinct full actual authority objects required')
    def protected(row):
        legacy.require(isinstance(row,dict) and set(row)=={'uid','mode','nlink','rawSha256','rawBase64','value'}
            and type(row['uid']) is int and row['uid']==0 and type(row['mode']) is int
            and row['mode'] in (0o400,0o600) and type(row['nlink']) is int and row['nlink']==1,
            'Exact root-owned no-link protected current evidence required')
        raw=base64.b64decode(row['rawBase64'],validate=True)
        legacy.require(0<len(raw)<=1048576 and row['rawSha256']=='sha256:'+legacy.sha(raw)
            and agent.parse(raw)==row['value'],'Actual protected raw/value current evidence changed')
        return row['value']
    for target,seal,record in zip(binding['targets'],seals,records):
        row=active[target['pod_uid']];name='cps-native-enrollment-'+row['binding_id'][:40]
        cm=copy.deepcopy(by_name.get(name));legacy.require(isinstance(cm,dict),'Actual immutable enrollment missing')
        cm.setdefault('apiVersion','v1');cm.setdefault('kind','ConfigMap')
        envelope=agent.validate_enrollment(cm,node,models)
        legacy.require(all(row.get(k)==v for k,v in envelope['enrollment'].items())
            and protected(snapshot['directories']['enrollments']['records'][target['pod_uid']+'.json'])==envelope
            and protected(snapshot['directories']['intents']['records'][target['pod_uid']+'.json'])==record.intent.to_dict()
            and protected(snapshot['directories']['journal']['records'][target['pod_uid']+'.json'])==record.to_dict()
            and snapshot['directories']['journal']['records'][target['pod_uid']+'.json']['rawSha256']=='sha256:'+seal['journal']['sha256']
            and protected(host['gateReceipts'][target['pod_uid']])==record.receipt(),
            'Full current immutable enrollment/ledger/protected seal/gate evidence must agree')
    old_authority['items']=[cm for cm in authority['items'] if cm['metadata']['name'] not in enrollment_names]
    legacy.require(len(authority['items'])-len(old_authority['items'])==2,'Exactly two actual new immutable enrollments required')
    projected={k:copy.deepcopy(snapshot[k]) for k in ('version','observerPodUid','node','nodeUid','bootId','driverGeneration','healthSourceSha256','observedAt','directories')}
    for directory in projected['directories'].values():
        for uid in active:legacy.require(uid+'.json' in directory['records'],'Actual current lifetime missing from full protected snapshot');directory['records'].pop(uid+'.json')
        for row in directory['records'].values():row.pop('rawBase64',None)
    legacy.require(terminal.map_history({'authority_maps':old_authority,'host_snapshot':projected},before,node)==history,
        'Complete unchanged terminal custody must survive real normal Start')
    retired=c.validate_retired(read(binding['retired_capture']),binding)
    historical=[models.CapRecord.from_dict(row['record']) for row in retired['records']]
    for row,r in zip(retired['records'],historical):
        original=projected['directories']['journal']['records'].get(r.intent.pod_uid+'.json')
        legacy.require(original is not None and original['value']==r.to_dict()
            and row['journal_sha256']==agent.canonical_sha256(original['value']),
            'Retirement inputs must equal full actual protected original journals')
    finite={uid for uid,row in projected['directories']['journal']['records'].items() if row['value']['state']=='retired-inert-cap'}
    legacy.require(finite=={r.intent.pod_uid+'.json' for r in historical},'Every actual finite retired lifetime must bind inventory, with no omitted history')
    bound={r.identity.cgroup_inode for r in records+historical};legacy.require(len(bound)==len(records)+len(historical),'Distinct complete physical lifetimes required')
    cleared=c.validate_cleared_inventory(inventory,pool,bound);rows={r['inode']:r for r in inventory['entries']}
    for r in records:
        row=rows[r.identity.cgroup_inode];legacy.require(row['offline'] is False and row['soft']==row['hard']==r.intent.cap_bytes and row['used']<=row['hard'],'Actual finite current sealed caps required')
    for r in historical:
        proof=models.validate_retired_inventory(inventory,r.identity,r.limit)
        legacy.require(proof.entry==r.retirement.entry and proof.gpu_id==r.retirement.gpu_id,'Original typed finite retirement must match actual inventory')
    devices={r.identity.cgroup_device for r in records+historical};legacy.require(len(devices)==1,'One actual cgroup2 device required')
    context={'preparation_mode':'current-normal-lifecycle-operator20','fresh_operator20_hardware_qualified':False,
        'current_controller_sha256':current.CONTROLLER_SHA256,'terminal_history_count':len(history),'baseline_allocation_count':len(old['allocations']),
        'original_protocols_unchanged':True,'actual_manifest':manifest,
        'source_dependency_pins':{'legacy_harness':HARNESS_SHA,'current_harness':CURRENT_SHA,
            'fixed20_protocol':PROFILE20_SHA,'terminal_mapper':TERMINAL_SHA}}
    return binding,context,{'rows':cleared,'cgroup_device':devices.pop(),'gpu_id':inventory['gpu_id']}


def prepare(manifest_path,manifest_sha,source_root,output,*,native_binary_path,native_binary_sha,native_build_path,native_build_sha):
    h,c,p=loaders();manifest=p.input_json({'path':str(manifest_path),'sha256':manifest_sha})
    binding,context,cleared=validate_inputs(manifest,h,c,p)
    def render(*a,**kw):
        out=c.render_sources(*a,**kw,cleared_baseline=cleared)
        mps=p.render_probes('cps5-cit20',out['run_group_acceptance.py'])
        for key in ('mps_probe.py','run_mps.py'):out['mps/'+key]=mps[key]
        return out
    return h._prepare_validated_binding(binding,manifest['binding']['sha256'],source_root,output,
        native_binary_path=native_binary_path,native_binary_sha=native_binary_sha,native_build_path=native_build_path,native_build_sha=native_build_sha,
        receipt_context=context,retirement_validator=c.validate_retired,source_renderer=render)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    for name in ('manifest','source-root','output','native-binary','native-build'):parser.add_argument('--'+name,type=Path)
    for name in ('manifest-sha256','native-binary-sha256','native-build-sha256'):parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'hardware_qualification':False}));return
    legacy.require(all((args.manifest,args.manifest_sha256,args.source_root,args.output,args.native_binary,args.native_binary_sha256,args.native_build,args.native_build_sha256)),'Complete actual pinned preparation inputs required')
    result=prepare(args.manifest,args.manifest_sha256,args.source_root,args.output,native_binary_path=args.native_binary,
        native_binary_sha=args.native_binary_sha256,native_build_path=args.native_build,native_build_sha=args.native_build_sha256)
    print(json.dumps({'state':result['state'],'hardware_qualification':False,'api_calls':False,'gpu_calls':False,'output':str(args.output)}))


if __name__=='__main__':main()
