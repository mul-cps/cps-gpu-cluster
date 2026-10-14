#!/home/bjoern/git/cps-compute/.venv/bin/python
"""Read-only actual sealed four-process baseline; no mutation entry point."""
import base64, hashlib, importlib.util, json, os
from datetime import datetime, timezone
from pathlib import Path
import subprocess

O=Path('/home/bjoern/.local/state/cps-full-project-20261013')
HERE=Path(__file__).parent
PHASE=O/'hub-custody-handover-a228db7f/phase-a228db7f'
SEED='sha256:4070b4a650f4338cbce4462c96faf832771a76be93c1b7d8166f48bd78cf41d5'
HUB='ghcr.io/mul-cps/cps-compute@sha256:a7155bebb5dff1b70ff79edbf57a1012bb37feed082bac8212c885b46e1cb950'
GATEWAY='ghcr.io/mul-cps/cps-compute@sha256:440711b2bb00151f8625e9df54c97e7ed4d137ca246453aae9ad7524d6681c3d'
NODE='ghcr.io/mul-cps/cps-compute:qualification-native-node-980408a@sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7'
FILES={'new-delivery-seed.json':'130e99093e8b3fb4cf428929e9da4cbb86c2811b279411580fa4abfe58e09eda',
 'new-delivery-activation-readback.json':'a9a3500847fa7cf9de42e29250b4c8e2d8e3e5c8e27a1e9756c55a9974e4051f',
 'delivery-activation-intent.json':'c8905880cf1e64816291913f2c5ca238f3e477deed67aa65914122ed496f0751',
 'final.json':'b548fb12168ac14ef6eabcfb7abbd432b0bbbb899aae7a6f81cacc2bda612a4d'}

def load(name,path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Exact reviewed helper required')
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

m=load('sealed_runtime',O/'run-reviewed-hub-neutral-handover-20261014.py','aedadbbfad1e3bb19b9bf17b4ff839219c075d5f9e1cd7edece14116ef178017')
h,r=m.h,m.r

def current_inputs():
    m.verified_software()
    for name,digest in FILES.items():m.require(hashlib.sha256(m.raw_private(PHASE/name)).hexdigest()==digest,'Exact current completed a715 phase required')
    seed=m.read(PHASE/'new-delivery-seed.json');proof=m.read(PHASE/'new-delivery-activation-readback.json')
    final=m.read(PHASE/'final.json');intent=m.read(PHASE/'delivery-activation-intent.json')
    m.require(r.canonical_sha256(seed)==SEED and final['seed']==seed and final['seed_sha256']==SEED
        and final['ready'] is True and proof['ready'] is True and proof['readiness']['ready'] is True
        and proof['production_qualified'] is False and intent['seed_sha256']==SEED
        and r.parse(base64.b64decode(intent['secret']['data']['config.json'],validate=True))==seed,
        'Current a715 completed publication/input/journal required')
    p=seed['previous_publication'];m.require(p==final['publication'] and seed['previous_publication_sha256']==r.canonical_sha256(p)
        and {c:v['image'] for c,v in p['process_declarations'].items()}=={'gateway':GATEWAY,'node':NODE,'hub:cps':HUB,'hub:cit':HUB},'Exact current four immutable images required')
    journal=r.parse(base64.b64decode(proof['journal_packet']['raw'],validate=True));m.completed(journal,p)
    m.require(journal['config_hash']==SEED and proof['objects']['secret']['data']['config.json']==intent['secret']['data']['config.json']
        and proof['controller']['spec']==intent['controller_patch'][-1]['value'],'Completed a715 durable journal/seed/controller custody required')
    return seed,proof,p

m.current_completed_inputs=current_inputs;m.CURRENT_DIRECTORY=PHASE;m.CURRENT_SEED_SHA256=SEED
h.REVIEWED_IMAGE=HUB

def main():
    context=subprocess.check_output(['kubectl','config','current-context'],text=True).strip();api=m.delivery.Kubectl(context)
    base=m.preflight(api,'read-only-preparation-no-shutdown-authority-claim')
    obs=m.observe(api,base['publication']);code_ref=next(v['configMap']['name'] for v in obs['deployments']['node']['spec']['template']['spec']['volumes'] if v['name']=='code')
    code=api.get('ConfigMap','cps-native-system',code_ref)
    m.write(HERE/'fresh-preflight.json',base);m.write(HERE/'fresh-observations.json',obs);m.write(HERE/'node-code-current.json',code)
    sanitized={'captured_at':datetime.now(timezone.utc).isoformat(),'context':context,'source_sha256':obs['source']['source_sha256'],
      'trusted_revision':obs['source']['trusted_revision'],'driver_epoch':obs['epoch']['driver_epoch'],
      'seed_sha256':SEED,'journal_raw_sha256':base['journal_packet']['raw_sha256'],
      'components':{c:{'deployment_uid':v['metadata']['uid'],'deployment_rv':v['metadata']['resourceVersion'],
        'generation':v['metadata']['generation'],'spec_sha256':r.canonical_sha256(v['spec']),
        'image':base['publication']['process_declarations'][c]['image'],'pod_uid':obs['pods'][c]['metadata']['uid'],
        'pod_name':obs['pods'][c]['metadata']['name'],'ack_uid':obs['acknowledgments'][c]['metadata']['uid'],
        'ack_sha256':r.canonical_sha256(obs['acknowledgments'][c]['data'])} for c,v in obs['deployments'].items()},
      'fresh_all_four_readiness_verified':True,'approved_workspace_pods_absent':True,'Source_workspace_lifecycle_not_observed':True,
      'GPU_inventory_not_yet_observed':True,'authoritative_no_start_fence_not_yet_proven':True,'cluster_mutations':False}
    m.write(HERE/'baseline-sanitized.json',sanitized);print(json.dumps(sanitized,indent=2))

if __name__=='__main__':main()
