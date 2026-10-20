"""Pure explicit checkpoint Job; no rotation, legacy adoption or new grants.

Root independently pins the actual immutable manifest and establishes maintenance
fences. The installed SDK owns all authority checks and lossless journal custody.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re


def render(config, *, configuration, image, config_secret, journal_pvc, job_name,
           checkpoint_reference, namespace='cps-compute', image_pull_secret=None,
           active_deadline_seconds=300):
    spec=importlib.util.spec_from_file_location('checkpoint_delivery_runtime',Path(__file__).with_name('render.py'))
    runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    runtime.require(checkpoint_reference is not None,'Independent immutable checkpoint reference required')
    runtime.require(isinstance(job_name,str)and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?',job_name),
        'Explicit canonical checkpoint Job name required')
    runtime.require(type(active_deadline_seconds)is int and 1<=active_deadline_seconds<=900,
        'Finite one-attempt checkpoint deadline required')
    docs=runtime.render(config,configuration=configuration,image=image,config_secret=config_secret,
        journal_pvc=journal_pvc,namespace=namespace,image_pull_secret=image_pull_secret,
        checkpoint_reference=checkpoint_reference)
    template=deepcopy(next(o for o in docs if o['kind']=='Deployment')['spec']['template'])
    template['spec']['restartPolicy']='Never'
    template['spec']['containers'][0]['args']+=['--checkpoint']
    return {'apiVersion':'batch/v1','kind':'Job','metadata':{'namespace':namespace,'name':job_name},
        'spec':{'backoffLimit':0,'activeDeadlineSeconds':active_deadline_seconds,
            'parallelism':1,'completions':1,'template':template}}
