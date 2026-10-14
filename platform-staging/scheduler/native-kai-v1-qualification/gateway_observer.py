"""Read-only pending custody/member SQL witness inside the explicitly enabled Gateway."""
import argparse
import json
import os
from pathlib import Path
import sqlite3


def need(x, text):
    if not x: raise ValueError(text)


def observe(uid, binding):
    config = json.loads(Path(os.environ['CPS_COMPUTE_CONFIG']).read_text())
    pending = json.loads(Path(os.environ['CPS_NATIVE_KAI_COORDINATOR_CONFIG']).read_text())
    need(pending['enabled'] is True and config['nativeGpuQualification']['profile_caps'] == {
        'interactive-native-qualification-10':10240}, 'Actual enabled single-authority configuration required')
    state=Path(config['state_directory']);custody=Path(pending['custodyPath'])
    with sqlite3.connect('file:'+str(custody)+'?mode=ro', uri=True, timeout=5) as db:
        result=db.execute('SELECT document FROM native_pending_custody WHERE uid=?',(uid,)).fetchone()
    need(result is not None,'Actual original Pod custody required')
    row=json.loads(result[0]);need(row['binding_id']==binding and row['source']=='cit'
        and row['workspace']=='native-group-a' and row['pod']['uid']==uid,'Immutable original custody required')
    with sqlite3.connect('file:'+str(state/'reservations.sqlite')+'?mode=ro',uri=True,timeout=5) as db:
        members=db.execute('SELECT count(*) FROM reservation WHERE workspace=?',('cit:native-group-a',)).fetchone()[0]
        active=db.execute('SELECT attempt,binding FROM reservation_binding WHERE workspace=?',('cit:native-group-a',)).fetchall()
    return {'pod_uid':uid,'binding_id':binding,'custody_state':row['state'],
            'member_reservations':members,'reservation_bindings':len(active),'writes':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--pod-uid');p.add_argument('--binding-id');a=p.parse_args()
    if not a.execute:print(json.dumps({'state':'inert','api_calls':False,'sql_calls':False}));return
    need(os.geteuid()==10001 and a.pod_uid and a.binding_id,'Explicit GatewayUID10001 witness required')
    print(json.dumps(observe(a.pod_uid,a.binding_id),sort_keys=True))

if __name__=='__main__':main()
