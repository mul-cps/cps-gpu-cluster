"""Synthetic target plus retained custody fixtures; never hardware evidence."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import qualification_proposal as proposal
import test_current_groups_qualification as current
from cps_compute.native_groups import APPROVAL_FIELDS
from cps_compute.native_qualification import NativeGroupQualification
from cps_compute.policy import Policy

IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4'
SOURCE='ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace'
SCOPE='cps:operator-qualification-531-5'
NOW=datetime(2026,10,12,20,20,30,tzinfo=timezone.utc)


def raw(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def raw_sha(value):return hashlib.sha256(value).hexdigest()


def fixture():
    old=current.CurrentGroupQualificationTest();old.setUp()
    args,authority,_,_=old.fixture(Path('/tmp'))
    body=args[0];policy=Policy(body['catalog']);workspace=SCOPE.split(':')[1]
    approval=copy.deepcopy(body['approvals']['cps:native-group-b'])
    approval.update(owner='cps-ws-'+'a'*32,server='rtc',pod='jupyter-cps-ws-'+'a'*32+'--rtc',
        principal='workspace:'+SCOPE,members=['d98fbadd-d9a0-4981-8d20-1ab58bb75745'],
        profiles=['interactive-cpu'],group_id='operator-531',course_id='operator-531',term_id='operator-531')
    registration=dict(approval,workspace=workspace,policy_hash=policy.hash,
        workspace_label=policy.labels['workspace'],workspace_hash=policy.owner_label(SCOPE))
    registration['storage']=dict(approval['storage'],state='active')
    body['approvals']={SCOPE:approval};body['observed_at']=NOW.isoformat()
    closure=json.loads((Path(__file__).parent/'source531-qualification-closure.json').read_bytes())
    import cps_compute.native_qualification as loaded
    closure['modules']['cps_compute.native_qualification']=hashlib.sha256(Path(loaded.__file__).read_bytes()).hexdigest()
    snapshot=dict(version=1,source='cps',workspace=workspace,profile='interactive-native-qualification-5',
        workload_image=IMAGE,operator_members=approval['members'],source_policy_hash=policy.hash,
        source_closure_sha256=raw_sha(raw(closure)),
        current_authority_sha256=proposal.agent.canonical_sha256(dict(ledger=body['ledger'],previous_node=body['node_config'],**authority)),
        source_instance=dict(namespace='cps-compute',deployment_uid='11111111-1111-4111-8111-111111111111',
            pod_uid='22222222-2222-4222-8222-222222222222',image=SOURCE),
        registration=registration,state='stopped',observed_at=NOW.isoformat())
    return args,authority,snapshot,closure


def render(values,**kw):
    args,authority,snapshot,closure=values
    options=dict(target_snapshot_raw=raw(snapshot),target_snapshot_sha256=raw_sha(raw(snapshot)),
        source_closure_raw=raw(closure),source_closure_sha256=raw_sha(raw(closure)),
        terminal_authority=authority,now=NOW)
    options.update(kw)
    return proposal.render_prospective_candidate(*args,**options)


def test_single_candidate_uses_typed_disabled_mode_and_preserves_complete_history():
    values=fixture();before=copy.deepcopy(values);result=render(values)
    mode=NativeGroupQualification.from_config(result['operator-qualification.json'],Policy(result['policy.json']))
    assert mode.workload_image==IMAGE and mode.profiles=={'interactive-native-qualification-5'}
    assert set(mode.workspaces)=={SCOPE} and mode.cap_mib(next(iter(mode.profiles)))==5120
    assert mode.node_pool['max_workspaces']==1 and mode.node_pool['memory_budget_mib']==5120
    assert result['policy.json']['profiles']['interactive-native-qualification-5']['enabled'] is False
    assert result['node-config.json']['terminal_history']==values[0][0]['terminal_history']
    assert result['acceptance.json']['terminal_history_sha256']==proposal.agent.canonical_sha256(values[0][0]['terminal_history'])
    assert result['acceptance.json']['hardware_qualified'] is False and result['acceptance.json']['live_applied'] is False
    assert not {'gates','evidence'} & set(result['operator-qualification.json'])
    assert values==before


@pytest.mark.parametrize('fault',[
    'image','source','workspace','owner','student-owner','pod','students','profile','policy','registration','labels',
    'stale','source-image','source-uid','source-namespace','closure','closure-module','authority','missing-history','missing-journal','live',
])
def test_untrusted_mixed_stale_or_incomplete_inputs_fail_closed(fault):
    values=fixture();body=values[0][0];target=values[2]
    if fault=='image':target['workload_image']='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:'+'9'*64
    elif fault=='source':target['source']='cit'
    elif fault=='workspace':target['workspace']='shared-gpu-lab'
    elif fault=='owner':target['registration']['owner']='bjoern'
    elif fault=='student-owner':target['registration']['owner']='cps-ws-27c474f74f9d41c53eac0be01fcca8a3'
    elif fault=='pod':target['registration']['pod']='jupyter-someone--rtc'
    elif fault=='students':target['operator_members']=target['registration']['members']=['15164372-7ae5-4cfd-8b5d-fd402aa891bd']
    elif fault=='profile':target['profile']='interactive-shared-5'
    elif fault=='policy':target['source_policy_hash']='sha256:'+'9'*64
    elif fault=='registration':body['approvals'][SCOPE]['storage']['path']+='/changed'
    elif fault=='labels':target['registration']['workspace_hash']='9'*32
    elif fault=='stale':target['observed_at']=(NOW-timedelta(seconds=901)).isoformat()
    elif fault=='source-image':target['source_instance']['image']='old@sha256:'+'9'*64
    elif fault=='source-uid':target['source_instance']['pod_uid']='name-only'
    elif fault=='source-namespace':target['source_instance']['namespace']='jupyterhub'
    elif fault=='closure':values[3]['modules'].pop('e2x_course_hub.cps.workspaces');target['source_closure_sha256']=raw_sha(raw(values[3]))
    elif fault=='closure-module':values[3]['modules']['cps_compute.native_qualification']='9'*64;target['source_closure_sha256']=raw_sha(raw(values[3]))
    elif fault=='authority':target['current_authority_sha256']='sha256:'+'9'*64
    elif fault=='missing-history':body['terminal_history'].clear()
    elif fault=='missing-journal':values[1]['host_snapshot']['directories']['journal']['records'].clear();target['current_authority_sha256']=proposal.agent.canonical_sha256(dict(ledger=body['ledger'],previous_node=body['node_config'],**values[1]))
    elif fault=='live':
        ledger=json.loads(body['ledger']['data']['state.json']);next(iter(ledger['allocations'].values()))['state']='enrolled'
        body['ledger']['data']['state.json']=json.dumps(ledger)
    with pytest.raises(ValueError):render(values)


@pytest.mark.parametrize('pin',['target_snapshot_sha256','source_closure_sha256'])
def test_independent_root_raw_pins_required(pin):
    with pytest.raises(ValueError):render(fixture(),**{pin:'sha256:'+'9'*64})


def test_full_retired_authority_and_source_closure_are_mandatory():
    with pytest.raises(ValueError):render(fixture(),terminal_authority=None)
    with pytest.raises(ValueError):render(fixture(),source_closure_raw=b'{}',source_closure_sha256=proposal.checksum(b'{}'))


def test_existing_d48_to_39ef_retired_configuration_authority_is_preserved(tmp_path):
    import test_current_group_historical_source as history
    old=history.CurrentHistoricalTest();old.setUp()
    node,_,_,_,_,_,maps,records,_=old.values(tmp_path)
    values=fixture();body=values[0][0];authority=values[1]
    authority['authority_maps']['items']=copy.deepcopy(list(maps.values()))
    identity=next(iter(records.values())).identity
    authority['host_snapshot'].update(bootId=identity.boot_id,driverGeneration=identity.driver_generation)
    for name in ('enrollments','intents','journal'):
        rows={}
        for path in (tmp_path/name).glob('*.json'):
            data=json.loads(path.read_bytes())
            if name=='journal':data=records[path.stem].to_dict()
            rows[path.name]=dict(uid=0,mode=0o600,nlink=1,
                rawSha256=proposal.checksum((proposal.agent.canonical_json(data)+'\n').encode()),value=data)
        authority['host_snapshot']['directories'][name]=dict(ownerUid=0,mode=0o700,records=rows)
    authority['host_snapshot']['directories']['journal']['records']={uid+'.json':dict(uid=0,mode=0o600,nlink=1,
        rawSha256=proposal.checksum((proposal.agent.canonical_json(record.to_dict())+'\n').encode()),value=record.to_dict())
        for uid,record in records.items()}
    # This legacy finite-history fixture exercises the retained mapper, not the
    # modern immutable allocation checksum schema used by the full render test.
    _,map_history=proposal._candidate_history_context()
    mapped=map_history(authority,maps['cps-native-gpu-allocations'],node)
    assert mapped==node['terminal_history']
    assert any('configuration_authority' in row for row in mapped.values())


def test_no_candidate_flag_is_inert_and_legacy_single_scope_still_rejects():
    assert proposal.main([])==0
    with pytest.raises(ValueError,match='Only the reviewed neutral workspace scopes'):
        proposal.render(*fixture()[0],now=NOW)


def test_candidate_cli_missing_pins_rejects_before_private_read(monkeypatch):
    def no_read(*args):raise AssertionError('Private read before complete explicit pins')
    monkeypatch.setattr(proposal,'private_read',no_read)
    with pytest.raises(ValueError,match='candidate raw pins'):
        proposal.main(['--render','--source-mode','prospective-candidate','--input','missing',
            '--observation','missing','--health','missing','--output','missing'])


def test_candidate_cli_writes_only_fresh_unqualified_offline_proposal(tmp_path):
    args,authority,target,closure=fixture();body=args[0];observed=datetime.now(timezone.utc).isoformat()
    body['observed_at']=target['observed_at']=authority['host_snapshot']['observedAt']=observed
    target['current_authority_sha256']=proposal.agent.canonical_sha256(dict(ledger=body['ledger'],previous_node=body['node_config'],**authority))
    files={'input':raw(body),'observation':args[1],'health':args[2],'terminal-authority':raw(authority),
        'target-snapshot':raw(target),'source-closure':raw(closure)}
    argv=['--render','--source-mode','prospective-candidate','--output',str(tmp_path/'result')]
    for name,data in files.items():
        path=tmp_path/(name+'.json');path.write_bytes(data);path.chmod(0o600);argv+=['--'+name,str(path)]
    argv+=['--target-snapshot-sha256',raw_sha(files['target-snapshot']),'--source-closure-sha256',raw_sha(files['source-closure'])]
    assert proposal.main(argv)==0
    accepted=json.loads((tmp_path/'result/acceptance.json').read_bytes())
    assert accepted['source_mode']=='prospective-candidate' and accepted['hardware_qualified'] is False
    assert accepted['target_snapshot_sha256']==raw_sha(files['target-snapshot'])
    assert accepted['terminal_history_sha256']==proposal.agent.canonical_sha256(body['terminal_history'])
