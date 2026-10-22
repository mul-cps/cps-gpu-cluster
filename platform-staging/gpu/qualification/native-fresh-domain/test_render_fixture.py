import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).parent


def renderer():
    spec = importlib.util.spec_from_file_location('fresh_qa_renderer', HERE / 'render_fixture.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def request():
    return {'version': 1, 'namespace': 'cps-native-qa147-20261022',
            'namespace_uid': '1f7d941a-872d-4453-a1ba-fd489d8aff14',
            'gate_image': 'ghcr.io/mul-cps/cps-compute@sha256:' + 'a' * 64,
            'policy_hash': 'sha256:' + 'b' * 64}


def test_real_compiler_qa_pods_have_exact_root_gate_nonroot_main_and_separate_state():
    r = renderer()
    result = r.render(request(), approve_qa_hostpaths=True)
    assert result['live_applied'] is False and result['hardware_qualified'] is False
    assert result['namespace_uid'] == request()['namespace_uid']
    assert len(result['pods']) == 2
    for pod in result['pods'].values():
        spec = pod['spec']
        assert spec['nodeName'] == 'k3s-wk-gpu2'
        assert [c['name'] for c in spec['initContainers']] == ['cps-native-cap-gate', 'cps-native-device-identity']
        gate, identity = spec['initContainers']
        assert gate['command'][:4] == ['python', '-I', '-S', '-c']
        assert gate['securityContext']['runAsUser'] == 0
        assert identity['securityContext']['runAsUser'] == 1000
        main, = spec['containers']
        assert main['name'] == 'notebook' and main['securityContext']['runAsUser'] == 1000
        assert main['securityContext']['runAsGroup'] == 100
        assert not spec['automountServiceAccountToken']
        assert not any(v.get('hostPath') for v in spec['volumes'] if v['name'] in {m['name'] for m in main['volumeMounts']})
        paths = {v['name']: v.get('hostPath', {}).get('path') for v in spec['volumes']}
        assert paths['cps-native-receipts'] == r.QA_STATE + '/receipts'
        assert paths['cps-native-authority'] == r.LOAD_AUTHORITY
        assert pod['metadata']['annotations'][r.runtime.SPEC_ANNOTATION] == r.runtime.native_spec_sha256(pod)
    cm = result['source_configmap']
    assert cm['immutable'] is True
    assert set(cm['data']) == {'__init__.py', 'native_gpu_runtime.py', 'native_gpu_health.py'}
    assert 'CUDA' not in json.dumps(result['pods']['a']['spec']['containers'][0]['command'])


def test_explicit_hostpath_review_required():
    with pytest.raises(ValueError, match='hostPath'):
        renderer().render(request())

def test_reviewed_new_cohort_has_distinct_names_state_and_no_original_state_reuse():
    r=renderer();value=request();value['cohort_uid']='6ba3353d-bf13-4cad-9c35-3119dd279a67'
    result=r.render(value,approve_qa_hostpaths=True)
    assert result['qa_state'].endswith('/cohorts/'+value['cohort_uid']+'/state')
    assert {p['metadata']['name'] for p in result['pods'].values()}=={'native-qa147-a-6ba3353d','native-qa147-b-6ba3353d'}
    for pod in result['pods'].values():
        paths={v['name']:v.get('hostPath',{}).get('path') for v in pod['spec']['volumes']}
        assert paths['cps-native-receipts']==result['qa_state']+'/receipts'
    for bad in ('../state','00000000-0000-0000-0000-000000000000',True):
        value['cohort_uid']=bad
        with pytest.raises(ValueError):r.render(value,approve_qa_hostpaths=True)


def test_gate_executes_only_bundled_sdk_despite_installed_or_cwd_shadow(tmp_path):
    r = renderer()
    result = r.render(request(), approve_qa_hostpaths=True)
    package = tmp_path / 'immutable-package' / 'cps_compute'
    package.mkdir(parents=True)
    for name, source in result['source_configmap']['data'].items(): (package / name).write_text(source)
    cwd = tmp_path / 'old-installed-cwd'
    (cwd / 'cps_compute').mkdir(parents=True)
    (cwd / 'cps_compute/__init__.py').write_text('raise RuntimeError("OLD SDK IMPORTED")')
    command = result['pods']['a']['spec']['initContainers'][0]['command']
    command = [sys.executable, *[arg.replace('/opt/cps-qa', str(package.parent)) for arg in command[1:]], '--help']
    actual = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=5)
    assert actual.returncode == 0, actual.stderr
    assert 'wait-for-cap' in actual.stdout and 'OLD SDK IMPORTED' not in actual.stderr
