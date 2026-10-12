"""Execute the real backup script with synthetic database/configuration tools."""
import hashlib
import json
import os
from pathlib import Path
import stat
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
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
    def run_backup(self, root, *, complete=True, fail='', superuser=True, missing='', hub_known=True, snapshot_known=True, version='pg_dump (PostgreSQL) 15.17', fresh=None):
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
        if fresh is not None:
            env.update(FRESH_API_CAPTURE_ENABLED='true', PROTECTED_CONFIGURATION_DIRECTORY=str(fresh))
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

    def fresh_capture(self, root, failure=''):
        """Real TLS/API and script boundary; no Kubernetes or external networking."""
        resources={'deployments':['hub'],'statefulsets':['postgresql'], 'configmaps':['hub'], 'secrets':['hub'], 'pods':['hub-fixture','postgresql-fixture']}
        kinds={'deployments':('apps/v1','Deployment'),'statefulsets':('apps/v1','StatefulSet'), 'configmaps':('v1','ConfigMap'),'secrets':('v1','Secret'),'pods':('v1','Pod')}
        objects={}
        for resource,names in resources.items():
            for name in names:
                api,kind=kinds[resource]
                obj={'apiVersion':api,'kind':kind,'metadata':{'name':name,'namespace':'jupyterhub','uid':name+'-uid','resourceVersion':'123'}}
                if resource=='pods':
                    image='docker.io/library/postgres@sha256:'+'a'*64 if name.startswith('postgresql') else 'quay.io/jupyterhub/k8s-hub@sha256:'+'b'*64
                    container='postgresql' if name.startswith('postgresql') else 'hub'
                    obj.update(spec={'containers':[{'name':container,'image':image}]},status={'containerStatuses':[{'name':container,'imageID':'docker-pullable://'+image}]})
                prefix='/apis/apps/v1' if api=='apps/v1' else '/api/v1'
                objects[prefix+'/namespaces/jupyterhub/'+resource+'/'+name]=obj
        if failure=='mutable': objects['/api/v1/namespaces/jupyterhub/pods/hub-fixture']['status']['containerStatuses'][0]['imageID']='hub:latest'
        if failure=='wrong-identity': objects['/api/v1/namespaces/jupyterhub/secrets/hub']['metadata']['namespace']='cit-jhub'
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                requests.append((self.path,self.headers.get('Authorization')))
                status=403 if failure=='denied' else 404 if failure=='missing' and '/secrets/' in self.path else 200
                body=json.dumps(objects.get(self.path,{})).encode() if status==200 else b'fixture-secret-must-not-leak'
                self.send_response(status); self.end_headers(); self.wfile.write(body)
        key=root/'key.pem'; cert=root/'ca.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        server=HTTPServer(('127.0.0.1',0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert,key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        token=root/'token'; token.write_text('fixture-token'); token.chmod(0o600)
        output=root/'fresh'; output.mkdir(mode=0o700)
        if failure=='existing':
            previous=output/'complete'; previous.mkdir(mode=0o700); (previous/'retained').write_bytes(b'preserve previous capture')
        env={**os.environ,'FRESH_CONFIGURATION_CAPTURE':'true','FRESH_CAPTURE_DIRECTORY':str(output), 'FRESH_API_HOST':'127.0.0.1','FRESH_API_PORT':str(server.server_port),'FRESH_API_NAMESPACE':'jupyterhub','FRESH_API_RESOURCES':json.dumps(resources), 'FRESH_API_TOKEN_FILE':str(token),'FRESH_API_CA_FILE':str(cert),'FRESH_CAPTURE_IMAGE':'example.org/capture@sha256:'+'c'*64}
        if failure=='flush':
            tools=root/'init-bin'; tools.mkdir()
            shim=tools/'python3'
            shim.write_text('#!'+sys.executable+'\nimport os,sys\nreal_fsync=os.fsync\ndef fail_parent(fd):\n    if os.path.realpath("/proc/self/fd/"+str(fd))==os.environ["FRESH_CAPTURE_DIRECTORY"]: raise OSError("fixture-secret-must-not-leak")\n    return real_fsync(fd)\nos.fsync=fail_parent\nexec(compile(sys.stdin.read(),"capture-under-test","exec"))\n')
            shim.chmod(0o700); env['PATH']=str(tools)+os.pathsep+env['PATH']
        try: result=subprocess.run(['sh',str(SCRIPT)],env=env,capture_output=True,text=True,timeout=20)
        finally: server.shutdown(); thread.join(); server.server_close()
        self.assertNotIn('fixture-secret-must-not-leak',result.stdout+result.stderr)
        self.assertNotIn('fixture-token',result.stdout+result.stderr)
        return result,output,requests

    def test_fresh_api_capture_records_actual_object_versions_and_image_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); result,capture,requests=self.fresh_capture(root)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(requests),6)
            self.assertTrue(all(auth=='Bearer fixture-token' for _,auth in requests))
            complete=capture/'complete'
            snapshot=json.loads((complete/'snapshot.json').read_bytes())
            self.assertEqual(snapshot['source'],'kubernetes-api'); self.assertIs(snapshot['observed_live'],True)
            self.assertEqual(snapshot['namespace'],'jupyterhub')
            self.assertEqual({(o['resource'],o['name'],o['uid'],o['resource_version']) for o in snapshot['objects']}, {('deployments','hub','hub-uid','123'),('statefulsets','postgresql','postgresql-uid','123'),('configmaps','hub','hub-uid','123'),('secrets','hub','hub-uid','123'),('pods','hub-fixture','hub-fixture-uid','123'),('pods','postgresql-fixture','postgresql-fixture-uid','123')})
            backup=root/'backup-test'; backup.mkdir()
            result,published,calls=self.run_backup(backup,fresh=complete,snapshot_known=False)
            self.assertEqual(result.returncode,0,result.stderr)
            manifest=json.loads((published[0]/'manifest.json').read_bytes())
            self.assertEqual(manifest['configuration_snapshot'],snapshot)
            self.assertFalse(manifest['recovery_qualified'])
            self.assertEqual(stat.S_IMODE(complete.stat().st_mode),0o700)
            self.assertTrue(all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in complete.iterdir()))

    def test_fresh_denied_missing_mutable_or_mismatched_capture_publishes_nothing(self):
        for failure in ('denied','missing','mutable','wrong-identity'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                result,capture,requests=self.fresh_capture(Path(directory),failure)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(list(capture.iterdir()),[])
                self.assertGreater(len(requests),0)

    def test_fresh_capture_never_replaces_existing_or_keeps_unflushed_publication(self):
        for failure in ('existing','flush'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                result,capture,requests=self.fresh_capture(Path(directory),failure)
                self.assertNotEqual(result.returncode,0)
                if failure=='existing':
                    self.assertEqual([p.name for p in capture.iterdir()],['complete'])
                    self.assertEqual((capture/'complete/retained').read_bytes(),b'preserve previous capture')
                else: self.assertEqual(list(capture.iterdir()),[])

    def test_fresh_chart_has_only_named_get_permissions_and_init_only_token(self):
        settings={'enabled':True,'privilegedCredentialSecretRef':'reviewed-admin','userKey':'username','passwordKey':'password', 'freshApi':{'enabled':True,'image':'example.org/capture@sha256:'+'c'*64,'apiServerHost':'10.43.0.1','apiServerPort':443,'resources':{'deployments':['hub'],'statefulsets':['postgresql'],'configmaps':['hub'],'secrets':['hub'],'pods':['hub-fixture','postgresql-fixture']}}}
        result=self.render(settings)
        self.assertEqual(result.returncode,0,result.stderr)
        docs=[d for d in yaml.safe_load_all(result.stdout) if d]
        role=next(d for d in docs if d['kind']=='Role')
        self.assertEqual({r['resources'][0]:r['resourceNames'] for r in role['rules']},settings['freshApi']['resources'])
        self.assertTrue(all(r['verbs']==['get'] for r in role['rules']))
        self.assertFalse(any(d['kind'].startswith('ClusterRole') for d in docs))
        pod=next(d for d in docs if d['kind']=='CronJob')['spec']['jobTemplate']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertNotIn('api-credentials',[v['name'] for v in pod['containers'][0]['volumeMounts']])
        self.assertIn('api-credentials',[v['name'] for v in pod['initContainers'][0]['volumeMounts']])
        policy=next(d for d in docs if d['kind']=='NetworkPolicy')
        self.assertIn({'to':[{'ipBlock':{'cidr':'10.43.0.1/32'}}],'ports':[{'protocol':'TCP','port':443}]},policy['spec']['egress'])
        for field,value in [('image','capture:latest'),('apiServerHost','host.example.org'),('resources',{'secrets':['*']})]:
            with self.subTest(field=field):
                self.assertNotEqual(self.render({**settings,'freshApi':{**settings['freshApi'],field:value}}).returncode,0)
        reviewed={**settings,'credentialQualified':True,'qualificationEvidence':'private/credential-receipt'}
        self.assertNotEqual(self.render(reviewed,suspend=False).returncode,0)
        self.assertNotEqual(self.render({**reviewed,'freshApi':{**settings['freshApi'],'captureQualified':True}},suspend=False).returncode,0)
        self.assertEqual(self.render({**reviewed,'freshApi':{**settings['freshApi'],'captureQualified':True,'qualificationEvidence':'private/fresh-capture-receipt'}},suspend=False).returncode,0)


if __name__=='__main__': unittest.main()
