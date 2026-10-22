#!/usr/bin/env python3
"""Default-inert packaged5/10 preparation with strictly observed original cleanup768."""
import argparse,ast,hashlib,json,os,subprocess,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCER_SHA='060c47788c43fd8334b1db52eefcf0d3bf17066d607ad7fbbab4a832fb89e872'
SDK=Path('/home/bjoern/git/cps-compute-worktrees/native-cleanup-offline-unlimited-20261023/src')
SDK_COMMIT='76800510088bfdf92cc928f22eaae7934916e8a0'
PINS={'native_gpu_controller.py':'d677b3756965dc0f3a3042728ac41687b5cd085e052e235909cd41263573645a',
'native_gpu_health.py':'fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8',
'native_node/backend.py':'23a5cc22701d058499f8f818d0a6e34595110d4eb334150852df6dc853a85a73',
'native_node/identity.py':'9864e8df1406cce46bdc847e2d85619e7ca1d9723811e731ea93844f0c838dfd',
'native_node/nvml.py':'0bedb1ea0a6301a2298da30d318dae2519ac0e05e0d35d05b7b5f2136a0d221c',
'native_node/transport.py':'51c301067def92dbced90f5e1e7cba0e694850df88ed6d64189fbcc8a54743ba'}
def require(ok,message):
 if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def replace(source,old,new):
 require(source.count(old)==1,'Exact reviewed adaptation span changed');return source.replace(old,new)
def load(name,raw):
 module=types.ModuleType('cleanup_'+name.replace('.','_'));module.__file__=str(HERE/name)
 exec(compile(raw,module.__file__,'exec'),module.__dict__);return module

def bundle_sources():
 require(subprocess.check_output(['git','-C',str(SDK.parent),'rev-parse','HEAD'],text=True).strip()==SDK_COMMIT,'Exact committed cleanup768 source required')
 raw={name:(SDK/'cps_compute'/name).read_bytes() for name in PINS}
 require(all(sha(raw[name])==pin for name,pin in PINS.items()),'Complete reviewed source bundle bytes required')
 return raw

def build_sources(cohort):
 producer=(HERE/'prepare_packaged_gate.py').read_bytes();require(sha(producer)==PRODUCER_SHA,'Exact packaged producer required')
 bundle_sources() # Authenticate every runtime preimage before dependency execution.
 original=load('prepare_packaged_gate.py',producer).build_sources(cohort)
 source=original['controller.py'].decode()
 source=replace(source,'61ce9fa1d04d4ca2b1af02ceee6985eba8a6c2f291b139599b15c9e75a667ae7',PINS['native_gpu_controller.py'])
 source=replace(source,'f544fc3266e710119651010e3fcc35696b3b096ebe7de0a7dc5da65f31ae250e',PINS['native_node/backend.py'])
 source=replace(source,"SDK = Path('/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')",'SDK = Path('+repr(str(SDK))+')')
 old="""        require(record.state=='retired-inert-cap' and record.recovery is None
                and record.retirement is not None,'Only original fully retired-inert-cap journals are admissible')
        fresh=backend.retired_inert_cap(record.identity,record.limit)
        require(fresh.identity==record.retirement.identity and fresh.epoch==record.retirement.epoch
                and fresh.gpu_id==record.retirement.gpu_id and fresh.entry==record.retirement.entry
                and backend.read_gate(record.identity) is None,'Fresh original retirement entry/absence changed')
        fresh.require_limit(record.limit)"""
 new="""        def no_set(*args,**kwargs):raise ValueError('Prior retirement observation forbids native SET')
        backend.set_limit=no_set
        require(record.recovery is None,'Operator exception is not a normal retirement input')
        if record.state=='cleanup-offline-unlimited':
            require(type(record.cleanup_offline) is backend.m.CleanupOfflineUnlimited,
                    'Exact original completed cleanup proof required')
            # Revalidate an ALREADY completed immutable terminal, not initial cleanup.
            # As with finite retirement, unrelated live peers do not own this offline pin.
            intent,group=backend._current(record.identity,absent=True)
            require(group is None and backend.get_pod(intent) is None
                    and backend.read_gate(record.identity) is None,'Original completed cleanup absence changed')
            backend._retired_mount(record.identity)
            fresh=backend.m.validate_cleanup_inventory(backend._inventory(record.identity),record)
            require(type(fresh) is backend.m.CleanupOfflineUnlimited,'Original unlimited terminal changed')
            fresh.require_same_target(record.cleanup_offline)
            intent,group=backend._current(record.identity,absent=True)
            require(group is None and backend.get_pod(intent) is None
                    and backend.read_gate(record.identity) is None,'Final original completed cleanup absence changed')
            backend._retired_mount(record.identity)
        else:
            require(record.state=='retired-inert-cap' and record.retirement is not None,
                    'Only original typed completed retirements are admissible')
            fresh=backend.retired_inert_cap(record.identity,record.limit)
            require(fresh.identity==record.retirement.identity and fresh.epoch==record.retirement.epoch
                    and fresh.gpu_id==record.retirement.gpu_id and fresh.entry==record.retirement.entry
                    and backend.read_gate(record.identity) is None,'Fresh original retirement entry/absence changed')
            fresh.require_limit(record.limit)"""
 source=replace(source,old,new)
 result=dict(original);result['controller.py']=source.encode()
 result['observe.py']=replace(original['observe.py'].decode(),sha(original['controller.py']),sha(result['controller.py'])).encode()
 result['observe.py']=replace(result['observe.py'].decode(),
     """            cap=caps.get(row.get('inode'),retired.get(row.get('inode'),{}).get('hard'))""",
     """            if row.get('inode') in retired:
                require(row==retired[row['inode']],'Exact independently proven retired row required')
                continue
            cap=caps.get(row.get('inode'))""").encode()
 for name,content in result.items():compile(content,name,'exec')
 return result

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--inputs',type=Path);p.add_argument('--inputs-sha256');p.add_argument('--output',type=Path);p.add_argument('--approve-qa-hostpaths',action='store_true');a=p.parse_args(argv)
 if not a.prepare:print('{"state":"inert","api_calls":false,"gpu_calls":false}');return
 require(a.inputs and a.inputs_sha256 and a.output and a.approve_qa_hostpaths,'Reviewed request and new output/Root hostpath approval required')
 raw=a.inputs.read_bytes();require(0<len(raw)<=65536 and sha(raw)==a.inputs_sha256,'Exact reviewed request bytes required')
 def unique(pairs):
  result={}
  for key,value in pairs:require(key not in result,'Duplicate request key');result[key]=value
  return result
 request=json.loads(raw,object_pairs_hook=unique);require(type(request)is dict,'Closed request required')
 sources=build_sources(request.get('cohort_uid'));bundle=bundle_sources()
 review=load('render_fixture.py',sources['render_fixture.py']).render(request,approve_qa_hostpaths=True)
 documents={'review.json':review,'inputs.json':request,'preparation.json':{'version':1,'sdk_commit':SDK_COMMIT,'producer_sha256':PRODUCER_SHA,'source_sha256':{n:sha(r)for n,r in sources.items()},'bundle_sha256':PINS,'api_calls':False,'hardware_qualified':False,'production_qualified':False},**{k+'.proposed.json':v for k,v in review['pods'].items()}}
 a.output.mkdir(mode=0o700)
 output={**sources,**{'bundle/cps_compute/'+n:r for n,r in bundle.items()},**{n:(json.dumps(v,sort_keys=True,allow_nan=False)+'\n').encode()for n,v in documents.items()}}
 for name,content in output.items():
  path=a.output/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as f:f.write(content)
 print(json.dumps({'state':'prepared-awaiting-Root-execution','source_sha256':{n:sha(r)for n,r in sources.items()},'bundle_sha256':PINS,'api_calls':False,'gpu_calls':False}))
if __name__=='__main__':main()
