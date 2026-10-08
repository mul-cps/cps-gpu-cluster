import copy
import base64
import io
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import patch

import handover

PERSON = '24e0a44f-4546-4b0b-a41d-c3850aef11ec'
OTHER = '5247cf15-9584-4a63-9d6e-2f7b9bdd4a8f'
STAMP = '2026-10-08T12:30:00+00:00'


def fixture():
    runtime = {'hubs': {'cps': {'url': 'https://cps.invalid', 'canonical_people': {}},
                        'cit': {'url': 'https://cit.invalid', 'canonical_people': {}}},
               'service_token_envs': {'cps': 'CPS_TOKEN'}, 'gpu': {'enabled': False}}
    proofs = []
    for hub, user in handover.ALIASES.items():
        reason = 'Explicit own-account review by Rancher u-vhm9n/cpsadmin; no email matching'
        identity = {'person_id': PERSON, 'authority': 'reviewed_account_alias',
                    'review_actor': user, 'review_reason': reason, 'reviewed_at': STAMP}
        proofs.append({'console': hub, 'username': user, 'canonical_person_id': PERSON,
                       'review_actor': user, 'review_reason': reason, 'reviewed_at': STAMP,
                       'source': handover.SOURCE, 'image': handover.IMAGE, 'schema': 6,
                       'audit': {'actor': user, 'console': hub, 'kind': 'identity-aliases',
                                 'id': user, 'outcome': 'success', 'new': identity, 'time': STAMP}})
    return runtime, proofs


class HandoverTests(unittest.TestCase):
    def test_reviewed_alias_without_email_compiles_and_preserves_other_config(self):
        runtime, proofs = fixture()
        before = copy.deepcopy(runtime)
        result = handover.compile_runtime(runtime, proofs, PERSON)
        self.assertEqual(runtime, before)
        self.assertEqual(result['hubs']['cps']['canonical_people'], {'bjoern': PERSON})
        self.assertEqual(result['hubs']['cit']['canonical_people'], {'akadmin': PERSON})
        restored = copy.deepcopy(result)
        for hub in handover.ALIASES: restored['hubs'][hub]['canonical_people'] = {}
        self.assertEqual(restored, before)

    def test_exact_existing_uuid_is_preserved_and_handover_is_idempotent(self):
        runtime, proofs = fixture()
        runtime['hubs']['cps']['canonical_people']['bjoern'] = PERSON
        result = handover.compile_runtime(runtime, proofs, PERSON)
        self.assertEqual(handover.compile_runtime(result, proofs, PERSON), result)

    def test_foreign_console_or_changed_own_alias_never_compiles(self):
        for field, value in [('console', 'foreign'), ('username', 'other-user')]:
            runtime, proofs = fixture(); proofs[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                handover.compile_runtime(runtime, proofs, PERSON)

    def test_missing_or_duplicate_source_proof_denies(self):
        runtime, proofs = fixture()
        for candidate in (proofs[:1], proofs + [proofs[0]]):
            with self.assertRaises(ValueError): handover.compile_runtime(runtime, candidate, PERSON)

    def test_alias_reassignment_and_duplicate_person_on_a_hub_deny(self):
        runtime, proofs = fixture()
        for existing in ({'bjoern': OTHER}, {'another-existing-user': PERSON}):
            runtime['hubs']['cps']['canonical_people'] = existing
            with self.assertRaises(ValueError): handover.compile_runtime(runtime, proofs, PERSON)

    def test_conflicting_console_uuid_denies(self):
        runtime, proofs = fixture(); proofs[1]['canonical_person_id'] = OTHER
        with self.assertRaises(ValueError): handover.compile_runtime(runtime, proofs, PERSON)

    def test_wrong_source_image_schema_or_missing_review_provenance_denies(self):
        for field, value in [('source', 'unknown'), ('image', 'unqualified:latest'),
                             ('schema', 5), ('review_actor', ''), ('review_reason', ''),
                             ('reviewed_at', '2026-10-08T12:30:00')]:
            runtime, proofs = fixture(); proofs[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                handover.compile_runtime(runtime, proofs, PERSON)

    def test_missing_denied_or_spoofed_api_audit_denies(self):
        for field, value in [('outcome', 'denied'), ('actor', 'u-vhm9n'),
                             ('kind', 'identities'), ('id', 'foreign')]:
            runtime, proofs = fixture(); proofs[0]['audit'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                handover.compile_runtime(runtime, proofs, PERSON)
        runtime, proofs = fixture(); del proofs[0]['audit']
        with self.assertRaises(ValueError): handover.compile_runtime(runtime, proofs, PERSON)

    def test_audit_uuid_and_review_time_must_match_exact_persisted_alias(self):
        for field, value in [('person_id', OTHER), ('reviewed_at', '2026-10-09T12:30:00+00:00'),
                             ('authority', 'verified_email')]:
            runtime, proofs = fixture(); proofs[0]['audit']['new'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                handover.compile_runtime(runtime, proofs, PERSON)

    def test_unverified_email_or_name_equality_cannot_replace_alias_proof(self):
        runtime, proofs = fixture()
        proofs[0] = {'console': 'cps', 'username': 'bjoern', 'email': 'equal@example.invalid',
                     'verified': False, 'canonical_person_id': PERSON}
        with self.assertRaises(ValueError): handover.compile_runtime(runtime, proofs, PERSON)

    def test_rollback_preserves_exact_other_fields_and_refuses_concurrent_changes(self):
        before, proofs = fixture(); after = handover.compile_runtime(before, proofs, PERSON)
        self.assertEqual(handover.rollback_runtime(before, after, copy.deepcopy(after)), before)
        concurrent = copy.deepcopy(after); concurrent['argoUi'] = {'enabled': True}
        with self.assertRaises(ValueError): handover.rollback_runtime(before, after, concurrent)

    def test_uuid_selection_reuses_legacy_reference_without_promoting_authority(self):
        inventory = {h: {'username': u, 'admin': True, 'person_ids': []}
                     for h, u in handover.ALIASES.items()}
        inventory['cps']['person_ids'] = [PERSON]
        runtime, _ = fixture()
        self.assertEqual(handover.select_person(inventory, runtime), PERSON)
        self.assertNotIn('canonical_people', inventory['cps'])

    def test_conflicting_existing_uuid_selection_denies_before_seed(self):
        inventory = {h: {'username': u, 'admin': True, 'person_ids': [PERSON if h == 'cps' else OTHER]}
                     for h, u in handover.ALIASES.items()}
        runtime, _ = fixture()
        with self.assertRaises(ValueError): handover.select_person(inventory, runtime)

    def test_no_existing_uuid_allocates_once_and_reuses_explicit_proposal(self):
        inventory = {h: {'username': u, 'admin': True, 'person_ids': []}
                     for h, u in handover.ALIASES.items()}
        runtime, _ = fixture()
        selected = handover.select_person(inventory, runtime)
        self.assertEqual(handover.select_person(inventory, runtime, proposed=selected), selected)

    def test_api_payload_never_claims_verified_email_or_spoofed_actor(self):
        payload = handover.alias_payload('cps', PERSON)
        row = payload['mappings'][0]
        self.assertEqual(row['username'], 'bjoern')
        self.assertEqual(row['person_id'], PERSON)
        self.assertTrue(row['administrator_reviewed'])
        self.assertIn('u-vhm9n/cpsadmin', row['review_reason'])
        self.assertTrue({'actor', 'review_actor', 'email', 'verified', 'reviewed_at'}.isdisjoint(row))

    def test_private_output_cannot_enter_checkout_or_replace_evidence(self):
        with self.assertRaises(ValueError):
            handover.private_write(Path(__file__).parent/'forbidden-runtime.json', {})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'runtime.json'
            handover.private_write(path, {'credential_reference': 'synthetic'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(handover.private_read(path), {'credential_reference': 'synthetic'})
            with self.assertRaises(FileExistsError): handover.private_write(path, {})
            path.chmod(0o644)
            with self.assertRaises(ValueError): handover.private_read(path)

    def test_capture_reads_actual_schema6_alias_and_audit_without_mutation(self):
        import asyncio
        import capture
        from e2x_course_hub.cps.providers import LocalCourseProvider
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'console.sqlite'
            provider = LocalCourseProvider(path, 'cps')
            asyncio.run(provider.link_identities(handover.alias_payload('cps', PERSON)['mappings'], actor='bjoern'))
            provider.db.close()
            raw_before = path.read_bytes()
            code = ('TARGET=("cps","bjoern")\nSOURCE='+repr(handover.SOURCE)+'\nIMAGE='+repr(handover.IMAGE)+'\n'
                    +capture.CONSOLE.replace('file:/data/courses.sqlite', 'file:'+str(path)))
            output = io.StringIO()
            account = io.BytesIO(json.dumps({'name':'bjoern','admin':True,'groups':['existing-group'],'roles':['user','admin']}).encode())
            with patch.dict(os.environ, {'JUPYTERHUB_API_URL':'https://hub.invalid/hub/api','JUPYTERHUB_API_TOKEN':'synthetic-test-token'}), \
                 patch('urllib.request.urlopen', return_value=account), patch('sys.stdout',output):
                exec(code, {})
            observed = json.loads(output.getvalue())
            self.assertEqual(observed['person_ids'], [PERSON])
            self.assertEqual(observed['table_counts']['reviewed_account_aliases'], 1)
            self.assertEqual(observed['email_verification_counts'], {})
            proof = observed['alias_proofs'][0]
            self.assertEqual(handover.validate_proof(proof, PERSON), 'cps')
            self.assertEqual(path.read_bytes(), raw_before)
            self.assertNotIn('email', proof)

    def test_seed_uses_minimal_native_user_token_and_revokes_after_real_api_path(self):
        import seed
        _, proofs = fixture()
        before = {'alias_proofs': []}
        after = {'alias_proofs': [proofs[0]]}
        created = {'status':201,'body':{'token':'synthetic-user-token','id':'synthetic-id','user':'bjoern','expires_at':(datetime.now(timezone.utc)+timedelta(seconds=900)).isoformat(),'scopes':['read:users:name!user=bjoern','access:services!service=cps-admin']}}
        response = {'status':200,'identity':proofs[0]['audit']['new']}
        credential = {'data':{'hub-api-token':base64.b64encode(b'synthetic-service-token').decode()}}
        with patch('capture.exec_json', side_effect=[before,after]), patch('capture.get',return_value=credential), \
             patch('capture.qualified_console',return_value={'image_id':handover.IMAGE}), \
             patch('seed.call',side_effect=[created,response,{'status':204}]) as call:
            result = seed.seed_account('cps',PERSON,expected_inventory=before)
        self.assertEqual(result['proof'],proofs[0])
        minted = call.call_args_list[0].args[2]
        self.assertEqual(minted['body']['expires_in'],900)
        self.assertEqual(minted['body']['scopes'],['read:users:name!user=bjoern','access:services!service=cps-admin'])
        posted = call.call_args_list[1].args[2]
        self.assertEqual(posted['user_token'],'synthetic-user-token')
        self.assertNotIn('admin_token',posted)
        self.assertEqual(call.call_args_list[2].args[2]['operation'],'delete')
        self.assertNotIn('synthetic-user-token',json.dumps(result))
        self.assertNotIn('synthetic-service-token',json.dumps(result))
        self.assertNotIn('synthetic-id',json.dumps(result))

    def test_seed_auth_failure_revokes_token_and_never_accepts_service_visitor_substitution(self):
        import seed
        before = {'alias_proofs': []}
        credential = {'data':{'hub-api-token':base64.b64encode(b'synthetic-service-token').decode()}}
        created = {'status':201,'body':{'token':'synthetic-user-token','id':'synthetic-id','user':'bjoern',
            'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=900)).isoformat(),
            'scopes':['read:users:name!user=bjoern','access:services!service=cps-admin']}}
        with patch('capture.exec_json',return_value=before), patch('capture.get',return_value=credential), \
             patch('capture.qualified_console',return_value={'image_id':handover.IMAGE}), \
             patch('seed.call',side_effect=[created,{'status':403},{'status':204}]) as call:
            with self.assertRaises(ValueError): seed.seed_account('cps',PERSON,expected_inventory=before)
        self.assertEqual(call.call_count,3)
        self.assertEqual(call.call_args_list[2].args[2]['operation'],'delete')

    def test_concurrent_seed_inventory_change_denies_before_any_credential_or_token_operation(self):
        import seed
        with patch('capture.exec_json',return_value={'person_ids':[OTHER]}), patch('capture.get') as get, patch('seed.call') as call:
            with patch('capture.qualified_console',return_value={'image_id':handover.IMAGE}):
                with self.assertRaises(ValueError): seed.seed_account('cps',PERSON,expected_inventory={'person_ids':[]})
        get.assert_not_called();call.assert_not_called()

    def test_broad_or_unbounded_native_token_receipt_denies_and_is_revoked(self):
        import seed
        for field,value in [('scopes',['inherit']),('expires_at',None),('user','foreign'),
                            ('expires_at',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())]:
            created={'status':201,'body':{'token':'synthetic-user-token','id':'42','user':'bjoern',
                'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=900)).isoformat(),
                'scopes':['read:users:name!user=bjoern','access:services!service=cps-admin']}}
            created['body'][field]=value
            with self.subTest(field=field), patch('capture.exec_json',return_value={'alias_proofs':[]}), \
                 patch('capture.qualified_console',return_value={'image_id':handover.IMAGE}), \
                 patch('seed.operator_call',side_effect=[created,{'status':204}]) as operator, \
                 patch('seed.call',return_value={'status':403}) as call:
                with self.assertRaises((ValueError,TypeError)):
                    seed.seed_account('cps',PERSON,expected_inventory={'alias_proofs':[]},native_operator=True)
            self.assertEqual(operator.call_args_list[-1].args,('cps','delete','42'))
            self.assertEqual(call.call_args_list[0].args[1],seed.VERIFY_REVOKED)

    def test_changed_qualified_pod_receipt_denies_before_console_post_and_revokes(self):
        import seed
        created={'status':201,'body':{'token':'synthetic-user-token','id':'42','user':'bjoern',
            'expires_at':(datetime.now(timezone.utc)+timedelta(seconds=900)).isoformat(),
            'scopes':['read:users:name!user=bjoern','access:services!service=cps-admin']}}
        with patch('capture.exec_json',return_value={'alias_proofs':[]}), \
             patch('capture.qualified_console',side_effect=[{'pod_uid':'old'},{'pod_uid':'replacement'}]), \
             patch('seed.operator_call',side_effect=[created,{'status':204}]) as operator, \
             patch('seed.call',return_value={'status':401}) as call:
            with self.assertRaises(ValueError): seed.seed_account('cps',PERSON,expected_inventory={'alias_proofs':[]},native_operator=True)
        self.assertEqual(operator.call_args_list[-1].args,('cps','delete','42'))
        self.assertEqual(call.call_args_list[0].args[1],seed.VERIFY_REVOKED)

    def test_uncertain_native_mint_is_guarded_by_exact_owned_cleanup(self):
        import seed
        with patch('capture.exec_json',return_value={'alias_proofs':[]}), \
             patch('capture.qualified_console',return_value={'image_id':handover.IMAGE}), \
             patch('seed.operator_call',side_effect=[TimeoutError('uncertain issuance'),{'status':204}]) as operator, \
             patch('seed.call') as call:
            with self.assertRaises(TimeoutError): seed.seed_account('cps',PERSON,expected_inventory={'alias_proofs':[]},native_operator=True)
        self.assertEqual(operator.call_args_list[-1].args,('cps','cleanup-owned'))
        call.assert_not_called()


if __name__ == '__main__': unittest.main()
