#!/usr/bin/env python3
"""Bounded installed approval revision delivery; inert unless --run is given.

The operator supplies a trusted Source capture executable and reviewed seed.
All policy/process validation remains in native_group_approval_renderer. No
acknowledgment is ever written here. Kubernetes mutations are immutable CM
creation and exact named Role/Deployment JSON patches only.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import time

import native_group_approval_renderer as r


class Pending(Exception):
    """The API has not yet produced an unambiguous current process."""


class RoleIdentityChanged(ValueError):
    """A fresh Role read must never replace a retained authorization identity."""


def private_directory(path):
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    r.require(not path.is_symlink() and path.is_dir() and info.st_uid == os.getuid()
        and info.st_mode & 0o777 == 0o700, 'Private owned delivery directory required')


def save(path, value):
    """Atomic, durable checkpoint; a lost API reply is recovered by readback."""
    temporary = path.with_suffix('.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(r.canonical(value) + '\n'); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class Kubectl:
    """Ordinary authenticated kubectl; explicit context, no shell or broad apply."""
    def __init__(self, context, executable='kubectl'):
        r.require(isinstance(context, str) and context and not context.startswith('-'), 'Explicit context required')
        self.prefix = [executable, '--context', context, '--request-timeout=20s']

    def command(self, args, value=None):
        result = subprocess.run(self.prefix + args, input=None if value is None else r.canonical(value),
            text=True, capture_output=True, timeout=25, check=False)
        if result.returncode:
            # Do not print object data, credentials or kubectl's unrestricted stderr.
            raise RuntimeError('Kubernetes command failed; no mutation assumed successful')
        return r.parse(result.stdout) if result.stdout.strip() else None

    def get(self, kind, namespace, name, missing=False):
        args = ['get', kind, name, '-n', namespace, '-o', 'json']
        if missing: args.append('--ignore-not-found=true')
        return self.command(args)

    def create(self, obj):
        r.require(obj.get('kind') == 'ConfigMap' and obj.get('immutable') is True,
            'Only immutable document/reference creation permitted')
        return self.command(['create', '-n', obj['metadata']['namespace'], '-f', '-', '-o', 'json'], obj)

    def patch(self, kind, namespace, name, patch):
        r.require(kind in ('Role', 'Deployment'), 'Only reviewed named Role/Deployment patch permitted')
        return self.command(['patch', kind, name, '-n', namespace, '--type=json', '-p', r.canonical(patch), '-o', 'json'])

    def processes(self, publication):
        records = {key:{} for key in ('deployments','replicasets','pods')}
        for component, declaration in publication['process_declarations'].items():
            namespace = declaration['namespace']
            dep = self.get('Deployment', namespace, declaration['name'])
            selector = dep['spec']['selector']
            parts = [key + '=' + value for key,value in sorted(selector.get('matchLabels',{}).items())]
            for expression in selector.get('matchExpressions',[]):
                key, operator = expression['key'], expression['operator']
                if operator in ('In','NotIn'):
                    parts.append(key + (' in (' if operator == 'In' else ' notin (') + ','.join(expression['values']) + ')')
                elif operator == 'Exists': parts.append(key)
                elif operator == 'DoesNotExist': parts.append('!' + key)
                else: raise ValueError('Unknown Deployment selector operator')
            r.require(parts, 'Nonempty namespaced process discovery selector required')
            rows = self.command(['get','Pod','-n',namespace,'--selector',','.join(parts),'-o','json'])['items']
            candidates = []
            for pod in rows:
                try:
                    owner = r.process_validation._owner(pod,'ReplicaSet')
                    rs = self.get('ReplicaSet',namespace,owner['name'],missing=True)
                    if rs is None: continue
                    r._permission_bootstrap_target(pod,rs,dep,declaration)
                    r._observed_projection(pod,publication['expected_deployments'][component],component)
                    candidates.append((pod,rs))
                except ValueError:
                    continue  # old, terminating, unrelated or structurally invalid candidate
            if len(candidates) != 1:
                raise Pending('Waiting for one structurally verified current Pod per component')
            records['deployments'][component] = dep
            records['pods'][component], records['replicasets'][component] = candidates[0]
        return records


class CommandCapture:
    """An operator-owned server-side adapter, never a browser-supplied export."""
    def __init__(self, argv):
        r.require(isinstance(argv,list) and argv and all(isinstance(arg,str) for arg in argv),
            'Trusted capture executable argv required')
        self.argv = argv

    def __call__(self):
        result = subprocess.run(self.argv, text=True, capture_output=True, timeout=25, check=False)
        r.require(result.returncode == 0 and len(result.stdout.encode()) <= 2*1024*1024,
            'Trusted server capture failed or exceeded limit')
        return r.parse(result.stdout)


class Delivery:
    def __init__(self, config, directory, api, capture, now=None, *, epoch_reader):
        r.require(isinstance(config,dict) and set(config) == {'version','policy','qualification',
            'previous_publication','previous_publication_sha256','baselines','ttlSeconds'}
            and type(config['version']) is int and config['version']==1,
            'Closed reviewed installed-publication seed required')
        r.require(config['previous_publication_sha256'] == r.canonical_sha256(config['previous_publication']),
            'Independently pinned reviewed seed publication required')
        self.config = copy.deepcopy(config); self.directory = Path(directory)
        self.api, self.capture = api, capture
        r.require(callable(epoch_reader), 'Independent trusted qualified epoch reader required')
        self.epoch_reader = epoch_reader
        self.now = now or (lambda:datetime.now(timezone.utc))
        self.policy = r.Policy(config['policy'])
        self.qualification = r.NativeGroupDeployment.from_config(config['qualification'],self.policy)
        self.config_hash = r.canonical_sha256(config)

    def _get(self, kind, identity):
        return self.api.get(kind,identity['namespace'],identity['name'])

    def _ensure(self, candidate, bound=None):
        meta = candidate['metadata']
        actual = self.api.get('ConfigMap',meta['namespace'],meta['name'],missing=True)
        if actual is None:
            r.require(bound is None, 'Previously bound immutable ConfigMap disappeared')
            self.api.create(candidate)
            actual = self._get('ConfigMap',meta)
        ameta = r.object_guard(actual,'ConfigMap')
        r.require(set(actual) <= {'apiVersion','kind','metadata','immutable','data'}
            and actual['apiVersion']=='v1' and actual.get('immutable') is True
            and not ameta.get('deletionTimestamp') and not ameta.get('ownerReferences')
            and actual.get('data') == candidate['data']
            and all(ameta.get(k)==meta[k] for k in ('namespace','name'))
            and (bound is None or ameta['uid']==bound['metadata']['uid']),
            'Exact immutable create/readback identity and full data required')
        return actual

    def _prepare_patch(self, kind, identity, operations):
        # Renderer guards stay intact. Rebase only RV after exact UID/full-value
        # readback, permitting status/controller churn without bypassing CAS.
        r.require(len(operations)==4 and [op['op'] for op in operations]==['test','test','test','replace']
            and operations[0]['path']=='/metadata/uid' and operations[1]['path']=='/metadata/resourceVersion'
            and operations[2]['path']==operations[3]['path']
            and operations[2]['path'] in ('/spec','/rules'), 'Complete reviewed renderer patch required')
        actual = self._get(kind,identity); meta = r.object_guard(actual,kind)
        field = operations[2]['path'][1:]
        r.require(meta['uid']==operations[0]['value'] and not meta.get('deletionTimestamp'),
            'Original guarded object UID required')
        if actual[field] == operations[3]['value']: return None
        r.require(actual[field] == operations[2]['value'], 'Guarded full preimage changed; operator review required')
        patch = copy.deepcopy(operations); patch[1]['value'] = meta['resourceVersion']
        return patch

    def _patch(self, kind, identity, operations):
        patch = self._prepare_patch(kind,identity,operations)
        if patch is None: return
        self.api.patch(kind,identity['namespace'],identity['name'],patch)
        after = self._get(kind,identity)
        r.require(after['metadata']['uid']==operations[0]['value']
            and after[operations[3]['path'][1:]]==operations[3]['value'],
            'Exact guarded mutation readback required')

    def _apply(self, kind, targets):
        # Preflight the complete guarded stage before its first mutation. The
        # patch itself is read/rechecked again, so intervening changes conflict.
        for identity,patch in targets: self._prepare_patch(kind,identity,patch)
        for identity,patch in targets: self._patch(kind,identity,patch)

    def _apply_roles(self, intent):
        self._apply('Role',[({'namespace':key.split('/')[0],'name':key.split('/')[1]},patch)
            for key,patch in intent['patches'].items()])

    def _request(self, source, baselines):
        return dict(source_raw=source['source_raw'].encode(),source_sha256=source['source_sha256'],
            trusted_revision=source['trusted_revision'],captured_at=datetime.fromisoformat(source['captured_at'].replace('Z','+00:00')),
            now=self.now(),policy=self.policy,qualification=self.qualification,baselines=baselines)

    def _roles(self, publication, guards=None, *, check_rules=False):
        roles={obj['metadata']['namespace']+'/'+obj['metadata']['name']:self._get('Role',obj['metadata'])
            for obj in r.access_intent(projection=publication)['objects'] if obj['kind']=='Role'}
        if guards is not None:
            r.require(set(roles)==set(guards),'All retained named Role identities required')
            for key,actual in roles.items():
                if actual['metadata']['uid']!=guards[key]['uid']:
                    raise RoleIdentityChanged('Retained Role UID changed during fresh capture')
                if check_rules:
                    r.require(actual.get('rules')==guards[key]['rules'],'Retained full Role rules changed')
        return roles

    def _reconcile_current(self, state, path):
        """Keep named GETs current after ordinary same-template Pod turnover."""
        publication=state['publication']
        if state.get('process_refresh') is not None:
            self._apply_roles(state['process_refresh'])
            self._retain_role_guards(state,state['process_refresh'])
            state['process_refresh']=None; state['structural_prior']=True; save(path,state)
        records=self.api.processes(publication)
        names=r._revision_process_names(publication,**records,permission_bootstrap=True)
        guards=state.get('role_guards')
        roles=self._roles(publication,guards,check_rules=True)
        old_names=state.get('process_names') or names
        # Initial reviewed packet may lack previous_publication_sha256; this
        # pure guard helper uses it only as returned provenance metadata.
        projection={**publication,'previous_publication_sha256':publication.get(
            'previous_publication_sha256',r.canonical_sha256(publication))}
        intent={**r._revision_role_patches(projection,r._access_rows(publication,old_names),
            r._access_rows(publication,names),roles),'actual_process_names':names}
        if guards is None or names!=old_names:
            state['process_refresh']=intent; save(path,state)
            self._apply_roles(intent); self._retain_role_guards(state,intent)
            state['process_refresh']=None
            if names!=old_names: state['structural_prior']=True
            save(path,state)
        return records

    def _retain_role_guards(self, state, intent):
        state['role_guards']={key:{'uid':patch[0]['value'],'rules':copy.deepcopy(patch[-1]['value'])}
            for key,patch in intent['patches'].items()}
        state['process_names']=copy.deepcopy(intent['actual_process_names'])

    def _readiness(self, publication, epoch):
        records = self.api.processes(publication)
        acks, processes = {}, {}
        for component, ref in publication['acknowledgment_references'].items():
            actual = self._get('ConfigMap',ref); meta = r.object_guard(actual,'ConfigMap')
            r.require(meta['uid']==ref['uid'] and not meta.get('deletionTimestamp')
                and not meta.get('ownerReferences') and actual.get('immutable') in (None,False)
                and actual.get('apiVersion')=='v1' and set(actual.get('data',{}))=={'ack.json'},
                'Actual own UID-pinned acknowledgment required')
            acks[component] = r.parse(actual['data']['ack.json'])
            pod = records['pods'][component]; decl = publication['process_declarations'][component]
            processes[component] = {k:decl[k] for k in ('namespace','container','image','service_account')}
            processes[component].update(name=pod['metadata']['name'],uid=pod['metadata']['uid'])
        documents = {c:self._get('ConfigMap',ref) for c,ref in publication['references'].items()}
        proof = r.readiness_intent(projection=publication,documents=documents,policy=self.policy,
            qualification=self.qualification,**records,expected_processes=processes,acknowledgments=acks,
            driver_epoch=epoch,now=self.now(),ttl_seconds=self.config['ttlSeconds'])
        return proof, records, documents

    def _resume_process_permissions(self, state, path):
        """Repair installed rollout GETs; neither epoch nor readiness authority.

        A new node publisher needs its own exact Pod GET before it can publish
        the acknowledgment required by the independent epoch observer. Only a
        fully installed, durable transition may break that bootstrap cycle.
        """
        transition = state['transition']
        r.require(isinstance(transition, dict) and transition.get('publication') is not None
            and transition.get('document_access') is not None
            and all(isinstance(transition.get(key), dict) and set(transition[key])==set(r.COMPONENTS)
                and all(isinstance(bound,dict) for bound in transition[key].values())
                for key in ('documents','references','bootstraps')),
            'Complete durable installed transition required for permission bootstrap')
        publication, prior = transition['publication'], transition['prior']
        r.require(prior==state['publication'], 'Retained installed prior publication required')
        r._revision_access_scope(publication, prior)
        guards = state.get('role_guards')
        r.require(isinstance(guards, dict) and set(guards)==set(transition['roles'])
            and all(guards[key]=={'uid':role['metadata']['uid'], 'rules':role['rules']}
                for key,role in transition['roles'].items()), 'Original complete Role custody required')
        old_names = r._revision_process_names(prior, **transition['old_records'], permission_bootstrap=True)
        document_access = r._revision_role_patches(publication, r._access_rows(prior,old_names),
            r._access_rows(publication,old_names), transition['roles'])
        r.require(transition['document_access']['patches']==document_access['patches'],
            'Exact retained document permission stage required')
        # Bound lookups cannot create anything: absence/replacement is fatal.
        for key in ('documents','references','bootstraps'):
            for bound in transition[key].values():
                r.object_guard(bound,'ConfigMap')
        for row in state['baselines'].values():
            for key in ('previous_document','previous_reference'):
                r.require(isinstance(row.get(key),dict), 'Prior immutable ConfigMap binding required')
                r.object_guard(row[key],'ConfigMap')
                self._ensure(row[key],row[key])
        for component in r.COMPONENTS:
            bootstrap = transition['bootstraps'][component]
            r.require(bootstrap['data']==prior['bootstrap_maps'][component]['data']
                and all(bootstrap['metadata'].get(key)==prior['bootstrap_maps'][component]['metadata'].get(key)
                    for key in ('namespace','name')), 'Retained publisher bootstrap required')
            self._ensure(bootstrap,bootstrap)
            document = self._ensure(publication['documents'][component],transition['documents'][component])
            r.require(all(document['metadata'].get(key)==publication['references'][component].get(key)
                    for key in ('namespace','name','uid'))
                and publication['reference_maps'][component]['data']==
                    {'reference.json':r.canonical(publication['references'][component])},
                'Exact bound document and immutable reference linkage required')
            self._ensure(publication['reference_maps'][component],transition['references'][component])
        # Structural verification includes all four full Deployment specs,
        # owner chains, approved Pod templates and exact projected inputs.
        records = self.api.processes(publication)
        names = r._revision_process_names(publication, **records, permission_bootstrap=True)
        roles = self._roles(publication,guards)
        if transition['process_access'] is None:
            transition['process_access'] = {**r._revision_role_patches(publication,
                r._access_rows(publication,old_names),r._access_rows(publication,names),roles),
                'actual_process_names':names}
            save(path,state)
        intent = transition['process_access']
        targets = {obj['metadata']['namespace']+'/'+obj['metadata']['name']:obj['rules']
            for obj in r._access_rows(publication,intent['actual_process_names']) if obj['kind']=='Role'}
        initial = {key:patch[-1]['value'] for key,patch in document_access['patches'].items()}
        r.require(set(intent['patches'])==set(targets)==set(guards), 'Complete named permission stage required')
        for key,patch in intent['patches'].items():
            r.require(patch[0]['value']==guards[key]['uid'] and patch[-1]['value']==targets[key],
                'Retained Role identity and exact structural GET targets required')
            # Even a resumed partial stage may change only singleton Pod/RS
            # GET names. Every other full rule remains the installed target.
            for rules in (patch[2]['value'],patch[-1]['value']):
                r.require(len(rules)==len(initial[key]), 'Complete installed Role rules required')
                for rule,wanted in zip(rules,initial[key]):
                    if wanted['resources'] in (['pods'],['replicasets']):
                        r.require({k:v for k,v in rule.items() if k!='resourceNames'}==
                            {k:v for k,v in wanted.items() if k!='resourceNames'}
                            and isinstance(rule.get('resourceNames'),list) and len(rule['resourceNames'])==1
                            and isinstance(rule['resourceNames'][0],str) and rule['resourceNames'][0],
                            'Only singleton current process GET names may change')
                    else:
                        r.require(rule==wanted, 'Non-process permissions must remain exact')
        self._apply_roles(intent)
        if names != intent['actual_process_names']:
            intent = {**r._revision_role_patches(publication,
                r._access_rows(publication,intent['actual_process_names']),r._access_rows(publication,names),
                self._roles(publication,guards)), 'actual_process_names':names}
            transition['process_access']=intent; save(path,state); self._apply_roles(intent)
        return {'phase':'processes','ready':False,'revision':publication['revision']}

    def tick(self):
        private_directory(self.directory)
        fd = os.open(self.directory/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return self._tick()

    def _tick(self):
        path = self.directory/'state.json'
        state = r._private_json(path) if path.exists() else {'version':1,'config_hash':self.config_hash,
            'publication':self.config['previous_publication'],'baselines':self.config['baselines'],
            'structural_prior':False,'transition':None}
        r.require(state.get('version')==1 and state.get('config_hash')==self.config_hash,
            'Journal belongs to a different reviewed seed')
        source = self.capture()
        r.require(isinstance(source,dict) and set(source)=={'version','source_raw','source_sha256',
            'trusted_revision','captured_at'} and type(source['version']) is int and source['version']==1,
            'Closed trusted server capture required')
        try:
            observed_epoch = self.epoch_reader()
        except (RuntimeError,ValueError,Pending,subprocess.TimeoutExpired):
            if state.get('transition') is not None:
                return self._resume_process_permissions(state,path)
            raise
        epoch = r.DriverEpoch(**observed_epoch)
        pool = self.qualification._config()['node_pool']
        r.require(epoch.__dict__=={k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')},
            'Fresh qualified driver epoch observation required')
        # Reuse the renderer for raw pins/freshness/SDK Source validation even
        # when generation has not advanced; ignore this initial-install plan.
        bare = copy.deepcopy(state['baselines'])
        for row in bare.values(): row.update(previous_document=None,previous_reference=None)
        r.document_intent(**self._request(source,bare))
        transition = state['transition']
        # Refresh can never overwrite a bound immutable UID, including an
        # identically named/content reference replaced after a completed head.
        for row in state['baselines'].values():
            for key in ('previous_document','previous_reference'):
                row[key]=self._ensure(row[key],row[key])
        if transition is None:
            try:
                self._reconcile_current(state,path)
            except Pending:
                return {'phase':'processes','ready':False,'revision':state['publication']['revision']}
        if transition is None and source['trusted_revision'] != state['publication']['revision']:
            prior = state['publication']; baselines = copy.deepcopy(state['baselines'])
            for component,row in baselines.items():
                row['deployment'] = self._get('Deployment',row['deployment']['metadata'])
            kwargs = self._request(source,baselines)
            candidates = r.document_intent(**kwargs)
            transition = {'source':source,'baselines':baselines,'candidates':candidates['documents'],
                'documents':{},'references':{},'prior':prior,'old_records':self.api.processes(prior),
                'roles':self._roles(prior,state['role_guards'],check_rules=True),'bootstraps':{c:self._get('ConfigMap',obj['metadata']) for c,obj in prior['bootstrap_maps'].items()},
                'acks':{c:self._get('ConfigMap',ref) for c,ref in prior['acknowledgment_references'].items()},
                'structural_prior':state['structural_prior'],
                'publication':None,'document_access':None,'process_access':None}
            state['transition'] = transition; save(path,state)
        if transition is not None:
            for bootstrap in transition['bootstraps'].values():
                self._ensure(bootstrap,bootstrap)
            for component,candidate in transition['candidates'].items():
                bound = transition['documents'].get(component)
                transition['documents'][component] = self._ensure(candidate,bound)
                save(path,state)
            if transition['publication'] is None:
                # The authenticated capture was validated before durable intent.
                # Resume retains its provenance; only this planning timestamp is
                # replayed, never a readiness/driver observation.
                kwargs = self._request(transition['source'],transition['baselines'])
                kwargs['now'] = kwargs['captured_at']
                transition['publication'] = r.revision_projection_intent(**kwargs,documents=transition['documents'],
                    previous_publication=transition['prior'],previous_publication_sha256=r.canonical_sha256(transition['prior']),
                    previous_bootstrap_maps=transition['bootstraps'],acknowledgments=transition['acks'],
                    driver_epoch=epoch,ttl_seconds=self.config['ttlSeconds'])
                save(path,state)
            publication = transition['publication']
            for component,candidate in publication['reference_maps'].items():
                transition['references'][component] = self._ensure(candidate,transition['references'].get(component))
                save(path,state)
            if transition['document_access'] is None:
                if transition['structural_prior']:
                    # Same bundled renderer's reviewed Pending permission-only
                    # path, preserving every owner/template/executable guard.
                    # No old loaded-head or Pod Ready proof is asserted here.
                    r._revision_access_scope(publication,transition['prior'])
                    names = r._revision_process_names(transition['prior'],**transition['old_records'],permission_bootstrap=True)
                    transition['document_access'] = r._revision_role_patches(publication,
                        r._access_rows(transition['prior'],names),r._access_rows(publication,names),transition['roles'])
                else:
                    transition['document_access'] = r.revision_access_intent(projection=publication,
                        previous_publication=transition['prior'],**transition['old_records'],roles=transition['roles'])
                save(path,state)
            # After process permission delivery the initial Role target is
            # intentionally superseded. Its saved guard remains provenance.
            if transition['process_access'] is None:
                self._apply_roles(transition['document_access'])
            self._apply('Deployment',[(publication['process_declarations'][component],patch)
                for component,patch in publication['patches'].items()])
            try:
                records = self.api.processes(publication)
                if transition['process_access'] is None:
                    if transition['structural_prior']:
                        old_names = r._revision_process_names(transition['prior'],**transition['old_records'],permission_bootstrap=True)
                        names = r._revision_process_names(publication,**records,permission_bootstrap=True)
                        transition['process_access'] = {**r._revision_role_patches(publication,
                            r._access_rows(publication,old_names),r._access_rows(publication,names),self._roles(publication,state['role_guards'])),
                            'actual_process_names':names}
                    else:
                        transition['process_access'] = r.revision_process_access_intent(projection=publication,
                            previous_publication=transition['prior'],previous_process_records=transition['old_records'],
                            **records,roles=self._roles(publication,state['role_guards']))
                    save(path,state)
            except RoleIdentityChanged:
                raise
            except (Pending,ValueError):
                return {'phase':'processes','ready':False,'revision':publication['revision']}
            self._apply_roles(transition['process_access'])
            names = r._revision_process_names(publication,**records,permission_bootstrap=True)
            if names != transition['process_access']['actual_process_names']:
                # Controllers may replace a Pending Pod while delivery waits
                # for real acks. Finish any partially applied old target, then
                # derive a fresh exact named target from the same renderer.
                transition['process_access'] = {**r._revision_role_patches(publication,
                    r._access_rows(publication,transition['process_access']['actual_process_names']),
                    r._access_rows(publication,names),self._roles(publication,state['role_guards'])), 'actual_process_names':names}
                save(path,state); self._apply_roles(transition['process_access'])
            if source['trusted_revision'] != publication['revision']:
                documents = {c:self._get('ConfigMap',ref) for c,ref in publication['references'].items()}
                self._complete(state,publication,records,documents,structural=True)
                save(path,state)
                return {'phase':'source-advanced','ready':False,'revision':publication['revision']}
        else:
            publication = state['publication']
        try:
            proof,records,documents = self._readiness(publication,epoch)
        except (Pending,ValueError):
            return {'phase':'acknowledgments','ready':False,'revision':publication['revision']}
        if transition is not None:
            self._complete(state,publication,records,documents,structural=False)
            save(path,state)
        elif state['structural_prior']:
            state['structural_prior']=False; save(path,state)
        # A newer Source head remains queued. This old loaded proof authorizes
        # no assertion of current-head readiness.
        return {'phase':'current' if source['trusted_revision']==proof['revision'] else 'source-advanced',
            'ready':source['trusted_revision']==proof['revision'],'revision':proof['revision']}

    def _complete(self, state, publication, records, documents, *, structural):
        state['publication'] = publication
        for component,row in state['baselines'].items():
            row.update(deployment=records['deployments'][component],previous_document=documents[component],
                previous_reference=state['transition']['references'][component])
        state['structural_prior'] = structural
        self._retain_role_guards(state,state['transition']['process_access'])
        state['transition'] = None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true'); parser.add_argument('--once',action='store_true')
    parser.add_argument('--config',type=Path); parser.add_argument('--state-dir',type=Path)
    parser.add_argument('--capture-command',type=Path,help='Private JSON argv file for trusted server Source export')
    parser.add_argument('--epoch-command',type=Path,help='Separate private JSON argv for current qualified epoch observer')
    parser.add_argument('--context'); parser.add_argument('--interval',type=float,default=5)
    args = parser.parse_args(argv)
    if not args.run:
        print('Inert: --run requires reviewed installed seed, trusted capture adapter and explicit context.'); return 0
    r.require(args.config and args.state_dir and args.capture_command and args.epoch_command and 1<=args.interval<=60,
        'Reviewed private config/capture argv, state directory and bounded interval required')
    controller = Delivery(r._private_json(args.config),args.state_dir,Kubectl(args.context),
        CommandCapture(r._private_json(args.capture_command)),epoch_reader=CommandCapture(r._private_json(args.epoch_command)))
    while True:
        try:
            print(r.canonical(controller.tick()),flush=True)
        except (RuntimeError,ValueError,Pending,BlockingIOError,subprocess.TimeoutExpired):
            print(r.canonical({'phase':'blocked','ready':False}),flush=True)
            if args.once: return 1
        if args.once: return 0
        time.sleep(args.interval)


if __name__=='__main__': raise SystemExit(main())
