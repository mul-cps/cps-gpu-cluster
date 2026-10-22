#!/usr/bin/env python3
"""Inert, exact-preimage preparation of a fresh 5/20GiB QA cohort; no live calls."""
import argparse
import hashlib
import json
import io
import tokenize
import os
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
COHORT='a9fc091b-f388-4f21-8771-b6ae7b4734dc'
PAIRS={'5-10':{'a':5120,'b':10240},'5-20':{'a':5120,'b':20480}}
PINS={
 'native-fresh-domain/render_fixture.py':'b5548e856124f7b1b0eef3112eb735315321c82c1161a1bcf64135879d7edbb0',
 'native-fresh-domain/controller.py':'2a5a9c2dee74fdcc870690033eab05b8ae15ea42c82ed2197dd123957349517f',
 'native-fresh-domain/observe.py':'c7a0b8105d73597fc0fb1deada8621ba816b366dcbde77b3b6352d548930a76b',
 'native-fresh-domain/fresh_preflight.py':'07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58',
 'native-fresh-domain/peer_probe.py':'ea49812f2f68371a27f63e709534f08aa1b23028395c4b76b2efc07b88d86834',
 'native-fresh-domain/run_peer_oom.py':'1e8a0d398672842bd124a3bbe3fbde50817b76c5394714dfbd374695d220653a',
 'native-fresh-aggregate/run_aggregate.py':'cf88f990aebc61267d8617dcd87faba319c468123f1dc9d75cc386d36cea391b'}


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def replace(source,old,new,count=1):
    require(source.count(old)==count,'Exact reviewed adaptation span changed: '+old[:90])
    return source.replace(old,new)


def load(name,raw):
    m=types.ModuleType('unequal_'+name.replace('.','_'));m.__file__=str(HERE/name)
    exec(compile(raw,m.__file__,'exec'),m.__dict__);return m


# These helpers are included in both generated runners, after exact original helpers.
HELD='''
def compare_observations(before,after):
 require(before['pods']==after['pods'] and before['host']['processes']==after['host']['processes'],'Current Pod/process drift')
 for prior,latest in zip(before['host']['targets'],after['host']['targets']):
  require({k:v for k,v in prior.items()if k!='limit'}=={k:v for k,v in latest.items()if k!='limit'},'Seal/journal/identity drift')

def held_accounting(before,held,events,targets,victim,*,aggregate=False):
 compare_observations(before,held)
 starts=[e for e in events if e.get('phase')=='oom-held-start'];ends=[e for e in events if e.get('phase')=='oom-held-end']
 require(len(starts)==len(ends)==1,'Exact held accounting interval required')
 observed=held['host']['observed_monotonic_ns']
 require(type(observed)is int and starts[0]['monotonic_ns']<observed<ends[0]['monotonic_ns'],'Native accounting must be observed inside held pressure')
 rows=held['host']['targets'];wanted={r['uid']:r['cap_mib'] for r in targets['pods'].values()}
 require({r['pod_uid'] for r in rows}==set(wanted),'Exact current native accounting targets required')
 for row in rows:
  cap=wanted[row['pod_uid']]*1048576;limit=row['limit']
  require(limit['soft']==limit['hard']==cap and type(limit['used'])is int and 0<=limit['used']<=cap,'Per-UID exact finite accounting required')
 require(sum(r['limit']['hard'] for r in rows)==25600*1048576 and sum(r['limit']['used'] for r in rows)<=25600*1048576,'Actual aggregate accounting exceeds25GiB')
 row=next(r for r in rows if r['pod_uid']==targets['pods'][victim]['uid'])
 minimum=targets['pods'][victim]['cap_mib']-(1536 if aggregate else 1024)
 require(row['limit']['used']>=minimum*1048576,'Meaningful held native charge required')
'''


def build_sources(pair='5-20'):
    require(type(pair)is str and pair in PAIRS,'Closed reviewed pair must be5-10 or5-20')
    raw={name:(HERE.parent/name).read_bytes() for name in PINS}
    require(all(sha(raw[name])==pin for name,pin in PINS.items()),'Exact complete reviewed source preimages required')
    out={Path(name).name:content.decode() for name,content in raw.items()}
    r=out['render_fixture.py']
    r=replace(r,"'gate_image', 'policy_hash'},","'gate_image', 'policy_hash', 'pair'},")
    r=replace(r,"'gate_image', 'policy_hash', 'cohort_uid'}","'gate_image', 'policy_hash', 'cohort_uid', 'pair'}")
    r=replace(r,"and type(value['version']) is int","and value['pair']=="+repr(pair)+" and type(value['version']) is int")
    r=replace(r,'    request = validate_request(request)\n    require(approve_qa_hostpaths',
        "    request = validate_request(request)\n    require(request.get('cohort_uid')=="+repr(COHORT)+", 'Exact reviewed fresh unequal cohort required')\n    require(approve_qa_hostpaths")
    r=replace(r,"        binding = runtime.NativeGpuBinding", "        cap = 5120 if label == 'a' else 20480\n        profile = deepcopy(PROFILE); profile['gpu']['nominalMemoryGiB'] = cap // 1024\n        binding = runtime.NativeGpuBinding")
    r=replace(r,"profile='native-gpu-5g-pilot'", "profile='native-gpu-'+str(cap//1024)+'g-pilot'")
    r=replace(r,'compile_native_gpu_pod(base, PROFILE,','compile_native_gpu_pod(base, profile,')
    r=replace(r,'NativePodContract(pod, binding, 5120,','NativePodContract(pod, binding, cap,')
    out['render_fixture.py']=r
    c=out['controller.py']
    c=replace(c,'def inventory(value, allowed, *, allow_offline=False, retired=None):',
        'def inventory(value, allowed, *, allow_offline=False, retired=None, sealed=False):')
    c=replace(c,"(5120*1048576,5120*1048576)","(allowed[row['inode']],allowed[row['inode']])")
    c=replace(c,"    require(set(retired).issubset(seen), 'Reviewed retained native entries disappeared')", """    require(set(retired).issubset(seen), 'Reviewed retained native entries disappeared')
    if sealed:
        require(set(allowed).issubset(seen),'Both exact active native parents required')
        live=[row for row in value['entries'] if row['inode'] in allowed]
        require(all(row['soft']==row['hard']==allowed[row['inode']] for row in live)
                and sum(row['hard'] for row in live)==25600*1048576
                and sum(row['used'] for row in live)<=25600*1048576,
                'Exact per-parent finite25GiB aggregate budget required')""")
    c=replace(c,'def cleanup_records(controller, journal, intents):', """def expected_cap(name,cohort):
    require(cohort=="""+repr(COHORT)+""",'Exact reviewed fresh unequal cohort required')
    names={'native-qa147-a-'+cohort[:8]:5120,'native-qa147-b-'+cohort[:8]:20480}
    require(name in names,'Exact unequal cohort Pod name required')
    return names[name]

def cleanup_records(controller, journal, intents):""")
    c=replace(c,'intent.gpu_uuid == GPU and intent.cap_mib == 5120',
        'intent.gpu_uuid == GPU and intent.cap_mib == expected_cap(intent.name,args.cohort_uid)')
    c=replace(c,'{record.identity.cgroup_inode for record in original},allow_offline=True',
        '{record.identity.cgroup_inode:record.intent.cap_bytes for record in original},allow_offline=True')
    c=replace(c,'allowed = {identity.cgroup_inode for identity in identities}',
        'allowed = {identity.cgroup_inode:intent.cap_bytes for identity,intent in zip(identities,intents)}')
    c=replace(c,'allowed.intersection(retired)','set(allowed).intersection(retired)')
    c=replace(c,"inventory(backend._inventory(identities[0]), allowed,retired=retired)\n        print", "inventory(backend._inventory(identities[0]), allowed,retired=retired,sealed=True)\n        print")
    out['controller.py']=c
    o=out['observe.py']
    o=replace(o,"CONTROLLER_SHA256='"+PINS['native-fresh-domain/controller.py']+"'", "CONTROLLER_SHA256='"+sha(c.encode())+"'")
    o=replace(o,'intent.gpu_uuid==c.GPU and intent.cap_mib==5120',
        'intent.gpu_uuid==c.GPU and intent.cap_mib==c.expected_cap(intent.name,args.cohort_uid)')
    o=replace(o,'        normalized=deepcopy(actual)',
        '        caps={r.identity.cgroup_inode:r.intent.cap_bytes for r in records}\n        normalized=deepcopy(actual)')
    o=replace(o,"        for row in normalized['entries']:\n            require", "        for row in normalized['entries']:\n            cap=caps.get(row.get('inode'),retired.get(row.get('inode'),{}).get('hard'))\n            require(cap is not None,'Unbound native parent denied')\n            require")
    o=replace(o,'0<=row[\'used\']<=5120*1048576',"0<=row['used']<=cap")
    o=replace(o,"row.get('soft')==row.get('hard')==5120*1048576", "row.get('soft')==row.get('hard')==cap")
    o=replace(o,'c.inventory(normalized,{r.identity.cgroup_inode for r in records},retired=retired)',
        "c.inventory(normalized,caps,retired=retired,sealed=True)\n        require(sum(row['used'] for row in actual['entries'] if row['inode'] in caps)<=25600*1048576,'Actual active charge exceeds25GiB')")
    out['observe.py']=o
    p=out['fresh_preflight.py']
    p=replace(p,"and row['cap_mib']==5120", "and row['cap_mib']==(5120 if key=='a' else 20480)")
    p=replace(p,"    require(type(cohort) is str and str(uuid.UUID(cohort))==cohort and uuid.UUID(cohort).int>0,", "    require(cohort=="+repr(COHORT)+" and type(cohort) is str and str(uuid.UUID(cohort))==cohort and uuid.UUID(cohort).int>0,")
    out['fresh_preflight.py']=p
    probe=out['peer_probe.py']
    probe=replace(probe,"    parser.add_argument('--duration',type=int,default=120)","    parser.add_argument('--duration',type=int,default=120)\n    parser.add_argument('--cap-mib',type=int,choices=(5120,20480),default=5120)")
    probe=replace(probe,'    args=parser.parse_args()', '    args=parser.parse_args()\n    global CAP_MIB\n    CAP_MIB=args.cap_mib')
    probe=replace(probe,'        for step in range(1,CAP_MIB//STEP_MIB+2):',"""        try:
            candidate=torch.empty((CAP_MIB+STEP_MIB)*MIB,dtype=torch.uint8,device='cuda')
        except Exception as error:
            proof=oom_proof(error,torch)
            if proof is None:raise
            result.update(oversized_denied=True,oversized_error=proof)
            mark('oversized-denial',{'attempted_total_tensor_mib':CAP_MIB+STEP_MIB,'typed_oom':proof})
        else:
            candidate=None;torch.cuda.empty_cache()
            raise RuntimeError('Oversized allocation unexpectedly succeeded; never touched')
        for step in range(1,CAP_MIB//STEP_MIB+2):""")
    probe=replace(probe,"1536 if args.case=='aggregate-oom' else 4096", "CAP_MIB-3584 if args.case=='aggregate-oom' else CAP_MIB-1024")
    out['peer_probe.py']=probe
    for name,aggregate in (('run_peer_oom.py',False),('run_aggregate.py',True)):
        s=out[name]
        s=replace(s,"'--duration', str(duration), '--expected-device-uuid', GPU]", "'--duration', str(duration), '--expected-device-uuid', GPU, '--cap-mib', str(target['cap_mib'])]")
        if aggregate:
            s=replace(s,"preflight=here.parent/'native-fresh-domain'/'fresh_preflight.py'", "preflight=here/'fresh_preflight.py'")
            s=replace(s,"def assess(peer,oom,samples,*,peer_case='aggregate-peer'):", "def assess(peer,oom,samples,*,cap_mib,peer_cap_mib,peer_case='aggregate-peer'):")
            s=replace(s,'1536<=held<=2816','cap_mib-3584<=held<=cap_mib-2304')
            s=replace(s,'def assess_aggregate(holder,oom,ordinary,samples):','def assess_aggregate(holder,oom,ordinary,samples,*,cap_mib,peer_cap_mib):')
            s=replace(s,'result=assess(holder,oom,samples)','result=assess(holder,oom,samples,cap_mib=cap_mib,peer_cap_mib=cap_mib)')
            s=replace(s,"other=assess(ordinary,oom,samples,peer_case='peer')", "other=assess(ordinary,oom,samples,cap_mib=cap_mib,peer_cap_mib=peer_cap_mib,peer_case='peer')")
            s=replace(s,'result=assess_aggregate(holder_events,oom_events,peer_events,samples)', "result=assess_aggregate(holder_events,oom_events,peer_events,samples,cap_mib=targets['pods'][selected['oom']]['cap_mib'],peer_cap_mib=targets['pods'][selected['ordinary']]['cap_mib'])\n  held_accounting(before,held,oom_events,targets,selected['oom'],aggregate=True)")
        else:
            s=replace(s,'def assess(peer,oom,samples):','def assess(peer,oom,samples,*,cap_mib,peer_cap_mib):')
            s=replace(s,'4096<=held<=5120','cap_mib-1024<=held<=cap_mib')
            s=replace(s,'result=assess(peer_events,oom_events,samples)', "result=assess(peer_events,oom_events,samples,cap_mib=targets['pods'][b]['cap_mib'],peer_cap_mib=targets['pods'][a]['cap_mib'])\n  held_accounting(before,held,oom_events,targets,b)")
        s=replace(s," typed=failure.get('over_error')", " require(pr.get('cap_mib')==peer_cap_mib and failure.get('cap_mib')==cap_mib and failure.get('oversized_denied')is True and failure.get('oversized_error')==failure.get('over_error') and failure.get('maximum_attempted_tensor_mib')==cap_mib+256,'Exact target oversized typed OOM required')\n typed=failure.get('over_error')")
        s=replace(s,"  samples=physical_samples(targets);write_json(output/'physical-samples.json',samples)", "  held=current.preflight({'manifest':targets});write_json(output/'held-native-accounting.json',held)\n  samples=physical_samples(targets);write_json(output/'physical-samples.json',samples)")
        s=replace(s,"if __name__=='__main__':main()",HELD+"\nif __name__=='__main__':main()")
        out[name]=s
    if pair=='5-10':
        # Only exact numeric tokens in GENERATED source are selected; never source
        # hashes, timeouts, arbitrary substrings or either-cap acceptance lists.
        for name,source in out.items():
            tokens=[]
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type==tokenize.NUMBER and token.string in ('20480','25600'):
                    token=token._replace(string={'20480':'10240','25600':'15360'}[token.string])
                tokens.append(token)
            out[name]=tokenize.untokenize(tokens).replace('finite25GiB','finite15GiB').replace('exceeds25GiB','exceeds15GiB')
        out['observe.py']=replace(out['observe.py'],sha(c.encode()),sha(out['controller.py'].encode()))
    result={name:source.encode() for name,source in out.items()}
    for name,source in result.items():compile(source,name,'exec')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true');p.add_argument('--inputs',type=Path)
    p.add_argument('--inputs-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--approve-qa-hostpaths',action='store_true')
    args=p.parse_args(argv)
    if not args.prepare:print(json.dumps({'inert':True,'api_calls':False,'gpu_calls':False}));return
    require(args.inputs and args.inputs_sha256 and args.output and args.approve_qa_hostpaths,
        'Explicit pinned reviewed request/exclusive output/QA hostpath approval required')
    raw=args.inputs.read_bytes();require(len(raw)<=65536 and sha(raw)==args.inputs_sha256,'Reviewed request raw bytes changed')
    request=json.loads(raw);pair=request.get('pair') if type(request)is dict else None
    sources=build_sources(pair)  # All exact preimages authenticate before any dependency executes.
    r=load('render_fixture.py',sources['render_fixture.py'])
    review=r.render(request,approve_qa_hostpaths=True)
    args.output.mkdir(mode=0o700)
    receipt={'version':1,'state':'prepared-awaiting-Root-execution','source_sha256':PINS,
        'generated_sha256':{name:sha(data) for name,data in sources.items()},'request_raw_sha256':sha(raw),
        'pair':pair,'profile_caps':PAIRS[pair],'budget_mib':sum(PAIRS[pair].values()),'hardware_qualified':False,'production_qualified':False}
    documents={'preparation.json':receipt,'inputs.json':request,'review.json':review,
        'gate-source.configmap.json':review['source_configmap'],
        **{key+'.proposed.json':pod for key,pod in review['pods'].items()}}
    for name,data in {**sources,**{name:canonical(value)+b'\n' for name,value in documents.items()}}.items():
        fd=os.open(args.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data)
    print(json.dumps({'prepared':True,'output':str(args.output),'api_calls':False,'gpu_calls':False}))


if __name__=='__main__':main()
