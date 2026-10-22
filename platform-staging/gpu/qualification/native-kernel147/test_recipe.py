import importlib.util
from pathlib import Path
import pytest

HERE=Path(__file__).parent

def load():
    spec=importlib.util.spec_from_file_location('recipe',HERE/'recipe.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_closed_target_and_symbol_closure():
    recipe=load()
    assert recipe.KERNEL=='6.8.0-147-generic'
    assert recipe.verify_symbols({'kernel':1},{'driver':2},{'kernel':1,'driver':2})==2
    with pytest.raises(ValueError):recipe.verify_symbols({'kernel':1},{'driver':2},{'kernel':9})
    with pytest.raises(ValueError):recipe.verify_symbols({'kernel':1},{'driver':2},{'unknown':2})


def test_abi_stock_exports_and_uvm_imports():
    recipe=load()
    expected={'x':1,'module_layout':2}
    recipe.require_same(expected,dict(expected),'imports')
    with pytest.raises(ValueError):recipe.require_same(expected,{'x':1},'imports')


def test_safe_archive_paths():
    recipe=load()
    assert recipe.safe_name('./kernel-open/Makefile')=='kernel-open/Makefile'
    for name in ('/etc/passwd','../escape','a/../../escape'):
        with pytest.raises(ValueError):recipe.safe_name(name)


def test_wrong_target_stops_before_any_module_tool(tmp_path,monkeypatch):
    recipe=load();headers=tmp_path/'headers'
    (headers/'include/generated').mkdir(parents=True)
    (headers/'include/generated/utsrelease.h').write_text('#define UTS_RELEASE "6.8.0-134-generic"\n')
    def forbidden(*args,**kwargs):raise AssertionError('Module tool reached with wrong headers')
    monkeypatch.setattr(recipe,'query',forbidden)
    with pytest.raises(ValueError,match='Actual target headers'):
        recipe.verify(headers,*[tmp_path/'unused']*4)


def test_changed_source_input_never_creates_output(tmp_path):
    recipe=load();bad=tmp_path/'bad';bad.write_bytes(b'changed')
    output=tmp_path/'output'
    with pytest.raises(ValueError,match='Pinned source input'):
        recipe.prepare(bad,bad,bad,bad,output)
    assert not output.exists()


def test_uvm_empty_exports_require_actual_absent_export_section(monkeypatch,tmp_path):
    import subprocess
    recipe=load()
    def no_exports(*args):
        if args[0]=='modprobe':raise subprocess.CalledProcessError(1,args)
        assert args[:3]==('readelf','--wide','--sections')
        return 'There are 12 section headers: .text .modinfo __versions'
    monkeypatch.setattr(recipe,'query',no_exports)
    assert recipe.symbols('--show-exports',tmp_path/'uvm',allow_empty=True)=={}
    with pytest.raises(subprocess.CalledProcessError):recipe.symbols('--show-exports',tmp_path/'core')
    def hidden_exports(*args):
        if args[0]=='modprobe':raise subprocess.CalledProcessError(1,args)
        return '__ksymtab'
    monkeypatch.setattr(recipe,'query',hidden_exports)
    with pytest.raises(ValueError):recipe.symbols('--show-exports',tmp_path/'uvm',allow_empty=True)
