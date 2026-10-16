"""Bridge a fresh Root custody collector to the Source restoration callback.

A collector must return the actual complete final authority/ledger/history/
physical/PodList capture. No receipt flag or timestamp is manufactured here.
The existing bounded Node inverse validates the entire archive and preservation
of baseline history before any zero-charge summary can reach Source.
"""
import copy
import inspect
import json
import time
from datetime import datetime, timezone

import configuration_inverse as inverse


def physical_release_verifier(*,collect_final,phase,original,current,baseline,
                              contract_raw,contract_sha256,approval_raw,approval_sha256,
                              original_node_source,original_epoch_source):
    if not inspect.iscoroutinefunction(collect_final):
        raise ValueError('Trusted asynchronous complete physical custody collector required')
    validators={'unstarted':inverse.derive_unstarted_node_inverse,
                'partial':inverse.derive_partial_node_inverse,'complete':inverse.derive_node_inverse}
    if phase not in validators:raise ValueError('Explicit unstarted/partial/complete phase required')
    # Root-reviewed fixed inputs cannot drift through mutable caller dictionaries.
    fixed=copy.deepcopy(dict(original=original,current=current,baseline=baseline,
        contract_raw=contract_raw,contract_sha256=contract_sha256,approval_raw=approval_raw,
        approval_sha256=approval_sha256,original_node_source=original_node_source,
        original_epoch_source=original_epoch_source))

    async def verify():
        final=await collect_final()
        now=time.time_ns()
        validators[phase](**fixed,final=final,now_ns=now)
        observed=final['physical']['observed_at_ns']
        # Source restoration has a stricter 30-second freshness window. Check
        # after the potentially expensive complete replay, never renew its age.
        if not 0 <= time.time_ns()-observed <= 30_000_000_000:
            raise ValueError('Fresh physical custody older than Source restoration window')
        node=json.loads(fixed['current']['data']['config.json'])
        return dict(version=1,policy_hash=node['policy_hash'],
            ledger_uid=final['ledger']['metadata']['uid'],
            node_pool={k:node['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')},
            zero_charge=True,observed_at=datetime.fromtimestamp(observed/1_000_000_000,timezone.utc).isoformat())

    return verify
