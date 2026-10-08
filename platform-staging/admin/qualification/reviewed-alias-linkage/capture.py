#!/usr/bin/env python3
"""Read-only identity/runtime inventory with optional current online backups.

Uses the previously qualified backup runner against read-only live data. Private
Secret/runtime and SQLite evidence stays outside Git; stdout is sanitized only.
No aliases, grants, runtime configuration, credentials or Deployments are changed.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import handover

NS = 'cps-compute'
ROOT = Path(__file__).resolve().parents[4]


def run(*args, body=None):
    result = subprocess.run(['kubectl', '-n', NS, *args], input=body,
                            capture_output=True, text=True, timeout=45)
    if result.returncode: raise RuntimeError('Cluster operation failed; secret-free operator review required')
    return result.stdout


def get(kind, name): return json.loads(run('get', kind, name, '-o', 'json'))


def exec_json(deployment, code):
    return json.loads(run('exec', 'deployment/' + deployment, '--', 'python', '-c', code))


def qualified_console(hub):
    handover.require(hub in handover.ALIASES, 'Exact console owner required')
    deployment=hub+'-admin';observed=get('deployment',deployment)
    handover.require(observed['spec']['template']['spec']['containers'][0]['image']==handover.IMAGE, 'Unexpected console image')
    handover.require(observed['status'].get('readyReplicas')==1 and observed['status'].get('observedGeneration')==observed['metadata']['generation'], 'Current console generation must be ready')
    selector=','.join(k+'='+v for k,v in observed['spec']['selector']['matchLabels'].items())
    pods=json.loads(run('get','pods','-l',selector,'-o','json'))['items']
    ready=[p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase')=='Running'
           and p['status'].get('containerStatuses') and all(c.get('ready') for c in p['status']['containerStatuses'])]
    handover.require(len(ready)==1 and handover.IMAGE.split('@')[-1] in ready[0]['status']['containerStatuses'][0].get('imageID',''), 'Exact qualified console image must actually be running')
    return {'deployment_uid':observed['metadata']['uid'],'resourceVersion':observed['metadata']['resourceVersion'],
            'generation':observed['metadata']['generation'],'pod_uid':ready[0]['metadata']['uid'],
            'image_id':ready[0]['status']['containerStatuses'][0]['imageID']}


CONSOLE = r'''
import json,os,sqlite3,urllib.request
hub,user=TARGET
request=urllib.request.Request(os.environ['JUPYTERHUB_API_URL'].rstrip('/')+'/users/'+user,
    headers={'Authorization':'token '+os.environ['JUPYTERHUB_API_TOKEN']})
account=json.load(urllib.request.urlopen(request,timeout=10))
assert account['name']==user and account.get('admin') is True
db=sqlite3.connect('file:/data/courses.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row
db.execute('BEGIN')
assert db.execute('PRAGMA user_version').fetchone()[0]==6
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert [row[0] for row in db.execute('SELECT owner FROM console_owner')]==[hub]
person_ids=[row[0] for table in ('email_links','reviewed_account_aliases') for row in
    db.execute('SELECT canonical_person_id FROM '+table+' WHERE console=? AND username=? AND canonical_person_id IS NOT NULL',(hub,user))]
aliases=[]
for row in db.execute('SELECT console,username,canonical_person_id,review_actor,review_reason,reviewed_at FROM reviewed_account_aliases WHERE console=? AND username=?',(hub,user)):
    proof=dict(row);proof.update(source=SOURCE,image=IMAGE,schema=6)
    audits=[dict(a) for a in db.execute('SELECT actor,console,kind,target AS id,current AS new,time,outcome FROM audit WHERE console=? AND kind=? AND target=? AND outcome=? ORDER BY rowid',(hub,'identity-aliases',user,'success'))]
    assert audits
    audit=audits[-1];identity=json.loads(audit['new'])
    audit['new']={k:identity[k] for k in ('person_id','authority','review_actor','review_reason','reviewed_at')}
    proof['audit']=audit;aliases.append(proof)
print(json.dumps({'username':user,'admin':account['admin'],'groups':account.get('groups',[]),
    'roles':account.get('roles',[]),'person_ids':person_ids,'alias_proofs':aliases,
    'group_source':'Current exact owning Hub API read:users; not directory expiry proof',
    'group_expiry':None,'schema':6,'integrity':'ok',
    'table_counts':{t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
        ('records','email_links','reviewed_account_aliases','audit')},
    'email_verification_counts':{str(r[0]):r[1] for r in db.execute('SELECT verified,count(*) FROM email_links GROUP BY verified')}}))
db.close()
'''

GATEWAY = r'''
import os,json,sqlite3,hashlib
from pathlib import Path
config=json.loads(Path(os.environ['CPS_COMPUTE_CONFIG']).read_text())
policy=json.loads(Path(config['policy_file']).read_text())
db=sqlite3.connect('file:'+str(Path(config['state_directory'])/'control.sqlite')+'?mode=ro',uri=True)
db.execute('BEGIN')
tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
proof={}
for table in tables:
    rows=db.execute('SELECT * FROM "'+table+'" ORDER BY rowid').fetchall()
    proof[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,separators=(',',':'),default=str).encode()).hexdigest()}
print(json.dumps({'runtime_sha256':hashlib.sha256(Path(os.environ['CPS_COMPUTE_CONFIG']).read_bytes()).hexdigest(),
    'canonical_people':{h:s['canonical_people'] for h,s in config['hubs'].items()},
    'policy_hash':config['policy_hash'],'entitlement_bundles':policy['entitlements'],
    'reviewed_group_bindings':policy.get('group_bindings'),
    'disabled_profiles':[name for name,p in policy['profiles'].items() if p.get('enabled') is False],
    'control_tables':proof}))
db.close()
'''


def capture(private, *, backup=False, allow_reviewed_aliases=False):
    private = Path(private).resolve()
    handover.require(private.is_dir() and private.stat().st_uid == os.getuid()
                     and private.stat().st_mode & 0o777 == 0o700, 'Existing private 0700 evidence directory required')
    # An outside-repository directory prevents accidentally committing DB/Secret bytes.
    handover.require(not private.is_relative_to(ROOT), 'Private evidence must be outside the checkout')
    report = {'captured_at': datetime.now(timezone.utc).isoformat(), 'source': handover.SOURCE,
              'console_image': handover.IMAGE, 'accounts': {}, 'mutations': {'aliases': False, 'grants': False, 'runtime': False}}
    secret = get('secret', 'cps-compute-runtime')
    handover.private_write(private/'runtime-secret-before.json', secret)
    handover.require(len(secret['data']) == 1, 'Single current runtime configuration key required')
    key, encoded = next(iter(secret['data'].items()))
    runtime = json.loads(base64.b64decode(encoded, validate=True))
    handover.private_write(private/'runtime-before.json', runtime)
    report['runtime_secret'] = {'name': secret['metadata']['name'], 'resourceVersion': secret['metadata']['resourceVersion'],
                               'data_key': key, 'sha256': hashlib.sha256(base64.b64decode(encoded)).hexdigest()}
    report['gateway'] = exec_json('compute-gateway', GATEWAY)
    handover.require(report['runtime_secret']['sha256'] == report['gateway']['runtime_sha256'], 'Mounted runtime and observed Secret disagree')
    for hub, user in handover.ALIASES.items():
        deployment = hub+'-admin'
        receipt=qualified_console(hub)
        code = 'TARGET='+repr((hub,user))+'\nSOURCE='+repr(handover.SOURCE)+'\nIMAGE='+repr(handover.IMAGE)+'\n'+CONSOLE
        report['accounts'][hub] = exec_json(deployment, code)
        report.setdefault('console_receipts',{})[hub]=receipt
    handover.private_write(private/'inventory.json', report)
    if backup:
        spec = importlib.util.spec_from_file_location('qualified_console_rollout', Path(__file__).resolve().parent.parent/'reviewed-alias'/'rollout.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        if allow_reviewed_aliases:
            original='assert migrated[\'tables\'][\'reviewed_account_aliases\'][\'count\']==0'
            replacement='assert migrated[\'tables\'][\'reviewed_account_aliases\']==original[\'tables\'][\'reviewed_account_aliases\']'
            handover.require(module.PROBE.count(original)==1, 'Exact qualified probe alias precondition required')
            module.PROBE=module.PROBE.replace(original,replacement)
        # Before-seed capture refuses populated aliases; explicit post-backup
        # preserves their exact hashes while reopening a fresh online snapshot.
        report['backups'] = {}
        for hub in handover.ALIASES:
            deployment = hub+'-admin'
            handover.require(allow_reviewed_aliases or report['accounts'][hub]['table_counts']['reviewed_account_aliases'] == 0, 'Pre-seed probe refuses already-populated alias authority')
            report['backups'][hub] = module.probe(deployment, get('deployment', deployment), private)
            module.verify_snapshot(deployment, report['backups'][hub])
        handover.private_write(private/'inventory-with-backups.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--post-backup', action='store_true',help='Preserve and reopen already-reviewed aliases with exact row hashes')
    args = parser.parse_args()
    print(json.dumps(capture(args.private_dir, backup=args.backup or args.post_backup, allow_reviewed_aliases=args.post_backup), indent=2, sort_keys=True))


if __name__ == '__main__': main()
