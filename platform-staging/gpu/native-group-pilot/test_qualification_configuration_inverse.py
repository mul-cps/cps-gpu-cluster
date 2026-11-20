"""CPU replay of Root-reviewed full inputs, with deliberate authority faults.

Set CPS_NATIVE_INVERSE_CPU_INPUT to the private CPU-only fixture; public CI
does not obtain production captures or execute any GPU/cluster operation.
"""
import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest


class CompleteInverseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.environ.get('CPS_NATIVE_INVERSE_CPU_INPUT')
        if not path:raise unittest.SkipTest('Full private controlled31/25/20 CPU inputs are explicitly supplied by Root')
        cls.inputs=json.loads(Path(path).read_text())
        cls.helper=importlib.import_module('qualification_configuration_inverse')

    def test_complete30_archive18_history_restores_original15_without_erasing_any_old_record(self):
        data=copy.deepcopy(self.inputs);before=copy.deepcopy(data)
        result=self.helper.derive_inverse(**data)
        old=json.loads(data['originals']['node_config']['data']['config.json'])
        desired=result['node-config.json'];actual=copy.deepcopy(desired)
        actual['terminal_history']=old['terminal_history']
        self.assertEqual(actual,old);self.assertEqual(data,before)
        self.assertFalse(result['enabled']);self.assertFalse(result['hardware_qualified']);self.assertFalse(result['live_applied'])
        self.assertEqual(len(result['full-terminal-authority-archive.json']),30)
        self.assertEqual(len(desired['terminal_history']),18)
        self.assertEqual(desired['pool']['memory_budget_mib'],15360)
        self.assertEqual(result['policy.patch.json'][-1]['value'],data['originals']['policy']['data'])
        self.assertEqual(result['runtime.patch.json'][-1]['value'],data['originals']['runtime']['data'])
        self.assertEqual(result['restored_policy_hash'],old['policy_hash'])
        oldarchive=self.helper.terminal.map_history(data['captures']['baseline']['authority'],
            data['captures']['baseline']['ledger'],old)
        self.assertEqual(result['full-terminal-authority-archive.json']['8066366f-6e7e-42ea-83b2-86a58e9c3bad'],
            oldarchive['8066366f-6e7e-42ea-83b2-86a58e9c3bad'])
        for patch in result['deployment_patches'].values():
            self.assertEqual([op['op'] for op in patch],['test','test','test','replace'])
            self.assertEqual([op['path'] for op in patch],['/metadata/uid','/metadata/resourceVersion','/spec','/spec'])

    def test_missing_changed_claim_journal_completion_charge_uid_identity_or_baseline_refuses(self):
        from cps_compute.native_gpu_control import NativeAuthorityError
        from cps_compute.native_gpu_controller import ControllerError
        for fault in ('old-ledger','new-unreleased','new-missing','journal-missing','journal-charge','cleanup','enrollment-uid',
                      'physical-charge','physical-missing','source-actor','source-members','source-profile','baseline-history',
                      'same-name-pod','new-policy-live','historical-uid','historical-hash','historical-pool','historical-policy',
                      'code-recovery','deployment-image','policy-owner','old-enrollment-raw','old-intent-raw',
                      'new-enrollment-raw','new-intent-raw','extra-protected-intent','physical-core','physical-uvm',
                      'physical-health','physical-inventory','physical-valid-wrong-source','physical-stale'):
            with self.subTest(fault=fault):
                data=copy.deepcopy(self.inputs);captures=data['captures'];current=captures['current']
                state=json.loads(current['ledger']['data']['state.json']);oldstate=json.loads(captures['baseline']['ledger']['data']['state.json'])
                added=[key for key in state['allocations'] if key not in oldstate['allocations']]
                uid=state['allocations'][added[1]]['intent']['pod_uid'];prefix=added[1][:40]
                if fault=='old-ledger':state['allocations'][next(iter(oldstate['allocations']))]['actor']='forged'
                elif fault=='new-unreleased':state['allocations'][added[1]]['state']='enrolled'
                elif fault=='new-missing':state['allocations'].pop(added[1])
                elif fault=='journal-missing':current['authority']['host_snapshot']['directories']['journal']['records'].pop(uid+'.json')
                elif fault=='journal-charge':current['history']['records'][-1]['record']['retirement']['entry']['used']=1
                elif fault in ('cleanup','enrollment-uid'):
                    cm=next(cm for cm in current['authority']['authority_maps']['items']
                        if cm['metadata']['name']==('cps-native-cleanup-' if fault=='cleanup' else 'cps-native-enrollment-')+prefix)
                    if fault=='cleanup':cm['data']['receipt.json']='{}'
                    else:cm['metadata']['uid']='99999999-9999-4999-8999-999999999999'
                elif fault=='physical-charge':current['physical']['retired_caps'][-1]['inventory_row']['used']=1
                elif fault=='physical-missing':current['physical']['retired_caps'].pop()
                elif fault.startswith('source-'):
                    identity=data['approval']['sources']['cit']['identity']
                    if fault=='source-actor':identity['actor']='someone-else'
                    elif fault=='source-members':identity['members']=identity['members'][:1]
                    else:identity['profile']='interactive-native-qualification-10'
                elif fault=='baseline-history':data['baseline_history_raw']=data['baseline_history_raw']+' '
                elif fault=='same-name-pod':
                    target=captures['binding']['targets'][1]
                    current['pods']['items'].append({'apiVersion':'v1','kind':'Pod','metadata':{
                        'uid':'99999999-9999-4999-8999-999999999999','namespace':target['namespace'],'name':target['name']}})
                elif fault=='new-policy-live':current['physical']['targets']=[{'pod_uid':uid}]
                elif fault=='historical-uid':data['historical_configuration_reference']['uid']='99999999-9999-4999-8999-999999999999'
                elif fault=='historical-hash':data['historical_configuration_reference']['data_sha256']='sha256:'+'1'*64
                elif fault=='historical-policy':data['historical_configuration_reference']['policy_hash']=json.loads(data['originals']['node_config']['data']['config.json'])['policy_hash']
                elif fault=='historical-pool':
                    cm=data['current']['node_config'];body=json.loads(cm['data']['config.json']);body['pool']['memory_budget_mib']=20480
                    cm['data']['config.json']=json.dumps(body)
                elif fault=='code-recovery':data['current']['node_code']['data']['cleared_offline_recovery.py']+='\n# changed\n'
                elif fault=='deployment-image':data['current']['node_deployment']['spec']['template']['spec']['containers'][0]['image']='forged'
                elif fault in ('old-enrollment-raw','old-intent-raw','new-enrollment-raw','new-intent-raw'):
                    name='enrollments' if 'enrollment' in fault else 'intents'
                    files=current['authority']['host_snapshot']['directories'][name]['records']
                    filename=next(iter(captures['baseline']['authority']['host_snapshot']['directories'][name]['records'])) if fault.startswith('old') else uid+'.json'
                    files[filename]['rawSha256']='sha256:'+'1'*64
                elif fault=='extra-protected-intent':
                    files=current['authority']['host_snapshot']['directories']['intents']['records']
                    files['99999999-9999-4999-8999-999999999999.json']=copy.deepcopy(next(iter(files.values())))
                elif fault in ('physical-core','physical-uvm','physical-health','physical-inventory'):
                    key={'physical-core':'core_sha256','physical-uvm':'uvm_sha256','physical-health':'health_sha256',
                        'physical-inventory':'inventory_sha256'}[fault];current['physical'][key]='changed-invalid'
                elif fault=='physical-valid-wrong-source':current['physical']['core_sha256']='1'*64
                elif fault=='physical-stale':current['physical']['observed_at_ns']=1
                else:data['current']['policy']['metadata']['uid']='99999999-9999-4999-8999-999999999999'
                current['ledger']['data']['state.json']=self.helper.agent.canonical_json(state)
                with self.assertRaises((ValueError,NativeAuthorityError,ControllerError)):self.helper.derive_inverse(**data)

    def test_patched_actual_recovery_agent_preserves_all_unmodified_definitions_and_pins(self):
        from historical_configuration_source import definitions,extend_source
        originals=self.inputs['originals'];items=self.inputs['captures']['baseline']['authority']['authority_maps']['items']
        name=self.helper.code_reference(originals['node_deployment']['spec'])
        old=next(cm for cm in items if cm['metadata']['name']==name)['data']['node_agent.py']
        new=extend_source(old,self.inputs['node_agent_source'])
        before=definitions(old);after=definitions(new)
        for name,body in before.items():
            if name not in ('validate_config','validate_authority_enrollments'):self.assertEqual(after[name],body)
        self.assertIn("'recovered-cleared-offline-cap'",after['validate_authority_enrollments'])
        with self.assertRaises(ValueError):extend_source(old+'\n',self.inputs['node_agent_source'])
        with self.assertRaises(ValueError):extend_source(old,self.inputs['node_agent_source']+'\n')

    def test_original_full_inverse_requires_zero_new_claims_and_code_request_changes_one_key(self):
        from historical_configuration_source import code_handover
        data=copy.deepcopy(self.inputs);captures=data['captures']
        captures['current']=dict(copy.deepcopy(captures['baseline']),pods={'apiVersion':'v1','kind':'PodList','metadata':{},'items':[]})
        result=self.helper.pre_start_inverse(data['originals'],data['current'],captures,
            node_agent_source=data['node_agent_source'])
        original_deployments=self.helper.deployment_objects(data['originals'])
        for key,patch in result['deployment_patches'].items():self.assertEqual(patch[-1]['value'],original_deployments[key]['spec'])
        self.assertEqual(len(result['full-terminal-authority-archive.json']),28)
        with self.assertRaises(ValueError):self.helper.pre_start_inverse(self.inputs['originals'],self.inputs['current'],
            self.inputs['captures'],node_agent_source=self.inputs['node_agent_source'])
        name=self.helper.code_reference(data['originals']['node_deployment']['spec'])
        code=copy.deepcopy(next(cm for cm in captures['baseline']['authority']['authority_maps']['items']
            if cm['metadata']['name']==name));code.setdefault('apiVersion','v1');code.setdefault('kind','ConfigMap')
        plan=code_handover(code,data['originals']['node_deployment'],data['node_agent_source'])
        changed=[key for key,value in plan['node-code-configmap.json']['data'].items() if value!=code['data'][key]]
        self.assertEqual(changed,['node_agent.py']);self.assertFalse(plan['enabled'])
        desired=plan['node-deployment.patch.json'][-1]['value'];before=copy.deepcopy(desired)
        for volume in before['template']['spec']['volumes']:
            if volume.get('name')=='code':volume['configMap']['name']=name
        self.assertEqual(before,data['originals']['node_deployment']['spec'])

    def test_actual_patched_agent_accepts_all30_terminal_or_current_released_enrollments_on_two_reads(self):
        from types import SimpleNamespace
        from importlib.util import spec_from_file_location,module_from_spec
        result=self.helper.derive_inverse(**copy.deepcopy(self.inputs))
        code=self.inputs['current']['node_code']['data']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for filename,raw in code.items():(root/filename).write_text(raw)
            spec=spec_from_file_location('actual_patched_inverse_agent',root/'node_agent.py')
            runtime=module_from_spec(spec);spec.loader.exec_module(runtime)
            (root/'state').mkdir(mode=0o700)
            models=runtime.load_models_from_snapshot();store=runtime.EnrollmentStore(root/'state',models,trusted_uid=os.getuid())
            authority=result['authority-replay.json'];host=authority['host_snapshot']
            envelopes=[row['value'] for row in host['directories']['enrollments']['records'].values()]
            store.synchronize(envelopes)
            maps={cm['metadata']['name']:copy.deepcopy(cm) for cm in authority['authority_maps']['items']}
            for cm in maps.values():cm.setdefault('apiVersion','v1');cm.setdefault('kind','ConfigMap')
            maps['cps-native-gpu-allocations']=self.inputs['captures']['current']['ledger']
            records={name[:-5]:models.CapRecord.from_dict(row['value'])
                for name,row in host['directories']['journal']['records'].items()}
            for envelope in envelopes:
                uid=envelope['enrollment']['intent']['pod_uid'];binding=envelope['enrollment']['binding_id']
                if uid in records:
                    completion=maps['cps-native-cleanup-'+binding[:40]]
                    payload=runtime.parse(completion['data']['receipt.json'])
                    store.backend.private_write(store.state/'published-cleanup'/(uid+'.json'),{
                        'enrollment_uid':envelope['configmap_uid'],'receipt_uid':completion['metadata']['uid'],'receipt':payload},store.uid,create=True)
                else:
                    cm=maps['cps-native-abort-'+binding[:40]];payload=runtime.parse(cm['data']['abort.json'])
                    epoch=models.DriverEpoch(**payload['node_epoch'])
                    store.mark_abort(uid,envelope,runtime.validate_abort(cm,envelope,maps['cps-native-gpu-allocations'],epoch,models))
            calls=[]
            def get(ns,name):calls.append((ns,name));return copy.deepcopy(maps.get(name))
            kube=SimpleNamespace(configmap=get,pod=lambda intent:None)
            journal=SimpleNamespace(read=lambda uid:records.get(uid))
            cms=[maps[e['configmap_name']] for e in envelopes]
            accepted,terminal=runtime.validate_authority_enrollments(cms,result['node-config.json'],models,store,journal,kube)
            self.assertEqual(len(accepted),30);self.assertEqual(terminal,set(result['node-config.json']['terminal_history']))
            ref=self.inputs['historical_configuration_reference']
            self.assertGreaterEqual(calls.count((ref['namespace'],ref['name'])),6)
            aborted={uid for uid,entry in result['full-terminal-authority-archive.json'].items()
                if entry['completion_kind']=='pre-gate-abort'}
            runtime.validate_active_capacity(result['node-config.json'],
                [models.CapIntent(**e['enrollment']['intent']) for e in accepted],journal,aborted)
