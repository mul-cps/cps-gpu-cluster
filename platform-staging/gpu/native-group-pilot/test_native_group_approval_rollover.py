"""Installed publication rollover; synthetic readbacks are not live evidence."""
import copy
import hashlib
import unittest

import native_group_approval_renderer as r
from test_native_group_approval_renderer import (PublisherTests, actual_documents,
    readiness_fixture, request, uid)


def installed_fixture():
    initial=PublisherTests();initial.setUp();prior=initial.publisher()
    old=readiness_fixture(initial.f,prior,initial.docs)
    bootstraps=copy.deepcopy(prior['bootstrap_maps'])
    references=copy.deepcopy(prior['reference_maps'])
    for index,component in enumerate(r.COMPONENTS,300):
        bootstraps[component]['metadata'].update(uid=uid(index),resourceVersion='1')
        references[component]['metadata'].update(uid=uid(index+10),resourceVersion='1')
    baselines=copy.deepcopy(initial.args['baselines'])
    for component,row in baselines.items():
        row['deployment']=copy.deepcopy(old['deployments'][component])
        row['previous_document']=copy.deepcopy(initial.docs[component])
        row['previous_reference']=references[component]
    registry=copy.deepcopy(initial.f[2]);registry['generation']+=1
    # New Source-owned scope; unrelated policy, pool, images and history stay fixed.
    scope=copy.deepcopy(next(iter(registry['deployment']['workspaces'].values())))
    scope.update(owner='neutral-new-source-workspace',principal='workspace:cps:new-source-workspace',
        pod='jupyter-new-source-workspace',group_id='new-source-workspace')
    scope['storage'].update(pvc='new-source-pvc',pv='new-source-pv',path='/mnt/project/new-source-workspace',group_hash='new-source-workspace')
    registry['deployment']['workspaces']['cps:new-source-workspace']=scope
    raw=r.canonical(registry).encode()
    args={**initial.args,'baselines':baselines,'source_raw':raw,
        'source_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
        'trusted_revision':r.canonical_sha256(registry)}
    docs=actual_documents(r.document_intent(**args))
    for index,component in enumerate(r.COMPONENTS,400):docs[component]['metadata']['uid']=uid(index)
    kwargs={**args,'documents':docs,'previous_publication':prior,
        'previous_publication_sha256':r.canonical_sha256(prior),
        'previous_bootstrap_maps':bootstraps,'acknowledgments':initial.acks,
        'driver_epoch':initial.epoch,'ttl_seconds':30}
    initial_roles={}
    for index,obj in enumerate(r.access_intent(projection=prior)['objects'],500):
        if obj['kind']=='Role':
            obj=copy.deepcopy(obj);obj['metadata'].update(uid=uid(index),resourceVersion='10')
            initial_roles[obj['metadata']['namespace']+'/'+obj['metadata']['name']]=obj
    old_access=r.process_access_intent(projection=prior,roles=initial_roles,
        **{key:old[key] for key in ('deployments','replicasets','pods')})
    roles=copy.deepcopy(initial_roles)
    for key,patch in old_access['patches'].items():
        roles[key]['rules']=copy.deepcopy(patch[-1]['value']);roles[key]['metadata']['resourceVersion']='11'
    return initial,prior,old,kwargs,roles


class RolloverTests(unittest.TestCase):
    def setUp(self):self.initial,self.prior,self.old,self.kwargs,self.roles=installed_fixture()

    def render(self,**changes):
        args=copy.deepcopy(self.kwargs);args.update(changes)
        return r.revision_projection_intent(**args)

    def test_installed_next_generation_preserves_publishers_and_full_static_spec(self):
        legacy={key:self.kwargs[key] for key in self.initial.args}
        with self.assertRaisesRegex(ValueError,'Unknown approval volume collision'):
            r.projection_intent(**legacy,documents=self.kwargs['documents'])
        result=self.render()
        self.assertFalse(result['process_readiness_verified'])
        self.assertFalse(result['live_applied'])
        for key in ('acknowledgment_references','process_declarations','runtime_settings'):
            self.assertEqual(result[key],self.prior[key])
        self.assertEqual(result['bootstrap_maps'],self.kwargs['previous_bootstrap_maps'])
        for component in r.COMPONENTS:
            old=copy.deepcopy(self.kwargs['baselines'][component]['deployment']['spec'])
            new=result['expected_deployments'][component]['spec']
            for volume in old['template']['spec']['volumes']:
                if volume['name']==r.DOC_VOLUME:volume['configMap']['name']=result['documents'][component]['metadata']['name']
                if volume['name']==r.REF_VOLUME:volume['configMap']['name']=result['reference_maps'][component]['metadata']['name']
            self.assertEqual(new,old)
            self.assertEqual(result['patches'][component][:3],[
                {'op':'test','path':'/metadata/uid','value':self.kwargs['baselines'][component]['deployment']['metadata']['uid']},
                {'op':'test','path':'/metadata/resourceVersion','value':'20'},
                {'op':'test','path':'/spec','value':self.kwargs['baselines'][component]['deployment']['spec']}])
            self.assertEqual(len(r.parse(result['documents'][component]['data']['approval.json'])['history']),4)

    def test_changed_prior_custody_bootstrap_ack_settings_and_unknown_fields_denied(self):
        mutations=(
            lambda d:d['previous_publication'].update(unknown=True),
            lambda d:d['previous_publication']['runtime_settings'].update(ttlSeconds=31),
            lambda d:d['previous_bootstrap_maps']['node']['data'].update({'extra':'foreign'}),
            lambda d:d['previous_bootstrap_maps']['gateway']['metadata'].update(uid='not-a-uid'),
            lambda d:d['acknowledgments']['node']['metadata'].update(uid=uid(900)),
            lambda d:d['baselines']['gateway']['deployment']['spec']['template']['spec']['containers'][0]['args'].append('foreign'),
            lambda d:d['baselines']['node']['deployment']['spec']['template']['spec']['containers'][0]['args'].pop(),
            lambda d:d['baselines']['hub:cps']['previous_reference']['data'].update({'reference.json':'{}'}),
            lambda d:d.update(ttl_seconds=31),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bad=copy.deepcopy(self.kwargs);mutation(bad)
                with self.assertRaises(ValueError):r.revision_projection_intent(**bad)

    def test_named_document_then_actual_process_access_preserves_full_role_guards(self):
        result=self.render()
        old_records={key:self.old[key] for key in ('deployments','replicasets','pods')}
        stage=r.revision_access_intent(projection=result,previous_publication=self.prior,
            roles=self.roles,**old_records)
        staged=copy.deepcopy(self.roles)
        for key,patch in stage['patches'].items():
            self.assertEqual(patch[:3],[{'op':'test','path':'/metadata/uid','value':self.roles[key]['metadata']['uid']},
                {'op':'test','path':'/metadata/resourceVersion','value':'11'},
                {'op':'test','path':'/rules','value':self.roles[key]['rules']}])
            staged[key]['rules']=copy.deepcopy(patch[-1]['value']);staged[key]['metadata']['resourceVersion']='12'
            changed=copy.deepcopy(self.roles[key]['rules'])
            target=key.split('/')[0]
            component=next(c for c in r.COMPONENTS if r._namespaces(self.initial.f[1])[c]==target)
            changed[0]['resourceNames']=sorted([result['references'][component]['name'],self.prior['acknowledgment_references'][component]['name']])
            self.assertEqual(staged[key]['rules'],changed)
        current=readiness_fixture(self.initial.f,result,self.kwargs['documents'])
        for component in r.COMPONENTS:
            pod=current['pods'][component];rs=current['replicasets'][component]
            pod['metadata'].update(name=pod['metadata']['name']+'-new',uid=uid(700+r.COMPONENTS.index(component)))
            rs['metadata'].update(name=rs['metadata']['name']+'-new',uid=uid(710+r.COMPONENTS.index(component)))
            pod['metadata']['ownerReferences'][0].update(name=rs['metadata']['name'],uid=rs['metadata']['uid'])
            current['expected_processes'][component].update(name=pod['metadata']['name'],uid=pod['metadata']['uid'])
            current['acknowledgments'][component]['process']=copy.deepcopy(current['expected_processes'][component])
        fresh=r.revision_process_access_intent(projection=result,previous_publication=self.prior,
            previous_process_records=old_records,roles=staged,
            **{key:current[key] for key in ('deployments','replicasets','pods')})
        for key,patch in fresh['patches'].items():
            self.assertEqual(patch[2]['value'],staged[key]['rules'])
            self.assertEqual(patch[1]['value'],'12')
            self.assertTrue(any(rule['resources']==['pods'] and rule['resourceNames'][0].endswith('-new') for rule in patch[-1]['value']))
            self.assertEqual([rule for rule in patch[-1]['value'] if rule['resources'] not in (['pods'],['replicasets'])],
                [rule for rule in staged[key]['rules'] if rule['resources'] not in (['pods'],['replicasets'])])
        ready=r.readiness_intent(projection=result,documents=self.kwargs['documents'],policy=self.initial.f[0],
            qualification=self.initial.f[1],**current)
        self.assertTrue(ready['ready'])

    def test_unknown_prior_role_rules_and_owner_replacements_fail_closed(self):
        result=self.render();records={key:self.old[key] for key in ('deployments','replicasets','pods')}
        for mutation in (
            lambda roles:next(iter(roles.values()))['rules'].append({'apiGroups':[''],'resources':['secrets'],'verbs':['get']}),
            lambda roles:next(iter(roles.values()))['rules'][3]['resourceNames'].append('foreign-pod'),
            lambda roles:next(iter(roles.values())).update(unknown=True),
        ):
            roles=copy.deepcopy(self.roles);mutation(roles)
            with self.assertRaises(ValueError):r.revision_access_intent(projection=result,previous_publication=self.prior,roles=roles,**records)
        bad=copy.deepcopy(records);bad['pods']['node']['metadata']['ownerReferences'][0]['uid']=uid(998)
        with self.assertRaises(ValueError):r.revision_access_intent(projection=result,previous_publication=self.prior,roles=self.roles,**bad)

    def test_third_generation_reuses_same_publishers_and_keeps_eight_prior_refs(self):
        second=self.render();kwargs=copy.deepcopy(self.kwargs)
        registry=r.parse(kwargs['source_raw']);registry['generation']+=1
        raw=r.canonical(registry).encode()
        kwargs.update(source_raw=raw,source_sha256='sha256:'+hashlib.sha256(raw).hexdigest(),
            trusted_revision=r.canonical_sha256(registry),previous_publication=second,
            previous_publication_sha256=r.canonical_sha256(second))
        for index,component in enumerate(r.COMPONENTS,800):
            row=kwargs['baselines'][component]
            row['deployment']['spec']=copy.deepcopy(second['expected_deployments'][component]['spec'])
            row['deployment']['metadata']['resourceVersion']='30'
            row['previous_document']=copy.deepcopy(self.kwargs['documents'][component])
            row['previous_reference']=copy.deepcopy(second['reference_maps'][component])
            row['previous_reference']['metadata'].update(uid=uid(index),resourceVersion='1')
        request_keys=self.initial.args.keys();plan=r.document_intent(**{k:kwargs[k] for k in request_keys})
        kwargs['documents']=actual_documents(plan)
        for index,component in enumerate(r.COMPONENTS,820):kwargs['documents'][component]['metadata']['uid']=uid(index)
        third=r.revision_projection_intent(**kwargs)
        self.assertEqual(third['bootstrap_maps'],second['bootstrap_maps'])
        self.assertEqual(third['runtime_settings'],second['runtime_settings'])
        history=r.parse(third['documents']['node']['data']['approval.json'])['history']
        self.assertEqual(history,[self.prior['references'][c] for c in r.COMPONENTS]+[second['references'][c] for c in r.COMPONENTS])


if __name__=='__main__':unittest.main()
