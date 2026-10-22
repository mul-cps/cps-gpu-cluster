#!/usr/bin/env python3
"""Default-inert exact-preimage preparation of A5/B10 MPS sources; no live calls."""
import argparse,hashlib,json,os,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
PINS={'run_mps.py':'87e81c18737f72d0d7884ee676cff3e85680387e75374c2f6d232d77ec413ca7','engine.py':'a2dd364c6650336cbe2902f792bac625cbcbf074bb7971d38bcd9bd8027029df','mapper.py':'35b968c0d3291dc9d6b020c86a9ea0223662cb30a1211217f7e547374713273b','mps_probe.py':'a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e'}
PRODUCER_SHA='a35c0778bba76b0ca840216d585ef850cefb2313af7d1ca2ad6fb3c2688a019b'
def require(ok,msg):
 if not ok:raise ValueError(msg)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def replace(text,old,new):
 require(text.count(old)==1,'Exact reviewed adaptation span changed');return text.replace(old,new)
def build_sources():
 raw=(HERE/'prepare.py').read_bytes();require(digest(raw)==PRODUCER_SHA,'Exact cohort producer required')
 producer_raw=raw;result={}
 for name,pin in PINS.items():
  raw=(HERE.parent/'native-fresh-mps'/name).read_bytes();require(digest(raw)==pin,'Exact original MPS source required');result[name]=raw
 producer=types.ModuleType('mps_cohort_producer');producer.__file__=str(HERE/'prepare.py');exec(compile(producer_raw,producer.__file__,'exec'),producer.__dict__)
 generated=producer.build_sources('5-10')
 source=result['run_mps.py'].decode()
 for old,new in [('07137f623f1a0c383597c90fbf485f4ea95597a553b433ffc388dcedcbd70d58','8ada30e9aca3c49dd1835816589435986209145b5204b256368b933c50b6ff1c'),('1e8a0d398672842bd124a3bbe3fbde50817b76c5394714dfbd374695d220653a','4962c47258748f569122a4f9a51f247b94ddbfa206350d6c33ef81d3931e8b77'),('ea49812f2f68371a27f63e709534f08aa1b23028395c4b76b2efc07b88d86834','4e526355f18832da728b6fcdb9f525513c6451fc06b3ea56a57eb9795519a0b0'),("common=here.parent/'native-fresh-domain'","common=here"),("choices=('a','b')","choices=('a',)")]:source=replace(source,old,new)
 source=replace(source,"targets=current.read_targets(a.manifest,a.manifest_sha256);a.output.mkdir(mode=0o700)","targets=current.read_targets(a.manifest,a.manifest_sha256)\n require(targets['pods']['a']['cap_mib']==5120 and targets['pods']['b']['cap_mib']==10240,'Exact reviewed A5/B10 cohort required')\n a.output.mkdir(mode=0o700)")
 source=replace(source,"before=current.preflight({'manifest':targets});write(a.output/'before.json',before)","before=current.preflight({'manifest':targets})\n   require(len(before['host']['targets'])==2 and all(t['intent']['policy_hash']=='sha256:332d14fb9e510b9810feffb8d40b408743f9679ebd13ca1ba0e1077d666e9281' for t in before['host']['targets']),'Actual sealed Source332 intent required')\n   write(a.output/'before.json',before)")
 result['run_mps.py']=source.encode()
 for name in ('fresh_preflight.py','peer_probe.py','run_peer_oom.py'):result[name]=generated[name]
 return result

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args(argv)
 if not a.prepare:print('{"state":"inert","api_calls":false,"gpu_calls":false}');return
 require(a.output is not None,'New output directory required');sources=build_sources();a.output.mkdir(mode=0o700)
 for name,raw in sources.items():
  fd=os.open(a.output/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 print(json.dumps({'state':'prepared','sources':{n:digest(r) for n,r in sources.items()},'hardware_qualified':False},sort_keys=True))
if __name__=='__main__':main()
