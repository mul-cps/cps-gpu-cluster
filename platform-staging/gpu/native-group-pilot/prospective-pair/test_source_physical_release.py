"""The Source callback must validate full custody, never just a released flag."""
import asyncio
import copy
import importlib.util
from pathlib import Path
import sys
import time

import pytest
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import test_configuration_inverse as prior


def helper():
    path=HERE/'source_physical_release.py'
    assert path.exists(),'Source physical-release collector adapter required'
    spec=importlib.util.spec_from_file_location('source_physical_release',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def inputs(phase):
    args={'unstarted':prior.unstarted_fixture,'partial':prior.partial_fixture,'complete':prior.fixture}[phase]()
    args.pop('now_ns');final=args.pop('final');return args,final


@pytest.mark.parametrize('phase',['unstarted','partial','complete'])
def test_collects_fresh_complete_custody_and_replays_real_inverse(phase):
    async def run():
        args,final=inputs(phase);calls=[]
        async def collect():
            calls.append(1);value=copy.deepcopy(final);value['physical']['observed_at_ns']=time.time_ns();return value
        callback=helper().physical_release_verifier(collect_final=collect,phase=phase,**args)
        first=await callback();second=await callback()
        assert calls==[1,1] and first['zero_charge'] is second['zero_charge'] is True
        assert first['ledger_uid']==final['ledger']['metadata']['uid']
        assert first['policy_hash']==prior.json.loads(args['current']['data']['config.json'])['policy_hash']
        assert first['observed_at']!=second['observed_at']
    asyncio.run(run())


@pytest.mark.parametrize('fault',['charged','stale','missing-journal','missing-cleanup','active','wrong-ledger','live-pod','paginated','wrong-phase','approval','collector-error'])
def test_full_custody_faults_never_become_a_zero_charge_source_proof(fault):
    async def run():
        args,final=inputs('complete')
        async def collect():
            value=copy.deepcopy(final);value['physical']['observed_at_ns']=time.time_ns()
            if fault=='charged':value['physical']['retired_caps'][-1]['inventory_row']['used']=1
            elif fault=='stale':value['physical']['observed_at_ns']-=31_000_000_000
            elif fault=='missing-journal':value['authority']['host_snapshot']['directories']['journal']['records'].popitem()
            elif fault=='missing-cleanup':value['authority']['authority_maps']['items']=[c for c in value['authority']['authority_maps']['items'] if 'receipt.json' not in c['data']]
            elif fault=='active':
                state=prior.json.loads(value['ledger']['data']['state.json']);next(reversed(state['allocations'].values()))['state']='enrolled'
                value['ledger']['data']['state.json']=prior.terminal.canonical(state)
            elif fault=='wrong-ledger':value['ledger']['metadata']['uid']=prior.uid(9999)
            elif fault=='live-pod':
                state=prior.json.loads(value['ledger']['data']['state.json']);row=next(r for r in state['allocations'].values() if r['workspace'].startswith('operator-qualification-531-'))
                value['pods']['items']=[{'metadata':{'uid':row['intent']['pod_uid'],'namespace':row['namespace'],'name':row['name']}}]
            elif fault=='paginated':value['pods']['metadata']['continue']='next'
            elif fault=='collector-error':raise RuntimeError('Collector unavailable')
            return value
        if fault=='approval':args['approval_sha256']='0'*64
        callback=helper().physical_release_verifier(collect_final=collect,phase='partial' if fault=='wrong-phase' else 'complete',**args)
        with pytest.raises((ValueError,RuntimeError)):await callback()
    asyncio.run(run())
