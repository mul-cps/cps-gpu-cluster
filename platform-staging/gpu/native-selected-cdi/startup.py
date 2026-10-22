"""Pure optional cold-domain Node init stage; ordinary rotation is untouched."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from cps_compute.native_node.config import NodeConfiguration


def require(v,m):
    if not v:raise ValueError(m)


def candidates(configuration,deployment,*,authority_directory):
    require(type(configuration) is NodeConfiguration,'Actual typed target Node configuration required')
    body=configuration.document;declaration=body['component_declarations']['node']
    require(configuration.reference.to_dict()['namespace']=='cps-native-runtime'
        and configuration.cdi_pins.selected_filename=='cps-native-selected-147.json',
        'Explicit cold-domain selected CDI configuration required')
    require(type(authority_directory) is str and re.fullmatch(
        r'var/lib/cps-native-gpu/domains/[0-9a-f-]{36}/custody/authority',authority_directory),
        'Exact reviewed durable authority directory required')
    require(deployment.get('apiVersion')=='apps/v1' and deployment.get('kind')=='Deployment'
        and all(deployment['metadata'].get(k)==declaration[k] for k in ('namespace','name','uid')),
        'Exact declared Node Deployment identity required')
    spec=deepcopy(deployment['spec']);pod=spec['template']['spec']
    main=[c for c in pod['containers'] if c.get('name')==declaration['container']]
    bootstrap=[c for c in pod.get('initContainers',[]) if c.get('name')=='packaged-bootstrap']
    require(len(main)==len(bootstrap)==1 and main[0]['image']==bootstrap[0]['image']==declaration['image']
        and pod.get('serviceAccountName')==declaration['service_account'],
        'Qualified packaged Node startup/image/service account required')
    require(not any(v.get('name','').startswith('selected-cdi-') for v in pod.get('volumes',[]))
        and not any(c.get('name')=='selected-cdi-prepare' for c in pod.get('initContainers',[])),
        'Selected CDI startup already installed or colliding')
    pool=configuration.deployment.node_pool
    settings={'version':1,'node_pool':{k:pool[k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')},
        'cdi_pins':configuration.cdi_pins.to_dict(),'authority_directory':authority_directory}
    data={'selected_cdi.py':Path(__file__).with_name('selected_cdi.py').read_text(),
        'settings.json':json.dumps(settings,sort_keys=True,separators=(',',':'))}
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    cm={'apiVersion':'v1','kind':'ConfigMap','immutable':True,
        'metadata':{'namespace':declaration['namespace'],'name':'cps-native-selected-cdi-'+digest[:16]},'data':data}
    pod.setdefault('volumes',[]).extend([
        {'name':'selected-cdi-code','configMap':{'name':cm['metadata']['name'],'defaultMode':0o444}},
        {'name':'selected-cdi-host','hostPath':{'path':'/','type':'Directory'}},
        {'name':'selected-cdi-output','hostPath':{'path':'/run/cdi','type':'Directory'}}])
    initializer={'name':'selected-cdi-prepare','image':declaration['image'],'imagePullPolicy':'IfNotPresent',
        'command':['python','-I','-B','/opt/selected-cdi/selected_cdi.py','--execute','--settings','/opt/selected-cdi/settings.json'],
        'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':'void'}],
        'securityContext':{'runAsUser':0,'runAsGroup':0,'allowPrivilegeEscalation':False,
            'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
        'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'1','memory':'256Mi'}},
        'volumeMounts':[{'name':'selected-cdi-code','mountPath':'/opt/selected-cdi/selected_cdi.py','subPath':'selected_cdi.py','readOnly':True},
            {'name':'selected-cdi-code','mountPath':'/opt/selected-cdi/settings.json','subPath':'settings.json','readOnly':True},
            {'name':'selected-cdi-host','mountPath':'/host','readOnly':True,'mountPropagation':'HostToContainer'},
            {'name':'selected-cdi-output','mountPath':'/cdi','readOnly':False}]}
    pod['initContainers'].insert(0,initializer)
    return {'configmap':cm,'spec':spec}
