import importlib.util
from pathlib import Path
import unittest
SCRIPT=Path(__file__).resolve().parents[2]/'scripts/compute-platform/link-identity-subjects.py'
spec=importlib.util.spec_from_file_location('subject_mapping',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SubjectMapping(unittest.TestCase):
    def record(self,hub='cps',username='bjoern',subject='OpaqueSubject',**extra):
        return dict(hub=hub,username=username,issuer=m.TRUSTED_ISSUER,subject=subject,upstreamVerified=True,reviewed=True,**extra)
    def test_same_subject_links_distinct_existing_names(self):
        d=m.compile_mapping([self.record(),self.record('cit','akadmin')]);self.assertEqual(d['canonical_people']['cps']['bjoern'],d['canonical_people']['cit']['akadmin']);self.assertEqual(len(d['people']),1)
    def test_email_and_display_name_never_link_people(self):
        d=m.compile_mapping([self.record(subject='one',email='same@example.org'),self.record('cit','akadmin',subject='two',email='same@example.org')]);self.assertEqual(len(d['people']),2)
    def test_subject_is_case_sensitive(self):
        d=m.compile_mapping([self.record(subject='ABC'),self.record('cit','akadmin',subject='abc')]);self.assertEqual(len(d['people']),2)
    def test_unknown_issuer_and_unreviewed_records_fail(self):
        for change in ({'issuer':'https://attacker.example/realms/unileoben'},{'issuer':m.TRUSTED_ISSUER+'/'},{'upstreamVerified':False},{'reviewed':False},{'hub':'other'},{'username':''}):
            r=self.record();r.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):m.compile_mapping([r])
    def test_invalid_subjects_fail(self):
        for sub in ('',None,42,' leading','trailing ','new\nline','x'*256):
            with self.subTest(sub=sub),self.assertRaises(ValueError):m.compile_mapping([self.record(subject=sub)])
    def test_duplicate_hub_alias_or_person_requires_migration(self):
        for records in ([self.record(),self.record(subject='other')],[self.record(),self.record(username='other')]):
            with self.assertRaises(ValueError):m.compile_mapping(records)
    def test_existing_person_id_can_be_preserved(self):
        person='be0f469d-f691-5143-b3f8-7c670e94dd0a';d=m.compile_mapping([self.record(personId=person),self.record('cit','akadmin',personId=person)]);self.assertEqual(d['canonical_people']['cps']['bjoern'],person)
    def test_conflicting_person_ids_or_subjects_fail(self):
        records=[self.record(personId='be0f469d-f691-5143-b3f8-7c670e94dd0a'),self.record('cit','akadmin',personId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')]
        with self.assertRaises(ValueError):m.compile_mapping(records)
        records[1]['personId']=records[0]['personId'];records[1]['subject']='different'
        with self.assertRaises(ValueError):m.compile_mapping(records)
    def test_empty_inventory_never_activates(self):
        with self.assertRaises(ValueError):m.compile_mapping([])
