"""Offline actual private operator wiring; no Kubernetes/network/GPU calls."""
import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent.parent
PRIVATE=Path('/home/bjoern/.local/state/cps-full-project-20261013/native-kai-node-epoch-handover-preparation-20261014')

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class Tests(unittest.TestCase):
    def setUp(self):self.cli=module('actual_node_cli',ROOT/'handover_cli.py')

    def test_default_entrypoint_is_inert_before_loading_or_any_api(self):
        p=subprocess.run(['/home/bjoern/git/cps-compute/.venv/bin/python',str(ROOT/'handover_cli.py')],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout),{'inert':True,'api_calls':False,'mutations':False})

    def test_exact_existing_activation_software_accepts_bound_actual_observers(self):
        c,m,h,r,adapter,e,old=self.cli.setup();a=old.activation()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);path.chmod(0o700)
            record=self.cli.code_manifest(m,'fixture-context');m.write(path/'operator-code.json',record)
            result=a.software('fixture-context',path)
            self.assertEqual(result['context'],'fixture-context')
            self.assertIn(str(PRIVATE/'capture.py'),record['observer_files'])
            self.assertIn(str(PRIVATE/'source_snapshot_code.py'),record['observer_files'])
            self.assertIn(str(PRIVATE/'source_reservation_code.py'),record['observer_files'])

    def test_failed_owned_probe_inspection_still_exact_uid_cleanup_and_absence(self):
        calls=[];created={'metadata':{'name':'owned','namespace':'ns','uid':'actual-create-uid'}}
        api=SimpleNamespace(get=lambda *a,**k:None,command=lambda *a:created)
        m=SimpleNamespace(require=lambda ok,text:None if ok else (_ for _ in ()).throw(ValueError(text)),
            write=lambda *a,**k:None)
        e=SimpleNamespace(readonly_probe=lambda *a:{'metadata':{'name':'owned','namespace':'ns'}},
            inspect_probe=lambda *a:(_ for _ in ()).throw(ValueError('inspection denied')),
            delete_probe=lambda api,m,p:calls.append(p['metadata']['uid']))
        self.cli.bounded=lambda m,action,stage,seconds=150:action()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'inspection denied'):self.cli.probe(api,m,{},e,Path(d))
        self.assertEqual(calls,['actual-create-uid'])

    def test_private_executable_and_observer_bytes_match_source_controlled_copies(self):
        self.assertEqual((ROOT/'handover_cli.py').read_bytes(),(PRIVATE/'execute.py').read_bytes())
        for name in ('capture.py','source_snapshot_code.py','source_reservation_code.py'):
            self.assertEqual((ROOT/'handover_observers'/name).read_bytes(),(PRIVATE/name).read_bytes())

    def test_paused_source_capture_never_calls_node_dependent_epoch_endpoint(self):
        c,m,h,r,adapter,e,old=self.cli.setup();original=m.CAPTURE_CODE;seen=[]
        m._node_original_capture=lambda api,p:seen.append(m.CAPTURE_CODE) or {'source':'fixture'}
        self.assertEqual(e.source_capture(None,m,{}),{'source':'fixture'})
        self.assertEqual(m.CAPTURE_CODE,original)
        self.assertIn("endpoint='capture'",seen[0]);self.assertNotIn("endpoint='epoch'",seen[0])

if __name__=='__main__':unittest.main()
