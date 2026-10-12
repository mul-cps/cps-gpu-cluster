"""Offline exact source/build regression; synthetic lifetimes are never live evidence."""
import ast
import copy
import json
import os
import base64
import hashlib
import tempfile
from pathlib import Path
import unittest
import prepare_current_operator20 as q
import prepare_harness as old
from test_prepare_harness import binding
from cps_compute.native_gpu_controller import CapIdentity, CapIntent, CapLimit, CapRecord
from cps_compute.native_gpu_runtime import SPEC_ANNOTATION, native_spec_sha256


class Operator20Tests(unittest.TestCase):
    def complete_fixture(self,root):
        """Replay real released custody, append two explicitly SYNTHETIC new Pods."""
        cross=Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012')
        proposal=cross/'source20-current-proposal-v1';capture=cross/'profile20-current-transition-inputs-v1'
        if not proposal.exists():self.skipTest('Root safe prospective custody replay unavailable')
        root.chmod(0o700)
        def pin(name,value,raw=None):
            path=root/name;raw=raw if raw is not None else (old.canonical(value)+'\n').encode()
            path.write_bytes(raw);path.chmod(0o600)
            return {'path':str(path),'sha256':old.sha(raw)}
        def load(name):return json.loads((proposal/name).read_bytes())
        catalog=load('policy.json');mode=load('operator-qualification.json');node=load('node-config.json')
        baseline=load('terminal-authority-snapshot.json');host=json.loads((capture/'actual-full-terminal-host-records.json').read_bytes())
        snapshot=copy.deepcopy(baseline['host_snapshot']);snapshot['directories']=copy.deepcopy(host['directories']);authority=copy.deepcopy(baseline['authority_maps'])
        ledger=copy.deepcopy(baseline['ledger']);state=json.loads(ledger['data']['state.json'])
        inventory=copy.deepcopy(host['finiteCaps']);device=next(iter(snapshot['directories']['journal']['records'].values()))['value']['identity']['cgroup_device']
        b=self.fixture_binding();pool=mode['node_pool']
        b['pool'].update({k:pool[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')})
        seals=[]
        for i,t in enumerate(b['targets']):
            approved=mode['workspaces'][t['source']+':'+t['workspace']]
            pod={'metadata':{'namespace':t['namespace'],'name':t['name'],'uid':t['pod_uid']},
                'spec':{'nodeName':pool['node'],'containers':[{'name':'notebook','image':mode['workloadImage']}]}}
            t['spec_sha256']=native_spec_sha256(pod);pod['metadata']['annotations']={SPEC_ANNOTATION:t['spec_sha256']}
            t['pod_capture']=pin('synthetic-pod-'+str(i)+'.json',pod)
            intent=CapIntent(**{k:t[k] for k in ('namespace','name','pod_uid','spec_sha256','cap_mib')},
                **{k:pool[k] for k in ('node','node_uid','gpu_uuid')},policy_hash=q.POLICY_HASH)
            relative='/kubepods.slice/kubepods-pod'+t['pod_uid'].replace('-','_')+'.slice'
            identity=CapIdentity(t['pod_uid'],t['spec_sha256'],pool['node_uid'],pool['gpu_uuid'],str(i+4)*64,
                100+i,200+i,pool['boot_id'],relative,'/sys/fs/cgroup'+relative,device,9000000+i,pool['driver_generation'])
            record=CapRecord(intent,identity,'sealed','00000000-0000-4000-8000-00000000000'+str(i+4),CapLimit(intent.cap_bytes,intent.cap_bytes))
            journal=pin('synthetic-journal-'+str(i)+'.json',record.to_dict());gate=pin('synthetic-gate-'+str(i)+'.json',record.receipt())
            seals.append({'pod_uid':t['pod_uid'],'journal':journal,'gate_receipt':gate})
            fields={'source':t['source'],'actor':'synthetic-admin','workspace':t['workspace'],
                'principal':'workspace:'+t['source']+':'+t['workspace'],'members':approved['members'],
                'ceiling':approved['ceiling'],'group_id':approved['group_id'],'attempt':'synthetic-attempt-'+str(i),
                'profile':t['profile'],'policy_hash':q.POLICY_HASH,'namespace':t['namespace'],'name':t['name'],
                **{k:pool[k] for k in ('node','node_uid','gpu_uuid')},'cap_mib':t['cap_mib']}
            claim=hashlib.sha256(old.canonical(fields).encode()).hexdigest()[:60]
            row={**fields,'version':1,'binding_id':claim,'state':'enrolled','intent':intent.to_dict()};state['allocations'][claim]=row
            enrollment={k:v for k,v in row.items() if k not in ('state','group_id','ceiling')}
            cm={'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{'namespace':node['authority_namespace'],
                'name':'cps-native-enrollment-'+claim[:40],'uid':'00000000-0000-4000-8000-0000000000'+str(i+10),
                'labels':{'cps.compute/native-binding':claim}},'data':{'enrollment.json':old.canonical(enrollment)}}
            authority['items'].append(cm)
            envelope={'configmap_uid':cm['metadata']['uid'],'configmap_name':cm['metadata']['name'],
                'authority_namespace':cm['metadata']['namespace'],'enrollment':enrollment}
            for directory,value in [('enrollments',envelope),('intents',intent.to_dict()),('journal',record.to_dict())]:
                raw=(old.canonical(value)+'\n').encode()
                snapshot['directories'][directory]['records'][t['pod_uid']+'.json']={'uid':0,'mode':256,'nlink':1,
                    'rawSha256':'sha256:'+old.sha(raw),'value':value,'rawBase64':base64.b64encode(raw).decode()}
            raw=(old.canonical(record.receipt())+'\n').encode()
            host['gateReceipts'][t['pod_uid']]={'uid':0,'mode':256,'nlink':1,'value':record.receipt(),
                'rawSha256':'sha256:'+old.sha(raw),'rawBase64':base64.b64encode(raw).decode()}
            inventory['entries'].append({'cgroup_id':identity.cgroup_inode,'kernfs_id':identity.cgroup_inode,'inode':identity.cgroup_inode,
                'offline':False,'pinned':True,'default_hierarchy':True,'soft':intent.cap_bytes,'hard':intent.cap_bytes,'used':0})
        host['directories']=copy.deepcopy(snapshot['directories'])
        ledger['metadata']['resourceVersion']='synthetic-after';ledger['data']['state.json']=old.canonical(state)
        retired={'version':1,**{k:pool[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')},
            'controller_sha256':q.current.CONTROLLER_SHA256,'records':[]}
        for name,row in baseline['host_snapshot']['directories']['journal']['records'].items():
            if row['value']['state']=='retired-inert-cap':
                retired['records'].append({'pod_uid':name[:-5],'journal_sha256':'sha256:'+old.sha(old.canonical(row['value']).encode()),'record':row['value']})
        b['retired_capture']=pin('retired.json',retired)
        inv=pin('inventory.json',inventory);host['finiteCaps']=inventory;host['finiteCapsRawSha256']='sha256:'+inv['sha256']
        host['finiteCapsRawBase64']=base64.b64encode(Path(inv['path']).read_bytes()).decode()
        snapshot['observerPodUid']=b['observer_uid'];snapshot['captureSource']=pin('capture.py',None,q.capture_source([t['pod_uid'] for t in b['targets']]))
        manifest={'version':1,'state':'Root-reviewed-current-operator20-plan','binding':pin('binding.json',b),
            'policy':pin('policy.json',catalog),'native_qualification':pin('mode.json',mode),'node_config':pin('node.json',node),
            'baseline_terminal_snapshot':pin('baseline.json',baseline),'ledger_after':pin('ledger.json',ledger),
            'authority_after':pin('authority.json',authority),'sealed_targets':seals,
            'inventory_capture':{'inventory':inv,'host_records':pin('host.json',host),'host_snapshot':pin('snapshot.json',snapshot)}}
        return manifest,pin

    def test_complete_released_custody_plus_exact_two_synthetic_normal_lifetimes(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,pin=self.complete_fixture(Path(tmp));h,c,p=q.loaders()
            b,context,clear=q.validate_inputs(manifest,h,c,p)
            self.assertEqual(context['terminal_history_count'],34);self.assertEqual(context['baseline_allocation_count'],37)
            self.assertEqual(len(clear['rows']),13);self.assertFalse(context['fresh_operator20_hardware_qualified'])

    def test_missing_or_changed_custody_or_forged_active_inputs_are_rejected(self):
        for change in ('ledger-drop','authority-drop','history-drop','journal','gate','unknown-finite','retired','capture-source','protected-mode','protected-link','protected-raw','mode'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                m,pin=self.complete_fixture(Path(tmp));h,c,p=q.loaders()
                key={'ledger-drop':'ledger_after','authority-drop':'authority_after','history-drop':'node_config','mode':'native_qualification'}.get(change)
                if key:
                    value=json.loads(Path(m[key]['path']).read_bytes())
                    if change=='ledger-drop':
                        s=json.loads(value['data']['state.json']);s['allocations'].pop(next(iter(s['allocations'])));value['data']['state.json']=old.canonical(s)
                    elif change=='authority-drop':value['items'].pop()
                    elif change=='history-drop':value['terminal_history'].pop(next(iter(value['terminal_history'])))
                    else:value['enabled']=False
                    m[key]=pin('bad.json',value)
                elif change in ('journal','gate'):
                    key='journal' if change=='journal' else 'gate_receipt';value=json.loads(Path(m['sealed_targets'][0][key]['path']).read_bytes())
                    if change=='journal':value['state']='applied'
                    else:value['cap_mib']=20480
                    m['sealed_targets'][0][key]=pin('bad.json',value)
                elif change=='unknown-finite':
                    v=json.loads(Path(m['inventory_capture']['inventory']['path']).read_bytes());v['entries'][0]['used']=1
                    m['inventory_capture']['inventory']=pin('bad.json',v)
                elif change.startswith('protected-'):
                    v=json.loads(Path(m['inventory_capture']['host_snapshot']['path']).read_bytes())
                    row=v['directories']['journal']['records'][m['sealed_targets'][0]['pod_uid']+'.json']
                    if change=='protected-mode':row['mode']=0o644
                    elif change=='protected-link':row['nlink']=2
                    else:row['rawBase64']=base64.b64encode(b'{}').decode()
                    m['inventory_capture']['host_snapshot']=pin('bad.json',v)
                elif change=='capture-source':
                    v=json.loads(Path(m['inventory_capture']['host_snapshot']['path']).read_bytes());v['captureSource']=pin('bad.py',None,b'print("forged")')
                    m['inventory_capture']['host_snapshot']=pin('bad.json',v)
                else:
                    b=json.loads(Path(m['binding']['path']).read_bytes());v=json.loads(Path(b['retired_capture']['path']).read_bytes());v['records'].pop()
                    b['retired_capture']=pin('bad-retired.json',v);m['binding']=pin('bad-binding.json',b)
                with self.assertRaises((ValueError,KeyError)):q.validate_inputs(m,h,c,p)

    def fixture_binding(self):
        b=binding();b['policy_hash']=q.POLICY_HASH;b['pool']['budget_mib']=25600
        b['pool']['measured_free_bytes']=40470*1048576
        b['pool']['headroom_bytes']=1073741824
        b['targets'][1].update(cap_mib=20480,profile='interactive-native-qualification-20')
        return b

    def test_legacy_denies_twenty_new_exact_preset_accepts_without_relabelling(self):
        b=self.fixture_binding()
        with self.assertRaises(ValueError):old.validate_binding(b)
        h,c,p=q.loaders();self.assertEqual(h.validate_binding(b),b)
        self.assertEqual(h.SOURCE_PINS,old.SOURCE_PINS)
        for field,value in [('cap_mib',10240),('profile','interactive-shared-20'),('workspace','foreign')]:
            bad=copy.deepcopy(b);bad['targets'][1][field]=value
            with self.assertRaises(ValueError):h.validate_binding(bad)
        bad=copy.deepcopy(b);bad['pool']['budget_mib']=30720
        with self.assertRaises(ValueError):h.validate_binding(bad)

    def test_root_existing_twenty_elf_matches_exact_generated_source_and_build_receipt(self):
        h,c,p=q.loaders()
        root=Path('/home/bjoern/.local/state/cps-platform-completion-20261011/native20-probes-source-prepared-20261012/Root-native-import-build')
        if not root.exists():self.skipTest('Root existing controlled20 CPU build unavailable')
        build=json.loads((root/'build-receipt.json').read_bytes());raw=(root/'native-imports-20').read_bytes()
        self.assertEqual(old.sha(raw),'4db7dc727af4f8b64432d1431418851919437019675fd8302b73260f2830dcb7')
        h.validate_native_build(build,raw,old.sha(raw),root/'native-imports-20')

    def test_fixed_twenty_render_keeps_630_clear_guard_staging_and_kernel_protocol_pins(self):
        h,c,p=q.loaders();b=self.fixture_binding()
        root=Path(os.environ.get('CPS_OCT9_PROBE_ROOT','/home/bjoern/.local/state/cps-group-native-20261009/group-probes'))
        if not root.exists():self.skipTest('Exact original controlled protocol closure unavailable')
        sources={name:(root/name).read_bytes() for name in h.SOURCE_PINS}
        guard={'rows':[],'cgroup_device':9,'gpu_id':0}
        out=c.render_sources(sources,b,{'records':[]},cleared_baseline=guard)
        pre=out['run_group_acceptance.py'].decode();tree=ast.parse(pre)
        host=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='HOST_SOURCE' for t in n.targets)))
        self.assertIn(c.CONTROLLER_SHA256,pre);self.assertIn(c.CONTROLLER_SHA256,host)
        self.assertNotIn(c.LEGACY_CONTROLLER_SHA256,host)
        self.assertIn('qualification-current-controller-630d43cc',host)
        self.assertIn('Bounded complete cgroup2 absence walk required',host)
        self.assertIn('BUDGET_BYTES = 26843545600',pre)
        self.assertIn('19456',pre);self.assertIn('20736',pre)
        self.assertIn('check_vmm_staging(h,args)',out['vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py'].decode())
        mps=p.render_probes('cps5-cit20',out['run_group_acceptance.py'])
        self.assertIn(b'19456 <= held',mps['mps_probe.py'])
        self.assertIn(b'20736',mps['run_mps.py'])
        for name,raw in out.items():
            if name.endswith('.py'):compile(raw,name,'exec')

    def test_readonly_capture_changes_only_actual_target_assignment(self):
        uids=[t['pod_uid'] for t in binding()['targets']]
        raw=q.capture_source(uids);self.assertIn(repr(uids).encode(),raw)
        original=old.read_pinned(q.CAPTURE_TEMPLATE,q.current.INVENTORY_CAPTURE_SOURCE_SHA256,private=True)
        def normal(code):
            tree=ast.parse(code)
            for n in tree.body:
                if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='targets' for t in n.targets):n.value=ast.Constant('actual-uid-substitution')
            return ast.dump(tree,include_attributes=False)
        self.assertEqual(normal(raw),normal(original))
        with self.assertRaises(ValueError):q.capture_source([uids[0],uids[0]])


if __name__=='__main__':unittest.main()
