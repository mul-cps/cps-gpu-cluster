"""Read-only payload inventory, for both exact base and candidate."""
import hashlib,importlib.metadata as metadata,importlib.util,json
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
packages={}
for distribution in metadata.distributions():
    name=distribution.metadata['Name']
    files={}
    for f in distribution.files or []:
        p=Path(distribution.locate_file(f))
        if p.is_file():files[str(f)]=sha(p)
    packages[name]={'version':distribution.version,'files':files}
core=Path(importlib.util.find_spec('cps_compute').origin).parent
result={'packages':packages,'core':{p.name:sha(p) for p in core.glob('*.py')},'hub_present':bool(importlib.util.find_spec('cps_compute_hub')),
        'bundle':{p.name:sha(p) for p in Path('/opt/native').glob('*') if p.is_file()}}
print(json.dumps(result,sort_keys=True))
