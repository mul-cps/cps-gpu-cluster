import importlib.util
import json
import re
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('binder_oci',ROOT/'oci.py')
module=importlib.util.module_from_spec(spec)
if spec.loader is not None and (ROOT/'oci.py').exists():spec.loader.exec_module(module)


def test_dockerfile_provenance_matches_verified_binary_and_patch():
    dockerfile=(ROOT/'Dockerfile').read_text()
    labels=dict(re.findall(r'(org\.mul-cps\.[\w.-]+)="([^"]+)"',dockerfile))
    assert labels==module.LABELS
    assert dockerfile.splitlines()[0]=='FROM '+module.BASE


def test_default_does_no_build_io(monkeypatch,capsys):
    def forbidden(*a,**kw):raise AssertionError('unexpected process/file read')
    monkeypatch.setattr(module,'command',forbidden)
    monkeypatch.setattr(Path,'read_bytes',forbidden)
    monkeypatch.setattr(Path,'read_text',forbidden)
    assert module.main([])==0
    assert json.loads(capsys.readouterr().out)['published'] is False


def test_rejects_binary_mismatch_before_any_container_call(tmp_path):
    binary=tmp_path/'binder';binary.write_bytes(b'not trusted')
    with pytest.raises(ValueError,match='binary'):
        module.verify_inputs(binary,tmp_path/'missing-receipt')


@pytest.mark.parametrize('field,value',[('User','0'),('Entrypoint',['/bin/sh']),('Env',[]),('WorkingDir','/')])
def test_stock_runtime_drift_is_refused(field,value):
    config=dict(module.STOCK_CONFIG);config[field]=value
    with pytest.raises(ValueError,match='stock'):
        module.verify_stock_config(config)


def test_exact_stock_config_and_added_labels_preserve_everything_else():
    module.verify_stock_config(module.STOCK_CONFIG)
    candidate=dict(module.STOCK_CONFIG,Labels=module.LABELS)
    module.verify_candidate_config(module.STOCK_CONFIG,candidate)
    candidate['Cmd']=['--enabled']
    with pytest.raises(ValueError,match='runtime'):
        module.verify_candidate_config(module.STOCK_CONFIG,candidate)


@pytest.mark.parametrize('field,value',[
    ('binary_sha256','0'*64),('patch_sha256','0'*64),('upstream_commit','0'*40),
    ('source_files',[]),('rebuild_identical',False),('CGO_ENABLED',1),
    ('all_affected_packages_passed',[]),
])
def test_drifted_build_provenance_is_refused(field,value):
    manifest,_=module.recipe.load_manifest()
    receipt={'binary_sha256':module.BINARY_SHA,'patch_sha256':module.recipe.PATCH_SHA256,
             'upstream_commit':module.recipe.COMMIT,'toolchain_sha256':module.recipe.TOOLCHAIN_SHA256,
             'source_files':manifest['files'],'rebuild_identical':True,'CGO_ENABLED':0,
             'go_version':module.recipe.GO_VERSION,'all_affected_packages_passed':list(module.recipe.PACKAGES)}
    module.verify_build_receipt(receipt,manifest)
    receipt[field]=value
    with pytest.raises(ValueError,match='build receipt'):
        module.verify_build_receipt(receipt,manifest)
