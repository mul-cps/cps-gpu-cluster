import copy
import unittest
import readback
from test_pair import fixture


def observed_fixture():
    _,capacity=fixture()
    pool={**capacity['pool'],'boot_id':'boot-epoch','driver_generation':'driver-epoch'}
    targets={'native-group-a':'uid-a','native-group-b':'uid-b'}
    records={};entries=[]
    for i,(name,uid) in enumerate(targets.items(),1):
        records[name]={'state':'sealed','intent':{'pod_uid':uid,'cap_mib':5120},
            'identity':{**{k:pool[k] for k in ('node_uid','gpu_uuid','boot_id','driver_generation')},
                'pod_uid':uid,'cgroup_inode':i},'readback':{'hard':5120*1024**2,'soft':5120*1024**2}}
        entries.append({'inode':i,'hard':5120*1024**2,'soft':5120*1024**2,'used':64*1024**2,
                        'offline':False,'pinned':True,'default_hierarchy':True})
    return {'records':records,'inventory':{'entries':entries},'previous':{}},targets,pool


class ReadbackTests(unittest.TestCase):
    def test_two_actual_distinct_current_driver_caps_are_required(self):
        self.assertTrue(readback.validate(*observed_fixture()))

    def test_same_cgroup_cannot_fake_two_caps(self):
        v,t,p=observed_fixture();v['records']['native-group-b']['identity']['cgroup_inode']=1
        with self.assertRaisesRegex(RuntimeError,'parents-not-distinct'):
            readback.validate(v,t,p)

    def test_stale_driver_epoch_is_denied(self):
        v,t,p=observed_fixture();v['records']['native-group-b']['identity']['driver_generation']='old'
        with self.assertRaisesRegex(RuntimeError,'epoch-differs'):
            readback.validate(v,t,p)

    def test_foreign_active_or_charged_retired_parent_is_denied(self):
        for offline,used in ((False,0),(True,1)):
            v,t,p=observed_fixture();v['inventory']['entries'].append({'inode':3,'offline':offline,'used':used})
            with self.assertRaisesRegex(RuntimeError,'charged-retired'):
                readback.validate(v,t,p)

    def test_zero_charge_terminal_entries_remain_preserved(self):
        v,t,p=observed_fixture();v['inventory']['entries'].append({'inode':3,'offline':True,'used':0})
        self.assertTrue(readback.validate(v,t,p))

    def test_restart_requires_new_uids_and_original_terminal_identity(self):
        v,t,p=observed_fixture();prior=copy.deepcopy(v);old={k:'old-'+uid for k,uid in t.items()}
        for name,uid in old.items():
            prior['records'][name]['intent']['pod_uid']=uid
            prior['records'][name]['identity']['pod_uid']=uid
            v['previous'][name]={**copy.deepcopy(prior['records'][name]),'state':'retired-inert-cap'}
        previous={'targets':old,'pool':p,'observed':prior}
        self.assertTrue(readback.validate(v,t,p,previous))
        previous['targets']=t
        with self.assertRaisesRegex(RuntimeError,'reused-original'):
            readback.validate(v,t,p,previous)

    def test_probe_argv_uses_actual_CPS_parents_without_CIT_alias(self):
        _,targets,pool=observed_fixture()
        recipes=readback.probe_argv(targets,pool)
        for name,recipe in recipes.items():
            self.assertEqual(recipe['namespace'],'jupyterhub')
            self.assertIn(targets[name],recipe['same_parent_mps'])
            self.assertNotIn('cit-',str(recipe))
            self.assertEqual(recipe['same_parent_vmm_direct'][-1],'5120')


if __name__=='__main__':unittest.main()
