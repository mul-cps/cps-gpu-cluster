#!/usr/bin/env python3
"""Default-inert local source preparation and strict finite 5/20 growth proof.

The collector's execution is a separately reviewed Root operation. This module
only renders its pinned source closure or validates already captured evidence.
It supplies no Source CRUD, grant, driver, GPU or network operation.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType, SimpleNamespace

import prepare_profile20 as p20

BASE=p20.BASE
P20_SHA='5d78371154dd0fa4a3564a5ff39b04f2fc7373fc39b4f60403a7ac0033cfd6e8'
COLLECTOR=BASE/'normal-lifecycle-renewal-prepared-20261012/stop-collector-podlist-projection-v2'
COLLECTOR_SHA='1eafe22e99fc6bebd2c7c6b92e272305b1dd49cb46a1ec69de3a4b2e35306934'
CODE_PINS_SHA='c46f2f6d1153d24a7eaf411383fa9864eda15021a25e4a0212fd3c73643b2b8f'
GROWTH=Path('/home/bjoern/git/cps-gpu-cluster-worktrees/recovery-qualified-inverse-growth-20261012/platform-staging/gpu/qualification/native-profile-packing/qualified_recovery_inverse_growth.py')
GROWTH_SHA='947a0aaced56bfa2fc530920ebe3d39cd06eb6f5b2da36a9f931a261697a0176'
POST=BASE/'typed-stop-post-cycle-inverse-source-prepared-20261012/post_cycle_inverse.py'
POST_SHA='c226aa692a3b8151f773dd2dd0174769f9603c4a22792649bd6af7989f72fc6a'
BOOTSTRAP=BASE/'typed-stop-post-cycle-inverse-dynamic-source-prepared-20261012/prepare_inverse29.py'
BOOTSTRAP_SHA='94c9368fe3e104931c3d62498a5dcc252c4b77b743eff2412cbe7e2c4f781e1e'
BASE_ASSEMBLER=BASE/'sustained-mps-controlled-cycle-20261012/future-growth31-local-prepared/assemble_growth31.py'
BASE_ASSEMBLER_SHA='662a05c17b7f88082425ae71b86d9267a683dc8b9374c16f59417d52598eaea6'
IDENTITY={'source','actor','workspace','principal','members','ceiling','group_id','profile',
    'policy_hash','namespace','name','node','node_uid','gpu_uuid','cap_mib'}
MUTABLE_IDENTITY={'profile','policy_hash','ceiling','cap_mib'}
PAIR_KEYS={'before','binding','cleanups','enrollments','journals','ledger','normal_stop','physical','pods'}
INDEX_KEYS={'version','enabled','baseline_index','baseline_physical','binding','harness_receipt',
    'collection','collector_request','normal_stop','provenance','approved_identities'}

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def encode(value):return(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def read(ref):
    require(type(ref)is dict and set(ref)=={'path','sha256'} and type(ref['path'])is str
        and Path(ref['path']).is_absolute() and type(ref['sha256'])is str
        and re.fullmatch('[a-f0-9]{64}',ref['sha256']),'Closed actual absolute raw pin required')
    path=Path(ref['path']);directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        parent=os.fstat(directory)
        require(parent.st_uid==os.getuid()and stat.S_IMODE(parent.st_mode)==0o700,'Private owned input parent required')
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        try:
            before=os.fstat(fd)
            require(stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_nlink==1
                and stat.S_IMODE(before.st_mode)in(0o400,0o600)and 0<before.st_size<=16*1024*1024,
                'Protected bounded regular input required')
            parts=[];remaining=before.st_size
            while remaining:
                part=os.read(fd,min(remaining,1048576));require(bool(part),'Truncated protected input')
                parts.append(part);remaining-=len(part)
            raw=b''.join(parts);after=os.fstat(fd)
            require(sha(raw)==ref['sha256']and all(getattr(before,k)==getattr(after,k)for k in
                ('st_dev','st_ino','st_size','st_mode','st_uid','st_gid','st_nlink','st_mtime_ns','st_ctime_ns')),
                'Raw input changed')
            return raw
        finally:os.close(fd)
    finally:os.close(directory)

def code(path,pin):
    """Pinned immutable source read; worktree source parents need not be private."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,2*1024*1024+1);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and not before.st_mode&0o022
            and len(raw)<=2*1024*1024 and sha(raw)==pin and all(getattr(before,k)==getattr(after,k)
                for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'Exact frozen source pin required')
        return raw
    finally:os.close(fd)

def definition(raw,name):
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name==name)
    return ''.join(raw.decode().splitlines(keepends=True)[node.lineno-1:node.end_lineno])

def collector_sources():
    code(Path(p20.__file__),P20_SHA)
    pins=parse(read({'path':str(COLLECTOR/'code-pins.json'),'sha256':CODE_PINS_SHA}))
    require(set(pins)=={'version','files'}and pins['version']==1 and len(pins['files'])==14,
        'Exact frozen14 collector dependency closure required')
    files={name:code(COLLECTOR/name,ref['sha256'])for name,ref in pins['files'].items()}
    files['prepare_harness.py']=p20.profile_renderer_source(files['prepare_harness.py'],'cps5-cit20')
    files['recovery_history.py']=p20.replace(files['recovery_history.py'].decode(),
        'record.intent.cap_mib in (5120, 10240)','record.intent.cap_mib in (5120, 10240, 20480)').encode()
    for name in pins['files']:pins['files'][name]['sha256']=sha(files[name])
    files['code-pins.json']=encode(pins)
    source=code(COLLECTOR/'collect_stop.py',COLLECTOR_SHA).decode()
    source=p20.replace(source,'[5120, 10240]','[5120, 20480]')
    source=p20.replace(source,'CPS5/CIT10','CPS5/CIT20')
    source=p20.replace(source,CODE_PINS_SHA,sha(files['code-pins.json']))
    compile(source,'strict20-stop-collector','exec');files['collect_stop.py']=source.encode()
    return files

def growth_source():
    """Frozen finite proof, replacing only baseline bounds and approved identity."""
    source=definition(code(GROWTH,GROWTH_SHA),'validate_growth')
    for old,new in [('bridge.current_ledger(baseline_ledger, baseline)','_exact_baseline(baseline_ledger, baseline)'),
        ('1 <= len(pairs) <= 2','len(pairs) == 1'),('len(old_rows) == 17',"len(old_rows) == len(baseline_history['records'])"),
        ("pair['binding']['policy_hash'] == bridge.a.POLICY","pair['binding']['policy_hash'] == _approved_policy")]:
        source=p20.replace(source,old,new)
    old="""            w.require(binding_id not in expected_allocations
                and any(all(enrollment.get(k) == previous.get(k) for k in IDENTITY)
                    for previous in old_allocations.values()),
                'New lifetime must preserve exact original approved Source identity and allowance')
            expected_allocations[binding_id] = {**enrollment, 'state':'released'}"""
    new="""            allocation = state(pair['ledger'])['allocations'].get(binding_id)
            w.require(type(allocation) is dict and allocation.get('state') == 'released'
                and _sdk_enrollment(allocation) == enrollment
                and binding_id not in expected_allocations and _approved_allocation(allocation),
                'Exact SDK enrollment and separately approved full Source identity/allowance required')
            expected_allocations[binding_id] = copy.deepcopy(allocation)"""
    source=p20.replace(source,old,new);compile(source,'strict-full-baseline20-finite-growth','exec')
    return source

def frozen_dependencies():
    code(Path(p20.__file__),P20_SHA)
    old=p20.import_source('profile20_frozen_baseline_bootstrap',read({'path':str(BOOTSTRAP),'sha256':BOOTSTRAP_SHA}),BOOTSTRAP)
    post,files,base,loaded=old.dependencies()
    require(sha(code(POST,POST_SHA))==POST_SHA and sha(Path(post.g.__file__).read_bytes())==GROWTH_SHA,
        'Full frozen postcycle and finite-growth closure required')
    return post,files,base,loaded

def authenticated_baseline(index_ref,physical_ref):
    """Replay the old completed 5/10 chain unchanged before deriving new bounds."""
    assembler=p20.import_source('profile20_original31_assembler',read({'path':str(BASE_ASSEMBLER),
        'sha256':BASE_ASSEMBLER_SHA}),BASE_ASSEMBLER)
    index=parse(read(index_ref));doc,history_raw,receipt=assembler.assemble(index)
    old,core=assembler.dependencies();post,_,previous,loaded=old.dependencies()
    baseline_raw=read(index['baseline_growth']);baseline_history_raw=read(index['baseline_history'])
    base=old.future_document(post,previous,parse(baseline_raw),baseline_history_raw,loaded)
    result=core.finite_extension(base,doc['baseline_history'],doc['current_ledger'],doc['current_history'],
        doc['pairs'],doc['physical'],loaded,doc['normal_stop_provenance'])
    refreshed=parse(read(physical_ref))
    require({k:v for k,v in refreshed.items()if k!='observed_at_ns'}==
        {k:v for k,v in doc['physical'].items()if k!='observed_at_ns'},
        'Fresh baseline physical map must preserve every original non-time field')
    result.update(recorded_physical=refreshed,current_history_raw_sha256=sha(history_raw))
    return post,result,history_raw

def twenty_models(post):
    """Authenticated model/agent/recovery unchanged; reader finite allowlist only."""
    code(Path(p20.__file__),P20_SHA);recovery=post.b.a.prepare
    profile=p20.import_source('stop20_profile',p20.profile_renderer_source(code(COLLECTOR/'prepare_harness.py',p20.HARNESS_SHA),
        'cps5-cit20'),COLLECTOR/'prepare_harness.py')
    reader_raw=p20.replace(code(COLLECTOR/'recovery_history.py',p20.READER_SHA).decode(),
        'record.intent.cap_mib in (5120, 10240)','record.intent.cap_mib in (5120, 10240, 20480)').encode()
    reader=p20.import_source('stop20_reader',reader_raw,COLLECTOR/'recovery_history.py')
    bundle=recovery.bundle(COLLECTOR/'model.py',COLLECTOR/'control.py',COLLECTOR/'historical_agent.py',
        '05a6ca95eaaaf79cdbbdffec8172c804676d982a4154a422188639cd6b24f09b',COLLECTOR/'recovery_helper.py',
        '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b')
    bundle['reader']={'raw':reader_raw,'sha256':sha(reader_raw)}
    loader=p20.import_source('stop20_loader',code(COLLECTOR/'recovery_source_loader.py',
        'b3fd57f64f1dc7e4fe3b09c563b9a347f2767cfecb5de8e444d27668d735d3b9'),COLLECTOR/'recovery_source_loader.py')
    loader.r=reader;loaded=loader.load_sources(bundle)
    inspector=ModuleType('stop20_frozen_inspector');inspector.__file__=str(COLLECTOR/'inspect_stop.py')
    raw=code(COLLECTOR/'inspect_stop.py','5f97c8f410c8a2068ddfe3c292d71cb2b42b212010f464691b075f85e2e18934')
    # Only import binding is supplied externally; every inspector predicate is exact.
    source=raw.decode().replace('import prepare_harness as p\n','')
    inspector.p=profile;exec(compile(source,'unchanged-finite-Stop-inspector','exec'),inspector.__dict__)
    return reader,loader,loaded,inspector

def validate_identity_approval(base,binding,approval,history_pin,g):
    require(type(approval)is dict and set(approval)=={'version','enabled','preset','policy_hash',
        'baseline_ledger_state_sha256','baseline_history_raw_sha256','binding_sha256','sources'}
        and type(approval['version'])is int and approval['version']==1 and approval['enabled']is True
        and approval['preset']=='cps5-cit20' and approval['policy_hash']==binding['policy_hash']
        and approval['baseline_ledger_state_sha256']==sha(canonical(g.state(base['ledger'])).encode())
        and approval['baseline_history_raw_sha256']==history_pin
        and approval['binding_sha256']==sha(canonical(binding).encode())
        and type(approval['sources'])is dict and set(approval['sources'])=={'cps','cit'},
        'Closed actual separately reviewed full Source identity handover approval required')
    old=g.state(base['ledger'])['allocations'];identities={}
    for source,target,cap in zip(('cps','cit'),binding['targets'],(5120,20480)):
        item=approval['sources'][source]
        require(type(item)is dict and set(item)=={'identity','handover_provenance'},'Closed owning identity/provenance required')
        identity=item['identity'];provenance=item['handover_provenance']
        require(type(identity)is dict and set(identity)==IDENTITY and identity['source']==identity['actor']==source
            and identity['cap_mib']==cap and type(identity['cap_mib'])is int
            and identity['profile']=='interactive-native-qualification-'+str(cap//1024)
            and identity['policy_hash']==approval['policy_hash']
            and identity['ceiling']=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':cap//1024}
            and all(identity[k]==target[k]for k in('source','workspace','profile','namespace','name','cap_mib'))
            and all(identity[k]==binding['pool'][k]for k in('node','node_uid','gpu_uuid'))
            and any(all(identity[k]==row[k]for k in IDENTITY-MUTABLE_IDENTITY)for row in old.values()),
            'Only approved fixed cap/profile/policy/ceiling delta may change original full Source identity')
        require(type(provenance)is dict and set(provenance)=={'before_full_sha256','after_full_sha256',
            'receipt_sha256','review_sha256','adapter_sha256'}and all(type(v)is str and re.fullmatch('[a-f0-9]{64}',v)
            for v in provenance.values()),'Actual independently authenticated Source handover provenance pins required')
        identities[source]=copy.deepcopy(identity)
    return identities

def validate_future(base,baseline_history,current_ledger,current_history,pairs,physical,loaded,
                    provenance,approval,*,post,reader,loader,inspector,history_pin):
    """One strict pair only; counts derive from full authenticated current state."""
    g=post.g;w=post.w
    old=g.state(base['ledger']);rows=g.history_rows(baseline_history)
    old_physical=base['recorded_physical']
    require(baseline_history==base['current_history'] and 0<len(old['allocations'])<=128
        and 0<len(rows)<=30 and type(pairs)is list and len(pairs)==1 and set(pairs[0])==PAIR_KEYS
        and (base['allocation_count'],base['journal_count'],base['physical_count'])==
            (len(old['allocations']),len(rows),len(old_physical['retired_caps'])),
        'Every complete authenticated baseline body and one closed pair required')
    require(pairs[0]['before']['host']['retired_caps']==old_physical['retired_caps'],
        'Exact independently observed full prior physical map required')
    reader.validate_observed(baseline_history,old_physical['retired_caps'])
    identities=validate_identity_approval(base,pairs[0]['binding'],approval,history_pin,g)
    nested,links=post.matched_stops(pairs[0]['normal_stop'],pairs[0]['binding'],provenance)
    projected=copy.deepcopy(pairs);projected[0]['normal_stop']=nested
    def exact_baseline(cm,state):
        require(cm==base['ledger'] and state==old,'Every original allocation and exact UID/RV/full ledger preimage unchanged')
    def approved_allocation(allocation):
        source=allocation.get('source')
        return source in identities and all(allocation.get(k)==v for k,v in identities[source].items())
    def history_validate(history,binding,*,agent,recovery_codec):
        require(agent is loaded.agent and recovery_codec is loaded.codec,'Exact frozen model/agent/recovery closure required')
        return loader.validate(loaded,history,binding,allow_current=True)
    from cps_compute.native_gpu_control import NativeGpuAuthority
    ns={**g.__dict__,'r':reader,'stop':inspector,'_exact_baseline':exact_baseline,
        '_approved_policy':approval['policy_hash'],'_approved_allocation':approved_allocation,
        '_sdk_enrollment':NativeGpuAuthority._enrollment_record}
    exec(compile(growth_source(),'pinned20-full-baseline-finite-growth','exec'),ns)
    closure=SimpleNamespace(agent=loaded.agent,codec=loaded.codec,reader=SimpleNamespace(validate_history=history_validate))
    result=ns['validate_growth'](base['ledger'],baseline_history,current_ledger,current_history,projected,physical,closure)
    require((result['allocation_count'],result['journal_count'],result['physical_count'])==
        (len(old['allocations'])+2,len(rows)+2,len(old_physical['retired_caps'])+2),
        'Exactly two released finite lifetimes and full zero-charge closure required')
    result['authorities']=copy.deepcopy(base['authorities'])+result['authorities']
    result['normal_stop_captures']=copy.deepcopy(base['normal_stop_captures'])+links
    result['approved_identities']=copy.deepcopy(approval)
    return result

def assemble(index):
    """Only actual protected collector outputs can feed the finite inverse proof."""
    require(type(index)is dict and set(index)==INDEX_KEYS and type(index['version'])is int
        and index['version']==1 and index['enabled']is True,'Closed explicitly enabled actual input index required')
    post,base,baseline_history_raw=authenticated_baseline(index['baseline_index'],index['baseline_physical'])
    reader,loader,loaded,inspector=twenty_models(post)
    binding=parse(read(index['binding']));harness=parse(read(index['harness_receipt']))
    prior_count=len(base['current_history']['records']);prior_physical=len(base['recorded_physical']['retired_caps'])
    prior_allocations=len(post.g.state(base['ledger'])['allocations'])
    require(harness['binding_raw_sha256']==index['binding']['sha256']
        and binding['retired_capture']['sha256']==sha(baseline_history_raw)
        and harness['historical_journal_count']==prior_count and harness['historical_physical_count']==prior_physical,
        'Actual same-pair prepared H and complete accepted baseline required')
    collection=parse(read(index['collection']));request=parse(read(index['collector_request']))
    require(collection.get('version')==1 and type(collection['version'])is int
        and collection.get('state')=='strict-finite-pair-stop-evidence-collected-awaiting-Root-review'
        and collection.get('source_sha256')==sha(collector_sources()['collect_stop.py'])
        and collection.get('request_sha256')==index['collector_request']['sha256']
        and collection.get('phase')==request.get('phase')=='restart'
        and collection.get('journal_count')==prior_count+2 and collection.get('ledger_allocation_count')==prior_allocations+2
        and collection.get('historical_exception_count')==1 and collection.get('normal_stop_passed')is False
        and collection.get('hardware_qualification')is False and collection.get('production_qualified')is False,
        'Actual completed strict20 collector receipt and finite whole-baseline bounds required')
    require(set(request)=={'version','enabled','phase','binding','kernel_before','kernel_receipt','harness_receipt',
        'ready_pods','normal_stop','prior_ledger','prior_history','observer_pod','node','recovery_inputs','output'}
        and request['enabled']is True and request['binding']==index['binding']
        and request['harness_receipt']==index['harness_receipt']
        and read(request['prior_history'])==baseline_history_raw and parse(read(request['prior_ledger']))==base['ledger'],
        'Same actual collector request and complete protected baseline preimage required')
    manifest=parse(read(collection['inspect_manifest']))
    require(type(manifest)is dict and set(manifest)==PAIR_KEYS-{'normal_stop'}
        and manifest['binding']==index['binding']and manifest['before']==request['kernel_before'],
        'Same closed actual unchanged inspector manifest required')
    pair={k:parse(read(manifest[k]))for k in('before','binding','ledger','physical','pods')}
    for name in('enrollments','cleanups','journals'):
        require(type(manifest[name])is list and len(manifest[name])==2,'Both actual target authority/journal raw inputs required')
        raws=[read(ref)for ref in manifest[name]]
        pair[name]=[{'raw':raw.decode(),'sha256':sha(raw)}for raw in raws]if name=='journals'else[parse(raw)for raw in raws]
    require(type(index['normal_stop'])is dict and set(index['normal_stop'])=={'cps','cit'},'Both owning actual Source Stop captures required')
    pair['normal_stop']=[{'raw':read(index['normal_stop'][src]).decode(),'sha256':index['normal_stop'][src]['sha256']}
        for src in('cps','cit')]
    provenance=parse(read(index['provenance']));nested,links=post.matched_stops(pair['normal_stop'],binding,provenance)
    for src,capture in zip(('cps','cit'),nested):
        require(read(request['normal_stop'][src])==capture['raw'].encode()
            and request['normal_stop'][src]['sha256']==capture['sha256'],
            'Collector nested7 must equal authenticated actual outer22 projection')
    projections=collection['pod_list_projections']
    require(type(projections)is dict and set(projections)=={'pods','pods-after'},'Both actual full PodList observations required')
    collector=ModuleType('stop20_projection_only')
    collector.__file__=str(COLLECTOR/'collect_stop.py')
    exec(compile(code(COLLECTOR/'collect_stop.py',COLLECTOR_SHA),'frozen-podlist-projection-guards','exec'),collector.__dict__)
    for label,ref in projections.items():
        proof=parse(read(ref));original=parse(read(proof['original']));projection=parse(read(proof['projection']))
        require(set(proof)=={'version','original','projection','omitted_field','item_count',
            'all_other_values_and_item_order_preserved','normal_stop_passed','hardware_qualification','production_qualified'}
            and type(proof['version'])is int and proof['version']==1
            and proof['omitted_field']=='items[*].metadata.managedFields'
            and proof['all_other_values_and_item_order_preserved']is True
            and proof['item_count']==len(projection['items'])and proof['normal_stop_passed']is False
            and proof['hardware_qualification']is False and proof['production_qualified']is False,
            'Exact actual full PodList projection receipt required')
        collector.validate_podlist_projection(original,projection);collector.absent_targets(projection,binding['targets'])
        if label=='pods':require(proof['projection']==manifest['pods'],'Inspector must consume exact validated projection')
    current_history_raw=read(collection['history']);current_history=parse(current_history_raw)
    approval=parse(read(index['approved_identities']))
    result=validate_future(base,base['current_history'],pair['ledger'],current_history,[pair],pair['physical'],loaded,
        provenance,approval,post=post,reader=reader,loader=loader,inspector=inspector,history_pin=sha(baseline_history_raw))
    inspected=parse(read(collection['inspector_stdout']))
    require(inspected.get('state')=='stop-witnesses-consistent-awaiting-Root-review'
        and inspected.get('terminal_lifetimes')==collection['new_terminal_lifetimes'],
        'Actual unchanged finite inspector result and collector agree')
    doc={'version':1,'baseline_ledger':base['ledger'],'baseline_history':base['current_history'],
        'current_ledger':pair['ledger'],'current_history':current_history,'pairs':[pair],
        'physical':pair['physical'],'normal_stop_provenance':provenance,'approved_identities':approval}
    receipt={'version':1,'state':'actual-full-baseline20-finite-growth-assembled-awaiting-Root-review',
        'counts':[result[k]for k in('allocation_count','journal_count','physical_count')],
        'input_index':index,'normal_stop_links':links,'history_raw_sha256':sha(current_history_raw),
        'original_collector_sha256':COLLECTOR_SHA,'collector_source_sha256':sha(collector_sources()['collect_stop.py']),
        'finite_validator_sha256':sha(growth_source().encode()),'frozen_growth_sha256':GROWTH_SHA,
        'frozen_outer_projection_sha256':POST_SHA,'approved_identities_raw_sha256':index['approved_identities']['sha256'],
        'api_calls':False,'gpu_calls':False,'normal_stop_passed':False,'hardware_qualification':False,'production_qualified':False}
    return doc,current_history_raw,receipt

def emit(output,files,receipt):
    output=Path(output);parent=output.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode)and not output.parent.is_symlink()and parent.st_uid==os.getuid()
        and stat.S_IMODE(parent.st_mode)==0o700,'New private exclusive output parent required')
    output.mkdir(mode=0o700)
    for name,raw in {**files,'preparation-receipt.json':encode(receipt)}.items():
        require(not Path(name).is_absolute()and'..'not in Path(name).parts,'Relative source member required')
        path=output/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb')as stream:stream.write(raw)

def main(argv=None):
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--prepare-collector',action='store_true');parser.add_argument('--source-sha256')
    parser.add_argument('--output',type=Path);parser.add_argument('--assemble-growth',action='store_true')
    parser.add_argument('--index',type=Path);parser.add_argument('--index-sha256')
    args=parser.parse_args(argv)
    if not args.prepare_collector and not args.assemble_growth:
        print(canonical({'state':'inert','api_calls':False,'gpu_calls':False,'writes':False}));return 0
    require(args.source_sha256 and args.output,'Exact preparation source pin and new private output required')
    read({'path':str(Path(__file__).absolute()),'sha256':args.source_sha256})
    require(args.prepare_collector is not args.assemble_growth,'One explicit local preparation operation required')
    if args.assemble_growth:
        require(args.index and args.index_sha256,'Exact actual raw-pinned collector/approval index required')
        doc,history_raw,receipt=assemble(parse(read({'path':str(args.index.absolute()),'sha256':args.index_sha256})))
        files={'future-growth.json':encode(doc),'future-history-v2.json':history_raw}
        receipt['source_sha256']=args.source_sha256;receipt['output_pins']={k:sha(v)for k,v in files.items()}
        emit(args.output,files,receipt);print(canonical({'state':receipt['state'],'counts':receipt['counts'],'output':str(args.output)}));return 0
    files=collector_sources()
    receipt={'version':1,'state':'strict20-collector-source-prepared-not-executed',
        'source_sha256':args.source_sha256,'collector_source_sha256':sha(files['collect_stop.py']),
        'original_collector_sha256':COLLECTOR_SHA,'files':{k:sha(v)for k,v in files.items()},
        'api_calls':False,'gpu_calls':False,'collector_executed':False,'normal_stop_passed':False,
        'hardware_qualification':False,'production_qualified':False}
    emit(args.output,files,receipt);print(canonical({'state':receipt['state'],'output':str(args.output)}));return 0

if __name__=='__main__':raise SystemExit(main())
