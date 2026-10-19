#!/usr/bin/env python3
"""Offline OCI wrapper for the exact reviewed binder; no publication or live API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import recipe

ROOT=Path(__file__).resolve().parent
BASE='ghcr.io/kai-scheduler/kai-scheduler/binder@sha256:1d10b1b212faddab22cdaea5da2f9d17e1d4154d68d7d0f4bfc44dc6a343624b'
BINARY_SHA='4c99d890064a4024f0dc9b4b69c641b16a4f14718a0c2d98c6944a4d215c3bb0'
IMAGE='localhost/cps-native-kai-binder:registry-before-prebind-bdf434e-ed6bece8'
STOCK_CONFIG={'User':'65532:65532','Env':['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','TARGETARCH=amd64','SERVICE_NAME=binder'], 'Entrypoint':['/workspace/app'],'WorkingDir':'/workspace'}
LABELS={'org.mul-cps.kai.upstream-revision':recipe.COMMIT,
        'org.mul-cps.kai.patch-sha256':recipe.PATCH_SHA256,'org.mul-cps.binary-sha256':BINARY_SHA}


def verify_inputs(binary,receipt):
    if binary.is_symlink() or recipe.sha(binary)!=BINARY_SHA:
        raise ValueError('Exact reviewed static binary required')
    value=json.loads(receipt.read_text());manifest,_=recipe.load_manifest()
    verify_build_receipt(value,manifest)
    return recipe.verify_static_elf(binary)


def verify_build_receipt(value,manifest):
    expected={'binary_sha256':BINARY_SHA,'upstream_commit':recipe.COMMIT,
        'patch_sha256':recipe.PATCH_SHA256,'toolchain_sha256':recipe.TOOLCHAIN_SHA256,
        'source_files':manifest['files'],'rebuild_identical':True,'CGO_ENABLED':0,
        'go_version':recipe.GO_VERSION,'all_affected_packages_passed':list(recipe.PACKAGES)}
    if any(value.get(k)!=v for k,v in expected.items()):
        raise ValueError('Exact successful reviewed build receipt required')


def verify_stock_config(config):
    if config!=STOCK_CONFIG:
        raise ValueError('Exact inspected stock runtime configuration required')


def verify_candidate_config(stock,candidate):
    expected=dict(stock,Labels=LABELS)
    if candidate!=expected:
        raise ValueError('Candidate runtime configuration drifted from stock')


def command(*args):
    return subprocess.check_output(list(args),text=True,stderr=subprocess.STDOUT,timeout=180)


def inspect(image):
    return json.loads(command('podman','image','inspect',image))[0]


def filesystem(image,output):
    container=command('podman','create','--pull=never','--network=none',image,'--help').strip()
    try:
        command('podman','export','--output',str(output),container)
    finally:
        command('podman','rm',container)
    result={}
    with tarfile.open(output) as archive:
        for item in archive:
            name=item.name.removeprefix('./').rstrip('/')
            if name in result:
                raise ValueError('Duplicate image filesystem entry')
            digest=None
            if item.isfile():
                stream=archive.extractfile(item)
                if stream is None:raise ValueError('Actual regular image file required')
                with stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            result[name]={'type':item.type.decode('ascii'),'mode':item.mode,'uid':item.uid,
                          'gid':item.gid,'link':item.linkname,'sha256':digest}
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--binary',type=Path);parser.add_argument('--receipt',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if not args.build:
        print(json.dumps({'mode':'inert','published':False,'live_operations':False}));return 0
    if not all((args.binary,args.receipt,args.output)):
        raise ValueError('Explicit reviewed binary/receipt and new private output required')
    elf=verify_inputs(args.binary,args.receipt)
    if args.output.exists() or args.output.is_symlink():raise ValueError('New private output required')
    base=inspect(BASE);verify_stock_config(base['Config'])
    args.output.mkdir(mode=0o700,parents=True)
    out=args.output.resolve();context=out/'context';context.mkdir(mode=0o700)
    shutil.copyfile(args.binary,context/'binder');os.chmod(context/'binder',0o755)
    shutil.copyfile(ROOT/'Dockerfile',context/'Dockerfile')
    logs=[]
    for image in (IMAGE,IMAGE+'-rebuild'):
        logs.append(command('podman','build','--pull=never','--network=none','--timestamp','0',
            '--no-cache','--tag',image,str(context)))
    candidate=inspect(IMAGE);rebuilt=inspect(IMAGE+'-rebuild')
    if candidate['Id']!=rebuilt['Id']:raise ValueError('Repeated OCI config/layers differ')
    verify_candidate_config(base['Config'],candidate['Config'])
    before=filesystem(BASE,out/'stock.filesystem.tar')
    after=filesystem(IMAGE,out/'candidate.filesystem.tar')
    installed=after.pop('workspace/app');before.pop('workspace/app')
    if installed!={'type':'0','mode':0o755,'uid':65532,'gid':0,'link':'','sha256':BINARY_SHA}:
        raise ValueError('Installed binary ownership/mode/bytes differ')
    if before!=after:raise ValueError('Non-binary image filesystem drifted from stock')
    cert=after.get('etc/ssl/certs/ca-certificates.crt')
    if not cert or cert['type']!='0':raise ValueError('Stock CA bundle missing')
    help_output=command('podman','run','--rm','--pull=never','--network=none','--read-only',
        '--cap-drop=ALL','--security-opt=no-new-privileges','--security-opt=label=disable',
        '--memory=256m','--cpus=1',IMAGE,'--help')
    if '--native-pending-coordinator-enabled' not in help_output:
        raise ValueError('Installed terminal bridge flag missing')
    command('podman','save','--format','oci-dir','--output',str(out/'image.oci'),IMAGE)
    index=json.loads((out/'image.oci/index.json').read_text())
    if len(index['manifests'])!=1:raise ValueError('Exact single local OCI manifest required')
    manifest_digest=index['manifests'][0]['digest']
    receipt={'version':1,'base_image':BASE,'base_config_id':base['Id'],'local_image':IMAGE,
        'image_config_id':candidate['Id'],'oci_manifest_digest':manifest_digest,
        'binary_sha256':BINARY_SHA,'installed_static_elf':elf,'runtime_config':candidate['Config'],
        'unchanged_filesystem_entries':len(after),'ca_bundle_sha256':cert['sha256'],
        'rebuilt_image_identical':True,'help_exit':0,'help_sha256':hashlib.sha256(help_output.encode()).hexdigest(),
        'patch_sha256':recipe.PATCH_SHA256,'upstream_commit':recipe.COMMIT,
        'dockerfile_sha256':recipe.sha(ROOT/'Dockerfile'),'oci_recipe_sha256':recipe.sha(ROOT/'oci.py'),
        'published':False,'live_operations':False,'production_qualified':False}
    for name,value in [('verification.json',json.dumps(receipt,sort_keys=True,indent=2)+'\n'),
                       ('build.log',''.join(logs)),('installed-help.txt',help_output)]:
        (out/name).write_text(value);os.chmod(out/name,0o600)
    print(json.dumps(receipt,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
