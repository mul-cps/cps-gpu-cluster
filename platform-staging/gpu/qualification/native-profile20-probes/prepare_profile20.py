#!/usr/bin/env python3
"""Default-inert trusted profile probe renderer; no API or GPU operations."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).parent
MIB = 1048576
TEMPLATE_PINS = {
    'group_probe.py':'ed87e7fbf7930852e687632f63b37fcf343b99f38a25163cfdf6d1b04d9a66fe',
    'mps_probe.py':'336c036b1938ea272211a8f04b833e6d02d18351c6e5f7cbfae82a56da302893',
    'run_mps.py':'572b0929cb1ebeec04aa3173493963a31f8b1179ced80fc82773576706f89618'}
BASE = Path('/home/bjoern/.local/state/cps-platform-completion-20261011')
CODE = Path('/home/bjoern/git/cps-gpu-cluster-worktrees/no-mig-native-20261009/platform-staging/gpu/qualification/native-profile-packing')
ASSEMBLER_PATH = BASE/'native-next5-10-harness-source-prepared-20261012/prepare_next.py'
ASSEMBLER_SHA = '596b529664bca405025b09576f394296582e511d4d7caf5df65f1c3098ad92e6'
HARNESS_SHA = 'f656ece163800f2161bea3b067b3c71676e1bda67d21b4a43b9474946a1e84d7'
READER_SHA = 'e5be91b7b70cc3c69cba77190d212028508d4eaa19d444c96a475870b09f3bed'
INDEX_KEYS = {'version','enabled','preset','policy_hash','observed_at','node','observer','nvml',
    'host_snapshot','ledger','baseline_ledger','baseline_history','policy','runtime_config',
    'native_binary','native_build','sources'}

def need(ok,message):
    if not ok:raise ValueError(message)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def preset(value):
    need(type(value)is str and value in ('cps5-cit10','cps5-cit20'),'Explicit fixed CPS5/CIT10 or CPS5/CIT20 preset required')
    cap=10240 if value=='cps5-cit10'else 20480
    return dict(name=value,cps_cap_mib=5120,cit_cap_mib=cap,budget_mib=cap+5120,
        headroom_bytes=1024*MIB,minimum_held_mib=cap-1024,step_mib=256,oversized_mib=cap+256,
        per_client_previous_allocations=cap//512,maximum_client_allocations=cap//512+1)

def replace(code,old,new,count=1):
    need(code.count(old)==count,'Exact reviewed adaptation span changed: '+old[:90])
    return code.replace(old,new)

def literal(code,name):
    found=[n for n in ast.parse(code).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name)and t.id==name for t in n.targets)]
    need(len(found)==1,'Exact source assignment required: '+name)
    return ast.literal_eval(found[0].value)

def assignment(code,name,value):
    found=[n for n in ast.parse(code).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name)and t.id==name for t in n.targets)]
    need(len(found)==1,'Exact source assignment required: '+name)
    n=found[0];lines=code.splitlines(keepends=True)
    lines[n.lineno-1:n.end_lineno]=[name+' = '+repr(value)+'\n']
    return ''.join(lines)

def template(name):
    path=HERE/'templates'/name
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,2*1024*1024+1);after=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and not before.st_mode&0o022
            and len(raw)<=2*1024*1024 and all(getattr(before,k)==getattr(after,k)
            for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
            and sha(raw)==TEMPLATE_PINS[name],'Exact approved trusted source required')
        return raw
    finally:os.close(fd)

def render_probes(name,preflight):
    """Only fixed caps, allocator bounds and checksummed source bindings vary."""
    p=preset(name);group=template('group_probe.py');probe=template('mps_probe.py')
    wrapper=template('run_mps.py').decode()
    if p['cit_cap_mib']==20480:
        group=replace(group.decode(),'choices=(5120,10240)','choices=(5120,10240,20480)').encode()
        code=probe.decode()
        for old,new,count in [('1048576, 10240, 256, 10496','1048576, 20480, 256, 20736',1),
            ('9216 <= held','19456 <= held',1),('held >= 9216','held >= 19456',1),
            ('len(self.held) <= 20','len(self.held) <= 40',1),('10GiB','20GiB',2)]:
            code=replace(code,old,new,count)
        probe=code.encode()
        for old,new,count in [('==10496','==20736',1),
            ('9216 <= oom[\'held_mib\'] <= 10240','19456 <= oom[\'held_mib\'] <= 20480',1),
            ('<= 10496','<= 20736',1),("completed.get('cap_mib') == 10240","completed.get('cap_mib') == 20480",1),
            ("completed.get('max_attempted_mib') == 10496","completed.get('max_attempted_mib') == 20736",1),
            ('the10GiB CIT','the20GiB CIT',1)]:
            wrapper=replace(wrapper,old,new,count)
        wrapper=replace(wrapper,"    require(type(host.get('observed_at_ns')) is int, 'Actual trusted host charge timestamp required')",
            "    require(sum(t['inventory_row']['hard'] for t in host['targets']) <= 25600 * 1048576\n"
            "        and sum(t['inventory_row']['used'] for t in host['targets']) <= 25600 * 1048576,\n"
            "        'Aggregate native admission/charge exceeds fixed25GiB pool')\n"
            "    require(type(host.get('observed_at_ns')) is int, 'Actual trusted host charge timestamp required')")
    host=literal(preflight.decode(),'HOST_SOURCE');need(type(host)is str,'Literal complete host preflight required')
    host_sha=sha(host.encode());old_host=literal(wrapper,'PREFLIGHT_HOST_SHA');old_probe=literal(wrapper,'PROBE_SHA')
    wrapper=wrapper.replace(old_host,host_sha).replace(old_probe,sha(probe))
    wrapper=assignment(wrapper,'PREFLIGHT_SHA',sha(preflight))
    for raw in (group,probe,wrapper.encode()):compile(raw,'prepared-controlled-source','exec')
    return {'group_probe.py':group,'mps_probe.py':probe,'run_mps.py':wrapper.encode()}

def profile_renderer_source(raw,name):
    """Pinned sibling of the old preparer; historical guards stay byte exact."""
    p=preset(name);need(sha(raw)==HARNESS_SHA,'Exact frozen harness source required')
    code=raw.decode()
    if p['cit_cap_mib']==20480:
        for old,new,count in [
            ("'jupyter-citnativegroupa--rtc', 10240)","'jupyter-citnativegroupa--rtc', 20480)",1),
            ("p['budget_mib'] == 15360","p['budget_mib'] == 25600",1),
            ("p['headroom_bytes'] > 0","p['headroom_bytes'] == 1073741824",1),
            ('cover15GiB','cover25GiB',1),('CIT A10','CIT A20',1),
            ('cap_mib in (5120, 10240)','cap_mib in (5120, 10240, 20480)',1),
            ('else if(!strcmp(n,"10240"))cap_mib=10240;else return 2;',
             'else if(!strcmp(n,"10240"))cap_mib=10240;else if(!strcmp(n,"20480"))cap_mib=20480;else return 2;',1),
            ('native-imports-10','native-imports-20',3)]:code=replace(code,old,new,count)
    compile(code,'profile-specific-harness-source','exec')
    return code.encode()

def generalize_start_assembler(raw,name):
    """Retain every Start/enrollment/journal guard; derive counts from FULL baseline."""
    p=preset(name);need(sha(raw)==ASSEMBLER_SHA,'Exact frozen normal-Start assembler required')
    code=raw.decode()
    changes=[
        ("set(index)=={'version','enabled','observed_at','node','observer','nvml','host_snapshot','ledger','sources'}",
         "set(index)==INDEX_KEYS"),
        ("history=parse(read(HISTORY,HISTORY_SHA));prior=parse(read(PRIOR,PRIOR_SHA))",
         "history=input_value(index['baseline_history']);prior=input_value(index['baseline_ledger'])\n"
         "    HISTORY=Path(index['baseline_history']['path']);HISTORY_SHA=index['baseline_history']['sha256']\n"
         "    PRIOR=Path(index['baseline_ledger']['path']);PRIOR_SHA=index['baseline_ledger']['sha256']\n"
         "    global POLICY\n    POLICY=index['policy_hash']\n    validate_runtime_inputs(index,history,preset(index['preset']))\n"
         "    install_renderer(p,index['preset'])"),
        ("len(old['allocations'])==29 and len(new['allocations'])==31",
         "0<len(old['allocations'])<=128 and len(new['allocations'])==len(old['allocations'])+2"),
        ("len(history['records'])==23 and len(saved)==25",
         "0<len(history['records'])<=30 and len(saved)==len(history['records'])+2"),
        ('Every original29 released allocation','Every complete original released allocation'),
        ('Exact23 historical journals plus two','Every full historical journal plus two'),
        ("'budget_mib':15360","'budget_mib':preset(index['preset'])['budget_mib']"),
        ("'memory_budget_mib':15360","'memory_budget_mib':preset(index['preset'])['budget_mib']"),
        ("need((len(checked['finite']),len(checked['cleaned']))==(17,5),'Current17finite+5cleaned+1recovery history must remain exact')",
         "need(len(checked['finite'])+len(checked['cleaned'])+1==len(history['records']),"
         "'Every full classified finite/cleaned/recovered historical journal required')"),
        ("native_binary_path=BUILD/'native-imports-10',native_binary_sha='8776c4593144a3c8d87f2f08b8703826a1038fdebc35eb76f4779d0dfd6ff304',\n"
         "        native_build_path=BUILD/'build-receipt.json',native_build_sha='8958c8fd4f0b8cc4703fc4f9771c11168f71f7045b18dfd0ed73e30e19617bd7'",
         "native_binary_path=Path(index['native_binary']['path']),native_binary_sha=index['native_binary']['sha256'],\n"
         "        native_build_path=Path(index['native_build']['path']),native_build_sha=index['native_build']['sha256']"),
        ("'current_journals':25,'historical_journals':23,'historical_physical':18",
         "'current_journals':len(host['directories']['journal']['records']),'historical_journals':len(history['records']),"
         "'historical_physical':len(checked['finite'])+1"),
        ("'baseline29_ledger_raw_sha256'","'baseline_ledger_raw_sha256'"),
        ("'historical_journals':23,\n        'historical_physical':18",
         "'historical_journals':len(history['records']),\n        'historical_physical':len(checked['finite'])+1")]
    for old,new in changes:code=replace(code,old,new)
    if p['cit_cap_mib']==20480:
        code=replace(code,"'jupyter-citnativegroupa--rtc',10240)","'jupyter-citnativegroupa--rtc',20480)")
    compile(code,'complete-baseline-start-assembler','exec')
    return code

def import_source(name,raw,path):
    result=types.ModuleType(name);result.__file__=str(path);sys.modules[name]=result
    exec(compile(raw,str(path),'exec'),result.__dict__)
    return result

def install_renderer(recovery,name):
    """Only offline preparation functions vary; no controller/API is instantiated."""
    old=recovery.p;raw=old.read_pinned(CODE/'prepare_harness.py',HARNESS_SHA)
    profile=import_source('reviewed_profile_harness',profile_renderer_source(raw,name),CODE/'prepare_harness.py')
    recovery.p=profile
    reader_raw=old.read_pinned(CODE/'recovery_history.py',READER_SHA)
    if name=='cps5-cit20':
        reader_raw=replace(reader_raw.decode(),'record.intent.cap_mib in (5120, 10240)',
            'record.intent.cap_mib in (5120, 10240, 20480)').encode()
    recovery.r=import_source('reviewed_profile_history',reader_raw,CODE/'recovery_history.py')
    recovery.loader.r=recovery.r
    original_render=profile.render_sources
    def render(sources,binding,retired,**kw):
        out=original_render(sources,binding,retired,**kw)
        if name=='cps5-cit20':
            old_pre=out['run_group_acceptance.py'];pre=old_pre.decode()
            pre=replace(pre,'BUDGET_BYTES = 16106127360','BUDGET_BYTES = 26843545600')
            for old,new in [('(10240 if aggregate else 5120)','(20480 if aggregate else 5120)'),
                ("failure.get('cap_mib')==10240","failure.get('cap_mib')==20480"),
                ("failure.get('maximum_attempted_tensor_mib')==10496","failure.get('maximum_attempted_tensor_mib')==20736"),
                ('(6656 if aggregate else 9216)','(16896 if aggregate else 19456)'),
                ('(7936 if aggregate else 10240)','(18176 if aggregate else 20480)'),
                ('(8704 if aggregate else 9216)','(18944 if aggregate else 19456)'),
                ('Exact10GiB','Exact20GiB')]:pre=replace(pre,old,new)
            out['run_group_acceptance.py']=pre.encode()
            old_helper=out['imports/same_pod_imports.py'];helper=old_helper.decode()
            helper=replace(helper,'CAP = 10737418240','CAP = 21474836480')
            helper=replace(helper,"'--cap-mib', '10240'","'--cap-mib', '20480'")
            out['imports/same_pod_imports.py']=helper.encode()
            old_group=out['group_probe.py'];out['group_probe.py']=replace(old_group.decode(),
                'choices=(5120,10240)','choices=(5120,10240,20480)').encode()
            for key,value in list(out.items()):
                if key.endswith('.py')and key not in ('run_group_acceptance.py','imports/same_pod_imports.py','group_probe.py'):
                    out[key]=value.replace(sha(old_pre).encode(),sha(out['run_group_acceptance.py']).encode())\
                        .replace(sha(old_helper).encode(),sha(out['imports/same_pod_imports.py']).encode())\
                        .replace(sha(old_group).encode(),sha(out['group_probe.py']).encode())
            out['prepare_harness.py']=profile_renderer_source(raw,name)
        return out
    recovery.BASE_RENDER=render
    original_bundle=recovery.bundle
    def bundle(*args,**kw):
        result=original_bundle(*args,**kw)
        result['reader']={'raw':reader_raw,'sha256':sha(reader_raw)}
        recovery.loader.load_sources(result)
        return result
    recovery.bundle=bundle

def validate_runtime_inputs(index,history,p):
    need(index['preset']==p['name'],'Exact selected preset required')
    config=input_json(index['runtime_config'])
    from cps_compute.policy import Policy
    policy=Policy(input_json(index['policy']))
    need(policy.hash==index['policy_hash'],'Actual policy/catalog hash mismatch')
    need(config['version']==2 and config['enabled']is True and config['mode']=='operator-qualification'
        and config['policy_hash']==policy.hash and config['terminal_history']==history,
        'Exact operator-only full config/policy/history required')
    pool=config['pool']
    need(pool['memory_budget_mib']==p['budget_mib']and pool['max_workspaces']==2
        and pool['headroom_mib']*MIB==p['headroom_bytes'],'Fixed measured budget/headroom/two-lifetime pool required')
    need(config['workspaces']=={'cps:native-group-b':{'profile':'interactive-native-qualification-5','cap_mib':5120},
        'cit:native-group-a':{'profile':'interactive-native-qualification-'+str(p['cit_cap_mib']//1024),'cap_mib':p['cit_cap_mib']}},
        'Only fixed CPS B5 and CIT A10/A20 workspaces allowed')
    epochs=('node','node_uid','gpu_uuid','boot_id','driver_generation')
    need(all(pool[k]==history[k]for k in epochs),'Full runtime/baseline history epoch mismatch')
    need(pool['memory_budget_mib']<=pool['free_memory_mib']-pool['headroom_mib'],
        'Measured free memory minus additional headroom must cover whole pool')

def build_recipe(source_dir,output,name):
    """Exact offline CPU compiler recipe, never an execution or build receipt."""
    p=preset(name);source_dir=Path(source_dir);output=Path(output)
    need(source_dir.is_absolute()and output.is_absolute(),'Absolute reviewed offline build paths required')
    profile=import_source('cpu_build_profile',profile_renderer_source((CODE/'prepare_harness.py').read_bytes(),name),CODE/'prepare_harness.py')
    filename='native-imports-'+str(p['cit_cap_mib']//1024)
    compile_argv=['podman','run','--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--security-opt=label=disable','--userns=keep-id',
        '--tmpfs','/tmp:rw,nodev,nosuid,size=64m','-v',str(source_dir)+':/source:ro',
        '-v',str(profile.CUDA_HEADER.parent)+':/headers:ro','-v',str(output)+':/out:rw',
        '--entrypoint','gcc',profile.CPU_IMAGE,'-std=c11','-Wall','-Wextra','-Werror','-O2',
        '-I/headers','/source/native_imports.c','-ldl','-o','/out/'+filename]
    inert_argv=['podman','run','--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--security-opt=label=disable','--userns=keep-id',
        '-v',str(output)+':/out:ro','--entrypoint','/out/'+filename,profile.CPU_IMAGE]
    return dict(version=1,state='Root-reviewed-execution-pending-not-a-build-receipt',api_calls=False,gpu_calls=False,
        hardware_qualification=False,production_qualified=False,preset=p,
        compile_argv=compile_argv,cpu_inert_argv=inert_argv,
        abi_argv=['readelf','--version-info',str(output/filename)],
        source_sha256=sha(profile.native_build_sources()['native_imports.c']),
        compiler_sha256=profile.NATIVE_COMPILER_SHA,header_sha256=profile.CUDA_HEADER_SHA,
        cpu_image=profile.CPU_IMAGE,maximum_glibc_version='2.39',
        expected_inert_output=dict(state='inert',gpu_calls=False,payload_mib=64,production_qualified=False),
        prior_actual_build=str(BASE/'packing-session-20261011T154440Z/native-import-cpu-build/build-receipt.json'))

def input_read(pin):
    need(type(pin)is dict and set(pin)=={'path','sha256'},'Closed complete actual input pin required')
    path=Path(pin['path']);need(path.is_absolute(),'Absolute protected input required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);raw=os.read(fd,8*1024*1024+1);b=os.fstat(fd);parent=path.parent.lstat()
        need(stat.S_ISREG(a.st_mode)and a.st_uid==os.getuid()and a.st_nlink==1
            and stat.S_IMODE(a.st_mode)in(0o400,0o600)and stat.S_ISDIR(parent.st_mode)
            and parent.st_uid==os.getuid()and stat.S_IMODE(parent.st_mode)==0o700
            and len(raw)<=8*1024*1024 and sha(raw)==pin['sha256']
            and all(getattr(a,k)==getattr(b,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
            'Exact stable full owned private input required')
        return raw
    finally:os.close(fd)

def input_json(pin):
    def pairs(rows):
        out={}
        for key,value in rows:need(key not in out,'Duplicate input key');out[key]=value
        return out
    return json.loads(input_read(pin),object_pairs_hook=pairs,
        parse_constant=lambda _:need(False,'Nonfinite input forbidden'))

def prepare(index,output):
    need(type(index)is dict and set(index)==INDEX_KEYS and index['enabled']is True,'Closed Root-enabled actual index required')
    p=preset(index['preset'])
    raw=input_read({'path':str(ASSEMBLER_PATH),'sha256':ASSEMBLER_SHA})
    assembler=import_source('full_baseline_profile_assembler',generalize_start_assembler(raw,p['name']),ASSEMBLER_PATH)
    assembler.INDEX_KEYS=INDEX_KEYS;assembler.preset=preset;assembler.validate_runtime_inputs=validate_runtime_inputs
    assembler.install_renderer=install_renderer
    result=assembler.prepare(index,Path(output))
    path=Path(output);preflight=(path/'run_group_acceptance.py').read_bytes()
    # The runtime history reader must be the same reviewed sibling embedded in
    # the host closure, including the finite20 allowlist for subsequent Stop.
    if p['cit_cap_mib']==20480:
        reader=replace((path/'recovery_history.py').read_text(),
            'record.intent.cap_mib in (5120, 10240)','record.intent.cap_mib in (5120, 10240, 20480)')
        (path/'recovery_history.py').write_text(reader)
    rendered=render_probes(p['name'],preflight)
    destination=path/'mps-sustained120';destination.mkdir(mode=0o700)
    for key in('mps_probe.py','run_mps.py'):write(destination/key,rendered[key])
    write(destination/'preparation-receipt.json',json.dumps(dict(version=1,state='Root-review-and-execution-pending',
        api_calls=False,gpu_calls=False,hardware_qualification=False,production_qualified=False,preset=p,
        output_pins={k:sha(rendered[k])for k in('mps_probe.py','run_mps.py')},preflight_sha256=sha(preflight)),sort_keys=True).encode()+b'\n')
    # Replace the earlier short MPS recipe with this reviewed sustained recipe.
    # Every replacement occurs within this fresh, private, offline output only.
    for key in('mps_probe.py','run_mps.py'):(path/'mps'/key).write_bytes(rendered[key])
    receipt=json.loads((path/'preparation-receipt.json').read_text())
    receipt['rendered_sources'].update({'recovery_history.py':sha((path/'recovery_history.py').read_bytes()),
        'mps/mps_probe.py':sha(rendered['mps_probe.py']),'mps/run_mps.py':sha(rendered['run_mps.py']),
        'mps-sustained120/mps_probe.py':sha(rendered['mps_probe.py']),'mps-sustained120/run_mps.py':sha(rendered['run_mps.py'])})
    receipt['preset']=p;receipt['profile_preparer_source_sha256']=sha(Path(__file__).read_bytes())
    receipt['validator_source_pins']['reader']=sha((path/'recovery_history.py').read_bytes())
    (path/'preparation-receipt.json').write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n')
    chain_path=path.with_name(path.name+'-inputs')/'input-chain.json'
    chain=json.loads(chain_path.read_text());chain['prepared_sources']=receipt['rendered_sources']
    chain['preset']=p;chain_path.write_text(json.dumps(chain,sort_keys=True,separators=(',',':'))+'\n')
    recipe_path=path/'operator-argv.json';recipe=json.loads(recipe_path.read_text())
    old=recipe['commands'].pop('mps-cit10');key='mps-cit'+str(p['cit_cap_mib']//1024)+'-sustained120'
    old[1]=str(destination/'run_mps.py')
    old[old.index('--wrapper-source-sha256')+1]=sha(rendered['run_mps.py'])
    old[old.index('--output')+1]=str(path/'measurements'/key);recipe['commands'][key]=old
    recipe_path.write_text(json.dumps(recipe,sort_keys=True,separators=(',',':'))+'\n')
    result.update(preset=p,hardware_qualification=False,production_qualified=False)
    return result

def write(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preset',choices=('cps5-cit10','cps5-cit20'),default='cps5-cit10')
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--emit-native-import-source',action='store_true')
    parser.add_argument('--source-sha256');parser.add_argument('--index',type=Path)
    parser.add_argument('--index-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    need(not(args.prepare and args.emit_native_import_source),'One explicit offline operation required')
    if args.emit_native_import_source:
        need(args.source_sha256==sha(Path(__file__).read_bytes())and args.output is not None,
            'Reviewed source and fresh private output required')
        path=args.output;parent=path.parent.lstat()
        need(path.is_absolute()and stat.S_ISDIR(parent.st_mode)and parent.st_uid==os.getuid()
            and stat.S_IMODE(parent.st_mode)==0o700,'Owned private fresh output parent required')
        code=(CODE/'prepare_harness.py').read_bytes();profile=import_source('controlled_native_source',
            profile_renderer_source(code,args.preset),CODE/'prepare_harness.py')
        sources=profile.native_build_sources();path.mkdir(mode=0o700)
        for name,raw in sources.items():write(path/name,raw)
        print(json.dumps(dict(state='native-import-source-prepared-not-built',api_calls=False,gpu_calls=False,
            hardware_qualification=False,production_qualified=False,preset=preset(args.preset),
            files={name:sha(raw)for name,raw in sources.items()}),sort_keys=True));return
    if args.prepare:
        need(args.source_sha256==sha(Path(__file__).read_bytes())and args.index is not None
            and args.index_sha256 and args.output is not None,'Reviewed source/index/output required')
        index=input_json({'path':str(args.index),'sha256':args.index_sha256})
        need(index['preset']==args.preset,'CLI/index preset mismatch')
        print(json.dumps(prepare(index,args.output),sort_keys=True));return
    print(json.dumps(dict(state='inert',preset=args.preset,api_calls=False,gpu_calls=False,
        hardware_qualification=False,production_qualified=False),sort_keys=True))

if __name__=='__main__':main()
