"""Execute the real backup script with synthetic database/configuration tools."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'chart/files/backup.sh'
CONFIG_FILES = ('workloads.json', 'configmaps.json', 'secrets.json', 'running-images.txt')
FAKE_TOOL = '''#!/usr/bin/env python3
import hashlib, os, pathlib, shutil, sys
name=pathlib.Path(sys.argv[0]).name
with open(os.environ['CALLS'], 'a') as f: f.write(name+' '+str(sys.argv[1:])+'\\n')
if '--version' in sys.argv: print(os.environ['PG_DUMP_VERSION']); sys.exit(0)
if os.environ.get('FAIL_COMMAND')==name:
    print('fixture-secret-must-not-leak'); print('fixture-secret-must-not-leak',file=sys.stderr); sys.exit(1)
if name in ('psql','pg_dump','pg_dumpall') and os.environ['ROLE_CAPTURE_ENABLED']=='true':
    if os.environ.get('PGUSER')!='fixture_admin' or os.environ.get('PGPASSWORD')!='fixture-secret-must-not-leak': sys.exit(2)
if name=='psql': print('t' if os.environ.get('SUPERUSER','true')=='true' else 'f')
elif name in ('pg_dump','pg_dumpall'):
    filename=next(x.split('=',1)[1] for x in sys.argv if x.startswith('--file='))
    pathlib.Path(filename).write_bytes(b'PGDMPfixture' if name=='pg_dump' else b"CREATE ROLE fixture PASSWORD 'fixture-secret-must-not-leak';\\n")
    pathlib.Path(filename).chmod(0o644)
elif name=='cp': shutil.copyfile(sys.argv[-2],sys.argv[-1])
elif name=='sha256sum': print(hashlib.sha256(pathlib.Path(sys.argv[-1]).read_bytes()).hexdigest()+'  '+sys.argv[-1])
'''


class RoleCapture(unittest.TestCase):
    def run_backup(self, root, *, complete=True, fail='', superuser=True, missing='', hub_known=True, snapshot_known=True, version='pg_dump (PostgreSQL) 15.17'):
        backups=root/'backups'; backups.mkdir()
        old=backups/'previous-complete'; old.mkdir(); (old/'retained').write_bytes(b'preserve me')
        config=root/'configuration'; config.mkdir()
        for name in CONFIG_FILES: (config/name).write_bytes(b'protected synthetic configuration')
        if missing: (config/missing).unlink()
        tools=root/'bin'; tools.mkdir()
        for name in ('pg_dump','pg_dumpall','pg_restore','psql','cp','sha256sum'):
            path=tools/name; path.write_text(FAKE_TOOL); path.chmod(0o700)
        env={**os.environ, 'PATH':str(tools)+os.pathsep+os.environ['PATH'],
             'CALLS':str(root/'calls'), 'FAIL_COMMAND':fail, 'SUPERUSER':str(superuser).lower(),
             'PG_DUMP_VERSION':version,
             'BACKUP_DIRECTORY':str(backups), 'BACKUP_OWNER':'cps',
             'BACKUP_IMAGE':'docker.io/library/postgres@sha256:'+'a'*64,
             'ROLE_CAPTURE_ENABLED':str(complete).lower(), 'ROLE_CAPTURE_PGUSER':'fixture_admin',
             'ROLE_CAPTURE_PGPASSWORD':'fixture-secret-must-not-leak',
             'PROTECTED_CONFIGURATION_DIRECTORY':str(config),
             'BACKUP_CONFIGURATION_SECRET_REF':'fixture-snapshot',
             'BACKUP_CONFIGURATION_UID':'fixture-uid',
             'BACKUP_CONFIGURATION_RESOURCE_VERSION':'123',
             'BACKUP_CONFIGURATION_CAPTURED_AT':'2026-10-07T12:00:00Z',
             'BACKUP_HUB_IMAGE':'quay.io/jupyterhub/k8s-hub@sha256:'+'b'*64 if hub_known else '',
             'BACKUP_HUB_CHART_VERSION':'4.4.2' if hub_known else '',
             'BACKUP_HUB_APP_VERSION':'5.5.2' if hub_known else ''}
        if not snapshot_known: env['BACKUP_CONFIGURATION_UID']=''
        result=subprocess.run(['sh',str(SCRIPT)],env=env,capture_output=True,text=True)
        self.assertNotIn('fixture-secret-must-not-leak',result.stdout+result.stderr)
        self.assertEqual((old/'retained').read_bytes(),b'preserve me')
        published=[p for p in backups.iterdir() if p!=old]
        return result,published,(root/'calls').read_text() if (root/'calls').exists() else ''

    def test_complete_bundle_preserves_roles_acls_and_protected_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            result,published,calls=self.run_backup(Path(directory))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(published),1)
            manifest=json.loads((published[0]/'manifest.json').read_text())
            self.assertEqual(manifest['capture_mode'],'roles-acls-configuration')
            self.assertFalse(manifest['recovery_qualified'])
            self.assertEqual(manifest['hub'],{'image':'quay.io/jupyterhub/k8s-hub@sha256:'+'b'*64,'chart_version':'4.4.2','app_version':'5.5.2'})
            self.assertEqual(manifest['configuration_snapshot'],{
                'source':'operator-supplied-secret-snapshot','observed_live':False,
                'secret_ref':'fixture-snapshot','uid':'fixture-uid','resource_version':'123',
                'captured_at':'2026-10-07T12:00:00Z'})
            expected={'hub.pgdump','roles.sql',*CONFIG_FILES}
            self.assertEqual(set(manifest['sha256']),expected)
            self.assertEqual({p.name for p in published[0].iterdir()},expected|{'manifest.json'})
            self.assertEqual(stat.S_IMODE(published[0].stat().st_mode),0o700)
            for name in expected|{'manifest.json'}:
                path=published[0]/name
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
                if name!='manifest.json':
                    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertEqual(checksum,manifest['sha256'][name])
                    self.assertNotIn(checksum,result.stdout+result.stderr)
            self.assertIn('--roles-only',calls)
            self.assertIn('--create',calls)
            self.assertNotIn('--no-owner',calls); self.assertNotIn('--no-acl',calls)

    def test_failures_publish_no_bundle_or_receipt_and_preserve_old_backup(self):
        for command in ('psql','pg_dumpall','pg_dump','pg_restore','cp','sha256sum'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as directory:
                result,published,calls=self.run_backup(Path(directory),fail=command)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(published,[])
                self.assertIn(command+' ',calls)

    def test_missing_configuration_files_or_declared_metadata_publish_nothing(self):
        for name in CONFIG_FILES:
            with self.subTest(missing=name), tempfile.TemporaryDirectory() as directory:
                result,published,calls=self.run_backup(Path(directory),missing=name)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(published,[])
                self.assertIn('pg_dump ',calls)
        with tempfile.TemporaryDirectory() as directory:
            result,published,calls=self.run_backup(Path(directory),snapshot_known=False)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(published,[])
            self.assertEqual(calls,'')

    def test_unknown_hub_versions_remain_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            result,published,calls=self.run_backup(Path(directory),hub_known=False)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest=json.loads((published[0]/'manifest.json').read_text())
            self.assertEqual(manifest['hub'],{'image':None,'chart_version':None,'app_version':None})

    def test_postgres_distro_suffix_records_numeric_client_version_in_both_modes(self):
        for complete in (True,False):
            with self.subTest(complete=complete), tempfile.TemporaryDirectory() as directory:
                result,published,calls=self.run_backup(Path(directory),complete=complete,
                    version='pg_dump (PostgreSQL) 15.17 (Debian 15.17-1.pgdg13+1)')
                self.assertEqual(result.returncode,0,result.stderr)
                manifest=json.loads((published[0]/'manifest.json').read_text())
                self.assertEqual(manifest['client_version'],'15.17')

    def test_nonprivileged_capture_identity_fails_before_dump_or_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            result,published,calls=self.run_backup(Path(directory),superuser=False)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(published,[])
            self.assertIn('psql ',calls)
            self.assertNotIn('pg_dump ',calls); self.assertNotIn('pg_dumpall ',calls)

    def test_logical_mode_retains_explicit_limitations_and_does_not_capture_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            result,published,calls=self.run_backup(Path(directory),complete=False)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest=json.loads((published[0]/'manifest.json').read_text())
            self.assertEqual(manifest['capture_mode'],'logical')
            self.assertEqual(set(manifest['sha256']),{'hub.pgdump'})
            self.assertIn('roles',manifest['scope'])
            self.assertFalse(manifest['recovery_qualified'])
            self.assertNotIn('pg_dumpall',calls); self.assertNotIn('psql',calls)
            self.assertIn('--no-owner',calls); self.assertIn('--no-acl',calls)

    def render(self, role_capture, *, suspend=True):
        with tempfile.NamedTemporaryFile('w',suffix='.yaml') as file:
            yaml.safe_dump({'suspend':suspend,'roleCapture':role_capture},file); file.flush()
            return subprocess.run(['helm','template','hub-backup',str(ROOT/'chart'),'-f',str(ROOT/'cit-values.yaml'),'-f',file.name],capture_output=True,text=True)

    def test_role_capture_requires_separate_credentials_configuration_and_review_before_schedule(self):
        settings={'enabled':True,'privilegedCredentialSecretRef':'reviewed-admin-capture','userKey':'username','passwordKey':'password','protectedConfigurationSecretRef':'reviewed-hub-configuration',
                  'configurationSnapshot':{'uid':'fixture-uid','resourceVersion':'123','capturedAt':'2026-10-07T12:00:00Z'}}
        for key in ('privilegedCredentialSecretRef','userKey','passwordKey','protectedConfigurationSecretRef'):
            with self.subTest(missing=key):
                self.assertNotEqual(self.render({**settings,key:''}).returncode,0)
        for key in ('uid','resourceVersion','capturedAt'):
            with self.subTest(missing_snapshot_metadata=key):
                self.assertNotEqual(self.render({**settings,'configurationSnapshot':{**settings['configurationSnapshot'],key:''}}).returncode,0)
        self.assertNotEqual(self.render({**settings,'privilegedCredentialSecretRef':'jupyterhub-postgres-credentials'}).returncode,0)
        self.assertNotEqual(self.render(settings,suspend=False).returncode,0)
        for string_value in ('false','true'):
            with self.subTest(string_credential_qualification=string_value):
                self.assertNotEqual(self.render({**settings,'credentialQualified':string_value,
                    'qualificationEvidence':'private/operator-reviewed-receipt'},suspend=False).returncode,0)
        self.assertNotEqual(self.render({**settings,'credentialQualified':True},suspend=False).returncode,0)
        self.assertEqual(self.render({**settings,'credentialQualified':True,'qualificationEvidence':'private/operator-reviewed-receipt'},suspend=False).returncode,0)
        result=self.render(settings)
        self.assertEqual(result.returncode,0,result.stderr)
        docs=[d for d in yaml.safe_load_all(result.stdout) if d]
        self.assertFalse(any(d['kind'] in ('Role','ClusterRole','RoleBinding','ClusterRoleBinding','ServiceAccount') for d in docs))
        pod=next(d for d in docs if d['kind']=='CronJob')['spec']['jobTemplate']['spec']['template']['spec']
        self.assertIs(pod['automountServiceAccountToken'],False)
        env={e['name']:e for e in pod['containers'][0]['env']}
        for key in ('ROLE_CAPTURE_PGUSER','ROLE_CAPTURE_PGPASSWORD'):
            self.assertEqual(env[key]['valueFrom']['secretKeyRef']['name'],'reviewed-admin-capture')
        config=next(v for v in pod['volumes'] if v['name']=='protected-configuration')
        self.assertEqual(config['secret']['secretName'],'reviewed-hub-configuration')
        mount=next(v for v in pod['containers'][0]['volumeMounts'] if v['name']=='protected-configuration')
        self.assertIs(mount['readOnly'],True)


if __name__=='__main__': unittest.main()
