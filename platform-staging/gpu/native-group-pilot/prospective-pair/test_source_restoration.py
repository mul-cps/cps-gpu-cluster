"""Restoration uses the real local provider and authenticated policy API."""
import asyncio
import copy
import importlib.util
from pathlib import Path
import tempfile
import sys
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import test_source_handover as forward
import test_source_qualification_handover as prior
from cps_compute.internal import install_internal, ServiceIdentity


def helper():
    path=HERE/'source_restoration.py'
    assert path.exists(), 'Audited Source restoration implementation required'
    spec=importlib.util.spec_from_file_location('source_restoration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


async def prepare(f, phase):
    # CPU registrations omit GPU ceilings; a zero GPU ceiling is invalid.
    ceiling={k:v for k,v in f.local['course_ceiling'].items() if k!='gpuMemoryGiB'}
    f.local={**f.local,'course_ceiling':ceiling}
    f.review['original_local']=copy.deepcopy(f.local)
    f.review['original_course']['resource_ceiling']=ceiling
    f.old['ceiling']=ceiling;f.review['original_registration']=copy.deepcopy(f.old)
    await f.provider.put('workspaces',f.local,actor='admin')
    await f.provider.put('courses',f.review['original_course'],actor='admin')
    f.store.put_workspace(f.old,ServiceIdentity('cps','cps'),f.reservations)
    raw,pin=forward.contract(f)
    if phase=='complete':
        await forward.helper().migrate_fresh(f.context,f.review,contract_raw=raw,contract_sha256=pin)
    elif phase=='course-only':
        await f.provider.put('courses',{**f.review['original_course'],'resource_ceiling':f.review['target_ceiling']},actor='admin')
    # Restore the genuine original policy at the API boundary before restoring Source.
    original_catalog=copy.deepcopy(f.policy.catalog)
    for key in list(original_catalog['profiles']):
        if key.startswith('interactive-native-qualification-'):del original_catalog['profiles'][key]
    original_catalog['profiles']['interactive-cpu']={'enabled':True,'kind':'interactive','queue':'interactive','cpu':'4','memory':'16Gi','gpu':'0','images':[f.groups.workload_image]}
    from cps_compute.policy import Policy
    old_policy=Policy(original_catalog)
    f.old['policy_hash']=old_policy.hash;f.review['original_registration']['policy_hash']=old_policy.hash
    if phase!='complete':f.store.put_workspace(f.old,ServiceIdentity('cps','cps'),f.reservations)
    app=FastAPI()
    async def auth(token):
        assert token=='private-fixture';return ServiceIdentity('cps','cps')
    async def stopped(source,workspace):return source=='cps' and workspace==f.workspace
    async def owner(source,body):return source=='cps' and body['owner']==f.old['owner']
    install_internal(app,f.store,f.reservations,auth,stopped,old_policy,
        canonical_people={'cps':dict(zip(['member0','member1'],f.members))},workspace_owner_check=owner)
    await f.http.aclose();f.http=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid')
    for member in f.members:
        f.store.put({'id':member,'person':member,'profiles':['interactive-cpu'],'projects':['course'],'allowance':1,
            'expires':'2099-01-01T00:00:00+00:00'},ServiceIdentity('cps','cps'))
    context={**f.context,'policy':old_policy}
    async def physical():
        return dict(version=1,policy_hash=f.policy.hash,ledger_uid=f.review['stopped']['ledger_uid'],
            node_pool={k:f.groups.node_pool[k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')},
            zero_charge=True,observed_at=datetime.now(timezone.utc).isoformat())
    return context,raw,pin,physical


@pytest.mark.parametrize('phase',['unstarted','course-only','complete'])
@pytest.mark.parametrize('size',[5,20])
def test_restores_original_cpu_records_and_storage_through_audited_apis(phase,size):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=size)
            try:
                context,raw,pin,physical=await prepare(f,phase)
                result=await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                assert result['state']=='restored-cpu-stopped'
                assert await f.service.get(f.workspace)=={**f.review['original_local'],'archive_pending':False}
                assert (await f.provider.courses())[0]==f.review['original_course']
                assert f.store.workspace('cps',f.workspace)==f.review['original_registration']
                assert 'PUT workspaces' in f.calls
                assert f.provider.audit()[-1]['target']==f.workspace
            finally:await f.close()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['local','course','storage','member','admin','freeze','pod','reservation','physical','stale-physical','ledger-uid','policy','grant'])
def test_changed_or_unreleased_state_is_not_overwritten(fault):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=20)
            try:
                context,raw,pin,physical=await prepare(f,'complete')
                if fault=='local':await f.provider.put('workspaces',{**await f.service.get(f.workspace),'notice':'unrelated edit'},actor='admin')
                elif fault=='course':await f.provider.put('courses',{**(await f.provider.courses())[0],'name':'unrelated edit'},actor='admin')
                elif fault=='storage':
                    original_read=context['read_registration']
                    async def changed_read(source,workspace):
                        row=copy.deepcopy(await original_read(source,workspace));row['storage']['path']='/changed';return row
                    context['read_registration']=changed_read
                elif fault=='member':await f.provider.put('memberships',{'id':'m0','course_id':'course','term_id':'term','group_id':f.local['group_id'],'person_id':'member0','expires':'2000-01-01T00:00:00+00:00'},actor='admin')
                elif fault=='admin':f.admin=False
                elif fault=='freeze':f.fail_freeze_at=f.freeze_calls+1
                elif fault=='pod':f.core.live_pod={'metadata':{'uid':prior.uid()}}
                elif fault=='reservation':f.reservations.acquire('cps:'+f.workspace,f.members,attempt=prior.uid())
                elif fault=='physical':
                    original=physical
                    async def physical():return {**await original(),'zero_charge':False}
                elif fault=='stale-physical':
                    original=physical
                    async def physical():return {**await original(),'observed_at':'2000-01-01T00:00:00+00:00'}
                elif fault=='ledger-uid':f.core.maps[prior.LEDGER_NAME]['metadata']['uid']=prior.uid()
                elif fault=='policy':context['policy']=f.policy
                elif fault=='grant':f.store.put({'id':f.members[0],'person':f.members[0],'profiles':[],'projects':['course'],'allowance':1,'expires':'2099-01-01T00:00:00+00:00'},ServiceIdentity('cps','cps'))
                before=(await f.service.get(f.workspace),await f.provider.courses(),f.store.workspace('cps',f.workspace))
                with pytest.raises((ValueError,prior.h.HandoverIncomplete)):
                    await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                assert (await f.service.get(f.workspace),await f.provider.courses(),f.store.workspace('cps',f.workspace))==before
            finally:await f.close()
    asyncio.run(run())


def enrolled(f, *, active=False, cleanup=True):
    import hashlib
    from cps_compute.native_gpu_control import _json, NativeGpuAuthority, LABEL
    row=dict(source='cps',actor='service:cps-hub',workspace=f.workspace,principal=f.old['principal'],members=f.members,
        ceiling=f.review['target_ceiling'],group_id=f.local['group_id'],attempt=prior.uid(),profile=f.review['new_profile'],
        policy_hash=f.policy.hash,namespace='jupyterhub',name=f.old['pod'],
        **{k:f.groups.node_pool[k] for k in ('node','node_uid','gpu_uuid')},cap_mib=20480)
    binding=hashlib.sha256(_json(row).encode()).hexdigest()[:60]
    intent={k:row[k] for k in ('namespace','name','node','node_uid','gpu_uuid','cap_mib','policy_hash')}
    intent.update(pod_uid=prior.uid(),spec_sha256='b'*64)
    row.update(version=1,binding_id=binding,intent=intent,state='enrolled' if active else 'released')
    f.set_ledger(dict(version=1,allocations={binding:row}))
    def cm(name,key,value):
        return dict(apiVersion='v1',kind='ConfigMap',immutable=True,metadata=dict(name=name,namespace=f.backend.namespace,
            uid=prior.uid(),resourceVersion='1',labels={LABEL:binding}),data={key:prior.h.canonical(value)})
    name='cps-native-enrollment-'+binding[:40]
    f.core.maps[name]=cm(name,'enrollment.json',NativeGpuAuthority._enrollment_record(row))
    if cleanup:
        name='cps-native-cleanup-'+binding[:40]
        f.core.maps[name]=cm(name,'receipt.json',dict(version=1,binding_id=binding,attempt=row['attempt'],intent=intent,cleanup_confirmed=True))


@pytest.mark.parametrize('fault',[None,'active','missing-cleanup','changed-enrollment'])
def test_completed_gpu_lifetime_requires_immutable_release_provenance(fault):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=20)
            try:
                context,raw,pin,physical=await prepare(f,'complete')
                enrolled(f,active=fault=='active',cleanup=fault!='missing-cleanup')
                if fault=='changed-enrollment':
                    name=next(n for n in f.core.maps if n.startswith('cps-native-enrollment-'))
                    body=prior.h.decode(f.core.maps[name]['data']['enrollment.json']);body['actor']='changed'
                    f.core.maps[name]['data']['enrollment.json']=prior.h.canonical(body)
                if fault:
                    with pytest.raises(prior.h.HandoverIncomplete):await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                else:
                    await f.provider.put('workspaces',{**await f.service.get(f.workspace),'notice':None,'archive_pending':False},actor='admin')
                    result=await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                    assert result['state']=='restored-cpu-stopped'
            finally:await f.close()
    asyncio.run(run())


@pytest.mark.parametrize('boundary',['courses','workspaces'])
def test_partial_restoration_is_retryable_without_losing_original_records(boundary):
    async def run():
        with tempfile.TemporaryDirectory() as d:
            f=await prior.Fixture().setup(Path(d),fresh_profile=20)
            try:
                context,raw,pin,physical=await prepare(f,'complete')
                real_put=f.provider.put
                async def failing_put(kind,record,**kwargs):
                    if kind==boundary:raise RuntimeError('controlled commit failure')
                    return await real_put(kind,record,**kwargs)
                f.provider.put=failing_put
                with pytest.raises(prior.h.HandoverIncomplete):await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                f.provider.put=real_put
                result=await helper().restore(context,f.review,contract_raw=raw,contract_sha256=pin,verify_physical_release=physical)
                assert result['state']=='restored-cpu-stopped'
                assert await f.service.get(f.workspace)=={**f.review['original_local'],'archive_pending':False}
            finally:await f.close()
    asyncio.run(run())
