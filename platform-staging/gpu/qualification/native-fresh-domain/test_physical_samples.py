import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('physical_samples',HERE/'physical_samples.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_default_inert(capsys,monkeypatch):
 m=module();monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:pytest.fail('inert dispatch'))
 m.main([]);assert '"state": "inert"' in capsys.readouterr().out

def test_integrity_checks_both_files_before_dispatch(monkeypatch):
 m=module();calls=[]
 def checked(path,pin):
  calls.append(path)
  if path.name=='lib':raise ValueError('pin')
 monkeypatch.setattr(m,'checked_file',checked);monkeypatch.setattr(m.os,'geteuid',lambda:0)
 monkeypatch.setattr(m.subprocess,'run',lambda *a,**k:pytest.fail('unverified dispatch'))
 with pytest.raises(ValueError):m.sample(Path('/bin'), 'a'*64,Path('/lib'),'b'*64)
 assert calls==[Path('/bin'),Path('/lib')]

def test_exact_query_four_samples(monkeypatch):
 m=module();calls=[];sleeps=[]
 monkeypatch.setattr(m,'checked_file',lambda *a:None);monkeypatch.setattr(m,'loader_link',lambda *a:None);monkeypatch.setattr(m,'epoch',lambda:None)
 monkeypatch.setattr(m.os,'geteuid',lambda:0);monkeypatch.setattr(m.time,'sleep',sleeps.append)
 def run(argv,**kw):
  calls.append((argv,kw));return SimpleNamespace(returncode=0,stdout=m.GPU+', 40000, 40960\n')
 monkeypatch.setattr(m.subprocess,'run',run)
 rows=m.sample(Path('/usr/bin/nvidia-smi'),'a'*64,Path('/usr/lib/libnvidia-ml.so.615.71.09'),'b'*64)
 assert len(rows)==len(calls)==4 and sleeps==[.5,.5,.5]
 assert all(r['free_bytes']==40000*1048576 and r['total_bytes']==40960*1048576 for r in rows)
 assert calls[0][0]==['/usr/bin/nvidia-smi','--id='+m.GPU,'--query-gpu=uuid,memory.free,memory.total','--format=csv,noheader,nounits']
 assert calls[0][1]['env']['LD_LIBRARY_PATH']=='/usr/lib'

@pytest.mark.parametrize('row',['GPU-foreign, 1, 2','{gpu}, -1, 2','{gpu}, 3, 2','{gpu}, 1.5, 2','{gpu}, 1, 2\n{gpu}, 1, 2'])
def test_parse_denies_unknown_or_partial_readback(row):
 m=module()
 with pytest.raises(ValueError):m.parse(row.format(gpu=m.GPU))

def test_pinned_file_denies_symlink_and_sha(tmp_path):
 m=module();p=tmp_path/'binary';p.write_bytes(b'x');p.chmod(0o500)
 with pytest.raises(ValueError):m.checked_file(p,'0'*64)
 link=tmp_path/'alias';link.symlink_to(p)
 with pytest.raises(ValueError):m.checked_file(link,m.hashlib.sha256(b'x').hexdigest())
