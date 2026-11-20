"""Offline replay of complete captured custody; never a fresh hardware claim."""
import base64
import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import unittest
import current_group_historical_source as historical
import qualification_proposal as proposal
import qualification_transition_proposal as transition
import current_group_configuration_inverse as inverse
from test_current_group_configuration_intent import CurrentConfigurationTest


class CurrentRepeatTest(unittest.TestCase):
    def fixtures(self):
        value=os.environ.get('CPS_CURRENT_NATIVE_RESTART_CAPTURE')
        if not value:self.skipTest('Root supplies safe complete actual repeat capture')
        safe=Path(value);cross=safe.parent
        load=lambda name:json.loads((safe/name).read_bytes())
        body=json.loads((cross/'profile20-current-transition-inputs-v1/input-current-groups-to20-v1.json').read_bytes())
        body.update(catalog=load('policy.json'),node_config=load('node-config.json'),ledger=load('ledger.json'))
        code=load('node-code.json');source=code['data']['node_agent.py']
        validator,replay=historical.validation_context(source)
        host=load('host.json');snap=body['never_enrolled_evidence']['host_snapshot']
        snap.update(observedAt=host['observedAt'],directories=copy.deepcopy(host['directories']))
        for directory in snap['directories'].values():
            for row in directory['records'].values():
                raw=base64.b64decode(row.pop('rawBase64'),validate=True)
                self.assertEqual('sha256:'+hashlib.sha256(raw).hexdigest(),row['rawSha256'])
                self.assertEqual(json.loads(raw),row['value'])
        authority={'authority_maps':load('maps.json'),'host_snapshot':snap}
        body['never_enrolled_evidence'].update(authority);body['observed_at']=host['observedAt']
        body['terminal_history']=replay(authority,body['ledger'],body['node_config'])
        old=cross/'profile20-current-transition-inputs-v1'
        observation=(old/'actual-nvml-projection.json').read_bytes()
        health=(old/'actual-health-projection.json').read_bytes()
        runtime=load('native-runtime-source.json');hubs=load('source-current.json')['hubs']
        from cps_compute import native_gpu_controller as models
        runtime_raw=json.dumps(runtime).encode();hub_raw=json.dumps(hubs).encode()
        options=dict(terminal_authority=authority,now=datetime.fromisoformat(host['observedAt']),
            source_runtime_raw=runtime_raw,source_runtime_sha256=proposal.checksum(runtime_raw),
            source_hubs_raw=hub_raw,source_hubs_sha256=proposal.checksum(hub_raw),
            source_controller_raw=Path(models.__file__).read_bytes(),current_agent_source=source)
        result=proposal.render_current_approved_groups(body,observation,health,**options)
        fixture=CurrentConfigurationTest();fixture.setUp();_,baselines=fixture.fixtures()
        baselines['policy']['data']['policy.json']=json.dumps(body['catalog'])
        baselines['node_config']['data']['config.json']=json.dumps(body['node_config'])
        baselines['node_config']['metadata']['namespace']=code['metadata']['namespace']
        baselines['node_deployment']['metadata']['namespace']=code['metadata']['namespace']
        runtime_full=json.loads(base64.b64decode(baselines['runtime']['data']['runtime.json']))
        runtime_full.update(runtime)
        baselines['runtime']['data']['runtime.json']=base64.b64encode(json.dumps(runtime_full).encode()).decode()
        for hub in ('cps','cit'):
            settings=json.loads(baselines[hub]['config']['data']['settings.json']);settings.update(hubs[hub])
            baselines[hub]['config']['data'].update({'settings.json':json.dumps(settings),'policy.json':json.dumps(body['catalog'])})
        baselines['node_deployment']['spec']['template']['spec']['volumes'].append(
            {'name':'code','configMap':{'name':code['metadata']['name']}})
        return body,options,result,baselines,code,observation,health

    def test_complete_archive_runtime_projection_and_unchanged_current_code(self):
        body,options,result,baselines,code,_,_=self.fixtures()
        before=copy.deepcopy((body,result,baselines,code))
        full=body['terminal_history'];runtime=result['node-config.json']['terminal_history']
        self.assertEqual(len(full),36);self.assertEqual(len(runtime),34)
        self.assertEqual(set(full)-set(runtime),{uid for uid,row in full.items() if row['policy_hash']==historical.QUALIFICATION_POLICY})
        self.assertEqual(result['terminal-authority-snapshot.json']['ledger'],body['ledger'])
        packet=historical.code_intent(result,baselines,code,Path(historical.agent.__file__).read_text())
        self.assertTrue(packet['retained_node_code']);self.assertEqual(packet['one_key_diff'],[])
        self.assertEqual(packet['node-code-configmap.json'],code)
        spec=packet['node-deployment.patch.json'][-1]['value']
        self.assertEqual([v for v in spec['template']['spec']['volumes'] if v['name']=='code'],
            [v for v in baselines['node_deployment']['spec']['template']['spec']['volumes'] if v['name']=='code'])
        forward=transition.current_group_configuration_intent(result,baselines,current_agent_source=code['data']['node_agent.py'])
        for key in ('argoUi','cpu','unrelated','hubs'):
            self.assertEqual(forward['full-runtime-before.json'][key],forward['full-runtime-after.json'][key])
        self.assertEqual((body,result,baselines,code),before)

    def test_unknown_source_omitted_archive_and_forged_reference_deny(self):
        body,options,result,baselines,code,observation,health=self.fixtures()
        with self.assertRaises(ValueError):
            proposal.render_current_approved_groups(body,observation,health,**dict(options,current_agent_source=code['data']['node_agent.py']+'\n'))
        for fault in ('archive','source','authority'):
            changed=copy.deepcopy(result)
            if fault=='archive':changed['terminal-authority-snapshot.json']['authority_maps']['items'].clear()
            elif fault=='source':changed['acceptance.json']['source_node_agent_sha256']='sha256:'+'a'*64
            else:
                old=changed['terminal-authority-snapshot.json']['previous_node']['terminal_history']
                next(row for row in old.values() if 'configuration_authority' in row)['configuration_authority']['uid']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
            with self.assertRaises(ValueError):
                transition.current_group_configuration_intent(changed,baselines,current_agent_source=code['data']['node_agent.py'])

    def test_repeat_handover_retains_exact_original_code_uid_and_data(self):
        _,options,result,originals,code,_,_=self.fixtures()
        fixture=CurrentConfigurationTest();fixture.setUp();secrets=fixture.hub_secrets()
        packet=historical.code_intent(result,originals,code,Path(historical.agent.__file__).read_text())
        forward=transition.current_group_configuration_intent(result,originals,current_agent_source=code['data']['node_agent.py'])
        hooks=transition.current_group_hub_hook_intent(result,forward,secrets)
        current=copy.deepcopy(originals);current['node_code']=copy.deepcopy(code)
        for key in ('policy','runtime'):current[key]['data']=forward[key+'.patch.json'][-1]['value']
        current['node_config']=copy.deepcopy(forward['configurations']['node'])
        current['node_config']['metadata'].update(uid='dddddddd-dddd-4ddd-8ddd-dddddddddddd',resourceVersion='20')
        for hub in ('cps','cit'):
            current[hub]['config']=copy.deepcopy(forward['configurations'][hub])
            current[hub]['config']['metadata'].update(uid='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',resourceVersion='21')
            current[hub]['deployment']['spec']=forward['deployment_patches'][hub][-1]['value']
        current['gateway_deployment']['spec']=forward['deployment_patches']['gateway'][-1]['value']
        current['node_deployment']['spec']=packet['node-deployment.patch.json'][-1]['value']
        current_secrets=copy.deepcopy(secrets)
        for hub in ('cps','cit'):current_secrets[hub]['data']=hooks['secret_patches'][hub][-1]['value']
        captures={'baseline':{'authority':options['terminal_authority']}}
        args=(result,originals,current,captures,secrets,current_secrets)
        values=inverse.validate_configuration_handover(*args,node_agent_source=Path(historical.agent.__file__).read_text())
        self.assertEqual(values[0],json.loads(originals['node_config']['data']['config.json']))
        for fault in ('uid','data'):
            changed=copy.deepcopy(current)
            if fault=='uid':changed['node_code']['metadata']['uid']='ffffffff-ffff-4fff-8fff-ffffffffffff'
            else:changed['node_code']['data']['unrelated']='changed'
            with self.assertRaises(ValueError):
                inverse.validate_configuration_handover(result,originals,changed,captures,secrets,current_secrets,
                    node_agent_source=Path(historical.agent.__file__).read_text())

    def test_repeat_inverse_replay_preserves_prior_same_policy_configuration_refs(self):
        body,options,result,_,code,_,_=self.fixtures()
        reviewed,_=historical.validation_context(code['data']['node_agent.py'])
        replay=inverse.repeat_history_mapper(body['node_config'],result['node-config.json'],reviewed)
        history=replay(options['terminal_authority'],body['ledger'],result['node-config.json'])
        self.assertEqual(history,body['terminal_history'])
        self.assertEqual(sum('configuration_authority' in row for row in history.values()),2)
        for fault in ('epoch','policy'):
            changed=copy.deepcopy(result['node-config.json'])
            if fault=='epoch':changed['pool']['gpu_uuid']='GPU-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
            else:changed['policy_hash']='sha256:'+'a'*64
            with self.assertRaises(ValueError):replay(options['terminal_authority'],body['ledger'],changed)

    def test_synthetic_future_pair_extends_complete_archive_without_erasing_prior_refs(self):
        # These cloned future identities exist ONLY in this CPU unit fixture.
        # No file or receipt claiming actual future allocation is published.
        body,options,result,_,code,_,_=self.fixtures()
        reviewed,_=historical.validation_context(code['data']['node_agent.py'])
        replay=inverse.repeat_history_mapper(body['node_config'],result['node-config.json'],reviewed)
        authority=copy.deepcopy(options['terminal_authority']);ledger=copy.deepcopy(body['ledger'])
        rows=json.loads(ledger['data']['state.json']);added=[]
        for index,row in enumerate(list(rows['allocations'].values())):
            if row['policy_hash']!=historical.QUALIFICATION_POLICY:continue
            oldbinding=row['binding_id'];olduid=row['intent']['pod_uid']
            binding=hashlib.sha256(('synthetic-repeat-only-'+oldbinding).encode()).hexdigest()[:60]
            uid=('11111111-1111-4111-8111-111111111111' if row['source']=='cps'
                else '22222222-2222-4222-8222-222222222222')
            def clone(value):
                if isinstance(value,str):return value.replace(oldbinding,binding).replace(oldbinding[:40],binding[:40]).replace(olduid,uid).replace(olduid.replace('-','_'),uid.replace('-','_'))
                if isinstance(value,dict):return {k:clone(v) for k,v in value.items()}
                if isinstance(value,list):return [clone(v) for v in value]
                return value
            newrow=clone(row);rows['allocations'][binding]=newrow;added.append(uid)
            maps=authority['authority_maps']['items']
            oldenrollment=next(cm for cm in maps if cm['metadata']['name']=='cps-native-enrollment-'+oldbinding[:40])
            oldcleanup=next(cm for cm in maps if cm['metadata']['name']=='cps-native-cleanup-'+oldbinding[:40])
            enrollment=clone(oldenrollment);enrollment['data']['enrollment.json']=json.dumps(clone(json.loads(oldenrollment['data']['enrollment.json'])))
            enrollment['metadata']['uid']=('33333333-3333-4333-8333-333333333333' if row['source']=='cps' else '44444444-4444-4444-8444-444444444444')
            cleanup=clone(oldcleanup);receipt=clone(json.loads(oldcleanup['data']['receipt.json']))
            cleanup['metadata']['uid']=('55555555-5555-4555-8555-555555555555' if row['source']=='cps' else '66666666-6666-4666-8666-666666666666')
            directories=authority['host_snapshot']['directories']
            for name in ('enrollments','intents','journal'):
                protected=clone(directories[name]['records'][olduid+'.json'])
                if name=='enrollments':protected['value']['configmap_uid']=enrollment['metadata']['uid']
                if name=='journal':
                    record=protected['value'];receipt['retirement']['enrollment_uid']=enrollment['metadata']['uid']
                    receipt['retirement']['enrollment_sha256']=reviewed.canonical_sha256(json.loads(enrollment['data']['enrollment.json']))
                    receipt['retirement']['journal_sha256']=reviewed.canonical_sha256(record)
                protected['rawSha256']='sha256:'+hashlib.sha256((reviewed.canonical_json(protected['value'])+'\n').encode()).hexdigest()
                directories[name]['records'][uid+'.json']=protected
            cleanup['data']['receipt.json']=json.dumps(receipt);maps.extend((enrollment,cleanup))
        self.assertEqual(len(added),2)
        ledger['data']['state.json']=reviewed.canonical_json(rows)
        archive=replay(authority,ledger,result['node-config.json'])
        self.assertEqual(len(archive),38)
        self.assertTrue(all(archive[uid]==row for uid,row in body['terminal_history'].items()))
        restored=copy.deepcopy(body['node_config'])
        ref=next(row['configuration_authority'] for row in body['terminal_history'].values() if 'configuration_authority'in row)
        for uid in added:archive[uid]['configuration_authority']=copy.deepcopy(ref)
        restored['terminal_history']=historical.runtime_history(archive,restored['policy_hash'],code['data']['node_agent.py'])
        self.assertEqual(len(restored['terminal_history']),36)
        self.assertEqual(inverse.replay_history(authority,ledger,restored,reviewed),archive)
        for fault in ('missing','changed'):
            broken=copy.deepcopy(authority)
            records=broken['host_snapshot']['directories']['journal']['records']
            if fault=='missing':records.pop(added[0]+'.json')
            else:records[added[0]+'.json']['rawSha256']='sha256:'+'a'*64
            with self.assertRaises(ValueError):replay(broken,ledger,result['node-config.json'])


if __name__=='__main__':unittest.main()
