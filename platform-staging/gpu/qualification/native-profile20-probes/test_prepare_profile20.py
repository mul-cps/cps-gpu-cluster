import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent

def module(raw, name='cpu_probe'):
    path=HERE/'prepare_profile20.py'if name=='prepare_profile20'else HERE/'templates/mps_probe.py'
    value = SimpleNamespace(__name__=name, __file__=str(path))
    exec(compile(raw, name, 'exec'), value.__dict__)
    return value

def load():
    return module((HERE/'prepare_profile20.py').read_bytes(), 'prepare_profile20')

def events(runner, cap=20480):
    """CPU-only future measurement shape; never a hardware receipt."""
    sec = 1_000_000_000
    def event(phase, at, **values):
        return dict(phase=phase, run_id='synthetic-cpu-only', monotonic_ns=at*sec,
            wall_ns=at*sec, **values)
    registered=event('mps-registered',1,environment_controls=['CUDA_MPS_LOG_DIRECTORY','CUDA_MPS_PIPE_DIRECTORY'],
        control_sha256=runner.CONTROL_SHA,server_sha256=runner.SERVER_SHA)
    oom=event('typed-oom',2,cuda_result=2,held_mib=cap-1024,attempted_mib=cap-768)
    start=event('sustained-work-started',3,minimum_seconds=120,clients=2,held_mib=cap-1024)
    ticks=[event('sustained-kernel-tick',3+i,tick=i+1,clients=2,vector_verified=True,held_mib=cap-1024)for i in range(121)]
    end=event('sustained-work-completed',123,actual_work_ns=120*sec,kernel_ticks=121,minimum_seconds=120,clients=2,held_mib=cap-1024)
    recovery=event('recovery-passed',124,clients=2)
    cleaned=event('daemon-cleanup-confirmed',125,completed=True,client_exit_codes=[0,0],cleanup_errors=[],private_mps_processes=[])
    done=dict(state='bounded-sequence-passed',case='oom',cap_mib=cap,max_attempted_mib=cap+256,
        source_sha256=runner.PROBE_SHA,aggregate_sequence_passed=True,recovery_clients=2,
        typed_oom={k:oom[k]for k in('cuda_result','held_mib','attempted_mib')},production_qualified=False,
        duration_seconds=120,total_budget_seconds=175,cleanup_reserve_seconds=25,sustained_work_ns=120*sec,sustained_kernel_ticks=121)
    mps=[registered,event('oversized-denial',2,cuda_result=2,attempted_mib=cap+256),oom,start,*ticks,end,recovery,cleaned,done]
    peer=[event('peer_tick',i,tick=i+1,kernel_byte=i%200+1)for i in range(127)]
    peer.append(dict(phase='receipt',case='peer',state='measurement-completed',peer_loop_passed=True,
        production_qualified=False,hardware={'gpu_uuid':runner.GPU,'uid':1000,'gid':100}))
    targets=[]
    for uid,size in [('cps',5120),('cit',cap)]:
        targets.append(dict(pod_uid=uid,intent={'cap_mib':size},identity={'synthetic':True},seal_id=uid,
            journal_sha256=uid,gate_sha256=uid,inventory_row=dict(soft=size*1048576,hard=size*1048576,
            used=0,offline=False,pinned=True,default_hierarchy=True)))
    before=dict(pods=[{'synthetic':True}],host=dict(targets=targets,retired_caps=[{'complete':'cpu history'}]))
    samples=[]
    for i in range(13):
        s=copy.deepcopy(before);s['host']['observed_at_ns']=(3+i*10)*sec
        s['host']['targets'][0]['inventory_row']['used']=64*1048576
        s['host']['targets'][1]['inventory_row']['used']=(cap-768)*1048576
        samples.append(s)
    return mps,peer,samples,before

class ProbeTests(unittest.TestCase):
    def setUp(self):self.p=load()
    def rendered(self,preset='cps5-cit20'):
        self.assertTrue(hasattr(self.p,'render_probes'),'trusted preset renderer missing')
        return self.p.render_probes(preset, b"HOST_SOURCE = 'synthetic CPU source only'\n")
    def test_twenty_probe_cli_accepts_only_fixed_caps_and_defaults_inert(self):
        out=self.rendered();probe=HERE/'templates/group_probe.py'
        with patch('sys.argv',[str(probe),'--cap-mib','20480']):
            p=module(out['group_probe.py'])
            with patch('builtins.print')as emitted:p.main()
        value=json.loads(emitted.call_args.args[0]);self.assertEqual(value['cap_mib'],20480)
        self.assertEqual(value['state'],'inert');self.assertFalse(value['gpu_calls'])
        with patch('sys.argv',[str(probe),'--cap-mib','20481']),patch('sys.stderr'):
            with self.assertRaises(SystemExit):p.main()
    def test_original_ten_default_source_preserved(self):
        out=self.rendered('cps5-cit10')
        self.assertEqual(out['mps_probe.py'],(HERE/'templates/mps_probe.py').read_bytes())
        p=module(out['mps_probe.py']);self.assertEqual(p.CAP_MIB,10240)
        with patch.object(p,'emit')as emit:p.main([])
        self.assertFalse(emit.call_args.args[0]['gpu_calls'])
    def test_twenty_mps_fixed_per_client_bounds_and_no_gpu_at_import(self):
        out=self.rendered();p=module(out['mps_probe.py'])
        self.assertEqual((p.CAP_MIB,p.STEP_MIB,p.MAX_ATTEMPT_MIB),(20480,256,20736))
        self.assertEqual((p.WORK_SECONDS,p.TOTAL_SECONDS,p.CLEANUP_SECONDS),(120,175,25))
        c=p.Cuda.__new__(p.Cuda);c.held=[object()]*41
        with self.assertRaisesRegex(ValueError,'bounded'):c.allocate(256)
        c.held=[]
        with self.assertRaisesRegex(ValueError,'bounded'):c.allocate(20736,touch=True)
        with self.assertRaisesRegex(ValueError,'bounded'):c.allocate(20480,touch=False)
        c.held=[object()]*40;c.lib=SimpleNamespace(cuMemAlloc_v2=lambda pointer,size:2)
        self.assertEqual(c.allocate(256)['cuda_result'],2)
    def test_sustained_twenty_assessment_and_pool_limit(self):
        runner=module(self.rendered()['run_mps.py'])
        self.assertTrue(runner.assess(*events(runner))['sustained_measurement_passed'])
        for mutation in ('cap','pool','history','no-kernel','short','charge-gap','oom','cleanup','zero-peer'):
            m,p,s,b=events(runner)
            if mutation=='cap':s[5]['host']['targets'][1]['inventory_row']['used']=20480*1048576+1
            elif mutation=='pool':
                s[5]['host']['targets'][0]['inventory_row']['hard']=6144*1048576
                s[5]['host']['targets'][0]['inventory_row']['soft']=6144*1048576
                s[5]['host']['targets'][0]['intent']['cap_mib']=6144
                b['host']['targets'][0]=copy.deepcopy(s[5]['host']['targets'][0])
            elif mutation=='history':s[5]['host']['retired_caps']=[]
            elif mutation=='no-kernel':m[:]=[e for e in m if e.get('phase')!='sustained-kernel-tick']
            elif mutation=='short':next(e for e in m if e.get('phase')=='sustained-work-completed')['actual_work_ns']=11
            elif mutation=='charge-gap':del s[4:7]
            elif mutation=='oom':next(e for e in m if e.get('phase')=='typed-oom')['cuda_result']=801
            elif mutation=='cleanup':next(e for e in m if e.get('phase')=='daemon-cleanup-confirmed')['cleanup_errors']=['failed']
            elif mutation=='zero-peer':s[5]['host']['targets'][0]['inventory_row']['used']=0
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):runner.assess(m,p,s,b)
    def test_default_preparer_has_no_api_or_gpu(self):
        result=subprocess.run([sys.executable,str(HERE/'prepare_profile20.py')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout)
        self.assertEqual(value['state'],'inert');self.assertFalse(value['gpu_calls']);self.assertFalse(value['api_calls'])
    def test_unknown_preset_rejects(self):
        self.assertTrue(hasattr(self.p,'preset'),'explicit preset validator missing')
        for value in ('cps20-cit5','cps5-cit21',None,True):
            with self.subTest(value=value),self.assertRaises(ValueError):self.p.preset(value)
    def test_generic_baseline_spans_have_no_fixed29_31_23_25_shape(self):
        self.assertTrue(hasattr(self.p,'generalize_start_assembler'),'full-baseline assembler missing')
        path=Path('/home/bjoern/.local/state/cps-platform-completion-20261011/native-next5-10-harness-source-prepared-20261012/prepare_next.py')
        source=self.p.generalize_start_assembler(path.read_bytes(),'cps5-cit20')
        self.assertNotIn("len(old['allocations'])==29",source)
        self.assertNotIn("len(new['allocations'])==31",source)
        self.assertNotIn("len(history['records'])==23",source)
        self.assertNotIn('len(saved)==25',source)
        self.assertIn("new['allocations'].get(k)==v",source)
        self.assertIn("entry['value']==row['record']",source)
        self.assertIn("entry['rawSha256'].removeprefix",source)
    def test_harness_render_preserves_history_and_epoch_guards(self):
        self.assertTrue(hasattr(self.p,'profile_renderer_source'),'profile20 guarded renderer missing')
        path=Path('/home/bjoern/.local/state/cps-platform-completion-20261011/sustained-mps-controlled-cycle-20261012/harness-next/prepare_harness.py')
        raw=self.p.profile_renderer_source(path.read_bytes(),'cps5-cit20')
        self.assertIn('20480',raw.decode());self.assertIn("p['budget_mib'] == 25600",raw.decode())
        self.assertIn("record.identity.epoch == controller.DriverEpoch",raw.decode())
        self.assertIn("Actual fresh selected-device NVML/MIG/free-memory capture required",raw.decode())
    def test_complete_twenty_render_with_real_baseline_and_synthetic_target_shape(self):
        """Real immutable history replay plus fictional20 binding: CPU evidence only."""
        self.assertTrue(hasattr(self.p,'install_renderer'),'complete renderer missing')
        sys.path.insert(0,str(self.p.CODE))
        spec=importlib.util.spec_from_file_location('profile20_recovery_test',self.p.CODE/'prepare_recovery_harness.py')
        r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
        self.p.install_renderer(r,'cps5-cit20')
        h=self.p.BASE/'sustained-mps-controlled-cycle-20261012/harness-next-inputs/binding.json'
        binding=json.loads(h.read_text());binding['targets'][1]['cap_mib']=20480
        binding['targets'][1]['profile']='interactive-native-qualification-20';binding['pool']['budget_mib']=25600
        history=json.loads((self.p.BASE/'sustained-mps-controlled-cycle-20261012/stop-next-evidence-v1/history/terminal-history-v2.json').read_text())
        binding['targets'][0]['pod_uid']='1aac573b-2026-4000-8000-000000000001'
        binding['targets'][1]['pod_uid']='1aac573b-2026-4000-8000-000000000002'
        from_source=self.p.BASE.parent/'cps-group-native-20261009/group-probes'
        sources={k:r.p.read_pinned(from_source/k,v)for k,v in r.p.SOURCE_PINS.items()}
        validators=r.bundle(*[Path('/home/bjoern/git/cps-compute-worktrees/cleared-offline-recovery-20261011/src/cps_compute')/k for k in('native_gpu_controller.py','native_gpu_control.py')],
            Path('/home/bjoern/git/cps-gpu-cluster-worktrees/native-cleared-offline-recovery-20261011/platform-staging/gpu/native-group-pilot/node_agent.py'),
            '05a6ca95eaaaf79cdbbdffec8172c804676d982a4154a422188639cd6b24f09b',
            Path('/home/bjoern/git/cps-gpu-cluster-worktrees/native-cleared-offline-recovery-20261011/platform-staging/gpu/native-group-pilot/cleared_offline_recovery.py'),
            '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b')
        out=r.render_sources(sources,binding,history,validators,native_binary=b'CPU-render-only-never-an-ELF')
        pre=out['run_group_acceptance.py'].decode()
        self.assertIn('BUDGET_BYTES = 26843545600',pre)
        self.assertIn("failure.get('cap_mib')==20480",pre)
        self.assertIn('19456',pre);self.assertIn('20736',pre)
        self.assertEqual(json.loads(out['retired-caps.json']),history)
        self.assertIn('record.intent.cap_mib in (5120, 10240, 20480)',pre)
        self.assertIn("need(set(saved)",self.p.generalize_start_assembler(self.p.ASSEMBLER_PATH.read_bytes(),'cps5-cit20'))
    def test_offline_build_recipe_excludes_devices_network_and_privilege(self):
        self.assertTrue(hasattr(self.p,'build_recipe'),'inert offline build recipe missing')
        recipe=self.p.build_recipe('/root-reviewed/20-sources','/root-reviewed/20-build','cps5-cit20')
        for key in('compile_argv','cpu_inert_argv'):
            argv=recipe[key];self.assertIn('--network=none',argv);self.assertIn('--cap-drop=ALL',argv)
            self.assertIn('--read-only',argv);self.assertNotIn('--privileged',argv)
            self.assertFalse(any(a.startswith('--device')or '/dev/nvidia'in a for a in argv))
        self.assertEqual(recipe['compile_argv'][-1],'/out/native-imports-20')
        self.assertFalse(recipe['hardware_qualification']);self.assertNotEqual(recipe['state'],'cpu-compiled')
    def test_full_ledger_and_journal_extensions_preserve_actual31_25_baseline(self):
        """Full actual baseline + synthetic future pair; no count is a hardware claim."""
        raw=self.p.generalize_start_assembler(self.p.ASSEMBLER_PATH.read_bytes(),'cps5-cit20')
        a=module(raw,'extension_cpu_only')
        base=self.p.BASE/'sustained-mps-controlled-cycle-20261012'
        prior=json.loads((base/'stop-next-evidence-v1/ledger.json').read_text())
        history=json.loads((base/'stop-next-evidence-v1/history/terminal-history-v2.json').read_text())
        initial=json.loads((base/'current-lifetimes/ledger.json').read_text())
        from cps_compute.native_gpu_control import MeasuredNativeAuthority
        import cps_compute.native_gpu_controller as models
        codec=object.__new__(MeasuredNativeAuthority)
        binding=json.loads((base/'harness-next-inputs/binding.json').read_text())
        codec.pool={**binding['pool'],'memory_budget_mib':25600}
        state=json.loads(prior['data']['state.json']);old=copy.deepcopy(state)
        active=[r for r in json.loads(initial['data']['state.json'])['allocations'].values()if r['state']=='enrolled']
        targets=[];enrollments=[];starts={}
        new_journals={}
        original_host=json.loads((base/'harness-restart-inputs-driverroot/host-snapshot.json').read_text())
        for i,source in enumerate(('cps','cit')):
            record=copy.deepcopy(next(r for r in active if r['source']==source));cap=5120 if source=='cps'else 20480
            record['attempt']='1aac573b-2026-4000-8000-00000000000'+str(i+1)
            record['cap_mib']=cap;record['profile']='interactive-native-qualification-'+str(cap//1024)
            record['ceiling']['gpuMemoryGiB']=cap//1024;old_uid=record['intent']['pod_uid']
            uid='2aac573b-2026-4000-8000-00000000000'+str(i+1)
            record['intent'].update(pod_uid=uid,cap_mib=cap)
            identity={k:v for k,v in record.items()if k not in('version','binding_id','state','intent')}
            key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:60]
            record['binding_id']=key;state['allocations'][key]=record
            target={**record['intent'],'source':source,'workspace':record['workspace'],'profile':record['profile']}
            targets.append(target)
            enrollments.append(dict(kind='ConfigMap',immutable=True,metadata=dict(name='cps-native-enrollment-'+key[:40],
                namespace='cps-native-system',uid='3aac573b-2026-4000-8000-00000000000'+str(i+1)),
                data={'enrollment.json':json.dumps(codec._enrollment_record(record))}))
            starts[source]={'reservation_after':{'active':True,'attempt':record['attempt']}}
            journal=copy.deepcopy(original_host['directories']['journal']['records'][old_uid+'.json']['value'])
            journal['intent']=record['intent'];journal['readback']={'soft':cap*1048576,'hard':cap*1048576}
            journal['identity']['pod_uid']=uid;journal['identity']['cgroup_inode']+=1000
            for field in('cgroup_relative','cgroup_path'):
                journal['identity'][field]=journal['identity'][field].replace(old_uid.replace('-','_'),uid.replace('-','_')).replace(old_uid,uid)
            encoded=(a.canonical(journal)+'\n').encode()
            new_journals[uid+'.json']=dict(value=journal,uid=0,mode=0o600,nlink=1,rawSha256=hashlib.sha256(encoded).hexdigest())
        current=copy.deepcopy(prior);current['data']['state.json']=json.dumps(state)
        result=a.ledger_extension(prior,current,targets,enrollments,starts,codec)
        self.assertEqual(len(result['allocations']),len(old['allocations'])+2)
        for key,value in old['allocations'].items():self.assertEqual(result['allocations'][key],value)
        saved={r['pod_uid']+'.json':dict(value=r['record'],uid=0,mode=0o600,nlink=1,rawSha256=r['journal_sha256'])for r in history['records']}
        saved.update(new_journals);host={'directories':{'journal':{'ownerUid':0,'mode':0o700,'records':saved}}}
        a.journal_extension(host,history,targets,models,result)
        for kind in('old-ledger','old-journal','raw-journal','extra-journal','new-cap'):
            c=copy.deepcopy(current);h=copy.deepcopy(host)
            if kind=='old-ledger':
                bad=json.loads(c['data']['state.json']);next(iter(bad['allocations'].values()))['attempt']='changed';c['data']['state.json']=json.dumps(bad)
                with self.assertRaises(ValueError):a.ledger_extension(prior,c,targets,enrollments,starts,codec)
            else:
                if kind=='old-journal':next(iter(h['directories']['journal']['records'].values()))['value']['seal_id']='changed'
                elif kind=='raw-journal':next(iter(h['directories']['journal']['records'].values()))['rawSha256']='0'*64
                elif kind=='extra-journal':h['directories']['journal']['records']['extra.json']={}
                elif kind=='new-cap':h['directories']['journal']['records'][targets[1]['pod_uid']+'.json']['value']['readback']['hard']=2**64-1
                with self.subTest(kind=kind),self.assertRaises(ValueError):a.journal_extension(h,history,targets,models,result)
    def test_real_sequence_logic_holds19_gib_for120_verified_ticks_then_frees(self):
        """Only the clock and CUDA transport are simulated; sequence logic is real."""
        p=module(self.rendered()['mps_probe.py']);clock=SimpleNamespace(now=0.0);clients=[];marks=[]
        class Client:
            def __init__(self):self.held=0;self.ticks=[];self.maximum_blocks=0
            def request(self,op,**kw):
                if op=='allocate':
                    mib=kw['mib']
                    if mib==20736 or sum(c.held for c in clients)+mib>19456:return {'cuda_result':2}
                    self.held+=mib;self.maximum_blocks=max(self.maximum_blocks,self.held//256)
                    return {'cuda_result':0}
                if op=='free':self.held=0;return {'cuda_result':0}
                if op=='tick':
                    clock.now+=0.01;self.ticks.append((clock.now,sum(c.held for c in clients)))
                    return {'cuda_result':0,'vector_elements':256,'vector_verified':True}
                raise AssertionError(op)
        clients.extend(Client()for _ in range(2))
        def sleep(seconds):clock.now+=seconds
        with patch.object(p.time,'monotonic',lambda:clock.now),patch.object(p.time,'monotonic_ns',lambda:round(clock.now*1e9)),patch.object(p.time,'sleep',sleep):
            value=p.aggregate_sequence(clients,lambda phase,event:marks.append((phase,event,clock.now)),work_deadline=150)
        self.assertGreaterEqual(value['sustained_work_ns'],120_000_000_000)
        first=next(t for phase,v,t in marks if phase=='sustained-work-started')
        last=next(t for phase,v,t in marks if phase=='sustained-work-completed')
        self.assertEqual([c.held for c in clients],[0,0])
        for c in clients:
            ticks=[mib for at,mib in c.ticks if first<=at<=last]
            self.assertGreater(len(ticks),400);self.assertEqual(set(ticks),{19456})
            self.assertLessEqual(c.maximum_blocks,40)
        self.assertEqual(value['recovery_clients'],2)

if __name__=='__main__':unittest.main()
