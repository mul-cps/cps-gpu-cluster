"""Pure offline tests against the exact sealed helper and captured a715 frame.

Captured observations are fixtures, never current live authority. No API call
or credential transfer occurs; test output contains only bounded assertions.
"""
import base64,copy,hashlib,importlib.util,json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
O=Path('/home/bjoern/.local/state/cps-full-project-20261013/native-kai-node-epoch-handover-preparation-20261014')

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


class AdapterTests(unittest.TestCase):
    def setUp(self):
        capture=module('node_handover_capture',O/'capture.py')
        self.r=capture.r
        self.h=module('node_sealed_helper',Path(capture.h.__file__))
        self.a=module('node_sealed_adapter',HERE.parent/'handover_adapter.py')
        self.code=json.loads((O/'node-code-current.json').read_text())
        self.base=json.loads((O/'fresh-preflight.json').read_text())
        obs=json.loads((O/'fresh-observations.json').read_text())
        self.capture_input=json.loads((O/'capture-input-preimage.json').read_text())
        self.adapter=self.a.install(self.h,self.code,self.capture_input)
        controller=copy.deepcopy(self.base['controller']);controller['spec']['replicas']=0
        self.request={'version':1,'previous_publication':self.base['publication'],
          'previous_publication_sha256':self.r.canonical_sha256(self.base['publication']),
          'policy':self.base['seed']['policy'],'qualification':self.base['seed']['qualification'],
          'reviewed_images':{'node':{'previous':self.a.OLD_IMAGE,'next':self.a.NEW_IMAGE}},
          'observations':obs,'gateway_runtime':obs['gateway_runtime'],
          'old_state':{'seed':self.base['seed'],'seed_sha256':self.r.canonical_sha256(self.base['seed']),
            'journal':self.r.parse(base64.b64decode(self.base['journal_packet']['raw'],validate=True)),
            'journal_sha256':self.r.canonical_sha256(self.r.parse(base64.b64decode(self.base['journal_packet']['raw'],validate=True))),
            'controller':controller,'journal_pvc':self.base['pvc'],
            'next_journal':{'namespace':'cps-compute','name':'cps-native-delivery-journal-node-8c2c456b'},
            'next_input_secret':{'namespace':'cps-compute','name':'cps-native-delivery-input-node-8c2c456b'}}}
        self.now=max(self.h.moment(obs['source']['captured_at']),self.h.moment(obs['epoch']['captured_at']))

    def test_real_sealed_plan_node_only_keeps_policy_source_and_peer_history(self):
        result=self.h.plan_intent(self.request,now=self.now);self.adapter.validate_scope(result)
        self.assertEqual(set(result['deployment_patches']),{'node','gateway'})
        self.assertEqual(set(result['bootstrap_candidates']),{'node'})
        self.assertTrue(result['request']['policy']==self.request['policy'])
        self.assertTrue(result['request']['qualification']==self.request['qualification'])
        for c in ('gateway','hub:cps','hub:cit'):
            expected=copy.deepcopy(self.base['publication']['expected_deployments'][c])
            if c=='gateway':
                next(v for v in expected['spec']['template']['spec']['volumes'] if v['name']=='capture-seed')['secret']['secretName']=result['capture_input_candidate']['metadata']['name']
            self.assertTrue(result['projection']['expected_deployments'][c]==expected)
            self.assertTrue(result['projection']['bootstrap_maps'][c]==self.base['publication']['bootstrap_maps'][c])
        spec=result['projection']['expected_deployments']['node']['spec'];pod=spec['template']['spec'];container=pod['containers'][0]
        self.assertEqual(container['image'],self.a.NEW_IMAGE)
        self.assertNotIn('/opt/native',[m['mountPath'] for m in container['volumeMounts']])
        self.assertTrue(container['args']==self.request['observations']['deployments']['node']['spec']['template']['spec']['containers'][0]['args'])
        cfg=self.r.parse(base64.b64decode(result['capture_input_candidate']['data']['config.json'],validate=True))
        prior=self.r.parse(base64.b64decode(self.capture_input['data']['config.json'],validate=True))
        prior['node_process']['image']=self.a.NEW_IMAGE
        self.assertTrue(cfg==prior)
        for k in ('export.token','qualification.json'):
            self.assertTrue(result['capture_input_candidate']['data'][k]==self.capture_input['data'][k])
        old,key=self.h.runtime_secret(self.request['gateway_runtime'],self.request)
        new,_=self.h.runtime_secret(result['gateway_runtime_target'],self.request)
        expected=copy.deepcopy(old);expected['nativeGroupApprovals']['processes']['node']['image']=self.a.NEW_IMAGE
        self.assertTrue(new==expected)

    def test_forged_other_component_or_bundle_never_admitted(self):
        result=self.h.plan_intent(self.request,now=self.now)
        result['projection']['process_declarations']['hub:cps']['image']=self.a.NEW_IMAGE
        with self.assertRaises(ValueError):self.adapter.validate_scope(result)
        bad=copy.deepcopy(self.code);bad['data']['node_backend.py']+='\n# foreign\n'
        with self.assertRaises(ValueError):self.a.install(module('other_helper',Path(self.h.__file__)),bad,self.capture_input)

    def test_pair_and_plan_are_closed_and_independently_reproducible(self):
        q=copy.deepcopy(self.request);q['reviewed_images']['hub:cps']=q['reviewed_images']['node']
        with self.assertRaises(ValueError):self.h.plan_intent(q,now=self.now)
        result=self.h.plan_intent(self.request,now=self.now);result['deployment_patches']['node'][-1]['value']['replicas']=2
        with self.assertRaises(ValueError):self.adapter.validate_scope(result)

    def test_inverse_restores_exact_original_projection_and_never_adopts_foreign_role(self):
        forward=self.h.plan_intent(self.request,now=self.now)
        restore=self.a.RestoreHandover(self.adapter)
        inverse=restore.plan(forward,self.request['observations']['roles'],self.request['gateway_runtime'],
                             self.request['observations']['pods']['gateway'],None)
        self.assertTrue(restore.validate(inverse)==forward['request']['previous_publication'])
        self.assertTrue(inverse['gateway_runtime_target']['data']==forward['request']['gateway_runtime']['data'])
        bad=copy.deepcopy(inverse);bad['projection']['expected_deployments']['node']['spec']['replicas']=2
        with self.assertRaises(ValueError):restore.validate(bad)
        roles=copy.deepcopy(self.request['observations']['roles']);key=next(iter(roles));roles[key]['rules'].append({'verbs':['*']})
        with self.assertRaises(ValueError):restore.plan(forward,roles,self.request['gateway_runtime'],self.request['observations']['pods']['gateway'],None)
        # A failed Gateway needs no HTTP path to restore known config while
        # the actual Node absence barrier stays closed. Reads only; no API.
        from types import SimpleNamespace
        e=module('inverse_execution',HERE.parent/'handover_execution.py')
        obs=copy.deepcopy(self.request['observations']);obs['deployments']['node']['spec']['replicas']=0
        obs['deployments']['gateway']['spec']=copy.deepcopy(forward['projection']['expected_deployments']['gateway']['spec'])
        runtime=copy.deepcopy(forward['gateway_runtime_target']);matches=[]
        def get(kind,ns,name,missing=False):
            if kind=='Deployment':
                return next(v for v in obs['deployments'].values() if v['metadata']['namespace']==ns and v['metadata']['name']==name)
            if kind=='Secret':
                return self.capture_input if name==self.capture_input['metadata']['name'] else runtime if name==runtime['metadata']['name'] else None
            return None
        api=SimpleNamespace(get=get,command=lambda *a:{'items':matches})
        m=SimpleNamespace(r=self.r,controller_current=lambda a:self.request['old_state']['controller'],controller_pods=lambda *a:[])
        recovery=e.gateway_recovery_intents(api,m,self.h,forward)
        self.assertTrue(recovery['gateway'][-1]['value']==self.request['previous_publication']['expected_deployments']['gateway']['spec'])
        self.assertTrue(recovery['runtime'][-1]['value']==self.request['gateway_runtime']['data'])
        matches.append({'metadata':{'uid':'still-live-old-node'}})
        with self.assertRaises(ValueError):e.gateway_recovery_intents(api,m,self.h,forward)
        matches.clear();obs['deployments']['gateway']['spec']['replicas']=7
        with self.assertRaises(ValueError):e.gateway_recovery_intents(api,m,self.h,forward)


if __name__=='__main__':unittest.main()
