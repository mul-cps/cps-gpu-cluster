"""Evaluate generated admission CEL, not a Python mirror of the predicates.

Run with the documented cached cel-python interpreter on PYTHONPATH. These
offline cases do not qualify API-server typing, RBAC authorizer or propagation.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scheduler/qualification/dynamic-admission'))
import cel_evaluate as engine
import native_group_approval_renderer as r
import native_group_approval_delivery_runtime as runtime
from test_native_group_approval_rollover import installed_fixture


class DeliveryAdmissionTests(unittest.TestCase):
    def setUp(self):
        initial,prior,old,kwargs,self.roles=installed_fixture()
        seed={'previous_publication':prior,'previous_publication_sha256':r.canonical_sha256(prior)}
        self.objects=runtime.render(seed,image='ghcr.io/example/delivery@sha256:'+'a'*64,
            config_secret='reviewed-input',journal_pvc='reviewed-journal',context='reviewed-context')
        self.policy=next((o for o in self.objects if o['kind']=='ValidatingAdmissionPolicy'
            and o['metadata']['name'].endswith('-role-update')),None)
        self.assertIsNotNone(self.policy,'Bounded Role update admission policy required with escalation privilege')
        self.publication=r.revision_projection_intent(**kwargs)
        self.intent=r.revision_access_intent(projection=self.publication,previous_publication=prior,
            roles=self.roles,**{key:old[key] for key in ('deployments','replicasets','pods')})

    def evaluate(self, old, new, *, namespace=None):
        result=engine.evaluate_policy(self.policy,{'object':new,'oldObject':old,'params':None,
            'request':{'namespace':namespace or old['metadata']['namespace'],'userInfo':{
                'username':'system:serviceaccount:cps-compute:cps-native-approval-delivery'}}})
        self.assertTrue(result['compiled'],result)
        self.assertTrue(result['evaluated'],result)
        return result['allExpressionsTrue']

    def test_named_escalation_covers_exact_seven_role_updates_without_ack_patch_authority(self):
        targets=[]
        for role in (o for o in self.objects if o['kind']=='Role'):
            for rule in role['rules']:
                if 'escalate' in rule['verbs']:
                    self.assertEqual(rule['apiGroups'],['rbac.authorization.k8s.io'])
                    self.assertEqual(rule['resources'],['roles'])
                    targets.extend(role['metadata']['namespace']+'/'+name for name in rule['resourceNames'])
                if rule['resources']==['configmaps']: self.assertNotIn('patch',rule['verbs'])
        self.assertEqual(set(targets),set(self.roles)); self.assertEqual(len(targets),7)
        # Retained target Roles include own acknowledgment PATCH that the
        # controller must not acquire directly. Named escalate covers the
        # Kubernetes Role-update anti-escalation check for these targets only.
        self.assertTrue(any(rule['verbs']==['patch'] and rule['resources']==['configmaps']
            for role in self.roles.values() for rule in role['rules']))
        for key,patch in self.intent['patches'].items():
            old=self.roles[key]; new=copy.deepcopy(old); new['rules']=patch[-1]['value']
            self.assertTrue(self.evaluate(old,new))

    def test_literal_cel_allows_only_document_and_current_controller_process_name_changes(self):
        for key,old in self.roles.items():
            new=copy.deepcopy(old); new['rules']=copy.deepcopy(self.intent['patches'][key][-1]['value'])
            namespace=old['metadata']['namespace']
            declaration=next(p for p in self.publication['process_declarations'].values() if p['namespace']==namespace)
            for rule in new['rules']:
                if rule['resources']==['pods']: rule['resourceNames']=[declaration['name']+'-76cbfb4c9b-abcde']
                if rule['resources']==['replicasets']: rule['resourceNames']=[declaration['name']+'-76cbfb4c9b']
            self.assertTrue(self.evaluate(old,new))
            # A non-GET acknowledgment rule remains byte-for-byte unchanged.
            self.assertEqual([x for x in old['rules'] if x['verbs']!=['get']],
                [x for x in new['rules'] if x['verbs']!=['get']])

    def test_literal_cel_rejects_ack_patch_changes_and_any_permission_expansion(self):
        key=next(k for k,v in self.roles.items() if any(x['verbs']==['patch'] for x in v['rules']))
        old=self.roles[key]
        mutations=(
            lambda o:next(x for x in o['rules'] if x['verbs']==['patch'])['resourceNames'].append('foreign-ack'),
            lambda o:next(x for x in o['rules'] if x['verbs']==['patch']).update(verbs=['get','patch']),
            lambda o:o['rules'].append({'apiGroups':[''],'resources':['secrets'],'resourceNames':['foreign'],'verbs':['get']}),
            lambda o:o['rules'][0].update(resources=['secrets']),
            lambda o:o['rules'][0].update(apiGroups=['foreign']),
            lambda o:o['rules'][0].update(verbs=['list']),
            lambda o:o['rules'][0].update(nonResourceURLs=[]),
            lambda o:o['rules'].reverse(),
            lambda o:o['rules'][0].update(resourceNames=['foreign-cm']),
            lambda o:next(x for x in o['rules'] if x['resources']==['pods']).update(resourceNames=['foreign-pod']),
            lambda o:next(x for x in o['rules'] if x['resources']==['replicasets']).update(resourceNames=['foreign-rs']),
            lambda o:next(x for x in o['rules'] if x['resources']==['deployments']).update(resourceNames=['foreign-deployment']),
            lambda o:o['metadata'].update(name='foreign-role'),
            lambda o:o['metadata'].update(uid='00000000-0000-4000-8000-000000009999'),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                new=copy.deepcopy(old); mutation(new)
                self.assertFalse(self.evaluate(old,new))
        self.assertFalse(self.evaluate(old,copy.deepcopy(old),namespace='foreign-namespace'))

    def test_admission_scopes_identity_and_cannot_be_updated_by_controller(self):
        condition=self.policy['spec']['matchConditions'][0]
        self.assertIn('system:serviceaccount:cps-compute:cps-native-approval-delivery',condition['expression'])
        self.assertEqual(self.policy['spec']['failurePolicy'],'Fail')
        rule=self.policy['spec']['matchConstraints']['resourceRules'][0]
        self.assertEqual(rule,{'apiGroups':['rbac.authorization.k8s.io'],'apiVersions':['v1'],
            'resources':['roles'],'operations':['UPDATE']})
        binding=next(o for o in self.objects if o['kind']=='ValidatingAdmissionPolicyBinding'
            and o['spec']['policyName']==self.policy['metadata']['name'])
        self.assertEqual(binding['spec']['validationActions'],['Deny'])
        for role in (o for o in self.objects if o['kind']=='Role'):
            for privilege in role['rules']:
                self.assertNotIn('validatingadmissionpolicies',privilege['resources'])
                self.assertNotIn('validatingadmissionpolicybindings',privilege['resources'])


if __name__=='__main__': unittest.main()
