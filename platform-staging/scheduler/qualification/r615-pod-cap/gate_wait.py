#!/usr/bin/env python3
"""Trusted CPU-only first init; read-only root receipt, no GPU or API authority."""
import argparse
import json
import os
from pathlib import Path
import time


def verify(proof, uid, gpu, cap, boot, start):
    expected={'state':'applied-before-main','pod_uid':uid,'gpu_uuid':gpu,'cap_bytes':cap*1048576,
              'boot_id':boot,'pid_start_ticks':start}
    if not isinstance(proof,dict) or any(proof.get(k)!=v for k,v in expected.items()):
        raise ValueError('Exact current applied driver-cap receipt required')
    readback=proof.get('readback')
    if not isinstance(readback,dict) or readback.get('soft')!=cap*1048576 or readback.get('hard')!=cap*1048576:
        raise ValueError('Exact driver cap readback required')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--pod-uid',default=os.environ.get('POD_UID'),required='POD_UID' not in os.environ)
    parser.add_argument('--gpu-uuid',required=True)
    parser.add_argument('--cap-mib',type=int,choices=(64,128,5120,10240,20480),required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:print(json.dumps({'state':'inert','gpu_calls':False}));return
    # This exact Python process must be the CRI first-init PID1, not a child wrapper.
    start=int(Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19])
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        if args.receipt.exists():
            stat=args.receipt.lstat()
            if args.receipt.is_symlink() or stat.st_uid!=0 or stat.st_mode&0o777!=0o600:
                raise ValueError('Read-only native root-owned0600 receipt required')
            proof=json.loads(args.receipt.read_text())
            if proof.get('state')=='prepared-before-set':time.sleep(0.2);continue
            verify(proof,args.pod_uid,args.gpu_uuid,args.cap_mib,boot,start)
            print(json.dumps({'state':'first-init-driver-cap-verified','pod_uid':args.pod_uid}));return
        time.sleep(0.2)
    raise TimeoutError('Driver-cap gate timeout; user containers must remain blocked')


if __name__=='__main__':main()
