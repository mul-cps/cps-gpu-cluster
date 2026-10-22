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


def test_actual_ubuntu147_header_and_ambiguous_denials():
    recipe=load()
    actual='#define UTS_RELEASE "6.8.0-147-generic"\n#define UTS_UBUNTU_RELEASE_ABI 147\n'
    recipe.validate_release(actual)
    for bad in (actual.replace('147-generic','134-generic'),actual+actual,
                actual.replace('ABI 147','ABI 134'),actual+'#define UTS_RELEASE "foreign"\n',
                actual.replace('"6.8.0-147-generic"','"6.8.0-147-generic" "foreign"')):
        with pytest.raises(ValueError):recipe.validate_release(bad)


def test_success_empty_exports_also_require_no_elf_exports(monkeypatch,tmp_path):
    recipe=load()
    def query(*args):return '' if args[0]=='modprobe' else '__ksymtab'
    monkeypatch.setattr(recipe,'query',query)
    with pytest.raises(ValueError,match='Unparsed module exports'):
        recipe.symbols('--show-exports',tmp_path/'uvm',allow_empty=True)


def version_entry(name,crc=0x12345678):
    import struct
    raw=name.encode()+b'\0';size=(8+len(raw)+3)//4*4
    return struct.pack('<II',size,crc)+raw+b'\0'*(size-8-len(raw))


def test_dynamic_versions_actual_packed_layout_and_terminal():
    recipe=load();body=version_entry('first')+version_entry('module_layout',7)+b'\0'*9
    assert recipe.parse_modversions(body)=={'first':0x12345678,'module_layout':7}


@pytest.mark.parametrize('fault',['short','unaligned','overrun','nonul','badname','duplicate','tail','terminal-crc','padding'])
def test_dynamic_versions_reject_malformed_fields(fault):
    import struct
    recipe=load();entry=version_entry('first');tail=b'\0'*9
    if fault=='short':body=b'x'*7
    elif fault=='unaligned':body=struct.pack('<I',15)+entry[4:]+tail
    elif fault=='overrun':body=struct.pack('<I',4096)+entry[4:]+tail
    elif fault=='nonul':body=entry[:8]+b'x'*(len(entry)-8)+tail
    elif fault=='badname':body=version_entry('bad/name')+tail
    elif fault=='duplicate':body=entry+entry+tail
    elif fault=='tail':body=entry+tail+b'\0'
    elif fault=='terminal-crc':body=entry+struct.pack('<II',0,1)+b'\0'
    else:body=entry[:-1]+b'x'+tail
    with pytest.raises(ValueError):recipe.parse_modversions(body)


def test_actual_retained_stock147_dynamic_versions_and_kernel_crcs():
    recipe=load()
    base=Path('/home/bjoern/.local/state/cps-full-project-20261013/gpu-recovery-20261022/kernel147-abi-inputs')
    if not base.exists():pytest.skip('Explicit retained147 ABI inputs unavailable')
    imports=recipe.modversion_imports(base/'stock/nvidia.ko')
    assert imports['__per_cpu_offset']==0xb19a5453 and len(imports)>400
    kernel={line.split()[1]:int(line.split()[0],16) for line in
            (base/'headers/linux-headers-6.8.0-147-generic/Module.symvers').read_text().splitlines()}
    assert recipe.verify_symbols(kernel,{},imports)==len(imports)
    changed=dict(imports);changed['__per_cpu_offset']^=1
    with pytest.raises(ValueError,match='CRC changed'):recipe.verify_symbols(kernel,{},changed)


def minimal_elf(body):
    import struct
    names=b'\0__versions\0.shstrtab\0';data=body+names
    shoff=(64+len(data)+7)//8*8
    header=struct.pack('<16sHHIQQQIHHHHHH',b'\x7fELF\x02\x01\x01'+b'\0'*9,1,62,1,0,0,shoff,0,64,0,0,64,3,2)
    sections=[(0,0,0,0,0,0,0,0,0,0),(1,1,2,0,64,len(body),0,0,4,0),
              (12,3,0,0,64+len(body),len(names),0,0,1,0)]
    return bytearray(header+data+b'\0'*(shoff-64-len(data))+b''.join(struct.pack('<IIQQQQIIQQ',*s) for s in sections))


def test_bounded_elf_section_extraction(tmp_path):
    recipe=load();path=tmp_path/'module.ko';path.write_bytes(minimal_elf(version_entry('first')+b'\0'*9))
    assert recipe.modversion_imports(path)=={'first':0x12345678}


@pytest.mark.parametrize('fault',['endianness','machine','section-table','string-index','version-offset','version-type','version-align','duplicate-section'])
def test_malformed_elf_never_selects_an_alternate_layout(tmp_path,fault):
    import struct
    recipe=load();raw=minimal_elf(version_entry('first')+b'\0'*9)
    shoff=struct.unpack_from('<Q',raw,40)[0]
    if fault=='endianness':raw[5]=2
    elif fault=='machine':struct.pack_into('<H',raw,18,183)
    elif fault=='section-table':struct.pack_into('<Q',raw,40,len(raw)+64)
    elif fault=='string-index':struct.pack_into('<H',raw,62,99)
    elif fault=='version-offset':struct.pack_into('<Q',raw,shoff+64+24,len(raw)+64)
    elif fault=='version-type':struct.pack_into('<I',raw,shoff+64+4,8)
    elif fault=='version-align':struct.pack_into('<Q',raw,shoff+64+48,3)
    else:raw[shoff:shoff+64]=raw[shoff+64:shoff+128]
    path=tmp_path/'bad.ko';path.write_bytes(raw)
    with pytest.raises(ValueError):recipe.modversion_imports(path)


def test_historical_stock134_to_qualified_delta_matches_new147():
    recipe=load()
    base=Path('/home/bjoern/.local/state')
    old=base/'cps-native-import-guard-20261009/final-retained-core'
    qualified=base/'cps-group-native-20261009/driver-optional-stack-f430b26/candidate-nvidia.ko'
    new=base/'cps-full-project-20261013/gpu-recovery-20261022/kernel147-module-compiled-output/nvidia.ko'
    if not all(p.exists() for p in (old,qualified,new)):pytest.skip('Explicit retained qualification inputs unavailable')
    import json
    receipt=json.loads((old/'baseline-receipt.json').read_text())['installedCore']
    raw=old/'installed-before.versions.raw'
    assert recipe.sha(raw)==receipt['versionsRawSha256']
    assert receipt['sha256']=='ed30b0cf47f71d24341d1fb1335b3e4598924bd07edcce4ef38e5ece100bdf0c'
    assert recipe.sha(qualified)=='4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421'
    before=recipe.parse_modversions(raw.read_bytes());after=recipe.modversion_imports(qualified)
    assert before=={row['symbol']:int(row['crc'],16) for row in receipt['crcSymbols']}
    assert all(after.get(k)==v for k,v in before.items())
    extras={'___ratelimit','__put_task_struct','cgrp_dfl_root','init_user_ns','ns_capable','param_ops_uint'}
    assert after.keys()-before.keys()==extras
    assert not after.keys()-before.keys()<={'cgrp_dfl_root'}  # old incremental expectation is wrong for stock
    assert recipe.modversion_imports(new).keys()==after.keys()


def actual147_imports():
    recipe=load();base=Path('/home/bjoern/.local/state/cps-full-project-20261013/gpu-recovery-20261022')
    if not (base/'kernel147-module-compiled-output/nvidia.ko').exists():pytest.skip('Actual147 candidate unavailable')
    return recipe,recipe.modversion_imports(base/'kernel147-abi-inputs/stock/nvidia.ko'),recipe.modversion_imports(base/'kernel147-module-compiled-output/nvidia.ko')


def test_exact_qualified_baseline_accepts_actual147():
    recipe,stock,candidate=actual147_imports()
    recipe.validate_import_baseline(stock,candidate)


@pytest.mark.parametrize('fault',['new-extra','missing-expected','missing-stock','changed-stock','wrong-hash'])
def test_exact_qualified_import_baseline_rejects_other_names_or_hash(monkeypatch,fault):
    recipe,stock,candidate=actual147_imports()
    if fault=='new-extra':candidate['foreign_extra']=1
    elif fault=='missing-expected':del candidate['param_ops_uint']
    elif fault=='missing-stock':del candidate['module_layout']
    elif fault=='changed-stock':candidate['module_layout']^=1
    else:monkeypatch.setattr(recipe,'QUALIFIED_IMPORT_NAMES_SHA','0'*64)
    with pytest.raises(ValueError):recipe.validate_import_baseline(stock,candidate)
