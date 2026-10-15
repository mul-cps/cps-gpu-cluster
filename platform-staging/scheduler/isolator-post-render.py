#!/usr/bin/env python3
"""Scope the reviewed isolator webhook before Helm activates it."""
import sys
import yaml
items=list(yaml.safe_load_all(sys.stdin))
matched=0
for item in items:
    if not item or item.get('kind')!='MutatingWebhookConfiguration':continue
    if item['metadata']['name']!='kai-resource-isolator-mutating':raise SystemExit('Unexpected mutating webhook in isolator chart')
    for webhook in item['webhooks']:
        if webhook['name']!='vgpu.lib.kai-resource-isolator.io':raise SystemExit('Unexpected isolator webhook')
        webhook['namespaceSelector']={'matchLabels':{'compute.cps.unileoben.ac.at/isolation':'required'}}
        webhook.pop('objectSelector',None)
        webhook['matchConditions']=[{'name':'kai-workload','expression':"object.spec.schedulerName == 'kai-scheduler'"}]
        matched+=1
if matched!=1:raise SystemExit('Exactly one reviewed isolator webhook required')
yaml.safe_dump_all(items,sys.stdout,sort_keys=False)
