import copy
import importlib.util
import json
from pathlib import Path
import hashlib
import pytest

P=Path(__file__).with_name('selected_cdi.py')
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
OTHER='GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'

def module():
    s=importlib.util.spec_from_file_location('selected_cdi',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixture():
    m=module()
    def device(gpu,minor):return {'name':gpu,'containerEdits':{'deviceNodes':[{'path':'/dev/nvidia'+str(minor),'hostPath':'/run/nvidia/driver/dev/nvidia'+str(minor)}]}}
    source={'cdiVersion':'0.5.0','kind':'k8s.device-plugin.nvidia.com/gpu','containerEdits':{'env':['NVIDIA_VISIBLE_DEVICES=void']},'devices':[device(GPU,0),device(OTHER,1)]}
    raw=m.canonical(source)
    pins=m.cdi.CDIRuntimePins.from_dict({'version':1,'common_edits_sha256':m.cdi.sha(source['containerEdits']),
        'selected_filename':m.OUTPUT,'other_cdi_files':{m.SOURCE:hashlib.sha256(raw).hexdigest()},'runtime_files':{'etc/runtime.toml':'a'*64}})
    inventory=[{'gpu_uuid':GPU,'pci_bdf':'0000:01:00.0','minor':0,'device':{'major':195,'minor':0}},
        {'gpu_uuid':OTHER,'pci_bdf':'0000:02:00.0','minor':1,'device':{'major':195,'minor':1}}]
    return m,source,raw,pins,inventory

def test_exact_single_uuid_and_unmodified_common_edits():
    m,s,raw,pins,inv=fixture();result=m.render(raw,pins,inv,GPU)
    expected=copy.deepcopy(s);expected['kind']='management.nvidia.com/gpu';expected['devices']=expected['devices'][:1]
    assert result==m.canonical(expected)
    assert s['devices'][1]['name']==OTHER

@pytest.mark.parametrize('fault',['hash','all','duplicate','minor','hostpath','common','kind','unknownkey','duplicatejson'])
def test_bad_source_or_mapping_denied(fault):
    m,s,raw,pins,inv=fixture()
    if fault=='hash':raw+=b' '
    elif fault=='all':s['devices'][0]['name']='all'
    elif fault=='duplicate':s['devices'].append(copy.deepcopy(s['devices'][0]))
    elif fault=='minor':inv[0]['minor']=2;inv[0]['device']['minor']=2
    elif fault=='hostpath':s['devices'][0]['containerEdits']['deviceNodes'][0]['hostPath']='/dev/nvidia0'
    elif fault=='common':s['containerEdits']['env'].append('EVIL=1')
    elif fault=='kind':s['kind']='other/gpu'
    elif fault=='unknownkey':s['extra']=True
    elif fault=='duplicatejson':raw=b'{"kind":1,"kind":2}'
    if fault not in ('hash','duplicatejson','minor'):
        raw=m.canonical(s)
        # Independently reviewed source hash does not authorize unsafe selected mapping/schema.
        data=pins.to_dict();data['other_cdi_files'][m.SOURCE]=hashlib.sha256(raw).hexdigest();pins=m.cdi.CDIRuntimePins.from_dict(data)
    with pytest.raises(ValueError):m.render(raw,pins,inv,GPU)


def test_atomic_publication_preserves_every_provider_and_existing_wrong_target(tmp_path):
    import os
    m=module();directory=tmp_path/'cdi';directory.mkdir(mode=0o755)
    source=directory/m.SOURCE;source.write_bytes(b'provider-unchanged')
    events=[]
    m.publish(directory,b'new',before=lambda **kw:events.append('before'),after=lambda:events.append('after'),trusted_uid=os.getuid())
    assert (directory/m.OUTPUT).read_bytes()==b'new' and source.read_bytes()==b'provider-unchanged'
    assert len(list(directory.iterdir()))==2 and events==['before','before','after']
    m.publish(directory,b'new',before=lambda **kw:None,after=lambda:None,trusted_uid=os.getuid())
    with pytest.raises(ValueError):m.publish(directory,b'wrong',before=lambda **kw:None,after=lambda:None,trusted_uid=os.getuid())
    assert (directory/m.OUTPUT).read_bytes()==b'new'


def test_failed_final_epoch_before_publish_leaves_no_target_or_temporary(tmp_path):
    import os
    m=module();count=0
    def check(**kw):
        nonlocal count
        count+=1
        if count==2:raise ValueError('epoch-changed')
    with pytest.raises(ValueError):m.publish(tmp_path,b'data',before=check,after=lambda:None,trusted_uid=os.getuid())
    assert list(tmp_path.iterdir())==[]


def test_symlink_output_is_never_followed(tmp_path):
    import os
    m=module();victim=tmp_path/'victim';victim.write_bytes(b'preserve')
    (tmp_path/m.OUTPUT).symlink_to(victim)
    with pytest.raises(OSError):m.publish(tmp_path,b'other',before=lambda **kw:None,after=lambda:None,trusted_uid=os.getuid())
    assert victim.read_bytes()==b'preserve'


def test_real_search_brackets_missing_output_atomic_publish(tmp_path,monkeypatch):
    import os
    m,s,raw,pins,inv=fixture();root=tmp_path/'host';directory=root/'run/cdi';directory.mkdir(parents=True)
    (directory/m.SOURCE).write_bytes(raw);runtime=root/'etc/runtime.toml';runtime.parent.mkdir();runtime.write_bytes(b'runtime')
    data=pins.to_dict();data['runtime_files']['etc/runtime.toml']=hashlib.sha256(b'runtime').hexdigest();pins=m.cdi.CDIRuntimePins.from_dict(data)
    read=m.cdi.read_root_file
    monkeypatch.setattr(m.cdi,'read_root_file',lambda path,**kw:read(path,trusted_uid=os.getuid()))
    result=m.render(raw,pins,inv,GPU)
    m.publish(directory,result,before=lambda **kw:m._search_precheck(root,pins,trusted_uid=os.getuid(),**kw),
        after=lambda:m._search_precheck(root,pins),trusted_uid=os.getuid())
    assert (directory/m.OUTPUT).read_bytes()==result
    assert set(p.name for p in directory.iterdir())=={m.SOURCE,m.OUTPUT}


def test_real_staged_search_still_denies_foreign_provider(tmp_path,monkeypatch):
    import os
    m,s,raw,pins,inv=fixture();root=tmp_path/'host';directory=root/'run/cdi';directory.mkdir(parents=True)
    (directory/m.SOURCE).write_bytes(raw);runtime=root/'etc/runtime.toml';runtime.parent.mkdir();runtime.write_bytes(b'runtime')
    data=pins.to_dict();data['runtime_files']['etc/runtime.toml']=hashlib.sha256(b'runtime').hexdigest();pins=m.cdi.CDIRuntimePins.from_dict(data)
    read=m.cdi.read_root_file
    monkeypatch.setattr(m.cdi,'read_root_file',lambda path,**kw:read(path,trusted_uid=os.getuid()))
    def before(**kw):
        if kw:(directory/'foreign.json').write_bytes(b'foreign')
        m._search_precheck(root,pins,trusted_uid=os.getuid(),**kw)
    with pytest.raises(ValueError,match='Unreviewed CDI provider'):
        m.publish(directory,m.render(raw,pins,inv,GPU),before=before,after=lambda:None,trusted_uid=os.getuid())
    assert not (directory/m.OUTPUT).exists()
    assert set(p.name for p in directory.iterdir())=={m.SOURCE,'foreign.json'}
