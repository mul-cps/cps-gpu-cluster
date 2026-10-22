import copy
import importlib.util
from pathlib import Path
import hashlib
import json
import pytest

HERE=Path(__file__).parent

def module():
    s=importlib.util.spec_from_file_location('fresh_preflight',HERE/'fresh_preflight.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def manifest():
    return {'version':1,'cohort_uid':'6ba3353d-bf13-4cad-9c35-3119dd279a67',
        'namespace_uid':'1f7d941a-872d-4453-a1ba-fd489d8aff14',
        'pods':{k:{'namespace':'cps-native-qa147-20261022','name':'native-qa147-'+k+'-6ba3353d',
        'uid':'00000000-0000-4000-8000-00000000000'+str(n),'cap_mib':5120,'spec_sha256':'a'*64}
        for n,k in enumerate(('a','b'),1)},
        'observer_argv':['ssh','root-reviewed-host','python3','-I','-B','observe.py','--execute',
                         '--cohort-uid','6ba3353d-bf13-4cad-9c35-3119dd279a67'],
        'physical_argv':['ssh','root-reviewed-host','python3','-I','-B','physical_samples.py','--execute']}

def test_closed_actual_cohort_manifest_and_foreign_or_ambiguous_targets_deny():
    m=module();value=manifest();assert m.validate_targets(value)==value
    for mutation in ('namespace','name','same-uid','capacity','extra','no-execute','wrong-cohort-command'):
        bad=copy.deepcopy(value)
        if mutation=='namespace':bad['pods']['a']['namespace']='old-native-domain'
        elif mutation=='name':bad['pods']['a']['name']='native-qa147-a'
        elif mutation=='same-uid':bad['pods']['b']['uid']=bad['pods']['a']['uid']
        elif mutation=='capacity':bad['pods']['a']['cap_mib']=10240
        elif mutation=='extra':bad['unrelated']='capture'
        elif mutation=='no-execute':bad['observer_argv'].remove('--execute')
        else:bad['observer_argv'][-1]='11111111-1111-4111-8111-111111111111'
        with pytest.raises(ValueError):m.validate_targets(bad)

def test_pod_uid_full_spec_image_and_restart_are_fresh_checks():
    m=module();row=manifest()['pods']['a']
    pod={'metadata':{'uid':row['uid'],'namespace':row['namespace'],'name':row['name']},
         'spec':{'nodeName':'k3s-wk-gpu2','containers':[{'name':'notebook','image':m.NOTEBOOK_IMAGE}]},
         'status':{'phase':'Running','containerStatuses':[{'name':'notebook','imageID':m.NOTEBOOK_IMAGE,
            'ready':True,'restartCount':0,'state':{'running':{}}}]}}
    row['spec_sha256']=hashlib.sha256(json.dumps(pod['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert m.checked_pod(pod,row)['uid']==row['uid']
    for field in ('uid','spec','restart'):
        bad=copy.deepcopy(pod)
        if field=='uid':bad['metadata']['uid']='replacement'
        elif field=='spec':bad['spec']['containers'][0]['env']=[{'name':'UNREVIEWED','value':'yes'}]
        else:bad['status']['containerStatuses'][0]['restartCount']=1
        with pytest.raises(ValueError):m.checked_pod(bad,row)
