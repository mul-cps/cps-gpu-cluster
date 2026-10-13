"""Offline handover fixtures are not live qualification evidence."""
import copy
import base64
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import native_group_approval_renderer as r
import test_native_group_approval_renderer as fixtures
from test_native_group_approval_renderer import NOW, uid, readiness_fixture
import qualified_hub_package_handover as h


def fixture():
    base = fixtures.PublisherTests(); base.setUp()
    for c in h.HUBS:
        base.f[-1][c]['deployment']['spec']['template']['spec']['containers'][0]['image'] = h.OLD_IMAGE
    gateway=base.f[-1]['gateway']['deployment']['spec']['template']['spec']
    gateway['containers'][0]['env'].append({'name':'CPS_COMPUTE_CONFIG','value':'/config/runtime.json'})
    gateway['volumes'][0]={'name':'config','secret':{'secretName':'actual-gateway-runtime'}}
    base.projection = r.projection_intent(**base.args, documents=base.docs)
    p = base.publisher()
    p['documents'] = copy.deepcopy(base.docs)
    for index, maps in enumerate((p['reference_maps'], p['bootstrap_maps']), 200):
        for n, cm in enumerate(maps.values()):
            cm['metadata'].update(uid=uid(index * 10 + n), resourceVersion='3')
    obs = observation(base, p)
    rows = {c: {'deployment':obs['deployments'][c], 'container':p['process_declarations'][c]['container'],
        'previous_document':obs['documents'][c], 'previous_reference':obs['reference_maps'][c]} for c in r.COMPONENTS}
    seed = {'version':1, 'policy':base.f[0].catalog, 'qualification':base.f[1]._config(),
        'previous_publication':p, 'previous_publication_sha256':r.canonical_sha256(p), 'baselines':rows, 'ttlSeconds':30}
    names = r._revision_process_names(p, **{k:obs[k] for k in ('deployments','replicasets','pods')})
    journal = {'version':1, 'config_hash':r.canonical_sha256(seed), 'publication':p, 'baselines':rows,
        'structural_prior':False, 'transition':None, 'process_refresh':None, 'process_names':names,
        'role_guards':{k:{'uid':v['metadata']['uid'], 'rules':v['rules']} for k,v in obs['roles'].items()}}
    controller = {'apiVersion':'apps/v1','kind':'Deployment','metadata':{
        'namespace':'cps-compute','name':'cps-native-approval-delivery','uid':uid(501),'resourceVersion':'7'},
        'spec':{'replicas':0,'template':{'spec':{'serviceAccountName':'cps-native-approval-delivery',
            'containers':[{'name':'delivery','image':'ghcr.io/example/controller@sha256:'+'a'*64,
                'volumeMounts':[{'name':'journal','mountPath':'/journal'}]}],
            'volumes':[{'name':'journal','persistentVolumeClaim':{'claimName':'old-journal'}}]}}}}
    pvc = {'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{
        'namespace':'cps-compute','name':'old-journal','uid':uid(502),'resourceVersion':'8'},
        'spec':{'accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'100Mi'}}},'status':{'phase':'Bound'}}
    state = {'seed':seed,'seed_sha256':r.canonical_sha256(seed),'journal':journal,
        'journal_sha256':r.canonical_sha256(journal),'controller':controller,'journal_pvc':pvc,
        'next_journal':{'namespace':'cps-compute','name':'new-journal'},
        'next_input_secret':{'namespace':'cps-compute','name':'new-input'}}
    packet = {'version':1,'previous_publication':p,'previous_publication_sha256':r.canonical_sha256(p),
        'policy':base.f[0].catalog,'qualification':base.f[1]._config(),
        'reviewed_images':{c:{'previous':h.OLD_IMAGE,'next':h.REVIEWED_IMAGE} for c in h.HUBS},
        'old_state':state,'observations':obs,'gateway_runtime':copy.deepcopy(obs['gateway_runtime'])}
    return base, packet


def observation(base, publication):
    records = readiness_fixture(base.f, publication, base.docs)
    acks = copy.deepcopy(base.acks)
    for c in r.COMPONENTS:
        acks[c]['data']['ack.json'] = r.canonical(records['acknowledgments'][c])
    names = r._revision_process_names(publication, **{k:records[k] for k in ('deployments','replicasets','pods')})
    roles = {o['metadata']['namespace']+'/'+o['metadata']['name']:o
        for o in r._access_rows(publication,names) if o['kind']=='Role'}
    for index, role in enumerate(roles.values(), 400):
        role['metadata'].update(uid=uid(index),resourceVersion='6')
    source = {'version':1,'source_raw':base.f[3].decode(),'source_sha256':base.args['source_sha256'],
        'trusted_revision':publication['revision'],'captured_at':NOW.isoformat()}
    runtime={'apiVersion':'v1','kind':'Secret','type':'Opaque','metadata':{'namespace':'cps-compute',
        'name':'actual-gateway-runtime','uid':uid(580),'resourceVersion':'4'},'data':{
        'preserved.bin':base64.b64encode(b'unchanged').decode(),'runtime.json':base64.b64encode(r.canonical({
            'policy_hash':publication['policy_hash'],'nativeGroupApprovals':publication['runtime_settings'],
            'nativeGpuGroups':{'kept':'exact'},'hubs':{'kept':'exact'},'source':'unchanged'}).encode()).decode()}}
    return {k:records[k] for k in ('deployments','replicasets','pods')} | {
        'documents':copy.deepcopy(base.docs),'reference_maps':copy.deepcopy(publication['reference_maps']),
        'bootstrap_maps':copy.deepcopy(publication['bootstrap_maps']),'acknowledgments':acks,'roles':roles,
        'source':source,'epoch':{'driver_epoch':records['driver_epoch'].__dict__,'captured_at':NOW.isoformat()},
        'gateway_runtime':runtime}


def post_observation(base, plan):
    p = copy.deepcopy(plan['projection'])
    for i,c in enumerate(h.HUBS,600):
        p['bootstrap_maps'][c]['metadata'].update(uid=uid(i),resourceVersion='2')
    obs = observation(base,p)
    # The actual two replacement processes have new Pod/ReplicaSet identities.
    for i,c in enumerate(h.HUBS,700):
        rs, pod = obs['replicasets'][c], obs['pods'][c]
        rs['metadata'].update(name='new-rs-'+str(i),uid=uid(i))
        pod['metadata'].update(name='new-pod-'+str(i),uid=uid(i+10))
        pod['metadata']['ownerReferences'][0].update(name=rs['metadata']['name'],uid=rs['metadata']['uid'])
        ack = r.parse(obs['acknowledgments'][c]['data']['ack.json'])
        ack['process'].update(name=pod['metadata']['name'],uid=pod['metadata']['uid'])
        obs['acknowledgments'][c]['data']['ack.json'] = r.canonical(ack)
    gateway=obs['pods']['gateway'];gateway['metadata'].update(name='new-gateway-pod',uid=uid(720))
    ack=r.parse(obs['acknowledgments']['gateway']['data']['ack.json'])
    ack['process'].update(name=gateway['metadata']['name'],uid=gateway['metadata']['uid'])
    obs['acknowledgments']['gateway']['data']['ack.json']=r.canonical(ack)
    obs['gateway_runtime']=copy.deepcopy(plan['gateway_runtime_target'])
    obs['roles'] = copy.deepcopy(plan['request']['observations']['roles'])
    return obs


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.base,self.packet = fixture()

    def plan(self):
        return h.plan_intent(self.packet,now=NOW)

    def final(self):
        plan=self.plan(); obs=post_observation(self.base,plan)
        access=h.process_access_intent(plan,obs,now=NOW)
        for k,patch in access['role_patches'].items():
            obs['roles'][k]['rules']=copy.deepcopy(patch[-1]['value'])
        return plan,access,obs,h.finalize_intent(plan,access,obs,now=NOW)

    def test_default_cli_is_inert(self):
        self.assertEqual(h.main([]),0)

    def candidate_packet(self):
        """Actual renderer serialization retains UIDs in journal baselines."""
        packet=copy.deepcopy(self.packet);publication=copy.deepcopy(packet['previous_publication'])
        packet['previous_publication']=publication
        for key in ('documents','reference_maps'):
            for cm in publication[key].values():
                cm['metadata']={k:cm['metadata'][k] for k in ('namespace','name')}
        packet['previous_publication_sha256']=r.canonical_sha256(publication)
        journal=packet['old_state']['journal'];journal['publication']=copy.deepcopy(publication)
        packet['old_state']['journal_sha256']=r.canonical_sha256(journal)
        # Test the serialized representation, with no aliases to the fixture.
        return r.parse(r.canonical(packet))

    def test_serialized_candidate_publication_uses_historical_journal_uid_custody(self):
        packet=self.candidate_packet();before=r.canonical(packet)
        plan=h.plan_intent(packet,now=NOW)
        for key in ('documents','reference_maps'):
            self.assertEqual(plan['projection'][key],packet['previous_publication'][key])
            for cm in plan['projection'][key].values():
                self.assertEqual(set(cm['metadata']),{'namespace','name'})
        obs=post_observation(self.base,plan)
        obs['reference_maps']=copy.deepcopy(packet['observations']['reference_maps'])
        access=h.process_access_intent(plan,obs,now=NOW)
        for key,patch in access['role_patches'].items():obs['roles'][key]['rules']=copy.deepcopy(patch[-1]['value'])
        final=h.finalize_intent(plan,access,obs,now=NOW)
        self.assertTrue(final['ready']);self.assertEqual(r.canonical(packet),before)
        self.assertEqual(final['publication']['documents'],packet['previous_publication']['documents'])
        for c in r.COMPONENTS:
            self.assertEqual(final['seed']['baselines'][c]['previous_reference']['metadata']['uid'],
                packet['old_state']['journal']['baselines'][c]['previous_reference']['metadata']['uid'])

    def test_candidate_objects_require_exact_completed_historical_journal_custody(self):
        for field in ('documents','reference_maps'):
            for c in r.COMPONENTS:
                with self.subTest(field=field,component=c):
                    packet=self.candidate_packet()
                    packet['observations'][field][c]['metadata']['uid']=uid(999)
                    with self.assertRaises(ValueError):h.plan_intent(packet,now=NOW)
        for mutation in ('missing_uid','different_uid','different_data','different_name','bad_hash','wrong_publication','transition'):
            with self.subTest(mutation=mutation):
                packet=self.candidate_packet();journal=packet['old_state']['journal']
                cm=journal['baselines']['hub:cps']['previous_reference']
                if mutation=='missing_uid':del cm['metadata']['uid']
                elif mutation=='different_uid':cm['metadata']['uid']=uid(999)
                elif mutation=='different_data':cm['data']['reference.json']='{}'
                elif mutation=='different_name':cm['metadata']['name']='foreign'
                elif mutation=='wrong_publication':journal['publication']['revision']='sha256:'+'0'*64
                elif mutation=='transition':journal['transition']={}
                if mutation!='bad_hash':packet['old_state']['journal_sha256']=r.canonical_sha256(journal)
                else:packet['old_state']['journal_sha256']='sha256:'+'0'*64
                with self.assertRaises(ValueError):h.plan_intent(packet,now=NOW)
        for field in ('documents','reference_maps'):
            with self.subTest(foreign_candidate_uid=field):
                packet=self.candidate_packet()
                packet['previous_publication'][field]['hub:cps']['metadata']['uid']=uid(999)
                packet['previous_publication_sha256']=r.canonical_sha256(packet['previous_publication'])
                packet['old_state']['journal']['publication']=copy.deepcopy(packet['previous_publication'])
                packet['old_state']['journal_sha256']=r.canonical_sha256(packet['old_state']['journal'])
                with self.assertRaises(ValueError):h.plan_intent(packet,now=NOW)

    def test_exact_two_images_bootstraps_full_spec_cas_and_unchanged_revision(self):
        plan=self.plan()
        self.assertFalse(plan['ready']); self.assertEqual(set(plan['bootstrap_candidates']),set(h.HUBS))
        self.assertEqual(set(plan['deployment_patches']),set(h.HUBS))
        old=self.packet['previous_publication']; new=plan['projection']
        for key in ('revision','policy_hash','references','documents','reference_maps','acknowledgment_references'):
            self.assertEqual(new[key],old[key])
        for c in r.COMPONENTS:
            if c not in h.HUBS:
                self.assertEqual(new['expected_deployments'][c],old['expected_deployments'][c])
                self.assertEqual(new['bootstrap_maps'][c],old['bootstrap_maps'][c])
                continue
            patch=plan['deployment_patches'][c]
            self.assertEqual([p['op'] for p in patch],['test','test','test','replace'])
            self.assertEqual(patch[2]['value'],self.packet['observations']['deployments'][c]['spec'])
            spec=copy.deepcopy(patch[-1]['value'])
            spec['template']['spec']['containers'][0]['image']=h.OLD_IMAGE
            volume=next(v for v in spec['template']['spec']['volumes'] if v['name']==r.PUBLISHER_VOLUME)
            volume['configMap']['name']=old['bootstrap_maps'][c]['metadata']['name']
            self.assertEqual(spec,patch[2]['value'])
            bootstrap=r.parse(plan['bootstrap_candidates'][c]['data']['publisher.json'])
            self.assertEqual(bootstrap['process']['image'],h.REVIEWED_IMAGE)
            self.assertEqual(bootstrap['acknowledgment'],old['acknowledgment_references'][c])

    def test_fresh_actual_ack_finalization_produces_bound_seed_and_lineage(self):
        plan,access,obs,final=self.final()
        self.assertTrue(final['ready']); self.assertTrue(final['readiness']['ready'])
        self.assertEqual(final['seed']['ttlSeconds'],30)
        self.assertEqual(final['seed']['previous_publication_sha256'],r.canonical_sha256(final['publication']))
        self.assertEqual(final['lineage']['previous_seed_sha256'],self.packet['old_state']['seed_sha256'])
        self.assertEqual(final['lineage']['previous_journal_sha256'],self.packet['old_state']['journal_sha256'])
        for c in r.COMPONENTS:
            self.assertEqual(final['seed']['baselines'][c]['deployment'],obs['deployments'][c])
            self.assertEqual(final['publication']['bootstrap_maps'][c],obs['bootstrap_maps'][c])

    def test_foreign_or_mutable_image_or_extra_component_fails(self):
        for kind in ('foreign','tag','gateway','missing'):
            with self.subTest(kind=kind):
                p=copy.deepcopy(self.packet)
                if kind=='foreign':p['reviewed_images']['hub:cps']['next']='ghcr.io/foreign/hub@sha256:'+'a'*64
                elif kind=='tag':p['reviewed_images']['hub:cps']['next']='ghcr.io/mul-cps/cps-compute:latest'
                elif kind=='gateway':p['reviewed_images']['gateway']={'previous':h.OLD_IMAGE,'next':h.REVIEWED_IMAGE}
                else:del p['reviewed_images']['hub:cit']
                with self.assertRaises(ValueError):h.plan_intent(p,now=NOW)

    def test_preflight_unrelated_spec_identity_policy_source_epoch_and_role_fails(self):
        for kind in ('config','mount','uid','verb','document','bootstrap','policy','source','epoch','stale_ack','paused','journal','publication_flag'):
            with self.subTest(kind=kind):
                p=copy.deepcopy(self.packet);o=p['observations'];c='hub:cps'
                if kind=='config':o['deployments'][c]['spec']['template']['spec']['volumes'][0]['configMap']['name']='foreign'
                elif kind=='mount':o['pods'][c]['spec']['containers'][0]['volumeMounts'][0]['mountPath']='/foreign'
                elif kind=='uid':o['deployments'][c]['metadata']['uid']=uid(999)
                elif kind=='verb':next(iter(o['roles'].values()))['rules'][0]['verbs'].append('list')
                elif kind=='document':o['documents'][c]['metadata']['uid']=uid(999)
                elif kind=='bootstrap':o['bootstrap_maps'][c]['metadata']['uid']=uid(999)
                elif kind=='policy':p['policy']['version']='foreign'
                elif kind=='source':o['source']['trusted_revision']='sha256:'+'0'*64
                elif kind=='epoch':o['epoch']['driver_epoch']['boot_id']=uid(999)
                elif kind=='stale_ack':
                    a=r.parse(o['acknowledgments'][c]['data']['ack.json']);a['observed_at']=(NOW-timedelta(seconds=31)).isoformat()
                    o['acknowledgments'][c]['data']['ack.json']=r.canonical(a)
                elif kind=='paused':p['old_state']['controller']['spec']['replicas']=1
                elif kind=='publication_flag':
                    p['previous_publication']['requires_actual_process_ack']=False
                    p['previous_publication_sha256']=r.canonical_sha256(p['previous_publication'])
                else:p['old_state']['journal']['transition']={}
                with self.assertRaises((ValueError,KeyError)):h.plan_intent(p,now=NOW)

    def test_structural_permission_step_never_claims_ready(self):
        plan=self.plan();obs=post_observation(self.base,plan)
        for c in h.HUBS:
            obs['pods'][c]['status']['phase']='Pending';obs['pods'][c]['status']['conditions']=[]
        access=h.process_access_intent(plan,obs,now=NOW)
        self.assertFalse(access['ready'])
        self.assertEqual(len(access['role_patches']),7)
        for k,p in access['role_patches'].items():
            for old,new in zip(p[2]['value'],p[3]['value']):
                if old['resources'] not in (['pods'],['replicasets']):self.assertEqual(old,new)
        with self.assertRaises(ValueError):h.finalize_intent(plan,access,obs,now=NOW)

    def test_final_foreign_fields_and_stale_old_image_ack_fail_closed(self):
        for kind in ('spec','bootstrap_uid','new_bootstrap_uid','wrong_bootstrap','document','ref_uid','epoch','source','ack_image','stale','role_uid','verb'):
            with self.subTest(kind=kind):
                plan,access,obs,_=self.final();c='hub:cps'
                if kind=='spec':obs['deployments'][c]['spec']['template']['spec']['containers'][0]['env'].append({'name':'OVERRIDE','value':'x'})
                elif kind=='bootstrap_uid':obs['bootstrap_maps']['node']['metadata']['uid']=uid(999)
                elif kind=='new_bootstrap_uid':obs['bootstrap_maps'][c]['metadata']['uid']=uid(999)
                elif kind=='wrong_bootstrap':obs['bootstrap_maps'][c]['data']['publisher.json']='{}'
                elif kind=='document':obs['documents'][c]['metadata']['uid']=uid(999)
                elif kind=='ref_uid':obs['reference_maps'][c]['metadata']['uid']=uid(999)
                elif kind=='epoch':obs['epoch']['driver_epoch']['boot_id']=uid(999)
                elif kind=='source':obs['source']['trusted_revision']='sha256:'+'0'*64
                elif kind in ('ack_image','stale'):
                    a=r.parse(obs['acknowledgments'][c]['data']['ack.json'])
                    if kind=='ack_image':a['process']['image']=h.OLD_IMAGE
                    else:a['observed_at']=(NOW-timedelta(seconds=31)).isoformat()
                    obs['acknowledgments'][c]['data']['ack.json']=r.canonical(a)
                elif kind=='role_uid':next(iter(obs['roles'].values()))['metadata']['uid']=uid(999)
                else:next(iter(obs['roles'].values()))['rules'][0]['verbs'].append('list')
                with self.assertRaises(ValueError):h.finalize_intent(plan,access,obs,now=NOW)

    def test_packet_tampering_and_linked_publication_inputs_fail(self):
        plan=self.plan();obs=post_observation(self.base,plan)
        plan['projection']['expected_deployments']['gateway']['spec']['replicas']=2
        with self.assertRaises(ValueError):h.process_access_intent(plan,obs,now=NOW)

    def test_gateway_runtime_change_is_exact_two_images_and_full_secret_cas(self):
        plan=self.plan();old=self.packet['gateway_runtime'];new=plan['gateway_runtime_target']
        patch=plan['gateway_runtime_patch']
        self.assertEqual([p['op'] for p in patch],['test','test','test','replace'])
        self.assertEqual(patch[2]['value'],old['data']);self.assertEqual(patch[3]['value'],new['data'])
        before=r.parse(base64.b64decode(old['data']['runtime.json']))
        after=r.parse(base64.b64decode(new['data']['runtime.json']))
        for c in h.HUBS:after['nativeGroupApprovals']['processes'][c]['image']=h.OLD_IMAGE
        self.assertEqual(after,before);self.assertEqual(new['data']['preserved.bin'],old['data']['preserved.bin'])
        self.assertEqual(plan['projection']['expected_deployments']['gateway'],self.packet['previous_publication']['expected_deployments']['gateway'])

    def test_runtime_foreign_name_uid_key_images_policy_process_and_other_fields_rejected(self):
        for kind in ('uid','data','policy','process','scope','tag','other','binary','same_gateway'):
            with self.subTest(kind=kind):
                plan,access,obs,_=self.final()
                secret=obs['gateway_runtime'];cfg=r.parse(base64.b64decode(secret['data']['runtime.json']))
                if kind=='uid':secret['metadata']['uid']=uid(999)
                elif kind=='data':secret['data']['preserved.bin']=base64.b64encode(b'foreign').decode()
                elif kind=='policy':cfg['policy_hash']='sha256:'+'0'*64
                elif kind=='process':cfg['nativeGroupApprovals']['processes']['node']['image']=h.REVIEWED_IMAGE
                elif kind=='scope':cfg['nativeGroupApprovals']['processes']['hub:cps']['namespace']='foreign'
                elif kind=='tag':cfg['nativeGroupApprovals']['processes']['hub:cps']['image']='hub:latest'
                elif kind=='other':cfg['nativeGpuGroups']['kept']='changed'
                elif kind=='binary':secret['stringData']={'credential':'foreign'}
                else:obs['pods']['gateway']['metadata']['uid']=plan['gateway_pod_restart_precondition']['uid']
                if kind in ('policy','process','scope','tag','other'):
                    secret['data']['runtime.json']=base64.b64encode(r.canonical(cfg).encode()).decode()
                with self.assertRaises(ValueError):h.finalize_intent(plan,access,obs,now=NOW)
        for kind in ('name','key','old_image','full_trust'):
            with self.subTest(preflight=kind):
                p=copy.deepcopy(self.packet);secret=p['gateway_runtime']
                cfg=r.parse(base64.b64decode(secret['data']['runtime.json']))
                if kind=='name':secret['metadata']['name']='foreign'
                elif kind=='key':secret['data']['other.json']=secret['data'].pop('runtime.json')
                elif kind=='old_image':cfg['nativeGroupApprovals']['processes']['hub:cps']['image']=h.REVIEWED_IMAGE
                else:cfg['nativeGroupApprovals']['processes']['gateway']['service_account']='foreign'
                if kind in ('old_image','full_trust'):secret['data']['runtime.json']=base64.b64encode(r.canonical(cfg).encode()).decode()
                p['observations']['gateway_runtime']=copy.deepcopy(secret)
                with self.assertRaises(ValueError):h.plan_intent(p,now=NOW)

    def test_new_seed_remains_compatible_with_ordinary_source_revision_renderer(self):
        plan,access,obs,final=self.final()
        registry=copy.deepcopy(self.base.f[2]);registry['generation']+=1
        raw=r.canonical(registry).encode();seed=final['seed']
        kwargs=dict(source_raw=raw,source_sha256='sha256:'+__import__('hashlib').sha256(raw).hexdigest(),
            trusted_revision=r.canonical_sha256(registry),policy=self.base.f[0],qualification=self.base.f[1],
            baselines=seed['baselines'],captured_at=NOW,now=NOW)
        candidates=r.document_intent(**kwargs)
        docs=fixtures.actual_documents(candidates)
        advanced=r.revision_projection_intent(**kwargs,documents=docs,previous_publication=final['publication'],
            previous_publication_sha256=seed['previous_publication_sha256'],
            previous_bootstrap_maps=obs['bootstrap_maps'],acknowledgments=obs['acknowledgments'],
            driver_epoch=self.base.epoch,ttl_seconds=30)
        self.assertEqual(advanced['process_declarations'],final['publication']['process_declarations'])
        self.assertFalse(advanced['publisher_reinstall_required'])
        self.assertNotEqual(advanced['revision'],final['publication']['revision'])

    def test_successful_real_cli_all_three_private_output_phases(self):
        def refresh(obs):
            stamp=datetime.now(timezone.utc).isoformat()
            obs['source']['captured_at']=stamp;obs['epoch']['captured_at']=stamp
            for cm in obs['acknowledgments'].values():
                ack=r.parse(cm['data']['ack.json']);ack['observed_at']=stamp;cm['data']['ack.json']=r.canonical(ack)
        def write(path,obj):
            path.write_text(r.canonical(obj));path.chmod(0o600)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);refresh(self.packet['observations']);write(root/'request.json',self.packet)
            self.assertEqual(h.main(['--phase','plan','--input',str(root/'request.json'),'--output',str(root/'plan')]),0)
            plan=r.parse((root/'plan/intent.json').read_text());obs=post_observation(self.base,plan);refresh(obs)
            write(root/'access.json',{'version':1,'plan':plan,'observations':obs})
            self.assertEqual(h.main(['--phase','process-access','--input',str(root/'access.json'),'--output',str(root/'access')]),0)
            access=r.parse((root/'access/intent.json').read_text())
            for key,patch in access['role_patches'].items():obs['roles'][key]['rules']=copy.deepcopy(patch[-1]['value'])
            refresh(obs);write(root/'final.json',{'version':1,'plan':plan,'access':access,'observations':obs})
            self.assertEqual(h.main(['--phase','finalize','--input',str(root/'final.json'),'--output',str(root/'final')]),0)
            self.assertTrue(r.parse((root/'final/intent.json').read_text())['ready'])
            for directory in ('plan','access','final'):
                self.assertEqual((root/directory).stat().st_mode&0o777,0o700)
                self.assertEqual((root/directory/'intent.json').stat().st_mode&0o777,0o600)

    def test_cli_private_files_freshness_and_no_network_default(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packet=root/'packet.json';packet.write_text(r.canonical(self.packet));packet.chmod(0o600)
            with self.assertRaises(ValueError):h.main(['--phase','plan','--input',str(packet),'--output',str(root/'bad')])
            # Fixture wall-clock is intentionally old: API tests inject NOW; CLI cannot override freshness.
            packet.chmod(0o644)
            with self.assertRaises(ValueError):h.main(['--phase','plan','--input',str(packet),'--output',str(root/'unsafe')])
            self.assertFalse((root/'unsafe').exists())
        env=dict(os.environ,KUBECONFIG='/does/not/exist',HTTP_PROXY='http://127.0.0.1:9')
        run=subprocess.run([sys.executable,str(Path(h.__file__))],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr);self.assertIn('Inert',run.stdout)

if __name__=='__main__':unittest.main()
