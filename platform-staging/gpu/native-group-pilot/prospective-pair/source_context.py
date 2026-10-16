"""Construct genuine Source services only under a freshly verified writer freeze.

This operator utility never starts an HTTP server, workflow runtime or workspace.
Forward and restoration callers retain responsibility for normal audited APIs.
"""
import asyncio
import copy
import hashlib
import os
from pathlib import Path

import node_successor
import source_maintenance
import source_qualification_handover as legacy
from source_qualification_factory import local_only_configuration
from source_handover import FROZEN_HANDOVER_SHA256
from prospective_source_qualification_workspace import SOURCE_CLOSURE_SHA256, WORKLOAD_IMAGE
from gateway_registration_reader import GatewayReader, reader_source

APPS = []


async def build_context(*, workspace, operation, contract_raw, contract_sha256,
                        policy, qualification, source_closure_raw, console,
                        core, apps, originals, operator_ref, review, gateway,
                        gateway_reader):
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.native_gpu_control import KubernetesNativeAuthorityBackend

    contract = node_successor.validate_contract(contract_raw, contract_sha256)
    scope = 'cps:' + workspace
    legacy.require(operation in ('forward', 'restore') and scope in contract['workspaces'],
                   'Explicit reviewed Source operation and workspace required')
    legacy.require(type(policy) is Policy and type(qualification) is NativeGroupQualification,
                   'Released policy and qualification types required')
    legacy.require(qualification.policy_hash == contract['policy_hash']
                   and qualification.workload_image == WORKLOAD_IMAGE
                   and set(qualification.workspaces) == set(contract['workspaces'])
                   and qualification.node_pool['memory_budget_mib'] == 25600
                   and qualification.node_pool['headroom_mib'] == 1024
                   and qualification.node_pool['max_workspaces'] == 2,
                   'Exact reviewed notebook531 pair configuration required')
    for key, expected in contract['workspaces'].items():
        actual = qualification.workspaces[key]
        legacy.require(actual['profiles'] == [expected['profile']]
                       and actual['members'] == sorted(contract['operator_members'][key])
                       and qualification.cap_mib(expected['profile']) == expected['cap_mib'],
                       'Qualification identities and caps differ from Root contract')
    legacy.require((policy.hash == contract['policy_hash']) == (operation == 'forward'),
                   'Policy does not match explicit operation')
    legacy.require(type(gateway_reader) is GatewayReader
                   and gateway_reader.metadata['pod_uid'] == gateway['pod_uid']
                   and gateway['policy_hash'] == policy.hash
                   and gateway['contract_sha256'] == contract_sha256
                   and gateway_reader.scopes == frozenset(contract['workspaces'])
                   and gateway_reader.source == reader_source(
                       (Path(legacy.__file__).parent / 'source_qualification_reader.py').read_bytes(),
                       contract_raw=contract_raw, contract_sha256=contract_sha256),
                   'Current Gateway process, policy and contract binding required')
    legacy.require(hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest() == FROZEN_HANDOVER_SHA256,
                   'Frozen Source loader implementation required')
    legacy.require(isinstance(source_closure_raw, bytes)
                   and hashlib.sha256(source_closure_raw).hexdigest() == SOURCE_CLOSURE_SHA256,
                   'Exact reviewed Source closure required')
    legacy.verify_source_closure(legacy.decode(source_closure_raw))
    legacy.closed(console, {'config_path', 'config_sha256', 'database_path',
                           'server_config_path', 'hub_api_url', 'compute_policy_url'},
                  'Exact captured console configuration required')
    legacy.closed(operator_ref, {'name', 'uid', 'spec_sha256'}, 'Exact operator reference required')
    originals, review, gateway, operator_ref, console = map(copy.deepcopy,
        (originals, review, gateway, operator_ref, console))
    backend = KubernetesNativeAuthorityBackend(core, qualification.authority_namespace)

    async def verify_external_freeze():
        await asyncio.to_thread(gateway_reader._check)
        current = {}
        for source in ('cps', 'cit'):
            current[source] = await backend._call(apps.read_namespaced_deployment,
                                                 source + '-admin', 'cps-compute')
        pods = await backend._call(core.list_namespaced_pod, 'cps-compute')
        matches = [p for p in pods.get('items', [])
                   if p.get('metadata', {}).get('name') == operator_ref['name']
                   and p.get('metadata', {}).get('uid') == operator_ref['uid']]
        legacy.require(len(matches) == 1
                       and source_maintenance.digest(matches[0]['spec']) == operator_ref['spec_sha256'],
                       'Actual unique reviewed operator required')
        return source_maintenance.verify_freeze(originals=originals, current=current,
                    pods=pods, operator=matches[0], review=review, gateway=gateway)

    await verify_external_freeze()
    from e2x_course_hub.course_service.app import CourseServiceApp
    legacy.private_bytes(console['config_path'], console['config_sha256'], root=True)
    probe = CourseServiceApp()
    probe.load_config_file(console['config_path'])
    legacy.require(local_only_configuration(probe.course_providers)
                   and probe.console_owner == 'cps'
                   and os.path.realpath(probe.database_path) == os.path.realpath(console['database_path'])
                   and os.path.realpath(probe.server_config_file) == os.path.realpath(console['server_config_path'])
                   and probe.compute_policy_url.rstrip('/') == console['compute_policy_url'].rstrip('/')
                   and probe.api_url.rstrip('/') == console['hub_api_url'].rstrip('/'),
                   'Captured local provider, paths and API endpoints required')
    await verify_external_freeze()
    app, service = legacy.load_configured_service(console['config_path'], console['config_sha256'],
                    source='cps', database_path=console['database_path'],
                    server_config_path=console['server_config_path'])
    APPS.append(app)
    legacy.require(local_only_configuration(app.course_providers)
                   and service.compute.base_url == console['compute_policy_url'].rstrip('/')
                   and service.hub.hub.api_url.rstrip('/') == console['hub_api_url'].rstrip('/'),
                   'Actual configured Source API endpoints required')

    async def read_registration(source, requested_workspace):
        legacy.require((source, requested_workspace) == ('cps', workspace),
                       'Only this reviewed Source workspace may be read')
        await verify_external_freeze()
        return await asyncio.to_thread(gateway_reader.get, source, requested_workspace)

    context = legacy.validate_context(dict(service=service, policy=policy,
              operator_qualification=qualification, authority_backend=backend,
              verify_external_freeze=verify_external_freeze, read_registration=read_registration))
    await verify_external_freeze()
    return context
