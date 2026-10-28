"""One canonical disabled personal profile; optional requests preserve old rows."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('personal_catalog_compiler',ROOT/'scripts/compile_compute_policy.py')
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)


class PersonalProfile(unittest.TestCase):
    def test_canonical_mujoco_profile_stays_unqualified_and_requests_are_bounded(self):
        catalog=json.loads((ROOT/'compute-policy/catalog.json').read_text())
        compiled=compiler.compile_catalog(catalog);row=compiled['profiles']['personal-mujoco-10']
        self.assertFalse(row['enabled']);self.assertEqual(row['images'],[])
        self.assertEqual((row['cpu'],row['memory'],row['maxAgeSeconds'],row['gpu']['nominalMemoryGiB']),('8','24G',28800,10))
        self.assertEqual(row['requests'],{'cpu':'2','memory':'4G'})
        self.assertEqual(row['personal'],{'alias':'gpu-mujoco-xpra','capability':'personal-native-nvidia-egl-v1'})
        baseline=copy.deepcopy(catalog);baseline['profiles'].pop('personal-mujoco-10')
        for name,old in compiler.compile_catalog(baseline)['profiles'].items():
            self.assertEqual(compiled['profiles'][name],old)
        bad=copy.deepcopy(catalog);bad['profiles']['personal-mujoco-10']['requests']['memory']='25G'
        with self.assertRaises(ValueError):compiler.compile_catalog(bad)
        bad=copy.deepcopy(catalog);bad['profiles']['personal-mujoco-10']['enabled']=True
        with self.assertRaises(ValueError):compiler.compile_catalog(bad)
        generated=json.loads((ROOT/'compute-policy/generated/policy.json').read_text())
        self.assertEqual(generated,compiled)
