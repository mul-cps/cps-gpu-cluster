import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('binder_recipe', ROOT / 'recipe.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


@pytest.fixture
def original(tmp_path):
    root = tmp_path / 'source'; root.mkdir()
    git(root, 'init', '-q'); git(root, 'config', 'user.name', 'test'); git(root, 'config', 'user.email', 'test@invalid')
    for name in ('go.mod', 'go.sum', 'original.go'):
        (root / name).write_text(name + '\n')
    git(root, 'add', '.'); git(root, 'commit', '-qm', 'original')
    digest = lambda n: hashlib.sha256((root / n).read_bytes()).hexdigest()
    manifest = {'upstream_commit': git(root, 'rev-parse', 'HEAD'),
                'go_mod_sha256': digest('go.mod'), 'go_sum_sha256': digest('go.sum'),
                'files': [{'path':'original.go','original_sha256':digest('original.go')},
                          {'path':'new.go','original_sha256':None}]}
    return root, manifest


def test_default_cli_is_inert_without_files_or_commands(monkeypatch, capsys):
    def forbidden(*a, **kw): raise AssertionError('unexpected I/O')
    monkeypatch.setattr(recipe.subprocess, 'run', forbidden)
    monkeypatch.setattr(pathlib.Path, 'read_text', forbidden)
    assert recipe.main([]) == 0
    assert json.loads(capsys.readouterr().out)['mode'] == 'inert'


def test_clean_source_is_verified_without_modification(original):
    root, manifest = original
    before = git(root, 'status', '--porcelain', '--untracked-files=all')
    recipe.verify_checkout(root, manifest)
    assert git(root, 'status', '--porcelain', '--untracked-files=all') == before


@pytest.mark.parametrize('drift', ['head', 'tracked', 'untracked', 'ignored', 'hash'])
def test_invalid_source_is_refused_before_clone(original, drift):
    root, manifest = original
    if drift == 'head': manifest['upstream_commit'] = '1' * 40
    elif drift == 'tracked': (root / 'original.go').write_text('changed')
    elif drift == 'untracked': (root / 'extra').write_text('extra')
    elif drift == 'ignored':
        (root / '.git/info/exclude').write_text('hidden\n'); (root / 'hidden').write_text('extra')
    else: manifest['files'][0]['original_sha256'] = '0' * 64
    with pytest.raises(ValueError): recipe.verify_checkout(root, manifest)


def test_packaged_patch_and_all_twelve_pins_are_exact(tmp_path):
    manifest, patch = recipe.load_manifest()
    assert len(manifest['files']) == 12
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == '0d8f6978d49167788032753a3b153338be51c5a7ce2472ed77052ddca5036fae'
    bad = tmp_path / 'bad.patch'; bad.write_bytes(patch.read_bytes()+b'\n')
    with pytest.raises(ValueError): recipe.load_manifest(patch=bad)


def test_local_preparation_checks_all_bytes_and_preserves_original(original, tmp_path):
    root, manifest = original
    output = tmp_path / 'prepared'
    patch = tmp_path / 'change.patch'
    patch.write_text('diff --git a/original.go b/original.go\n--- a/original.go\n+++ b/original.go\n@@ -1 +1 @@\n-original.go\n+changed\n'
                     'diff --git a/new.go b/new.go\nnew file mode 100644\n--- /dev/null\n+++ b/new.go\n@@ -0,0 +1 @@\n+new\n')
    for row, raw in zip(manifest['files'], (b'changed\n',b'new\n')):
        row.update(patched_sha256=hashlib.sha256(raw).hexdigest(),patched_bytes=len(raw))
    recipe.prepare(root, output, manifest, patch)
    assert (output/'original.go').read_text() == 'changed\n'
    assert (root/'original.go').read_text() == 'original.go\n'
    assert not git(root,'status','--porcelain')
    with pytest.raises(ValueError): recipe.prepare(root, output, manifest, patch)


def test_wrong_postimage_never_reports_prepared(original, tmp_path):
    root, manifest = original
    manifest['files'][0].update(patched_sha256='0'*64,patched_bytes=1)
    patch=tmp_path/'empty.patch';patch.write_text('not a patch')
    with pytest.raises((ValueError,subprocess.CalledProcessError)):
        recipe.prepare(root,tmp_path/'out',manifest,patch)


def test_bad_toolchain_refuses_before_creating_output(original, tmp_path):
    root, _ = original
    archive = tmp_path/'bad.tar.gz'; archive.write_bytes(b'not trusted Go')
    output = tmp_path/'build'
    with pytest.raises(ValueError, match='toolchain archive'):
        recipe.main(['--build','--source',str(root),'--output',str(output),
                     '--toolchain-archive',str(archive)])
    assert not output.exists()
    assert not git(root,'status','--porcelain')


def test_patched_postimage_drift_is_rejected(original):
    root, manifest = original
    for row in manifest['files']:
        row.update(patched_sha256='0'*64,patched_bytes=0)
    with pytest.raises(ValueError,match='source bytes'):
        recipe.verify_files(root,manifest,patched=True)


def test_output_inside_source_never_mutates_original(original):
    root, manifest = original
    with pytest.raises(ValueError,match='outside'):
        recipe.prepare(root,root/'nested'/'out',manifest,ROOT/'terminal-guard.patch')
    assert not (root/'nested').exists()
    assert not git(root,'status','--porcelain')


def test_static_validator_rejects_real_dynamic_elf_and_corrupt_input(tmp_path):
    with pytest.raises(ValueError,match='interpreter'):
        recipe.verify_static_elf(pathlib.Path(sys.executable).resolve())
    bad=tmp_path/'bad';bad.write_bytes(b'not ELF')
    with pytest.raises(ValueError,match='ELF'):
        recipe.verify_static_elf(bad)
