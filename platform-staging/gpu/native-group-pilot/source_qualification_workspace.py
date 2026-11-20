"""Separate operator-only qualification through the genuine console lifecycle.

Default invocation is inert. This does not use the migration freeze factory.
Root must finish migration, switch both Hubs, and retain the actual Start gates.
"""
import argparse
import asyncio
import hashlib
import json
import os
import stat

STAGE = '/tmp/cps-native-profile-qualification-20261011'
HANDOVER_SHA = '53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870'
SOURCES = {
    'cps': {'profile':'interactive-native-qualification-5', 'ceiling':{'cpu':'4','memory':'16Gi','gpuMemoryGiB':5}, 'actor': 'bjoern', 'workspace': 'native-group-b', 'group': 'native-pilot-group-b',
            'owner': 'cpsnativegroupb', 'namespace': 'jupyterhub',
            'config_sha': '4d82f1464127970eb8e3d0062092755f6ae2b4e3eb6072913b03cd9e36bb66b0'},
    'cit': {'profile':'interactive-native-qualification-10', 'ceiling':{'cpu':'4','memory':'16Gi','gpuMemoryGiB':10}, 'actor': 'akadmin', 'workspace': 'native-group-a', 'group': 'native-pilot-group-a',
            'owner': 'citnativegroupa', 'namespace': 'cit-jhub',
            'config_sha': 'b8677ce7ec494b0775bf099eb2db8157eca23c23f5c6819eb58dc9d799443171'},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def protected(path, expected_sha):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 10001 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) in (0o400, 0o600) and info.st_size <= 1024 * 1024,
                'Exact trusted operator-private regular source required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(1024 * 1024 + 1)
        require(len(raw) <= 1024 * 1024 and hashlib.sha256(raw).hexdigest() == expected_sha,
                'Exact pinned source bytes required')
        return raw
    finally:
        os.close(fd)


def workspace_guard(workspace, source):
    target = SOURCES[source]
    expected = {'id': target['workspace'], 'course_id': 'native-gpu-pilot-20261009',
                'term_id': 'qualification-20261009', 'group_id': target['group'],
                'hub_user': target['owner'], 'hub_server': 'rtc', 'namespace': target['namespace'],
                'pod': 'jupyter-' + target['owner'] + '--rtc', 'source': 'local',
                'profile': target['profile'], 'course_ceiling':target['ceiling']}
    require(type(workspace) is dict and all(workspace.get(k) == v for k, v in expected.items())
            and not workspace.get('archive_pending') and not workspace.get('archived'),
            'Exact source-owned migrated workspace required')


async def operate(service, source, operation):
    require(operation in ('get','start','stop'), 'Exact normal operation required')
    target = SOURCES[source]
    actor = await service.hub.hub.get_user(target['actor'])
    require(type(actor) is dict and actor.get('name') == target['actor'] and actor.get('admin') is True,
            'Fresh actual owning Hub administrator required')
    before = await service.get(target['workspace'])
    workspace_guard(before, source)
    if operation == 'start':
        require(before.get('state') == 'stopped', 'Normal Start requires stopped state')
        # This is the unmodified normal app lifecycle, including registration,
        # filesystem provisioning, Hub start, group/share sync and service cleanup.
        await service.start(target['workspace'], actor=target['actor'])
    elif operation == 'stop':
        # close is the existing audited app Stop: actual Hub stop, reservation
        # release after shutdown, Shares revocation, then persisted stopped.
        await service.close(target['workspace'], actor=target['actor'], archive=False)
    after = await service.get(target['workspace'])
    workspace_guard(after, source)
    require(operation != 'start' or after.get('state') == 'running', 'Normal Start must read back running')
    require(operation != 'stop' or after.get('state') == 'stopped', 'Normal Stop must read back stopped')
    return {'version': 1, 'source': source, 'actor': target['actor'], 'operation': operation,
            'before': before, 'workspace': after, 'normal_workspace_service': True}


async def execute(args):
    require(os.geteuid() == 10001, 'Exact trusted operator UID10001 required')
    protected(__file__, args.source_sha256)
    target = SOURCES[args.source]
    raw = protected(STAGE + '/source_qualification_handover.py', HANDOVER_SHA)
    namespace = {'__name__': 'pinned_normal_start_app_loader', '__file__': STAGE + '/source_qualification_handover.py'}
    exec(compile(raw, namespace['__file__'], 'exec'), namespace)
    closure=json.loads(protected(args.source_closure,args.source_closure_sha256))
    namespace['verify_source_closure'](closure)
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    policy=Policy(json.loads(protected(args.policy,args.policy_sha256)))
    mode=NativeGroupQualification.from_config(json.loads(protected(args.qualification_config,args.qualification_config_sha256)),policy)
    require(mode is not None and set(mode.workspaces)=={'cps:native-group-b','cit:native-group-a'}
        and set(mode.profiles)=={'interactive-native-qualification-5','interactive-native-qualification-10'}
        and mode.approval(args.source,target['workspace'])['profiles']==[target['profile']],
        'Exact bounded CPS5/CIT10 operator qualification required')
    app, service = namespace['load_configured_service'](
        STAGE + '/config.py', target['config_sha'], source=args.source,
        database_path='/data/courses.sqlite', server_config_path='/data/config.yml')
    from e2x_course_hub.cps.workspaces import WorkspaceService
    require(type(service) is WorkspaceService and app.console_owner == args.source
            and app.service_prefix == '/services/' + args.source + '-admin/'
            and service.provider is app.tornado_settings['course_provider']
            and service.compute is app.tornado_settings['compute_policy']
            and service.compute.console == args.source
            and service.compute.base_url == 'https://compute-gateway.cps-compute.svc.cluster.local:8000'
            and service.hub.hub.api_url.rstrip('/') == 'http://hub.' + target['namespace'] + '.svc.cluster.local:8081/hub/api',
            'Genuine owning app service/endpoints required')
    # Actual source-owned central registration must match the typed mode before
    # Start/Stop. This uses the genuine configured Source credential and endpoint.
    from urllib.parse import quote
    registered=await service.compute._request('workspaces/'+quote(target['workspace'],safe=''))
    mode.authorize(args.source,registered,target['profile'])
    return await operate(service, args.source, args.operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--source', choices=tuple(SOURCES))
    parser.add_argument('--operation', choices=('get', 'start', 'stop'))
    parser.add_argument('--source-sha256')
    for field in ('source-closure','policy','qualification-config'):
        parser.add_argument('--'+field)
        parser.add_argument('--'+field+'-sha256')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'version': 1, 'state': 'inert', 'live_execution': False}, sort_keys=True))
        return
    require(args.source and args.operation and args.source_sha256
        and all(getattr(args,k.replace('-','_')) for k in ('source-closure','source-closure-sha256','policy','policy-sha256','qualification-config','qualification-config-sha256')),
        'Explicit source, operation and protected typed configuration/closure pins required')
    print(json.dumps(asyncio.run(execute(args)), sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
