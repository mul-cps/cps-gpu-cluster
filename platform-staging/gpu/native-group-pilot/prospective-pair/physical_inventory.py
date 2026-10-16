"""Reconcile complete selected-device inventory with journals and a Root baseline.

Retained untracked MAX-limit rows are not workflow cleanup evidence. Only an
independently pinned exact baseline can account for them, while every workflow
retirement must still match its typed journal and finite physical limits.
"""
import copy
import hashlib
import json

import qualification_configuration_inverse as custody
import terminal_policy_proposal as terminal
import node_agent as guard

ROW_FIELDS={'cgroup_id','kernfs_id','inode','offline','pinned','default_hierarchy','used','soft','hard'}
EPOCH=('node','node_uid','gpu_uuid','boot_id','driver_generation')
MAX=(1<<64)-1


def physical_observation(*,capture,node,inventory,baseline_raw,baseline_sha256,observed_at_ns):
    guard.require(isinstance(baseline_raw,bytes) and len(baseline_raw)<=65536
        and hashlib.sha256(baseline_raw).hexdigest()==baseline_sha256,'Independent raw inert-baseline pin required')
    baseline=guard.parse(baseline_raw)
    guard.closed(baseline,{'version','node_pool','baseline_capture_sha256','rows'},'Closed reviewed inert baseline required')
    guard.require(type(baseline['version']) is int and baseline['version']==1
        and baseline['node_pool']=={k:node['pool'][k] for k in EPOCH}
        and custody.bare_sha(baseline['baseline_capture_sha256'])
        and isinstance(baseline['rows'],list) and len(baseline['rows'])<=32,
        'Same-epoch bounded retained baseline and original capture hash required')
    guard.closed(inventory,{'version','backend','gpu_uuid','gpu_id','entries'},'Full selected-device inventory required')
    guard.require(type(inventory['version']) is int and inventory['version']==1 and inventory['backend']=='misc-fallback'
        and inventory['gpu_uuid']==node['pool']['gpu_uuid'] and type(inventory['gpu_id']) is int
        and 0 <= inventory['gpu_id'] < 2**32 and isinstance(inventory['entries'],list)
        and len(inventory['entries'])<=256 and type(observed_at_ns) is int and observed_at_ns>0,
        'Actual selected-device misc inventory and observation time required')
    def indexed(rows):
        result={}
        for row in rows:
            guard.closed(row,ROW_FIELDS,'Closed current native inventory row required')
            guard.require(all(type(row[k]) is int and 0<row[k]<=MAX for k in ('inode','cgroup_id','kernfs_id'))
                and row['cgroup_id']==row['kernfs_id'] and row['inode'] not in result
                and all(type(row[k]) is int and 0<=row[k]<=MAX for k in ('used','soft','hard'))
                and all(type(row[k]) is bool for k in ('offline','pinned','default_hierarchy')),
                'Unique complete typed physical identities required')
            result[row['inode']]=row
        return result
    current=indexed(inventory['entries']);retained=indexed(baseline['rows'])
    for inode,row in retained.items():
        guard.require(row['offline'] is row['pinned'] is row['default_hierarchy'] is True
            and row['used']==0 and row['soft']==0 and row['hard']==MAX and current.get(inode)==row,
            'Every retained default must remain exact, offline, pinned, default-limit and uncharged')
    _,records=custody.history_records(capture,node)
    guard.require(not (set(retained)&{r.identity.cgroup_inode for r in records.values()}),
        'A retained default cannot replace or overlap a workflow lifetime')
    physical=copy.deepcopy(capture['physical'])
    physical['observed_at_ns']=observed_at_ns
    physical['inventory_sha256']=terminal.raw_sha(terminal.canonical(inventory).encode())
    checked=custody.physical_records({**capture,'physical':physical},node,records)
    expected={row['inventory_row']['inode']:row['inventory_row'] for row in checked.values()}
    guard.require(len(expected)==len(checked) and set(current)==set(expected)|set(retained)
        and all(current.get(inode)==row for inode,row in expected.items()),
        'Every actual inventory row must match a workflow retirement or explicit retained baseline')
    return physical
