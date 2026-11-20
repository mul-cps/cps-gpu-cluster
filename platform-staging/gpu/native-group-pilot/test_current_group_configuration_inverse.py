"""Offline inverse assembly checks; synthetic API UIDs are never live receipts."""
import copy
import importlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_current_group_configuration_intent as intent_tests


class CurrentInverseTest(unittest.TestCase):
    def fixtures(self):
        fixture=intent_tests.CurrentConfigurationTest();fixture.setUp()
        proposal,originals=fixture.fixtures()
        transition=fixture.helper
        forward=transition.current_group_configuration_intent(proposal,originals)
        oldsecrets=fixture.hub_secrets()
        hooks=transition.current_group_hub_hook_intent(proposal,forward,oldsecrets)
        current=copy.deepcopy(originals)
        for key in ('policy','runtime'):
            current[key]['data']=copy.deepcopy(forward[key+'.patch.json'][-1]['value'])
        for source in ('node','cps','cit'):
            cm=copy.deepcopy(forward['configurations'][source])
            cm['metadata'].update(uid='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',resourceVersion='29')
            if source=='node':current['node_config']=cm
            else:current[source]['config']=cm
        for key,obj in {'node':current['node_deployment'],'gateway':current['gateway_deployment'],
            'cps':current['cps']['deployment'],'cit':current['cit']['deployment']}.items():
            obj['spec']=copy.deepcopy(forward['deployment_patches'][key][-1]['value'])
            obj['metadata']['resourceVersion']='30'
        secrets=copy.deepcopy(oldsecrets)
        for source in ('cps','cit'):
            secrets[source]['data']=copy.deepcopy(hooks['secret_patches'][source][-1]['value'])
            secrets[source]['metadata']['resourceVersion']='31'
        authority={k:copy.deepcopy(proposal['terminal-authority-snapshot.json'][k]) for k in ('authority_maps','host_snapshot')}
        code={'apiVersion':'v1','kind':'ConfigMap','immutable':True,
            'metadata':{'name':'unchanged-code','namespace':'cps-compute',
                'uid':'ffffffff-ffff-4fff-8fff-ffffffffffff','resourceVersion':'32'},
            'data':{'node_agent.py':'synthetic reviewed code, never executed'}}
        for configs in (originals,current):
            for volume in configs['node_deployment']['spec']['template']['spec']['volumes']:
                if volume['name']=='source-controller630':volume['name']='code'
        current['node_code']=copy.deepcopy(code)
        authority['authority_maps']['items'].append(copy.deepcopy(code))
        captures={'baseline':{'authority':authority}}
        return proposal,originals,current,captures,oldsecrets,secrets

    def helper(self):
        return importlib.import_module('current_group_configuration_inverse')

    def test_exact_current_forward_and_hook_readbacks_required(self):
        args=self.fixtures();before=copy.deepcopy(args)
        result=self.helper().validate_configuration_handover(*args)
        self.assertEqual(result[0]['mode'],'qualified-group')
        self.assertEqual(result[1]['mode'],'operator-qualification')
        self.assertEqual(args,before)

    def test_code_images_mounts_secrets_and_unrelated_fields_deny(self):
        cases=(lambda a:a[2]['node_code']['data'].update({'node_agent.py':'changed'}),
            lambda a:a[2]['node_deployment']['spec']['template']['spec']['containers'][0].update(image='changed'),
            lambda a:a[2]['cps']['deployment']['spec']['template']['spec']['volumes'].append({'name':'unsafe','hostPath':{'path':'/'}}),
            lambda a:a[2]['runtime']['data'].update({'other':'changed'}),
            lambda a:a[5]['cit']['data'].update({'unrelated-auth':'changed'}),
            lambda a:a[5]['cps']['metadata'].update(uid='99999999-9999-4999-8999-999999999999'),
            lambda a:a[2]['node_config']['metadata'].update(name='wrong-config'),
            lambda a:a[2]['policy']['metadata'].update(name='foreign-policy'))
        for mutate in cases:
            with self.subTest(mutate=mutate):
                args=self.fixtures();mutate(args)
                with self.assertRaises(ValueError):self.helper().validate_configuration_handover(*args)

    def test_current_node_reference_needs_real_uid_exact_data_and_policy(self):
        args=self.fixtures();helper=self.helper();node=args[2]['node_config']
        reference={'namespace':node['metadata']['namespace'],'name':node['metadata']['name'],
            'uid':node['metadata']['uid'],'data_sha256':helper.agent.canonical_sha256(node['data']),
            'policy_hash':args[0]['acceptance.json']['policy_hash']}
        self.assertEqual(helper.configuration_reference(node,reference),reference)
        for key,value in (('uid','00000000-0000-0000-0000-000000000000'),('data_sha256','sha256:'+'a'*64),
                          ('policy_hash','sha256:'+'b'*64),('name','unrelated')):
            bad=dict(reference,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):helper.configuration_reference(node,bad)

    def prepared_extension(self):
        import current_group_historical_source as historical
        path=os.environ.get('CPS_CURRENT_NATIVE_AGENT_SOURCE')
        if not path:self.skipTest('Root safe actual source capture required for pinned code assembly')
        args=list(self.fixtures());proposal,originals,current,captures,oldsecrets,secrets=args
        originals['node_config']['data'].pop('keep')
        originals['node_config']['metadata']['namespace']=self.helper().agent.parse(originals['node_config']['data']['config.json'])['authority_namespace']
        forward=intent_tests.CurrentConfigurationTest();forward.setUp()
        expected=forward.helper.current_group_configuration_intent(proposal,originals)
        current['node_config']['data']=copy.deepcopy(expected['configurations']['node']['data'])
        current['node_config']['metadata'].update(expected['configurations']['node']['metadata'])
        for key,obj in {'node':current['node_deployment'],'gateway':current['gateway_deployment'],
            'cps':current['cps']['deployment'],'cit':current['cit']['deployment']}.items():
            obj['spec']=copy.deepcopy(expected['deployment_patches'][key][-1]['value'])
        code=captures['baseline']['authority']['authority_maps']['items'][-1]
        code['data']={'node_agent.py':Path(path).read_text(),'controller.py':'unchanged-controller630'}
        extension=Path(historical.agent.__file__).read_text()
        packet=historical.code_intent(proposal,originals,code,extension)
        current['node_code']=copy.deepcopy(packet['node-code-configmap.json'])
        current['node_code']['metadata'].update(uid='11111111-1111-4111-8111-111111111111',resourceVersion='44')
        current['node_deployment']['spec']=copy.deepcopy(packet['node-deployment.patch.json'][-1]['value'])
        return args,extension

    def test_exact_one_key_extension_forward_and_other_source_bytes_deny(self):
        args,extension=self.prepared_extension()
        self.helper().validate_configuration_handover(*args,node_agent_source=extension)
        self.assertEqual(args[2]['node_code']['data']['controller.py'],'unchanged-controller630')
        args[2]['node_code']['data']['controller.py']='changed'
        with self.assertRaises(ValueError):self.helper().validate_configuration_handover(*args,node_agent_source=extension)

    def test_inverse_assembly_preserves_archive_filters_current_policy_and_restores_full_hook_data(self):
        # Assembly-only stub replaces physical custody and replay, not evidence.
        global _EXPECTED_ARCHIVE
        args,extension=self.prepared_extension();proposal,originals,current,captures,oldsecrets,secrets=args
        helper=self.helper();oldnode=helper.agent.parse(originals['node_config']['data']['config.json'])
        history=copy.deepcopy(helper.agent.parse(current['node_config']['data']['config.json'])['terminal_history'])
        entry=copy.deepcopy(next(iter(history.values())))
        current_uid='22222222-2222-4222-8222-222222222222'
        history[current_uid]=dict(entry,policy_hash=oldnode['policy_hash'])
        newuids={'33333333-3333-4333-8333-333333333333','44444444-4444-4444-8444-444444444444'}
        for uid,size in zip(sorted(newuids),(5,20)):
            history[uid]=dict(entry,policy_hash=proposal['acceptance.json']['policy_hash'],
                profile='interactive-native-qualification-'+str(size),cap_mib=size*1024,completion_kind='cleanup')
        node=current['node_config'];reference={'namespace':node['metadata']['namespace'],
            'name':node['metadata']['name'],'uid':node['metadata']['uid'],
            'data_sha256':helper.agent.canonical_sha256(node['data']),
            'policy_hash':proposal['acceptance.json']['policy_hash']}
        _EXPECTED_ARCHIVE=copy.deepcopy(history)
        for uid in newuids:_EXPECTED_ARCHIVE[uid]['configuration_authority']=copy.deepcopy(reference)
        captures['current']={'authority':copy.deepcopy(captures['baseline']['authority']),'ledger':{'assembly':'only'}}
        # Kubernetes ConfigMapList items omit GVK even when the GET of the
        # same immutable object includes it. Full custody still matches.
        listed_node=copy.deepcopy(node)
        listed_node.pop('apiVersion');listed_node.pop('kind')
        captures['current']['authority']['authority_maps']['kind']='ConfigMapList'
        captures['current']['authority']['authority_maps']['items'].append(listed_node)
        before=copy.deepcopy((args,history))
        with patch.object(helper.custody,'validate_extension',return_value=(history,newuids)),              patch.object(helper,'replay_history',return_value=copy.deepcopy(_EXPECTED_ARCHIVE)):
            result=helper.derive_inverse(proposal,originals,current,captures,{},baseline_history_raw='assembly-only',
                original_hub_secrets=oldsecrets,current_hub_secrets=secrets,
                historical_configuration_reference=reference,node_agent_source=extension)
            for field,value in (('uid','55555555-5555-4555-8555-555555555555'),
                                ('resourceVersion','changed'),('data',{'config.json':'changed'}),
                                ('apiVersion','v2'),('kind','Secret'),('listKind','List')):
                bad=copy.deepcopy(captures)
                listed=bad['current']['authority']['authority_maps']['items'][-1]
                if field=='listKind':bad['current']['authority']['authority_maps']['kind']=value
                elif field in ('uid','resourceVersion'):listed['metadata'][field]=value
                else:listed[field]=value
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Full fresh captured historical configuration'):
                    helper.derive_inverse(proposal,originals,current,bad,{},baseline_history_raw='assembly-only',
                        original_hub_secrets=oldsecrets,current_hub_secrets=secrets,
                        historical_configuration_reference=reference,node_agent_source=extension)
        restored=result['node-config.json']['terminal_history']
        self.assertNotIn(current_uid,restored);self.assertIn(current_uid,result['full-terminal-authority-archive.json'])
        self.assertTrue(newuids<=set(restored));self.assertEqual(result['full-terminal-authority-archive.json'],_EXPECTED_ARCHIVE)
        for uid,record in oldnode['terminal_history'].items():self.assertEqual(restored[uid],record)
        for source in ('cps','cit'):
            patch_rows=result['hub_secret_patches'][source]
            self.assertEqual(patch_rows[2]['value'],secrets[source]['data'])
            self.assertEqual(patch_rows[3]['value'],oldsecrets[source]['data'])
            self.assertEqual(result['deployment_patches'][source][-1]['value'],originals[source]['deployment']['spec'])
        node_spec=result['deployment_patches']['node'][-1]['value']
        self.assertEqual(helper.custody.code_reference(node_spec),current['node_code']['metadata']['name'])
        self.assertEqual((args,history),before)
        self.assertFalse(result['enabled']);self.assertFalse(result['hardware_qualified'])



if __name__=='__main__':unittest.main()
