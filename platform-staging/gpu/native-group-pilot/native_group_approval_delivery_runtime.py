"""Offline disabled runtime template; operator supplies image and input identities."""
import argparse
import json
from pathlib import Path

import native_group_approval_renderer as r


def role_update_policy(publication, access, namespace, name):
    """Named escalation is paired with fail-closed GET-name-only admission."""
    namespaces=sorted({p['namespace'] for p in publication['process_declarations'].values()})
    roles={target:sorted(o['metadata']['name'] for o in access
        if o['kind']=='Role' and o['metadata']['namespace']==target) for target in namespaces}
    controllers={target:sorted(p['name'] for p in publication['process_declarations'].values()
        if p['namespace']==target) for target in namespaces}
    names=("current.resourceNames.all(n, n in previous.resourceNames || "
        "(current.apiGroups == [''] && current.resources == ['configmaps'] && "
        "(n.matches('^cps-native-approvals-[0-9a-f]{16}$') || n.matches('^cps-native-approval-reference-[0-9a-f]{16}$'))) || "
        "(((current.apiGroups == [''] && current.resources == ['pods']) || "
        "(current.apiGroups == ['apps'] && current.resources == ['replicasets'])) && "
        "size(n) <= 253 && n.matches('^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$') && "
        "variables.controllersByNamespace[request.namespace].exists(d, n.startsWith(d + '-'))))")
    matches=("current == previous || (previous.verbs == ['get'] && current.verbs == previous.verbs && "
        "current.apiGroups == previous.apiGroups && current.resources == previous.resources && "
        "has(current.nonResourceURLs) == has(previous.nonResourceURLs) && "
        "(!has(previous.nonResourceURLs) || current.nonResourceURLs == previous.nonResourceURLs) && "
        "has(current.resourceNames) && has(previous.resourceNames) && size(current.resourceNames) > 0 && "+names+")")
    policy_name=name+'-role-update'
    return [
        {'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicy',
            'metadata':{'name':policy_name},'spec':{'failurePolicy':'Fail',
                'matchConstraints':{'resourceRules':[{'apiGroups':['rbac.authorization.k8s.io'],
                    'apiVersions':['v1'],'resources':['roles'],'operations':['UPDATE']}]},
                'matchConditions':[{'name':'dedicated-delivery-identity','expression':
                    'request.userInfo.username == '+json.dumps('system:serviceaccount:'+namespace+':'+name)}],
                'variables':[{'name':'rolesByNamespace','expression':json.dumps(roles)},
                    {'name':'controllersByNamespace','expression':json.dumps(controllers)}],
                'validations':[
                    {'expression':'request.namespace in variables.rolesByNamespace && object.metadata.name in variables.rolesByNamespace[request.namespace]',
                        'message':'Only seven exact owned approval Roles'},
                    {'expression':'object.metadata.namespace == request.namespace && oldObject.metadata.namespace == request.namespace && object.metadata.name == oldObject.metadata.name && object.metadata.uid == oldObject.metadata.uid',
                        'message':'Preserve original named Role identity'},
                    {'expression':'size(object.rules) == size(oldObject.rules) && '+
                        'object.rules.map(current, [current.apiGroups,current.resources,current.verbs]) == '+
                        'oldObject.rules.map(previous, [previous.apiGroups,previous.resources,previous.verbs]) && '+
                        'object.rules.all(current, oldObject.rules.exists(previous, ('+matches+'))) && '+
                        'oldObject.rules.all(previous, object.rules.exists(current, ('+matches+')))',
                        'message':'Only named GET targets may change; retain every other permission exactly'}]}},
        {'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicyBinding',
            'metadata':{'name':policy_name},'spec':{'policyName':policy_name,'validationActions':['Deny']}}]


def render(seed, *, image, config_secret, journal_pvc, context, namespace='cps-compute', protected_capture=False, image_pull_secret=None):
    r.require(type(protected_capture) is bool, 'Explicit protected capture material setting required')
    r.require(seed['previous_publication_sha256']==r.canonical_sha256(seed['previous_publication']),
        'Reviewed installed publication pin required')
    r.require(isinstance(image,str) and '@sha256:' in image and len(image.rsplit('@sha256:',1)[1])==64
        and all(c in '0123456789abcdef' for c in image.rsplit('@sha256:',1)[1]), 'Immutable controller image required')
    for name in (namespace,config_secret,journal_pvc):
        r.require(isinstance(name,str) and name and len(name)<=63
            and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in name), 'Operator runtime identity required')
    if image_pull_secret is not None:
        r.require(isinstance(image_pull_secret,str) and image_pull_secret and len(image_pull_secret)<=63
            and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in image_pull_secret),
            'Operator image pull Secret name required')
    name='cps-native-approval-delivery'; publication=seed['previous_publication']
    subject={'kind':'ServiceAccount','namespace':namespace,'name':name}
    objects=[{'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':namespace,'name':name}}]
    access=r.access_intent(projection=publication)['objects']
    namespaces=sorted({p['namespace'] for p in publication['process_declarations'].values()})
    for target in namespaces:
        deployments=sorted(p['name'] for p in publication['process_declarations'].values() if p['namespace']==target)
        roles=sorted(o['metadata']['name'] for o in access if o['kind']=='Role' and o['metadata']['namespace']==target)
        metadata={'namespace':target,'name':name}
        objects.extend([
            {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata,'rules':[
                {'apiGroups':['apps'],'resources':['deployments'],'resourceNames':deployments,'verbs':['get','patch']},
                {'apiGroups':['rbac.authorization.k8s.io'],'resources':['roles'],'resourceNames':roles,'verbs':['get','patch','escalate']},
                # Future content-addressed CM/Pod/RS names cannot be put in
                # static resourceNames. Reads stay within four namespaces;
                # admission limits CREATE to exact immutable projection forms.
                {'apiGroups':[''],'resources':['configmaps'],'verbs':['get','create']},
                {'apiGroups':[''],'resources':['pods'],'verbs':['list']},
                {'apiGroups':['apps'],'resources':['replicasets'],'verbs':['get']}]},
            {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':dict(metadata),
                'subjects':[dict(subject)],'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':name}}])
    admission_name=name+'-immutable-create'
    objects.extend([
        {'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicy',
            'metadata':{'name':admission_name},'spec':{'failurePolicy':'Fail',
                'matchConstraints':{'resourceRules':[{'apiGroups':[''],'apiVersions':['v1'],
                    'resources':['configmaps'],'operations':['CREATE']}]},
                'matchConditions':[{'name':'dedicated-delivery-identity','expression':
                    'request.userInfo.username == '+json.dumps('system:serviceaccount:'+namespace+':'+name)}],
                'validations':[
                    {'expression':'request.namespace in '+json.dumps(namespaces),'message':'Only four approval projection namespaces'},
                    {'expression':'has(object.immutable) && object.immutable == true && has(object.data) && size(object.data) == 1',
                        'message':'Only one-key immutable projection ConfigMaps'},
                    {'expression':"(!has(object.binaryData) || size(object.binaryData) == 0) && (!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0)",
                        'message':'No binary data or garbage-collection owners'},
                    {'expression':"(object.metadata.name.matches('^cps-native-approvals-[0-9a-f]{16}$') && 'approval.json' in object.data) || (object.metadata.name.matches('^cps-native-approval-reference-[0-9a-f]{16}$') && 'reference.json' in object.data)",
                        'message':'Only content-addressed document/reference names and keys'}]}},
        {'apiVersion':'admissionregistration.k8s.io/v1','kind':'ValidatingAdmissionPolicyBinding',
            'metadata':{'name':admission_name},'spec':{'policyName':admission_name,'validationActions':['Deny']}}])
    objects.extend(role_update_policy(publication,access,namespace,name))
    input_names=('config.json','source-command.json','epoch-command.json','kubeconfig')
    if protected_capture:input_names+=('export.token','gateway-ca.pem')
    copy_inputs="from pathlib import Path; import os; p=Path('/inputs/delivery'); p.mkdir(mode=0o700); " \
        "[(p.joinpath(n).write_bytes(Path('/seed').joinpath(n).read_bytes()),os.chmod(p/n,0o600)) for n in " + repr(input_names) + "]"
    security={'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'allowPrivilegeEscalation':False,
        'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}
    objects.append({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':namespace,'name':name},
        'spec':{'replicas':0,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':name}},
            'template':{'metadata':{'labels':{'app':name}},'spec':{'serviceAccountName':name,
                'securityContext':{'fsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
                'initContainers':[{'name':'private-inputs','image':image,'command':['python','-c',copy_inputs],
                    'securityContext':dict(security),'volumeMounts':[
                        {'name':'seed','mountPath':'/seed','readOnly':True},{'name':'inputs','mountPath':'/inputs'}]}],
                'containers':[{'name':'delivery','image':image,
                    'command':['python','/opt/cps-native-delivery/native_group_approval_delivery.py'],
                    'args':['--run','--config','/inputs/delivery/config.json','--state-dir','/journal/delivery',
                        '--capture-command','/inputs/delivery/source-command.json','--epoch-command','/inputs/delivery/epoch-command.json',
                        '--context',context],
                    'env':[{'name':'KUBECONFIG','value':'/inputs/delivery/kubeconfig'},
                        {'name':'PYTHONDONTWRITEBYTECODE','value':'1'}],
                    'securityContext':dict(security),'resources':{'requests':{'cpu':'50m','memory':'128Mi'},
                        'limits':{'cpu':'500m','memory':'512Mi'}},
                    'volumeMounts':[{'name':'inputs','mountPath':'/inputs','readOnly':True},
                        {'name':'journal','mountPath':'/journal'},{'name':'tmp','mountPath':'/tmp'}]}],
                'volumes':[{'name':'seed','secret':{'secretName':config_secret,'defaultMode':0o444}},
                    {'name':'inputs','emptyDir':{}},{'name':'journal','persistentVolumeClaim':{'claimName':journal_pvc}},
                    {'name':'tmp','emptyDir':{}}]}}}})
    if image_pull_secret is not None:
        objects[-1]['spec']['template']['spec']['imagePullSecrets']=[{'name':image_pull_secret}]
    return objects


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=Path,required=True); parser.add_argument('--image',required=True)
    parser.add_argument('--config-secret',required=True); parser.add_argument('--journal-pvc',required=True)
    parser.add_argument('--context',required=True)
    parser.add_argument('--protected-capture',action='store_true')
    parser.add_argument('--image-pull-secret')
    args=parser.parse_args(argv)
    objects=render(r._private_json(args.seed),image=args.image,config_secret=args.config_secret,
        journal_pvc=args.journal_pvc,context=args.context,protected_capture=args.protected_capture,
        image_pull_secret=args.image_pull_secret)
    print(r.canonical({'apiVersion':'v1','kind':'List','items':objects})); return 0


if __name__=='__main__': raise SystemExit(main())
