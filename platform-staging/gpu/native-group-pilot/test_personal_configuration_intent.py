"""Synthetic API/CPU intent, never publication or hardware qualification."""
import copy
import json
import pytest

from test_personal_qualification_promotion import promoted_node_fixture


def test_personal_intent_retains_full_cas_and_inverse(monkeypatch):
    import personal_configuration_intent as module
    from pathlib import Path
    from test_personal_qualification_promotion import __file__ as fixture_module
    fixture=Path(fixture_module).parent/'fixtures/personal_qualification_runner_source.py'
    assert fixture.read_bytes()==(Path(__file__).parent/'personal-qualification/run.py').read_bytes(), \
        'Update the explicitly pinned compute runner fixture after reviewed runner changes'
    f=promoted_node_fixture(monkeypatch)
    source=f.source
    policy={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'policy','namespace':'control',
        'uid':'12121212-1212-4212-8212-121212121212','resourceVersion':'5'},
        'data':{'policy.json':json.dumps(source.source.catalog),'unrelated':'retain exact bytes'}}
    deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'node','namespace':'control',
        'uid':'13131313-1313-4313-8313-131313131313','resourceVersion':'9'},
        'spec':{'replicas':0,'selector':{'matchLabels':{'app':'node'}},'template':{'metadata':{'labels':{'app':'node'}},
        'spec':{'containers':[{'name':'node','image':'unchanged','env':[{'name':'KEEP','value':'exact'}]}],
        'volumes':[{'name':'configuration','configMap':{'name':source.node['metadata']['name']}}]}}}}
    node=source.loaded.document['component_declarations']['node']
    deployment['metadata'].update(name=node['name'],namespace=node['namespace'])
    baselines={'policy':policy,'node':source.node,'node_deployment':deployment}
    before=copy.deepcopy(baselines)
    result=module.personal_configuration_intent(f.loaded,f.node,baselines)
    assert baselines==before and result['baseline']==before
    assert result['live_applied'] is False and result['enabled'] is False
    assert result['inverse']['original_objects']==before
    assert result['inverse']['fresh_uid_resource_version_and_full_current_tests_required'] is True
    for name,path in (('policy','/data'),('node_deployment','/spec')):
        patch=result['patches'][name]
        assert patch[:2]==[
            {'op':'test','path':'/metadata/uid','value':before[name]['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':before[name]['metadata']['resourceVersion']}]
        assert patch[2]=={'op':'test','path':path,'value':before[name][path[1:]]}
    updated=result['patches']['node_deployment'][-1]['value']
    restored=copy.deepcopy(updated)
    restored['template']['spec']['volumes'][0]['configMap']['name']=source.node['metadata']['name']
    assert restored==deployment['spec']
    assert result['patches']['policy'][-1]['value']['unrelated']=='retain exact bytes'
    assert result['target_node_ref']==f.loaded.reference.to_dict()
    # A mutable/incomplete baseline cannot authorize even offline CAS output.
    baselines['node']['metadata']['resourceVersion']='moved'
    with pytest.raises(ValueError):module.personal_configuration_intent(f.loaded,f.node,baselines)


def test_actual_runner_final_directory_promotes_and_rejects_window_substitution(tmp_path,monkeypatch):
    """Reuse owning lifecycle's synthetic IO; execute actual main and finally."""
    import importlib.util
    import sys
    from pathlib import Path
    from test_personal_qualification_promotion import promotion_fixture,completed_input
    from cps_compute.personal_qualification_promotion import plan_personal_promotion
    from cps_compute.personal_qualification_probe import canonical,digest
    spec=importlib.util.spec_from_file_location('paired_runner_tests',Path(__file__).parent/'personal-qualification/test_runner.py')
    owning=importlib.util.module_from_spec(spec);spec.loader.exec_module(owning)
    runner=owning.runner
    f=promotion_fixture(monkeypatch);raw,window,objects=completed_input(f)
    output=tmp_path/'actual-output';finished=False
    class Window:
        rows=[window['raw_window']]
        def finish(self):return window['raw_window']
        def abandon(self):pass
    class SyntheticIO(runner.Collector):
        def initialize(self):
            self.window=Window()
            # OwnedWindow streams this file before execute writes its index.
            (self.output/'reset-window.partial.jsonl').write_bytes(window['raw_window'])
            self.window_identity={k:v for k,v in window['identities'].items() if k not in ('peer','peer_checks')}
            self.baseline=json.loads(raw['host-baseline.json']);self.kernel_baseline=self.baseline['kernel_anchor']
            (self.output/'host-baseline.json').write_bytes(raw['host-baseline.json'])
            (self.output/'native-health-source.py').write_bytes(objects['sources']['health'])
        def check_final_authority(self):pass
        def pod(self,role):return b'{}',{}
        def check_peer(self,pid):
            check=copy.deepcopy(window['identities']['peer_checks'][len(self.peer_checks)])
            self.peer_checks.append(check)
            (self.output/('peer-binding-'+str(len(self.peer_checks))+'.json')).write_bytes(canonical(check))
        def host_baseline(self):return raw['host-final.json'],json.loads(raw['host-final.json'])
        def sample(self,event,pid):
            return copy.deepcopy(next(s for s in json.loads(raw['samples.json']) if s['event_sha256']==digest(canonical(event))))
        def rpc(self,role,body):
            nonlocal finished
            op=body['operation']
            if op=='setup':return {'root':'/tmp/cps-mujoco-'+role}
            if op=='read':
                stream=raw[role+'-stdout'].decode().rstrip('\n')+'\n'
                return {'stdout':stream,**({'exit':'0'} if role=='pressure' or finished else {})}
            if op=='finish-peer':finished=True;return {}
            if op in ('ack','cleanup'):return {}
            raise AssertionError(op)
    manifest=tmp_path/'manifest';manifest.write_bytes(raw['manifest.raw.json']);manifest.chmod(0o600)
    args=['run.py','--execute','--manifest',str(manifest),'--manifest-sha256',runner.sha(manifest.read_bytes()),
          '--runner-sha256',runner.sha(Path(runner.__file__).read_bytes()),'--output',str(output)]
    for key,flag in (('probe','probe'),('collector','collector'),('window','window')):
        path=tmp_path/(key+'.py');path.write_bytes(objects['sources'][key])
        args += ['--'+flag+'-source',str(path),'--'+flag+'-sha256',runner.sha(path.read_bytes())]
    monkeypatch.setattr(runner,'Collector',SyntheticIO);monkeypatch.setattr(runner.time,'sleep',lambda _:None)
    monkeypatch.setattr(sys,'argv',args);runner.main()
    complete={p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}
    retained=json.loads(complete['reset-window-input.json'])
    retained.update(raw_window=bytes.fromhex(retained['raw_window']),raw_peer=bytes.fromhex(retained['raw_peer']))
    result=plan_personal_promotion(complete,retained,objects,f.target,f.neutral)
    assert not result['live_applied']
    assert 'reset-window.partial.jsonl' in json.loads(complete['retained-index.json'])
    assert 'cleanup.json' not in json.loads(complete['retained-index.json'])
    assert json.loads(complete['cleanup.json'])=={'pressure':'owned-terminal-cleaned','peer':'owned-terminal-cleaned'}
    assert complete['reset-window.partial.jsonl']==complete['reset-window.jsonl']
    rows=[json.loads(line) for line in complete['reset-window.jsonl'].splitlines()]
    rows[1].update(rc=0,payload={'device':77,'eventType':8,'eventData':79,'gpuInstanceId':0,'computeInstanceId':0})
    complete['reset-window.jsonl']=b'\n'.join(canonical(row) for row in rows)
    index=json.loads(complete['retained-index.json']);index['reset-window.jsonl']=digest(complete['reset-window.jsonl'])
    complete['retained-index.json']=canonical(index)
    with pytest.raises(ValueError):plan_personal_promotion(complete,retained,objects,f.target,f.neutral)
