"""Pure one-attempt, same-journal configuration rotation Job.

Root must stop the writer and establish maintenance fences before applying.
The installed SDK authenticates current authority and preserves original custody.
This renderer grants no permissions and performs no API or filesystem actions.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path, PurePosixPath
import re


def _runtime():
    spec=importlib.util.spec_from_file_location('rotation_delivery_runtime',Path(__file__).with_name('render.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def render(config, *, configuration, image, config_secret, journal_pvc, job_name,
           previous_config_sha256, previous_state_sha256, anchor_sha256,
           previous_node_template_sha256, namespace='cps-compute',
           image_pull_secret=None, active_deadline_seconds=300):
    runtime=_runtime()
    for value in (previous_config_sha256,previous_state_sha256,anchor_sha256,previous_node_template_sha256):
        runtime.require(isinstance(value,str) and re.fullmatch(r'sha256:[a-f0-9]{64}',value)
            and value!='sha256:'+'0'*64,'Explicit original byte SHA-256 pins required')
    runtime.require(isinstance(job_name,str) and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?',job_name),
        'Explicit canonical rotation Job name required')
    runtime.require(type(active_deadline_seconds) is int and 1<=active_deadline_seconds<=900,
        'Finite one-attempt rotation deadline required')
    docs=runtime.render(config,configuration=configuration,image=image,config_secret=config_secret,
        journal_pvc=journal_pvc,namespace=namespace,image_pull_secret=image_pull_secret)
    extras={'previous-config.json':previous_config_sha256,'previous-node-template.json':previous_node_template_sha256}
    current={'delivery.json',*(PurePosixPath(path).name for path in
        (config['policy_path'],config['capture']['ca_file'],config['capture']['token_file']))}
    runtime.require(not current.intersection(extras),'Previous rotation inputs cannot shadow current protected files')
    template=deepcopy(next(o for o in docs if o['kind']=='Deployment')['spec']['template'])
    pod=template['spec'];pod['restartPolicy']='Never'
    pod['containers'][0]['args'] += ['--rotate-config','--previous-config','/inputs/delivery/previous-config.json',
        '--previous-config-sha256',previous_config_sha256,'--previous-state-sha256',previous_state_sha256,
        '--anchor-sha256',anchor_sha256,'--previous-node-template','/inputs/delivery/previous-node-template.json']
    # Fixed extra Secret keys only. No raw configuration/template or token bytes
    # are embedded. The SDK revalidates the archived originals during rotation.
    pod['initContainers'][0]['command'][-1] += '\nimport hashlib\n' + '\n'.join(
        "raw = Path('/seed/"+name+"').read_bytes()\n"
        "if 'sha256:' + hashlib.sha256(raw).hexdigest() != "+repr(pin)+":\n"
        "    raise ValueError('Original rotation input byte pin differs')\n"
        "fd = os.open('/inputs/delivery/"+name+"', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)\n"
        "with os.fdopen(fd, 'wb') as output:\n"
        "    output.write(raw)\n    output.flush()\n    os.fsync(output.fileno())\n"
        for name,pin in extras.items())
    return {'apiVersion':'batch/v1','kind':'Job','metadata':{'namespace':namespace,'name':job_name},
        'spec':{'backoffLimit':0,'activeDeadlineSeconds':active_deadline_seconds,
            'parallelism':1,'completions':1,'template':template}}
