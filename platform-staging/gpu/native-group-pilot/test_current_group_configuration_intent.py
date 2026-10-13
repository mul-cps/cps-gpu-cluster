"""Offline full-configuration CAS preparation; no live objects or credentials."""
import base64
import copy
import importlib
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import test_current_groups_qualification as qualification_tests


class CurrentConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.helper = importlib.import_module('qualification_transition_proposal')

    def fixtures(self):
        renderer = qualification_tests.CurrentGroupQualificationTest(); renderer.setUp()
        with tempfile.TemporaryDirectory() as tmp:
            fixture = renderer.fixture(Path(tmp))
            proposal = renderer.run_proposal(fixture)
        source = proposal['current-source.json']
        def cm(name, data):
            return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
                'metadata':{'name':name,'namespace':'cps-compute',
                    'uid':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','resourceVersion':'17'},'data':data}
        def deployment(name, config):
            return {'apiVersion':'apps/v1','kind':'Deployment','metadata':{
                'name':name,'namespace':'cps-compute',
                'uid':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','resourceVersion':'18'},
                'spec':{'replicas':1,'template':{'metadata':{'annotations':{'keep':'unchanged'}},'spec':{
                    'containers':[{'name':name,'image':'reviewed@sha256:'+'a'*64,
                        'env':[{'name':'UNRELATED','value':'unchanged'}],
                        'volumeMounts':[{'name':'config','mountPath':'/current','readOnly':True}]}],
                    'volumes':[{'name':'config','configMap':{'name':config}},
                        {'name':'source-controller630','configMap':{'name':'unchanged-code'}},
                        {'name':'keep','emptyDir':{}}]}}}}
        catalog = fixture[0][0]['catalog']
        policy = cm('compute-policy', {'policy.json':json.dumps(catalog),'keep':'unchanged-policy-key'})
        runtime = dict(copy.deepcopy(source['runtime']), argoUi={'enabled':True,'reader':'unchanged'},
            hubs={'cps':{'credential':'synthetic-private-value'},'cit':{'credential':'other-synthetic-value'}},
            cpu={'runner':'unchanged'}, unrelated={'nested':[1,2,3]})
        secret = {'apiVersion':'v1','kind':'Secret','metadata':{'name':'compute-runtime',
            'namespace':'cps-compute','uid':'cccccccc-cccc-4ccc-8ccc-cccccccccccc','resourceVersion':'19'},
            'data':{'runtime.json':base64.b64encode(json.dumps(runtime).encode()).decode(),
                'unrelated-credential':'c3ludGhldGlj'}}
        node = cm('cps-native-node-current-h32', {'config.json':json.dumps(fixture[0][0]['node_config']),
            'keep':'unchanged-node-key'})
        baselines = {'policy':policy,'runtime':secret,'node_config':node,
            'node_deployment':deployment('agent',node['metadata']['name']),
            'gateway_deployment':deployment('gateway','unrelated-gateway-config')}
        for hub in ('cps','cit'):
            settings = dict(copy.deepcopy(source['hubs'][hub]), owners=['unchanged-neutral-owner'],
                trust='unchanged', unrelated={'keep':'yes'})
            config = cm('current-'+hub, {'settings.json':json.dumps(settings),'policy.json':json.dumps(catalog),
                'config.py':'unchanged-adapter-source','canonical-people.json':'unchanged-identities'})
            baselines[hub] = {'config':config,'deployment':deployment('hub',config['metadata']['name'])}
        return proposal, baselines

    def test_real_group_mode_is_rejected_by_legacy_and_accepted_only_explicitly(self):
        proposal, baselines = self.fixtures(); before = copy.deepcopy((proposal,baselines))
        with self.assertRaises((ValueError,KeyError)):
            self.helper.configuration_intent(proposal,baselines)
        result = self.helper.current_group_configuration_intent(proposal,baselines)
        self.assertFalse(result['enabled']); self.assertFalse(result['hardware_qualified']); self.assertFalse(result['live_applied'])
        old = result['full-runtime-before.json']; new = result['full-runtime-after.json']
        for key in set(old)-{'policy_hash','nativeGpuGroups','nativeGpuPilot','nativeGpuQualification'}:
            self.assertEqual(new[key],old[key])
        self.assertEqual(new['nativeGpuGroups'],{'enabled':False})
        self.assertEqual(new['nativeGpuPilot'],{'enabled':False})
        self.assertEqual(new['nativeGpuQualification'],proposal['operator-qualification.json'])
        self.assertEqual(result['runtime.patch.json'][-1]['value']['unrelated-credential'],baselines['runtime']['data']['unrelated-credential'])
        for hub,size in (('cps',5),('cit',20)):
            config = result['configurations'][hub]; settings = json.loads(config['data']['settings.json'])
            self.assertEqual(settings['profiles'],['interactive-cpu','interactive-native-qualification-'+str(size)])
            self.assertEqual(settings['groupDeployment'],{'enabled':False})
            self.assertEqual(settings['pilotDeployment'],{'enabled':False})
            self.assertEqual(settings['qualificationDeployment'],proposal['operator-qualification.json'])
            for key in ('owners','trust','unrelated'):
                self.assertEqual(settings[key],json.loads(baselines[hub]['config']['data']['settings.json'])[key])
            for key in ('config.py','canonical-people.json'):
                self.assertEqual(config['data'][key],baselines[hub]['config']['data'][key])
        for name,baseline in (('node',baselines['node_deployment']),('gateway',baselines['gateway_deployment']),
                ('cps',baselines['cps']['deployment']),('cit',baselines['cit']['deployment'])):
            patch = result['deployment_patches'][name]
            self.assertEqual([p['op'] for p in patch],['test','test','test','replace'])
            for key in ('containers',):
                self.assertEqual(patch[-1]['value']['template']['spec'][key],baseline['spec']['template']['spec'][key])
            self.assertEqual(result['inverse']['original_deployment_specs'][name],baseline['spec'])
        self.assertEqual(result['inverse']['original_runtime_data'],baselines['runtime']['data'])
        self.assertEqual((proposal,baselines),before)

    def test_raw_source_pins_remain_distinct_from_canonical_projection_hashes(self):
        proposal, baselines = self.fixtures()
        result = self.helper.current_group_configuration_intent(proposal,baselines)
        closure = result['current-source-binding.json']
        self.assertEqual(closure['source_runtime_sha256'],proposal['acceptance.json']['source_runtime_sha256'])
        self.assertEqual(closure['source_hubs_sha256'],proposal['acceptance.json']['source_hubs_sha256'])
        self.assertEqual(closure['runtime_canonical_sha256'],self.helper.digest(proposal['current-source.json']['runtime']))
        self.assertNotEqual(closure['source_runtime_sha256'],closure['runtime_canonical_sha256'])

    def test_image_mount_general_fake_projection_and_incomplete_custody_deny(self):
        for fault in ('image','mount','general','fake-source','missing-custody','history','overlay','cpu-policy','controller','wrong-source-mode'):
            with self.subTest(fault=fault):
                proposal,baselines = self.fixtures()
                if fault=='image':proposal['operator-qualification.json']['workloadImage']='foreign@sha256:'+'d'*64
                elif fault=='mount':baselines['node_deployment']['spec']['template']['spec']['volumes'][0]['configMap']['name']='foreign'
                elif fault=='general':
                    runtime=json.loads(base64.b64decode(baselines['runtime']['data']['runtime.json']))
                    runtime['nativeGpuPilot']={'enabled':True}
                    baselines['runtime']['data']['runtime.json']=base64.b64encode(json.dumps(runtime).encode()).decode()
                elif fault=='fake-source':proposal['current-source.json']['hubs']['cps']['profiles']=['interactive-cpu']
                elif fault=='missing-custody':proposal['terminal-authority-snapshot.json']['authority_maps']['items'].clear()
                elif fault=='history':proposal['node-config.json']['terminal_history'].clear()
                elif fault=='overlay':proposal['hub-native-overlays.json']['cps']['credentials']='foreign'
                elif fault=='cpu-policy':proposal['policy.json']['profiles']['batch-cpu']['images']=[]
                elif fault=='controller':proposal['acceptance.json']['source_controller_sha256']='sha256:'+'d'*64
                else:proposal['acceptance.json']['source_mode']='legacy-qualification'
                with self.assertRaises((ValueError,KeyError)):
                    self.helper.current_group_configuration_intent(proposal,baselines)

    def hub_secrets(self):
        import yaml
        result={}
        for source in ('cps','cit'):
            owners="['cpsnativegroupa', 'cpsnativegroupb']" if source=='cps' else "['citnativegroupa']"
            hook=("import json\nimport inspect as _native_pull_inspect\nfrom pathlib import Path\n"
                "from cps_compute.native_hub_config import install_native_group_hub_configuration\n"
                "install_native_group_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))\n"
                "_native_released_pre = c.KubeSpawner.pre_spawn_hook\n_native_pull_owners = frozenset("+owners+")\n"
                "async def _native_private_pull_pre(spawner):\n    result = _native_released_pre(spawner)\n"
                "    if _native_pull_inspect.isawaitable(result):\n        await result\n"
                "    if spawner.user.name in _native_pull_owners:\n        spawner.image_pull_secrets = ['cps-native-image-pull']\n"
                "c.Spawner.pre_spawn_hook = c.KubeSpawner.pre_spawn_hook = _native_private_pull_pre\n")
            values={'hub':{'extraConfig':{'zz-native-group-pilot':hook,'unrelated':'unchanged-source'},
                'credential':'synthetic-only'},'singleuser':{'cpu':'unchanged'},'argo':'unchanged'}
            result[source]={'apiVersion':'v1','kind':'Secret','metadata':{'name':'hub',
                'namespace':'jupyterhub' if source=='cps' else 'cit-jhub',
                'uid':'dddddddd-dddd-4ddd-8ddd-dddddddddddd','resourceVersion':'27'},
                'data':{'values.yaml':base64.b64encode(yaml.safe_dump(values).encode()).decode(),
                    'unrelated-auth':'c3ludGhldGlj'}}
        return result

    def test_explicit_hub_installer_hook_preserves_yaml_secrets_and_private_pull_suffix(self):
        import yaml
        proposal,baselines=self.fixtures();configuration=self.helper.current_group_configuration_intent(proposal,baselines)
        secrets=self.hub_secrets();before=copy.deepcopy(secrets)
        result=self.helper.current_group_hub_hook_intent(proposal,configuration,secrets)
        self.assertFalse(result['enabled']);self.assertFalse(result['live_applied'])
        for source in ('cps','cit'):
            patch=result['secret_patches'][source]
            self.assertEqual([p['op'] for p in patch],['test','test','test','replace'])
            self.assertEqual(patch[-1]['value']['unrelated-auth'],secrets[source]['data']['unrelated-auth'])
            old=yaml.safe_load(base64.b64decode(secrets[source]['data']['values.yaml']))
            new=yaml.safe_load(base64.b64decode(patch[-1]['value']['values.yaml']))
            oldhook=old['hub']['extraConfig'].pop('zz-native-group-pilot')
            newhook=new['hub']['extraConfig'].pop('zz-native-group-pilot')
            self.assertEqual(old,new)
            self.assertEqual(oldhook.split('_native_released_pre =',1)[1],newhook.split('_native_released_pre =',1)[1])
            self.assertIn('install_native_qualification_hub_configuration',newhook)
            self.assertNotIn('install_native_group_hub_configuration',newhook)
            self.assertIn("!= {'enabled': False}",newhook)
            compile(newhook,'qualification-native-hook','exec')
            self.assertEqual(result['inverse']['original_data'][source],secrets[source]['data'])
        self.assertEqual(secrets,before)

    def test_hook_source_foreign_secret_bad_config_and_duplicate_yaml_deny(self):
        import yaml
        for fault in ('hook','foreign-secret','configuration','duplicate-yaml','missing-hook'):
            with self.subTest(fault=fault):
                proposal,baselines=self.fixtures();configuration=self.helper.current_group_configuration_intent(proposal,baselines)
                secrets=self.hub_secrets()
                if fault=='foreign-secret':secrets['cit']['metadata']['namespace']='foreign'
                elif fault=='configuration':
                    data=configuration['configurations']['cps']['data'];settings=json.loads(data['settings.json'])
                    settings['groupDeployment']={'enabled':True};data['settings.json']=json.dumps(settings)
                else:
                    values=yaml.safe_load(base64.b64decode(secrets['cps']['data']['values.yaml']))
                    if fault=='hook':values['hub']['extraConfig']['zz-native-group-pilot']+='print("foreign")\n'
                    elif fault=='missing-hook':del values['hub']['extraConfig']['zz-native-group-pilot']
                    raw=yaml.safe_dump(values)
                    if fault=='duplicate-yaml':raw+='hub: {}\n'
                    secrets['cps']['data']['values.yaml']=base64.b64encode(raw.encode()).decode()
                with self.assertRaises((ValueError,KeyError)):
                    self.helper.current_group_hub_hook_intent(proposal,configuration,secrets)

    def test_hook_rejects_active_modes_before_install_and_filters_only_false_modes(self):
        import yaml
        proposal,baselines=self.fixtures();configuration=self.helper.current_group_configuration_intent(proposal,baselines)
        result=self.helper.current_group_hub_hook_intent(proposal,configuration,self.hub_secrets())
        values=yaml.safe_load(base64.b64decode(result['secret_patches']['cps'][-1]['value']['values.yaml']))
        hook=values['hub']['extraConfig']['zz-native-group-pilot']
        original=json.loads(configuration['configurations']['cps']['data']['settings.json'])
        for active in (None,'groupDeployment','pilotDeployment'):
            with self.subTest(active=active):
                settings=copy.deepcopy(original)
                if active:settings[active]={'enabled':True}
                calls=[]
                c=SimpleNamespace(KubeSpawner=SimpleNamespace(pre_spawn_hook=lambda spawner:None),Spawner=SimpleNamespace())
                def install(config,plain):calls.append(copy.deepcopy(plain))
                with patch('pathlib.Path.read_text',return_value=json.dumps(settings)),patch(
                        'cps_compute.native_hub_config.install_native_qualification_hub_configuration',side_effect=install):
                    if active:
                        with self.assertRaises(ValueError):exec(hook,{'c':c})
                    else:exec(hook,{'c':c})
                if active:self.assertEqual(calls,[])
                else:
                    expected=copy.deepcopy(settings)
                    for key in ('groupDeployment','pilotDeployment'):del expected[key]
                    self.assertEqual(calls,[expected])

    def test_full_secret_data_cas_covers_unrelated_authentication_drift(self):
        proposal,baselines=self.fixtures();configuration=self.helper.current_group_configuration_intent(proposal,baselines)
        secrets=self.hub_secrets()
        result=self.helper.current_group_hub_hook_intent(proposal,configuration,secrets)
        for source in ('cps','cit'):
            cas=result['secret_patches'][source]
            self.assertEqual(cas[2]['path'],'/data')
            self.assertEqual(cas[2]['value'],secrets[source]['data'])
            fresh=copy.deepcopy(secrets[source]);fresh['data']['unrelated-auth']='changed'
            self.assertNotEqual(cas[2]['value'],fresh['data'])


if __name__=='__main__':unittest.main()
