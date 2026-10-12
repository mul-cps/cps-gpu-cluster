"""CPU-only source preparation and synthetic finite-growth checks."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

HERE=Path(__file__).parent
def load():
    path=HERE/'prepare_stop20.py'
    spec=importlib.util.spec_from_file_location('prepare_stop20_cpu',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixture(m):
    """Actual complete baseline, synthetic new lifetimes: never hardware evidence."""
    def pin(path):return{'path':str(path),'sha256':m.sha(path.read_bytes())}
    root=m.BASE/'sustained-mps-controlled-cycle-20261012'
    post,base,history_raw=m.authenticated_baseline(pin(root/'future-growth31-local-prepared/index-actual.json'),
        pin(root/'stop-next-evidence-v1/physical/physical.json'))
    reader,loader,loaded,inspector=m.twenty_models(post)
    olddoc=json.loads((root/'future-growth31-local-prepared/actual31/future-growth.json').read_text())
    pair=copy.deepcopy(olddoc['pairs'][0]);binding=pair['binding']
    policy='sha256:a7bbf3bd475f38e3bed5d274ae4564940fff2665c053c680c5ed5c21f48a30a4'
    binding['policy_hash']=policy;binding['pool']['budget_mib']=25600
    oldstate=post.g.state(base['ledger']);state=copy.deepcopy(oldstate)
    pair['physical']=copy.deepcopy(base['recorded_physical']);pair['before']['host']['retired_caps']=copy.deepcopy(pair['physical']['retired_caps'])
    history=copy.deepcopy(base['current_history']);provenance=copy.deepcopy(olddoc['normal_stop_provenance']);identities={}
    from cps_compute.native_gpu_control import NativeGpuAuthority
    for i,(target,cap)in enumerate(zip(binding['targets'],(5120,20480))):
        olduid=target['pod_uid'];uid='3aac573b-2026-4000-8000-00000000000'+str(i+1)
        target.update(pod_uid=uid,cap_mib=cap,profile='interactive-native-qualification-'+str(cap//1024))
        journal=json.loads(pair['journals'][i]['raw']);journal['intent'].update(pod_uid=uid,cap_mib=cap,policy_hash=policy)
        identity=journal['identity'];identity['pod_uid']=uid;identity['cgroup_inode']+=10000000
        for key in ('cgroup_relative','cgroup_path'):
            identity[key]=identity[key].replace(olduid,uid).replace(olduid.replace('-','_'),uid.replace('-','_'))
        journal['seal_id']='4aac573b-2026-4000-8000-00000000000'+str(i+1)
        journal['readback']={'soft':cap*1048576,'hard':cap*1048576};proof=journal['retirement']
        proof['identity']=copy.deepcopy(identity)
        for key in ('inode','kernfs_id','cgroup_id'):proof['entry'][key]=identity['cgroup_inode']
        proof['entry'].update(soft=cap*1048576,hard=cap*1048576)
        native=pair['before']['host']['targets'][i]
        native.update(pod_uid=uid,intent=copy.deepcopy(journal['intent']),identity=copy.deepcopy(identity),seal_id=journal['seal_id'])
        allocation=copy.deepcopy(next(v for v in oldstate['allocations'].values()if v['source']==target['source']
            and v['workspace']==target['workspace']and v['profile']=='interactive-native-qualification-'+str(5 if i==0 else 10)))
        allocation.update(cap_mib=cap,profile=target['profile'],policy_hash=policy,intent=copy.deepcopy(journal['intent']),
            attempt='5aac573b-2026-4000-8000-00000000000'+str(i+1))
        allocation['ceiling']['gpuMemoryGiB']=cap//1024
        hashed={k:v for k,v in allocation.items()if k not in('version','binding_id','state','intent')}
        bid=m.sha(m.canonical(hashed).encode())[:60];allocation['binding_id']=bid
        state['allocations'][bid]=allocation;enrollment=NativeGpuAuthority._enrollment_record(allocation)
        ec,cc=pair['enrollments'][i],pair['cleanups'][i]
        for cm,prefix in ((ec,'cps-native-enrollment-'),(cc,'cps-native-cleanup-')):
            cm['metadata'].update(name=prefix+bid[:40],labels={'cps.compute/native-binding':bid})
        ec['data']['enrollment.json']=m.canonical(enrollment)
        cleanup=json.loads(cc['data']['receipt.json']);cleanup.update(binding_id=bid,attempt=allocation['attempt'],intent=journal['intent'])
        cleanup['retirement'].update(proof=copy.deepcopy(proof),enrollment_sha256='sha256:'+m.sha(m.canonical(enrollment).encode()),
            journal_sha256='sha256:'+m.sha(m.canonical(journal).encode()))
        cc['data']['receipt.json']=m.canonical(cleanup)
        raw=m.canonical(journal)+'\n';pair['journals'][i]={'raw':raw,'sha256':m.sha(raw.encode())}
        row={'pod_uid':uid,'journal_sha256':'sha256:'+m.sha(raw.encode()),'record':journal};history['records'].append(row)
        pair['physical']['retired_caps'].append({'pod_uid':uid,'journal_sha256':row['journal_sha256'],
            'identity':copy.deepcopy(identity),'retirement':copy.deepcopy(proof),'inventory_row':copy.deepcopy(proof['entry'])})
        outer=json.loads(pair['normal_stop'][i]['raw'])
        for body in (outer,outer['normal_source_receipt']):
            for model in (body['before'],body['workspace']):
                model['profile']=target['profile'];model['course_ceiling']['gpuMemoryGiB']=cap//1024
        outerraw=m.canonical(outer)+'\n';pair['normal_stop'][i]={'raw':outerraw,'sha256':m.sha(outerraw.encode())}
        identities[target['source']]={'identity':{k:copy.deepcopy(allocation[k])for k in m.IDENTITY},
            'handover_provenance':{k:'a'*64 for k in('before_full_sha256','after_full_sha256','receipt_sha256','review_sha256','adapter_sha256')}}
    current=copy.deepcopy(base['ledger']);current['metadata']['resourceVersion']='synthetic-cpu-33';current['data']['state.json']=m.canonical(state)
    pair['ledger']=current
    approval={'version':1,'enabled':True,'preset':'cps5-cit20','policy_hash':policy,
        'baseline_ledger_state_sha256':m.sha(m.canonical(oldstate).encode()),'baseline_history_raw_sha256':m.sha(history_raw),
        'binding_sha256':m.sha(m.canonical(binding).encode()),'sources':identities}
    args=(base,base['current_history'],current,history,[pair],pair['physical'],loaded,provenance,approval)
    kw=dict(post=post,reader=reader,loader=loader,inspector=inspector,history_pin=m.sha(history_raw))
    return args,kw

class Preparation(unittest.TestCase):
    def test_default_inert_does_not_read_or_execute(self):
        m=load()
        with patch.object(m,'read',side_effect=AssertionError('opened')),patch('subprocess.run',side_effect=AssertionError('executed')),redirect_stdout(io.StringIO())as out:
            self.assertEqual(m.main([]),0)
        self.assertEqual(json.loads(out.getvalue())['state'],'inert')
    def test_static_collector_changes_only_closed_caps_and_code_pins(self):
        m=load();files=m.collector_sources()
        original=(m.COLLECTOR/'collect_stop.py').read_bytes()
        code=files['collect_stop.py'].decode()
        self.assertIn('[5120, 20480]',code);self.assertNotIn('[5120, 10240]',code)
        codes=json.loads(files['code-pins.json']);self.assertEqual(len(codes['files']),14)
        self.assertEqual(set(codes['files']),set(json.loads((m.COLLECTOR/'code-pins.json').read_bytes())['files']))
        for name,item in codes['files'].items():self.assertEqual(hashlib.sha256(files[name]).hexdigest(),item['sha256'])
        self.assertEqual(files['inspect_stop.py'],(m.COLLECTOR/'inspect_stop.py').read_bytes())
        self.assertEqual(files['capture_host_journals.py'],(m.COLLECTOR/'capture_host_journals.py').read_bytes())
        self.assertEqual(files['capture_journal_raw.py'],(m.COLLECTOR/'capture_journal_raw.py').read_bytes())
        self.assertEqual(code.replace('[5120, 20480]','[5120, 10240]').replace('CPS5/CIT20','CPS5/CIT10').replace(m.p20.literal(code,'CODE_PINS_SHA'),m.CODE_PINS_SHA).encode(),original)
    def test_frozen_predicates_are_generalized_from_complete_preimages(self):
        m=load();raw=m.growth_source()
        self.assertIn('len(old_rows) == len(baseline_history[\'records\'])',raw)
        self.assertIn('_exact_baseline(baseline_ledger, baseline)',raw)
        self.assertIn('_approved_allocation(allocation)',raw)
        self.assertIn('len(pairs) == 1',raw)
        self.assertIn("all(new_rows.get(uid) == row for uid, row in old_rows.items())",raw)
        self.assertIn('stop.validate(',raw)
        self.assertNotIn('len(old_rows) == 17',raw)

class FiniteFuture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=load();cls.args,cls.kw=fixture(cls.m)
    def validate(self,args=None):return self.m.validate_future(*(args or self.args),**self.kw)
    def changed(self):return tuple(copy.deepcopy(x)if i!=6 else x for i,x in enumerate(self.args))
    def test_full31_25_20_baseline_plus_exact_finite_pair(self):
        result=self.validate()
        self.assertEqual((result['allocation_count'],result['journal_count'],result['physical_count']),(33,27,22))
        self.assertFalse(result['qualification']);self.assertFalse(result['source_writes'])
        for key,value in self.kw['post'].g.state(self.args[0]['ledger'])['allocations'].items():
            self.assertEqual(self.kw['post'].g.state(result['ledger'])['allocations'][key],value)
    def test_old_history_ledger_and_physical_never_change(self):
        for mutation in ('ledger','history','physical','extraPair','missingPair'):
            a=self.changed()
            if mutation=='ledger':
                value=json.loads(a[2]['data']['state.json']);next(iter(value['allocations'].values()))['principal']='foreign';a[2]['data']['state.json']=self.m.canonical(value)
            elif mutation=='history':a[3]['records'][0]['record']['readback']['hard']=2**64-1
            elif mutation=='physical':a[4][0]['before']['host']['retired_caps'].pop()
            elif mutation=='extraPair':a[4].append(copy.deepcopy(a[4][0]))
            else:a[4].clear()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(a)
    def test_complete_local_assembler_binds_raw_projection_and_future_outputs(self):
        m=self.m;args=self.args;pair=args[4][0]
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);root.chmod(0o700)
            def save(name,value,raw=False):
                path=root/name;data=value if raw else m.encode(value)
                path.write_bytes(data);path.chmod(0o600)
                return{'path':str(path),'sha256':m.sha(data)}
            prior_history=save('prior-history.json',args[1])
            # Raw original history is preserved, including its original whitespace.
            raw_history=(m.BASE/'sustained-mps-controlled-cycle-20261012/future-growth31-local-prepared/actual31/future-history-v2.json').read_bytes()
            Path(prior_history['path']).write_bytes(raw_history);prior_history['sha256']=m.sha(raw_history)
            binding=copy.deepcopy(pair['binding']);binding['retired_capture']=copy.deepcopy(prior_history)
            binding_pin=save('binding.json',binding)
            # Binding canonical pin is separate from the actual raw file pin.
            approval=copy.deepcopy(args[8]);approval['binding_sha256']=m.sha(m.canonical(binding).encode())
            before=save('before.json',pair['before'])
            refs={k:save(k+'.json',pair[k])for k in('ledger','physical','pods')}
            refs.update(binding=binding_pin,before=before)
            for name in('enrollments','cleanups','journals'):
                refs[name]=[save(name+str(i)+'.json',v['raw'].encode()if name=='journals'else v,raw=name=='journals')for i,v in enumerate(pair[name])]
            manifest=save('manifest.json',refs)
            nested,_=self.kw['post'].matched_stops(pair['normal_stop'],binding,args[7])
            normal={src:save(src+'-nested.json',capture['raw'].encode(),True)for src,capture in zip(('cps','cit'),nested)}
            outer={src:save(src+'-outer.json',capture['raw'].encode(),True)for src,capture in zip(('cps','cit'),pair['normal_stop'])}
            harness=save('harness.json',{'binding_raw_sha256':binding_pin['sha256'],
                'historical_journal_count':25,'historical_physical_count':20})
            dummy={'path':str(root/'unused'),'sha256':'a'*64}
            request={'version':1,'enabled':True,'phase':'restart','binding':binding_pin,'kernel_before':before,
                'kernel_receipt':dummy,'harness_receipt':harness,'ready_pods':{'cps':dummy,'cit':dummy},
                'normal_stop':normal,'prior_ledger':save('prior-ledger.json',args[0]['ledger']),
                'prior_history':prior_history,'observer_pod':dummy,'node':dummy,'recovery_inputs':{},'output':str(root)}
            request_pin=save('request.json',request)
            projection_proof={'version':1,'original':refs['pods'],'projection':refs['pods'],
                'omitted_field':'items[*].metadata.managedFields','item_count':len(pair['pods']['items']),
                'all_other_values_and_item_order_preserved':True,'normal_stop_passed':False,
                'hardware_qualification':False,'production_qualified':False}
            projection=save('projection.json',projection_proof)
            inspected=self.kw['inspector'].validate(binding,pair['before'],pair['ledger'],pair['pods'],pair['physical'],
                pair['enrollments'],pair['cleanups'],[j['raw'].encode()for j in pair['journals']])
            collection={'version':1,'state':'strict-finite-pair-stop-evidence-collected-awaiting-Root-review',
                'phase':'restart','request_sha256':request_pin['sha256'],'source_sha256':m.sha(m.collector_sources()['collect_stop.py']),
                'journal_count':27,'ledger_allocation_count':33,'historical_exception_count':1,'normal_stop_passed':False,
                'hardware_qualification':False,'production_qualified':False,'inspect_manifest':manifest,
                'history':save('future-history.json',args[3]),'inspector_stdout':save('inspect.stdout',inspected),
                'new_terminal_lifetimes':inspected['terminal_lifetimes'],'pod_list_projections':{'pods':projection,'pods-after':projection}}
            idxpath=m.BASE/'sustained-mps-controlled-cycle-20261012/future-growth31-local-prepared/index-actual.json'
            index={'version':1,'enabled':True,'baseline_index':{'path':str(idxpath),'sha256':m.sha(idxpath.read_bytes())},
                'baseline_physical':save('baseline-physical.json',args[0]['recorded_physical']),
                'binding':binding_pin,'harness_receipt':harness,'collection':save('collection.json',collection),
                'collector_request':request_pin,'normal_stop':outer,'provenance':save('provenance.json',args[7]),
                'approved_identities':save('approval.json',approval)}
            doc,raw,result=m.assemble(index)
            self.assertEqual(result['counts'],[33,27,22]);self.assertEqual(m.parse(raw),args[3])
            self.assertEqual(doc['approved_identities'],approval);self.assertFalse(result['hardware_qualification'])
            projection_proof['all_other_values_and_item_order_preserved']=False
            index['collection']=save('collection-bad.json',{**collection,'pod_list_projections':{
                'pods':save('projection-bad.json',projection_proof),'pods-after':projection}})
            with self.assertRaises(ValueError):m.assemble(index)
    def test_typed_finite_zero_charge_and_full_pod_absence_required(self):
        for mutation in ('max','charge','sameName','sameUID','seal','owner','journalRaw'):
            a=self.changed();pair=a[4][0]
            if mutation=='max':a[5]['retired_caps'][-1]['inventory_row']['hard']=2**64-1
            elif mutation=='charge':a[5]['retired_caps'][-1]['inventory_row']['used']=1
            elif mutation=='sameName':pair['pods']['items']=[{'metadata':{'namespace':pair['binding']['targets'][0]['namespace'],'name':pair['binding']['targets'][0]['name'],'uid':'replacement'}}]
            elif mutation=='sameUID':pair['pods']['items']=[{'metadata':{'uid':pair['binding']['targets'][0]['pod_uid']}}]
            elif mutation=='seal':pair['before']['host']['targets'][0]['seal_id']='wrong'
            elif mutation=='owner':pair['cleanups'][0]['metadata']['ownerReferences']=[{}]
            else:pair['journals'][0]['raw']+='\n';pair['journals'][0]['sha256']=self.m.sha(pair['journals'][0]['raw'].encode())
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(a)
    def test_owning_outer_source_stop_and_approved_identity_are_independent(self):
        for mutation in ('actor','image','request','nested','claim','approval','principal','cap','binding','handover'):
            a=self.changed()
            if mutation in ('actor','image','request','nested','claim'):
                capture=a[4][0]['normal_stop'][0];outer=json.loads(capture['raw'])
                if mutation=='actor':outer['actor']='foreign'
                elif mutation=='image':outer['installed_source_image']='foreign'
                elif mutation=='request':outer['root_request_sha256']='e'*64
                elif mutation=='nested':outer['normal_source_receipt']['workspace']['state']='running'
                else:outer['normal_stop_hardware_passed']=True
                capture['raw']=self.m.canonical(outer)+'\n';capture['sha256']=self.m.sha(capture['raw'].encode())
            elif mutation=='approval':a[8]['enabled']=False
            elif mutation=='binding':a[8]['binding_sha256']='e'*64
            elif mutation=='handover':a[8]['sources']['cit']['handover_provenance']=None
            else:a[8]['sources']['cit']['identity'][mutation]='foreign'if mutation=='principal'else 10240
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.validate(a)

if __name__=='__main__':unittest.main()
