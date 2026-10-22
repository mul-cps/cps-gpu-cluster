#!/usr/bin/env python3
"""Default-inert exact-source adapter: unchanged A5 import engines with fresh B10 peer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import types

HERE=Path(__file__).resolve().parent
POLICY='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281'
PRODUCER_SHA='a35c0778bba76b0ca840216d585ef850cefb2313af7d1ca2ad6fb3c2688a019b'
PINS={'run_imports.py':'5ad010a9823f8c02276eebb99779071b98d81bb45561ba7f9383e9b9bfedb802',
      'same_parent_engine.py':'dc6103ae49c8b91dab546f62fa67515a1fecd3caa3964cb220bda7d1c5aa9e58',
      'same_pod_imports.py':'d8cdbf06d93a0f46e0fc122f5f547ff121d0728b7d99b55f1ca8345c574e4f6c'}
GENERATED={'fresh_preflight.py':'8ada30e9aca3c49dd1835816589435986209145b5204b256368b933c50b6ff1c',
           'peer_probe.py':'4e526355f18832da728b6fcdb9f525513c6451fc06b3ea56a57eb9795519a0b0',
           'run_peer_oom.py':'4962c47258748f569122a4f9a51f247b94ddbfa206350d6c33ef81d3931e8b77'}


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def replace(source,old,new):
    require(source.count(old)==1,'Exact reviewed import adaptation span changed: '+old[:80])
    return source.replace(old,new)


def build_sources():
    raw={name:(HERE.parent/'native-fresh-imports'/name).read_bytes() for name in PINS}
    producer=(HERE/'prepare.py').read_bytes()
    require(sha(producer)==PRODUCER_SHA and all(sha(raw[name])==pin for name,pin in PINS.items()),
            'Exact complete import and producer sources required before execution')
    module=types.ModuleType('unequal_producer');module.__file__=str(HERE/'prepare.py')
    exec(compile(producer,module.__file__,'exec'),module.__dict__)
    generated=module.build_sources('5-10')
    require(all(sha(generated[name])==pin for name,pin in GENERATED.items()),'Exact fixed5/10 peer sources required')
    source=raw['run_imports.py'].decode()
    for old,name in (('1e8a0d398672842bd124a3bbe3fbde50817b76c5394714dfbd374695d220653a','run_peer_oom.py'),
                     ('07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58','fresh_preflight.py'),
                     ('ea49812f2f68371a27f63e709534f08aa1b23028395c4b76b2efc07b88d86834','peer_probe.py')):
        source=replace(source,old,GENERATED[name])
    source=replace(source,"common=here.parent/'native-fresh-domain'","common=here")
    source=replace(source,"p.add_argument('--side',choices=('a','b'),default='a')", "p.add_argument('--side',choices=('a',),default='a')")
    source=replace(source,"        before=current.preflight({'manifest':targets});write(a.output/'before.json',before)",
        "        before=current.preflight({'manifest':targets})\n        require(all(row['intent']['policy_hash']=="+repr(POLICY)+" for row in before['host']['targets']),'Actual protected Source332 intents required')\n        write(a.output/'before.json',before)")
    raw['run_imports.py']=source.encode()
    raw.update({name:generated[name] for name in GENERATED})
    for name,content in raw.items():compile(content,name,'exec')
    return raw


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true')
    p.add_argument('--output',type=Path);args=p.parse_args(argv)
    if not args.prepare:print(json.dumps({'inert':True,'api_calls':False,'gpu_calls':False}));return
    require(args.output is not None,'Exclusive private output directory required')
    raw=build_sources();args.output.mkdir(mode=0o700)
    receipt={'version':1,'pair':'5-10','source_sha256':PINS,'producer_sha256':PRODUCER_SHA,
        'generated_sha256':{name:sha(content) for name,content in raw.items()},
        'policy_hash':POLICY,'side':'a','hardware_qualified':False,'production_qualified':False}
    raw['preparation.json']=(json.dumps(receipt,sort_keys=True)+'\n').encode()
    for name,content in raw.items():
        fd=os.open(args.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(content)
    print(json.dumps({'prepared':True,'output':str(args.output),'api_calls':False,'gpu_calls':False}))


if __name__=='__main__':main()
