"""Fresh operator scopes through actual provider, policy and ASGI registration."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import pytest
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent))
import test_source_qualification_handover as prior


def helper():
    p=HERE/'source_handover.py'
    assert p.exists(), 'Fresh Source handover adapter required'
    spec=importlib.util.spec_from_file_location('fresh_source_handover',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def contract(f):
    body=json.loads(f.groups.document)
    members={scope:row['members'] for scope,row in body['workspaces'].items()}
    value=dict(version=1,policy_hash=f.policy.hash,workspaces={s:dict(profile=r['profiles'][0],cap_mib=body['profile_caps'][r['profiles'][0]]) for s,r in body['workspaces'].items()},
        terminal_history_sha256='sha256:'+'a'*64,operator_people=sorted(p for row in members.values() for p in row),operator_members=members)
    raw=json.dumps(value,sort_keys=True).encode();return raw,hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize('size',[5,20])
def test_fresh_cpu_workspace_handover_preserves_storage_and_uses_audited_apis(size):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=size)
            try:
                raw,pin=contract(f)
                result=await helper().migrate_fresh(f.context,f.review,contract_raw=raw,contract_sha256=pin)
                assert result['state']=='handover-complete-stopped'
                assert result['previous_profile']=='interactive-cpu'
                assert result['profile']=='interactive-native-qualification-'+str(size)
                assert result['hardware_qualified'] is result['start_performed'] is False
                assert f.store.workspace('cps',f.workspace)['storage']==f.old['storage']
                assert f.provider.audit()[-1]['target']==f.workspace
                assert 'POST workspace-policy/preview' in f.calls and 'PUT workspaces' in f.calls
            finally:await f.close()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['scope','profile','members','ceiling','actor','freeze','pod','reservation','grant','ledger-uid','prior-attempt','active-other'])
def test_fresh_handover_refuses_unreviewed_or_unresolved_state_without_profile_commit(fault):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=20)
            try:
                raw,pin=contract(f)
                if fault=='scope':f.review['workspace']='native-group-b'
                elif fault=='profile':f.review['new_profile']='interactive-shared-20'
                elif fault=='members':f.review['members']=['00000000-0000-4000-8000-000000000099']
                elif fault=='ceiling':f.review['target_ceiling']['gpuMemoryGiB']=40
                elif fault=='actor':f.admin=False
                elif fault=='freeze':f.fail_freeze_at=1
                elif fault=='pod':f.core.live_pod={'metadata':{'uid':prior.uid()}}
                elif fault=='reservation':f.reservations.acquire('cps:'+f.workspace,f.members,attempt=prior.uid())
                elif fault=='grant':
                    from cps_compute.internal import ServiceIdentity
                    f.store.put({'id':f.members[0],'person':f.members[0],'profiles':[],'projects':['course'],'allowance':1,
                        'expires':'2099-01-01T00:00:00+00:00'},ServiceIdentity('cps','cps'))
                elif fault=='ledger-uid':f.review['stopped']['ledger_uid']=prior.uid()
                else:
                    from cps_compute.native_gpu_control import _json
                    import copy
                    scope=f.workspace if fault=='prior-attempt' else 'other'
                    identity={'source':'cps','actor':'service:cps-hub','workspace':scope,'principal':'workspace:cps:'+scope,
                        'members':f.members,'ceiling':{'cpu':'4','memory':'16Gi','gpuMemoryGiB':20},'group_id':'group','attempt':prior.uid(),
                        'profile':'interactive-native-qualification-20','policy_hash':f.policy.hash,'namespace':'jupyterhub','name':f.local['pod'],
                        'node':f.groups.node_pool['node'],'node_uid':f.groups.node_pool['node_uid'],'gpu_uuid':f.groups.node_pool['gpu_uuid'],'cap_mib':20480}
                    binding=hashlib.sha256(_json(identity).encode()).hexdigest()[:60]
                    f.set_ledger({'version':1,'allocations':{binding:dict(identity,version=1,binding_id=binding,intent=None,
                        state='released' if fault=='prior-attempt' else 'reserved')}})
                with pytest.raises((ValueError,prior.h.HandoverIncomplete)):
                    await helper().migrate_fresh(f.context,f.review,contract_raw=raw,contract_sha256=pin)
                assert (await f.service.get(f.workspace))['profile']=='interactive-cpu'
                assert f.store.workspace('cps',f.workspace)==f.old
            finally:await f.close()
    asyncio.run(run())
