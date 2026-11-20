"""Literal CEL tests for the offline, operator-attested Pod binding candidate."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import binding_policy as binding
import cel_evaluate

NAMESPACE='cps-dynamic-admission-review'
BINDER='system:serviceaccount:kai-scheduler:kai-binder'
TRACE=Path('/tmp/kai-admission-source-trace-20261007-bdf434e5-b7058586')
RECORD={'podName':'reviewed-notebook','podUid':'11111111-2222-3333-4444-555555555555',
        'nodeName':'reviewed-gpu-node','capabilitiesName':'reviewed-job-caps',
        'capabilitiesUid':'22222222-3333-4444-5555-666666666666','capabilitiesResourceVersion':'17',
        'evarName':'reviewed-job-evar','evarUid':'33333333-4444-5555-6666-777777777777','evarResourceVersion':'18',
        'compiledWorkflowSha256':'a'*64,'registryReviewSha256':'b'*64}


def object_():
    return {'apiVersion':'v1','kind':'Binding','metadata':{'namespace':NAMESPACE,
        'name':RECORD['podName'],'uid':RECORD['podUid']},'target':{'kind':'Node','name':RECORD['nodeName']}}


def inputs(*, writer=BINDER, operation='CREATE', params=None):
    return {'request':{'namespace':NAMESPACE,'operation':operation,'userInfo':{'username':writer}},
            'object':object_(),'oldObject':None,
            'params':binding.build(writers=[BINDER],records=[RECORD])['items'][1] if params is None else params}


class BindingPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('celpy') is None:raise RuntimeError('The cached literal CEL interpreter is required')
        cls.bundle=binding.build(writers=[BINDER],records=[RECORD]);cls.policy=cls.bundle['items'][2]

    def assert_result(self, value, accepted, *, policy=None):
        report=cel_evaluate.evaluate_policy(policy or self.policy,value)
        self.assertTrue(report['compiled'],json.dumps(report))
        self.assertEqual(report['allExpressionsTrue'],accepted,json.dumps(report))
        if accepted:self.assertTrue(report['evaluated'])

    def test_separate_bundle_exact_scope_defaults_deny_and_no_bypass_conditions(self):
        crd,params,policy,vap_binding=binding.build()['items']
        self.assertEqual([crd['kind'],params['kind'],policy['kind'],vap_binding['kind']],
                         ['CustomResourceDefinition','DynamicGpuBindingPolicy','ValidatingAdmissionPolicy','ValidatingAdmissionPolicyBinding'])
        self.assertEqual(params['writers'],[]);self.assertEqual(params['records'],[])
        self.assertEqual(crd['spec']['scope'],'Namespaced')
        self.assertEqual(policy['spec']['failurePolicy'],'Fail');self.assertNotIn('matchConditions',policy['spec'])
        self.assertEqual(policy['spec']['matchConstraints']['resourceRules'],[{
            'apiGroups':[''],'apiVersions':['v1'],'resources':['pods/binding'],'operations':['CREATE'],'scope':'Namespaced'}])
        self.assertNotIn('objectSelector',policy['spec']['matchConstraints'])
        self.assertEqual(vap_binding['spec']['validationActions'],['Deny'])
        self.assertEqual(vap_binding['spec']['paramRef']['parameterNotFoundAction'],'Deny')
        self.assertTrue(all(i['metadata']['annotations']['compute.cps.unileoben.ac.at/qualification-state']=='disabled-offline-candidate'
                            for i in binding.build()['items']))
        self.assert_result(inputs(params=params),False,policy=policy)

    def test_source_exact_uid_binding_shape_and_cached_hash_receipts(self):
        binding.verify_source_trace(TRACE)
        source=(TRACE/'kai/pkg/binder/binding/binder.go').read_text()
        block=source[source.index('binding := &v1.Binding{'):source.index('b.plugins.PostBind')]
        self.assertIn('ObjectMeta: metav1.ObjectMeta{Namespace: pod.Namespace, Name: pod.Name, UID: pod.UID}',block)
        self.assertIn('Kind: "Node"',block);self.assertIn('Name: node.Name',block)
        self.assertIn('b.kubeClient.SubResource("binding").Create(ctx, pod, binding)',block)
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),binding.SOURCE_FILES['pkg/binder/binding/binder.go'])
        with tempfile.TemporaryDirectory(dir='/tmp') as root:
            target=Path(root);(target/'kai/pkg/binder/binding').mkdir(parents=True)
            (target/'source-manifest.json').write_bytes((TRACE/'source-manifest.json').read_bytes())
            (target/'kai/pkg/binder/binding/binder.go').write_text(source+'\n')
            with self.assertRaises(ValueError):binding.verify_source_trace(target)

    def test_exact_binding_with_absent_or_v1_target_api_version_is_accepted(self):
        self.assert_result(inputs(),True)
        value=inputs();value['object']['target']['apiVersion']='v1';self.assert_result(value,True)

    def test_unknown_binder_identity_request_namespace_or_operation_denied(self):
        for actor in ('system:serviceaccount:kai-scheduler:not-binder','system:serviceaccount:cps-workflows:runner','admin',BINDER+'-extra'):
            with self.subTest(actor=actor):self.assert_result(inputs(writer=actor),False)
        for operation in ('UPDATE','DELETE','CONNECT',''):
            with self.subTest(operation=operation):self.assert_result(inputs(operation=operation),False)
        for key in ('namespace','userInfo','operation'):
            value=inputs();value['request'].pop(key);self.assert_result(value,False)
        value=inputs();value['request']['namespace']='cps-workflows';self.assert_result(value,False)
        value=inputs();value['request']['userInfo'].pop('username');self.assert_result(value,False)

    def test_object_identity_target_and_missing_fields_denied(self):
        changes=[('apiVersion','v2'),('kind','Pod')]
        for key,bad in changes:
            value=inputs();value['object'][key]=bad;self.assert_result(value,False)
        for key,bad in [('namespace','cps-workflows'),('name','unknown-pod'),('uid','99999999-aaaa-bbbb-cccc-dddddddddddd')]:
            value=inputs();value['object']['metadata'][key]=bad;self.assert_result(value,False)
        for key,bad in [('kind','Pod'),('name','other-node'),('apiVersion',''),('apiVersion','v2')]:
            value=inputs();value['object']['target'][key]=bad;self.assert_result(value,False)
        for key in ('namespace','uid','name'):
            value=inputs();value['object']['metadata'].pop(key);self.assert_result(value,False)
        for key in ('kind','name'):
            value=inputs();value['object']['target'].pop(key);self.assert_result(value,False)
        for key in ('metadata','target','apiVersion','kind'):
            value=inputs();value['object'].pop(key);self.assert_result(value,False)

    def test_unregistered_or_ambiguous_pod_and_incomplete_attestation_denied(self):
        value=inputs();value['params']['records']=[];self.assert_result(value,False)
        value=inputs();value['params']['records'].append(copy.deepcopy(RECORD));self.assert_result(value,False)
        for field in binding.FIELDS:
            value=inputs();value['params']['records'][0].pop(field);self.assert_result(value,False)
        for field in ('capabilitiesResourceVersion','evarResourceVersion'):
            for bad in ('0','01','-1','not-observed',True):
                value=inputs();value['params']['records'][0][field]=bad;self.assert_result(value,False)
        for field in ('compiledWorkflowSha256','registryReviewSha256'):
            value=inputs();value['params']['records'][0][field]='not-a-hash';self.assert_result(value,False)

    def test_build_rejects_invalid_registry_structure_names_uids_rvs_hashes_and_duplicates(self):
        for field,bad in [('podName','UPPER'),('nodeName','../node'),('capabilitiesName',''),('evarName','x'*254),
                          ('podUid','not-uid'),('capabilitiesUid','ABCDEF'),('evarUid',None),
                          ('capabilitiesResourceVersion','0'),('evarResourceVersion','01'),
                          ('compiledWorkflowSha256','A'*64),('registryReviewSha256','a'*63)]:
            record=copy.deepcopy(RECORD);record[field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):binding.build(writers=[BINDER],records=[record])
        for mutate in (lambda r:r.update(extra='no'),lambda r:r.pop('nodeName'),
                       lambda r:r.update(evarUid=r['capabilitiesUid']),lambda r:r.update(evarName=r['capabilitiesName']),
                       lambda r:r.update(capabilitiesUid=r['podUid'])):
            record=copy.deepcopy(RECORD);mutate(record)
            with self.assertRaises(ValueError):binding.build(records=[record])
        with self.assertRaises(ValueError):binding.build(records=[RECORD,RECORD])
        with self.assertRaises(ValueError):binding.build(records=[RECORD]*33)
        for writers in ([BINDER,BINDER],['admin'],[BINDER]*9,{},'not-a-list',[{}]):
            with self.assertRaises(ValueError):binding.build(writers=writers)
        for namespace in ('cps-workflows','cps','UPPER','cps-dynamic-admission-'+('x'*64)):
            with self.assertRaises(ValueError):binding.build(namespace=namespace)

    def test_attestation_fields_are_prerequisites_and_not_claimed_cross_object_checks(self):
        # Binding does not contain CM contents, UID/RV or workflow bytes. An
        # operator attestation is accepted as input; the gate cannot look it up.
        value=inputs();value['params']['records'][0]['registryReviewSha256']='c'*64
        self.assert_result(value,True)
        text=' '.join(binding.LIMITATIONS)
        self.assertIn('operator-attested',text);self.assertIn('cross-object',text)
        self.assertIn('rollback',text);self.assertIn('out of scope',text)

    def test_valid_maximum_bounds_and_cross_record_generation_reuse(self):
        records=[]
        for i in range(32):
            record=copy.deepcopy(RECORD)
            record.update(podName='reviewed-pod-'+str(i),capabilitiesName='reviewed-caps-'+str(i),evarName='reviewed-evar-'+str(i))
            for field in ('podUid','capabilitiesUid','evarUid'):
                record[field]=str(uuid.uuid5(uuid.NAMESPACE_URL,'fixture://binding/'+str(i)+'/'+field))
            records.append(record)
        writers=['system:serviceaccount:kai-scheduler:binder-'+str(i) for i in range(8)]
        params=binding.build(writers=writers,records=records)['items'][1]
        self.assertEqual(len(params['records']),32);self.assertEqual(len(params['writers']),8)
        for field in ('podName','podUid','capabilitiesName','capabilitiesUid','evarName','evarUid'):
            bad=copy.deepcopy(records[:2]);bad[1][field]=bad[0][field]
            with self.subTest(field=field),self.assertRaises(ValueError):binding.build(records=bad)
        with self.assertRaises(ValueError):binding.build(writers=writers+['system:serviceaccount:kai-scheduler:binder-8'])


if __name__ == '__main__':unittest.main()
