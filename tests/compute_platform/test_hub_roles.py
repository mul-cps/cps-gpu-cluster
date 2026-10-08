import pathlib
import unittest
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]
class HubServiceRoles(unittest.TestCase):
    def test_bootstrap_cannot_mutate_users_groups_or_servers(self):
        for source in ('cps','cit'):
            config=yaml.safe_load((ROOT/'platform-staging/hub'/f'{source}-roles.yaml').read_text())
            self.assertEqual(set(config),{'hub'})
            self.assertEqual(set(config['hub']),{'loadRoles'})
            for name,role in config['hub']['loadRoles'].items():
                self.assertFalse(set(role)&{'users','groups'})
                self.assertTrue(all(scope.startswith('read:') or scope=='list:users' for scope in role['scopes']))
                if name=='cps-workspace-kernel':self.assertEqual(role['scopes'],[])
                else:
                    self.assertEqual(role['services'],[name.removesuffix('-api')])
                    self.assertTrue(role['services'][0].startswith(source+'-'))
