"""Retained unrelated default rows cannot stand in for workflow retirements."""
import copy,hashlib,importlib.util,json
from pathlib import Path
import sys
import pytest
HERE=Path(__file__).parent;sys.path[:0]=[str(HERE),str(HERE.parent)]
import test_configuration_inverse as prior


def helper():
    path=HERE/'physical_inventory.py'
    assert path.exists(),'Full physical inventory reconciler required'
    spec=importlib.util.spec_from_file_location('physical_inventory',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def fixture():
    args=prior.fixture();final=args['final'];node=json.loads(args['current']['data']['config.json'])
    rows=[copy.deepcopy(r['inventory_row']) for r in final['physical']['retired_caps']]
    inert=dict(cgroup_id=99999,kernfs_id=99999,inode=99999,offline=True,pinned=True,default_hierarchy=True,used=0,soft=0,hard=2**64-1)
    inventory=dict(version=1,backend='misc-fallback',gpu_uuid=node['pool']['gpu_uuid'],gpu_id=77,entries=rows+[inert])
    baseline=dict(version=1,node_pool={k:node['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')},
        baseline_capture_sha256='a'*64,rows=[inert])
    raw=json.dumps(baseline,sort_keys=True).encode()
    return dict(capture=final,node=node,inventory=inventory,baseline_raw=raw,baseline_sha256=hashlib.sha256(raw).hexdigest())


def test_complete_inventory_preserves_finite_records_and_explicit_inert_baseline():
    args=fixture();before=copy.deepcopy(args)
    result=helper().physical_observation(**args,observed_at_ns=2)
    assert result['retired_caps']==args['capture']['physical']['retired_caps']
    assert result['inventory_sha256']=='sha256:'+hashlib.sha256(prior.terminal.canonical(args['inventory']).encode()).hexdigest()
    assert result['targets']==[] and args==before


@pytest.mark.parametrize('fault',['pin','epoch','charged','active','finite-default','unpinned','foreign-extra','missing-default','missing-finite','changed-finite','duplicate','future-recovery'])
def test_unattributed_rows_cannot_hide_changed_or_missing_workflow_caps(fault):
    args=fixture();rows=args['inventory']['entries'];base=json.loads(args['baseline_raw'])
    if fault=='pin':args['baseline_sha256']='0'*64
    elif fault=='epoch':base['node_pool']['boot_id']=prior.uid(999)
    elif fault=='charged':rows[-1]['used']=1
    elif fault=='active':rows[-1]['offline']=False
    elif fault=='finite-default':rows[-1]['hard']=5120*1048576
    elif fault=='unpinned':rows[-1]['pinned']=False
    elif fault=='foreign-extra':rows.append({**rows[-1],'inode':99998,'cgroup_id':99998,'kernfs_id':99998})
    elif fault=='missing-default':rows.pop()
    elif fault=='missing-finite':rows.pop(0)
    elif fault=='changed-finite':rows[0]['hard']=2**64-1
    elif fault=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif fault=='future-recovery':args['capture']['physical']['retired_caps'][0]['pod_uid']=prior.uid(999)
    if fault=='epoch':args['baseline_raw']=json.dumps(base,sort_keys=True).encode();args['baseline_sha256']=hashlib.sha256(args['baseline_raw']).hexdigest()
    with pytest.raises(ValueError):helper().physical_observation(**args,observed_at_ns=2)
