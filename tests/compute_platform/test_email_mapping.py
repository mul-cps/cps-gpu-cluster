import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('mapping',Path(__file__).resolve().parents[2]/'scripts/compute-platform/link-identity-emails.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class EmailMapping(unittest.TestCase):
    def record(self,hub,user,email,**extra):return dict(hub=hub,username=user,email=email,verified=True,reviewed=True,**extra)
    def test_cross_hub_email_links_without_changing_usernames(self):
        d=m.compile_mapping([self.record('cps','legacy-user','SomeOne@uni.example'),self.record('cit','other-user','someone@uni.example')])
        self.assertEqual(d['canonical_people']['cps']['legacy-user'],d['canonical_people']['cit']['other-user'])
        self.assertEqual(len(d['people']),1)
    def test_missing_unverified_or_unreviewed_email_fails_closed(self):
        for value in ['', 'no-email', 'a@university.example']:
            r=self.record('cps','u',value);r['verified']=False
            with self.assertRaises(ValueError):m.compile_mapping([r])
        r=self.record('cps','u','a@university.example');r['reviewed']=False
        with self.assertRaises(ValueError):m.compile_mapping([r])
    def test_duplicate_person_inside_one_hub_requires_migration(self):
        with self.assertRaises(ValueError):m.compile_mapping([self.record('cps','a','same@uni.example'),self.record('cps','b','same@uni.example')])
    def test_reviewed_email_handover_preserves_existing_person_id(self):
        old=m.compile_mapping([self.record('cps','u','old@uni.example')])['canonical_people']['cps']['u']
        new=m.compile_mapping([self.record('cps','u','new@uni.example',personId=old)])
        self.assertEqual(new['canonical_people']['cps']['u'],old)
if __name__=='__main__':unittest.main()
