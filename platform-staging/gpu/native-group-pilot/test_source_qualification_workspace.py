"""CPU checks of proposal guards; these do not qualify real Start or console HTTP."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import AsyncMock

import source_qualification_workspace as proposal


def workspace(source, state='stopped'):
    target = proposal.SOURCES[source]
    return {'id': target['workspace'], 'course_id': 'native-gpu-pilot-20261009',
            'term_id': 'qualification-20261009', 'group_id': target['group'],
            'hub_user': target['owner'], 'hub_server': 'rtc', 'namespace': target['namespace'],
            'pod': 'jupyter-' + target['owner'] + '--rtc', 'source': 'local',
            'profile': target['profile'], 'course_ceiling': target['ceiling'], 'state': state}


class NormalSourceProposalTests(unittest.TestCase):
    def test_default_inert_without_app_import_or_source_paths(self):
        result = subprocess.run([sys.executable, str(Path(proposal.__file__))],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout),
                         {'version': 1, 'state': 'inert', 'live_execution': False})

    def test_exact_source_binding_and_canonical_profile(self):
        for source in proposal.SOURCES:
            proposal.workspace_guard(workspace(source), source)
            for field, value in [('id', 'other'), ('source', 'external'),
                                 ('profile', 'interactive-shared-5'), ('course_ceiling', {'cpu':'4','memory':'16Gi','gpuMemoryGiB':20}), ('hub_user', 'other'),
                                 ('namespace', 'other'), ('archived', True)]:
                with self.subTest(source=source, field=field), self.assertRaises(ValueError):
                    proposal.workspace_guard({**workspace(source), field: value}, source)

    def test_fresh_actor_denial_precedes_workspace_or_start(self):
        for source in proposal.SOURCES:
            for actor in ({'name': 'other', 'admin': True},
                          {'name': proposal.SOURCES[source]['actor'], 'admin': False}):
                service = types.SimpleNamespace(
                    hub=types.SimpleNamespace(hub=types.SimpleNamespace(get_user=AsyncMock(return_value=actor))),
                    get=AsyncMock(), start=AsyncMock())
                with self.assertRaises(ValueError):
                    asyncio.run(proposal.operate(service, source, 'start'))
                service.get.assert_not_called()
                service.start.assert_not_called()

    def test_start_calls_only_normal_service_then_gets_same_workspace(self):
        for source in proposal.SOURCES:
            target = proposal.SOURCES[source]
            service = types.SimpleNamespace(
                hub=types.SimpleNamespace(hub=types.SimpleNamespace(
                    get_user=AsyncMock(return_value={'name': target['actor'], 'admin': True}))),
                get=AsyncMock(side_effect=[workspace(source), workspace(source, 'running')]),
                start=AsyncMock())
            result = asyncio.run(proposal.operate(service, source, 'start'))
            service.start.assert_awaited_once_with(target['workspace'], actor=target['actor'])
            self.assertEqual([call.args for call in service.get.await_args_list],
                             [(target['workspace'],), (target['workspace'],)])
            self.assertEqual(result['workspace']['state'], 'running')

    def test_stop_uses_normal_audited_close_without_archive(self):
        for source in proposal.SOURCES:
            target=proposal.SOURCES[source]
            service=types.SimpleNamespace(
                hub=types.SimpleNamespace(hub=types.SimpleNamespace(
                    get_user=AsyncMock(return_value={'name':target['actor'],'admin':True}))),
                get=AsyncMock(side_effect=[workspace(source,'running'),workspace(source)]),
                start=AsyncMock(),close=AsyncMock())
            result=asyncio.run(proposal.operate(service,source,'stop'))
            service.close.assert_awaited_once_with(target['workspace'],actor=target['actor'],archive=False)
            service.start.assert_not_called()
            self.assertEqual(result['workspace']['state'],'stopped')

    def test_get_and_unresolved_state_do_not_start(self):
        for operation, state in [('get', 'running'), ('start', 'starting'), ('start', 'reconciling')]:
            service = types.SimpleNamespace(
                hub=types.SimpleNamespace(hub=types.SimpleNamespace(
                    get_user=AsyncMock(return_value={'name': 'bjoern', 'admin': True}))),
                get=AsyncMock(return_value=workspace('cps', state)), start=AsyncMock())
            if operation == 'get':
                asyncio.run(proposal.operate(service, 'cps', operation))
            else:
                with self.assertRaises(ValueError):
                    asyncio.run(proposal.operate(service, 'cps', operation))
            service.start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
