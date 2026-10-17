#!/usr/bin/env python3
"""Pure release-pinned GitOps renderer. No Kubernetes client or API writes.

The reviewed baseline is an independent input, never copied from current API
Role rules. Rendered JSON is inert (replicas=0, no --execute) unless explicitly
activated. Root must separately review/apply; this file is not an executor.
"""
import argparse
import copy
import hashlib
import json
import re

NAME='cps-native-observer-operator'


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(value):
    return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def document(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate input JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique,
        parse_constant=lambda _:require(False,'Nonfinite input JSON'))


def _inventory(values,kind,version,*,limit=32):
    require(isinstance(values,list) and 1<=len(values)<=limit,'Bounded explicit '+kind+' inventory required')
    result={}
    for value in values:
        require(isinstance(value,dict) and value.get('kind')==kind and value.get('apiVersion')==version,
                'Actual '+kind+' API document required')
        meta=value.get('metadata',{});key=(meta.get('namespace'),meta.get('name'))
        require(all(isinstance(x,str) and x for x in key) and key not in result
                and not meta.get('deletionTimestamp'),'Unique nondeleting '+kind+' inventory required')
        result[key]=copy.deepcopy(value)
    return result


def render(release,reviewed_sha256,catalog,capture,image,*,activate=False):
    from cps_compute.native_observer_permissions import ObserverRelease,mutable_rows,role_targets,names
    from cps_compute.native_node.config import NodeConfiguration,ImmutableConfigMapRef
    from cps_compute.native_group_process import _object,_template
    from cps_compute.policy import Policy
    require(isinstance(reviewed_sha256,str) and reviewed_sha256==digest(release),
            'Reviewed independent baseline hash mismatch')
    validated_release=ObserverRelease.from_dict(release)
    trusted=validated_release.document
    require(isinstance(image,str) and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',image)
            and not image.endswith('0'*64),'Exact published immutable operator image required')
    require(type(activate) is bool,'Explicit activation boolean required')
    require(isinstance(capture,dict) and set(capture)=={'version','configmaps','deployments','roles'}
            and type(capture['version']) is int and capture['version']==1,'Closed version1 capture required')
    # Four bounded 128-name head read sets plus the original static inventory.
    maps=_inventory(capture['configmaps'],'ConfigMap','v1',limit=4*128+32 if trusted['version']==2 else 32)
    deployments=_inventory(capture['deployments'],'Deployment','apps/v1')
    roles=_inventory(capture['roles'],'Role','rbac.authorization.k8s.io/v1')
    reads=set()
    class CapturedCore:
        def read_namespaced_config_map(self,name,namespace):
            key=(namespace,name);require(key in maps,'Missing actual immutable authority ConfigMap')
            reads.add(key);return copy.deepcopy(maps[key])
    policy=Policy(catalog)
    expected=ImmutableConfigMapRef.from_dict(trusted['node_configuration'])
    configuration=NodeConfiguration.load(CapturedCore(),expected,policy)
    require(configuration is not None,'Disabled configuration cannot authorize an observer')
    config=configuration.document;declarations=config['component_declarations']
    targets=set(role_targets(config));baseline={(r['namespace'],r['name']):r for r in trusted['roles']}
    require(set(baseline)==targets and set(roles)==targets,'Exact seven baseline and actual target Roles required')
    require(set(deployments)=={(d['namespace'],d['name']) for d in declarations.values()},
            'Exact four declared controller captures required')
    head_rows,head_names={},{}
    if trusted['version']==2:
        from cps_compute.native_observer_permissions import observe_head_permissions
        _,head_names=observe_head_permissions(CapturedCore(),validated_release,configuration,policy)
        head_rows={(r['namespace'],r['name']):r['index'] for r in trusted['head_get_rows']}
    for key,pinned in baseline.items():
        actual=roles[key];meta=actual['metadata']
        require(meta.get('uid')==pinned['uid'] and isinstance(meta.get('resourceVersion'),str)
                and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion']),'Actual Role UID/RV differs from baseline')
        indexes=mutable_rows(pinned['rules']);require(mutable_rows(actual.get('rules'))==indexes,'Role schema differs from baseline')
        comparison=copy.deepcopy(actual['rules'])
        for index in indexes.values():comparison[index]['resourceNames']=pinned['rules'][index]['resourceNames']
        if key in head_rows:
            index=head_rows[key]
            required=set(pinned['rules'][index]['resourceNames'])
            allowed=required|set(head_names[key[0]])
            names(sorted(allowed))
            require(required<=set(actual['rules'][index]['resourceNames'])<=allowed,
                    'Actual ConfigMap GET names escaped authenticated head evidence')
            comparison[index]['resourceNames']=pinned['rules'][index]['resourceNames']
        require(comparison==pinned['rules'],'Actual nonmutable rules differ from independently reviewed baseline')
        component=next(c for c,d in declarations.items() if d['namespace']==key[0])
        for row in pinned['rules']:
            if row['verbs']==['patch']:
                own='cps-native-approval-'+{'node':'node','gateway':'gateway','hub:cps':'hub-cps','hub:cit':'hub-cit'}[component]
                require(key[1]==own and row['resourceNames']==[config['acknowledgment_targets'][component]['name']],
                        'Only exact own ACK PATCH baseline is admitted')
    pull_secrets=[]
    for component,declared in declarations.items():
        require(declared['kind']=='Deployment','Only fixed Deployment components supported')
        dep=deployments[(declared['namespace'],declared['name'])]
        _object(dep,'Deployment',declared['namespace'],declared['name'],declared['uid'])
        template=_template(dep);spec=template['spec']
        selected=[c for c in spec.get('containers',[]) if c.get('name')==declared['container']]
        require(len(selected)==1 and selected[0].get('image')==declared['image']
                and spec.get('serviceAccountName')==declared['service_account'],'Declared controller image or SA drift')
        if component=='node':
            if 'imagePullSecrets' in spec:
                references=spec['imagePullSecrets']
                require(isinstance(references,list) and 1<=len(references)<=8
                        and all(isinstance(ref,dict) and set(ref)=={'name'}
                            and isinstance(ref['name'],str) and 1<=len(ref['name'])<=253
                            and all(re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?',part)
                                    for part in ref['name'].split('.')) for ref in references),
                        'Closed canonical namespace-local imagePullSecrets references required')
                require(len({ref['name'] for ref in references})==len(references),'Duplicate imagePullSecrets reference')
                pull_secrets=copy.deepcopy(references)
            pin=trusted['held_node_template_sha256']
            require(pin is None or pin==digest(template),'Reviewed held Node template pin differs from actual controller')
            volumes=[v for v in spec.get('volumes',[]) if v.get('name')=='packaged-bootstrap-input']
            require(len(volumes)==1 and set(volumes[0])=={'name','configMap'}
                    and isinstance(volumes[0]['configMap'].get('name'),str),'Exact Node bootstrap volume required')
            bootstrap_key=(declared['namespace'],volumes[0]['configMap']['name'])
            require(bootstrap_key in maps,'Actual Node bootstrap capture required')
            bootstrap=maps[bootstrap_key];data=bootstrap.get('data',{})
            require(set(data)=={'config-ref.json','policy.json','release'}
                    and document(data['config-ref.json'])==expected.to_dict()
                    and document(data['policy.json'])==catalog and data['release'] in ('true','false'),
                    'Actual Node bootstrap trust inputs differ')
            reads.add(bootstrap_key)
    namespace=expected.to_dict()['namespace']
    labels={'app.kubernetes.io/name':NAME,'app.kubernetes.io/component':'observer-permissions'}
    def obj(kind,name,ns,**fields):
        version='apps/v1' if kind=='Deployment' else 'rbac.authorization.k8s.io/v1' if kind in ('Role','RoleBinding') else 'v1'
        return {'apiVersion':version,'kind':kind,'metadata':{'namespace':ns,'name':name,'labels':dict(labels)},**fields}
    data={'release.json':canonical(trusted),'policy.json':canonical(catalog)}
    input_name=NAME+'-'+digest(data)[7:23]
    result=[obj('ConfigMap',input_name,namespace,immutable=True,data=data),obj('ServiceAccount',NAME,namespace)]
    for component,declared in sorted(declarations.items()):
        ns=declared['namespace']
        rules=[{'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'verbs':['get','patch','escalate'],
                'resourceNames':sorted(name for target_ns,name in targets if target_ns==ns)},
               {'apiGroups':['apps'],'resources':['deployments'],'verbs':['get'],'resourceNames':[declared['name']]},
               {'apiGroups':[''],'resources':['serviceaccounts'],'verbs':['get'],'resourceNames':[declared['service_account']]},
               {'apiGroups':[''],'resources':['pods'],'verbs':['get','list']},
               {'apiGroups':['apps'],'resources':['replicasets'],'verbs':['get']}]
        cm_names=sorted(name for read_ns,name in reads if read_ns==ns)
        if cm_names:rules.append({'apiGroups':[''],'resources':['configmaps'],'verbs':['get'],'resourceNames':cm_names})
        result.extend([obj('Role',NAME,ns,rules=rules),obj('RoleBinding',NAME,ns,
            roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':NAME},
            subjects=[{'kind':'ServiceAccount','name':NAME,'namespace':namespace}])])
    args=['--release','/etc/cps-observer/release.json','--policy','/etc/cps-observer/policy.json',
          '--interval-seconds','5','--failure-limit','100']
    if activate:args.insert(0,'--execute')
    result.append(obj('Deployment',NAME,namespace,spec={
        'replicas':1 if activate else 0,'strategy':{'type':'Recreate'},
        'selector':{'matchLabels':{'app.kubernetes.io/name':NAME}},
        'template':{'metadata':{'labels':dict(labels)},'spec':{
            'serviceAccountName':NAME,'automountServiceAccountToken':True,
            'securityContext':{'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True},
            'containers':[{'name':'observer','image':image,'imagePullPolicy':'IfNotPresent',
                'command':['python','-I','-B','-m','cps_compute.native_observer_permissions'],'args':args,
                'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,
                                   'capabilities':{'drop':['ALL']}},
                'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
                'volumeMounts':[{'name':'trusted-inputs','mountPath':'/etc/cps-observer/'+key,
                                'subPath':key,'readOnly':True} for key in ('release.json','policy.json')]}],
            'volumes':[{'name':'trusted-inputs','configMap':{'name':input_name,'defaultMode':0o444}}]}}}))
    if pull_secrets:
        result[-1]['spec']['template']['spec']['imagePullSecrets']=pull_secrets
    return result


def read(path):
    with open(path,'rb') as stream:raw=stream.read(8*1024*1024+1)
    require(0<len(raw)<=8*1024*1024,'Bounded explicit JSON input required')
    return document(raw)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render',action='store_true');parser.add_argument('--activate-manifest',action='store_true')
    for name in ('release','reviewed-sha256','policy','capture','image'):parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    if not args.render:
        print(canonical({'state':'inert','api_writes':False,'files_written':False}));return 0
    require(all(getattr(args,n) for n in ('release','reviewed_sha256','policy','capture','image')),
            'Explicit reviewed release, policy, capture and published image required')
    objects=render(read(args.release),args.reviewed_sha256,read(args.policy),read(args.capture),args.image,
                   activate=args.activate_manifest)
    print(canonical({'apiVersion':'v1','kind':'List','items':objects}));return 0


if __name__=='__main__':raise SystemExit(main())
