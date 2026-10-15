#!/usr/bin/env python3
"""Verify recorded pilot compatibility without imports from artifacts or live calls.

This extends the policy compiler's six-report validation. A successful result
checks recorded bytes and compatibility; independent Root review supplies the
hardware/activation authority. It does not qualify a full-platform release.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
COMPILER_PATH = ROOT / 'scripts/compile_compute_policy.py'
spec = importlib.util.spec_from_file_location('candidate_policy_compiler', COMPILER_PATH)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
SCOPES = ['cps:native-group-b', 'cit:native-group-a']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def read_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 32*1024*1024,
                'bounded regular artifact required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(32*1024*1024+1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and all(getattr(before,k) == getattr(after,k)
                for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
                'artifact changed during verification')
        return raw
    finally:
        os.close(fd)


def field(value, fields):
    require(isinstance(fields,list) and fields and all(isinstance(k,str) for k in fields),
            'explicit provenance field required')
    for name in fields:
        value = value[name]
    return value


def modules(value):
    require(isinstance(value,dict) and value, 'source module map required')
    result = {k.removeprefix('src/'):v for k,v in value.items()}
    require(len(result)==len(value) and all(isinstance(k,str) and k.endswith('.py')
            and '..' not in Path(k).parts and not Path(k).is_absolute()
            and isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for k,v in result.items()),
            'invalid source module identity')
    return result


def image_identity(value):
    require(isinstance(value,str) and re.fullmatch(r'[^\s@]+@sha256:[0-9a-f]{64}',value),
            'immutable image required')
    repository,digest = value.split('@')
    prefix,separator,last = repository.rpartition('/')
    return (prefix+separator+last.split(':')[0],digest)


def verify_candidate(candidate, repository_root, artifact_root):
    require(candidate.get('schemaVersion')==1 and candidate.get('artifactKind')=='restricted-pilot-release-candidate',
            'unsupported release candidate')
    for flag in ['productionQualified','releasePublished','fleetPromoted','matchingCurrentSdkNotebookMatrix']:
        require(candidate.get(flag) is False, 'restricted pilot cannot assert '+flag)
    require(candidate['scope']['profiles']==['interactive-shared-5']
            and candidate['scope']['workspaces']==SCOPES, 'exact two-scope 5 GiB approval required')
    require(candidate['compilerSha256']==sha(read_bytes(COMPILER_PATH)), 'policy compiler source pin mismatch')
    raw,values,paths = {},{},{}
    for name,entry in candidate['artifacts'].items():
        require(set(entry)=={'root','path','sha256'} and entry['root'] in ('repository','private'),
                'closed artifact binding required')
        relative=Path(entry['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'artifact path must remain in its declared root')
        path=Path(repository_root if entry['root']=='repository' else artifact_root)/relative
        raw[name]=read_bytes(path); paths[name]=path
        require(sha(raw[name])==entry['sha256'], 'missing or altered artifact: '+name)
    def document(name):
        if name not in values: values[name]=compiler._decode_json(raw[name])
        return values[name]

    proof=document('nativeProof')
    compiled=compiler.compile_catalog(document('catalog'),native_group_evidence=proof,
        native_group_artifacts={gate:paths['gate:'+gate] for gate in compiler.NATIVE_GROUP_GATES})
    require(compiled==document('compiledPolicy'), 'compiled policy does not match current catalog/proof')
    require(candidate['policy']['hash']==compiled['policyHash'] and candidate['policy']['version']==compiled['version']
            and candidate['policy']['ordinaryGpuQualified'] is compiled['gpuQualification']['qualified'] is False,
            'candidate policy mismatch or ordinary GPU qualification asserted')
    expected_lock={'policyHash':compiled['policyHash'],'policyVersion':compiled['version'],
                   'status':'unqualified','compatibility':compiled['compatibility']}
    require(document('releaseLock')==expected_lock, 'compiled full-platform release lock mismatch')
    summary,receipt=document('summary'),document('runtimeReceipt')
    require(summary['policy']==candidate['policy'] and summary['nodePool']==candidate['scope']['nodePool']
            and summary['profile']['id']=='interactive-shared-5' and summary['profile']['nativeCapMiB']==5120,
            'summary policy/profile/pool mismatch')
    require(all(summary['nodePool'][public]==proof['node_pool'][private] for public,private in
            [('node','node'),('nodeUid','node_uid'),('gpuUuid','gpu_uuid'),('maxWorkspaces','max_workspaces')])
            and summary['nodePool']['migEnabled'] is False, 'summary pool differs from bounded native proof')
    require(all(summary['driver'][public]=='sha256:'+proof[private] for public,private in
            [('coreSha256','core_sha256'),('uvmSha256','uvm_sha256'),('healthSha256','health_sha256')]),
            'summary driver differs from measured native proof')
    require([s['source']+':'+s['workspace'] for s in summary['approvedScopes']]==SCOPES
            and receipt['scopes']==SCOPES and receipt['policyHash']==compiled['policyHash']
            and receipt['policyVersion']==compiled['version'], 'runtime receipt scope/policy mismatch')
    require(summary['runtimeActivation']['receiptSha256']==sha(raw['runtimeReceipt'])
            and summary['runtimeActivation']['reviewedAt']==receipt['reviewedAt']==candidate['observedAt']
            and summary['runtimeActivation']['status']==receipt['status']=='qualified-pilot-available',
            'runtime receipt hash/status/time mismatch')
    require(summary['evidence']['privateProofRawSha256']==sha(raw['nativeProof'])
            and summary['evidence']['privateProofCanonicalSha256']==sha(compiler.canonical(proof)),
            'native proof summary hash mismatch')
    for gate in compiler.NATIVE_GROUP_GATES:
        require(summary['gates'][gate]['passed'] is True and summary['gates'][gate]['privateReportRawSha256']
                ==proof['gates'][gate]['evidence_sha256']==sha(raw['gate:'+gate]), 'gate summary mismatch')
    require(receipt['gpuControls']['kernelPositiveAndRecoveryPassedBoth'] is True
            and receipt['gpuControls']['beforeAfterIdentityAndCapsStable'] is True
            and receipt['gpuControls']['capMiBPerWorkspace']==5120
            and receipt['shutdown']['bothStopped'] is True
            and receipt['shutdown']['bothNativeReservationsReleased'] is True
            and receipt['profileHandover']['bothNormalSourceFlowsPassed'] is True,
            'recorded pilot acceptance is incomplete')

    require(set(candidate['sdkPackages'])=={'currentSdk','capGateSdk','notebookSdk'}, 'three distinct measured SDK packages required')
    counts={}
    for name,package in candidate['sdkPackages'].items():
        require(re.fullmatch('[0-9a-f]{40}',package['sourceCommit']) and package['version']=='0.1.0', 'SDK source/version mismatch')
        source=document(package['sourceReceipt']); wheel=raw[package['wheelArtifact']]
        require(field(source,package['revisionField'])==package['sourceCommit'], 'SDK source commit mismatch')
        require('sha256:'+field(source,package['wheelHashField'])==sha(wheel), 'SDK wheel hash mismatch')
        expected=modules(package['modules'])
        require(modules(field(document(package['moduleEvidence']),package['moduleField']))==expected,
                'SDK source module evidence mismatch')
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            names=archive.namelist(); require(len(names)==len(set(names)), 'duplicate wheel file')
            actual={p:hashlib.sha256(archive.read(p)).hexdigest() for p in names if p.startswith('cps_compute/') and p.endswith('.py')}
            require(actual==expected, 'SDK wheel module mismatch')
            metadata=[p for p in names if p.endswith('.dist-info/METADATA')]
            require(len(metadata)==1, 'single SDK wheel metadata required')
            text=archive.read(metadata[0]).decode()
            require('Name: cps-compute\n' in text and 'Version: '+package['version']+'\n' in text, 'SDK wheel version mismatch')
        counts[name]=len(expected)

    components=candidate['components']
    require(set(components)=={'gateway','hub','admin','capGate','notebook'}, 'exact tested component set required')
    for role,component in components.items():
        expected_package={'gateway':'currentSdk','hub':'currentSdk','admin':'currentSdk','capGate':'capGateSdk','notebook':'notebookSdk'}[role]
        require(component['sdkPackage']==expected_package, 'component SDK role mismatch')
        identity=image_identity(component['image'])
        recorded=field(document(component['imageReceipt']),component['imageField'])
        require(identity[1]==recorded if isinstance(recorded,str) and recorded.startswith('sha256:')
                else identity==image_identity(recorded), 'component image provenance mismatch')
        registry=raw[component['registryArtifact']]
        require(component['registryKind'] in ('manifest','digest'), 'known registry evidence kind required')
        require((sha(registry) if component['registryKind']=='manifest' else registry.decode().strip())==identity[1],
                'component registry image digest mismatch')
        package=candidate['sdkPackages'][expected_package]; report=document(component['verificationArtifact'])
        if role!='notebook':
            require(report['source_revision']==package['sourceCommit'], 'installed SDK source revision mismatch')
        require(modules(field(report,component['moduleField']))==modules(package['modules']), 'installed SDK module mismatch')
        require('sha256:'+report['wheel_sha256']==sha(raw[package['wheelArtifact']]), 'installed SDK wheel mismatch')
    require(components['gateway']['image']==summary['images']['restartGateway']
            and components['notebook']['image']==proof['workload_image']==summary['images']['notebook']
            and components['capGate']['image']==proof['gate_image']==summary['images']['capGate'], 'tested policy image mismatch')
    versions=document('hubVerify')['runtime_versions']
    require(versions['jupyterhub']==candidate['compatibility']['jupyterhub']
            and versions['jupyterhub-kubespawner']==candidate['compatibility']['kubespawner']
            and candidate['compatibility']['z2jhChart']==compiled['compatibility']['productionTarget']['chart'],
            'Hub/chart compatibility mismatch')
    admin=components['admin']; source=document('adminSource'); build=document('adminReceipt')
    require(document('adminVerify')['runtime_versions']['e2x-course-hub']==admin['backendVersion'],
            'admin package version mismatch')
    require(source['backend_revision']==build['backend_revision']==admin['backendCommit']
            and source['ui_revision']==build['ui_source_revision']==admin['uiCommit'], 'admin source commit mismatch')
    require(modules(source['python_backend_files'])==modules(admin['backendModules'])
            and source['static_files']==build['static_manifest']==admin['staticFiles'], 'admin module/static source mismatch')
    require(set(admin['staticArtifacts'])==set(admin['staticFiles'])=={
            'course-service-ui/main.js','course-service-ui/assets/main.css','course-service-ui/assets/favicon.ico'},
            'exact three final admin static assets required')
    require(len(set(admin['staticArtifacts'].values()))==3 and all(
            hashlib.sha256(raw[artifact]).hexdigest()==admin['staticFiles'][name]
            for name,artifact in admin['staticArtifacts'].items()), 'admin final static bytes mismatch')
    with tarfile.open(fileobj=io.BytesIO(raw['adminArchive'])) as archive:
        expected=modules(admin['backendModules']); actual={}
        for entry in archive.getmembers():
            path=entry.name.removeprefix('./').removeprefix('src/')
            if path in expected:
                require(entry.isfile() and path not in actual, 'regular unique admin source module required')
                actual[path]=hashlib.sha256(archive.extractfile(entry).read()).hexdigest()
        require(actual==expected, 'admin archive module mismatch')
    installed_admin=document('adminVerify')
    for key,count in [('admin_source_files_verified',len(admin['backendModules'])),
                      ('admin_static_files_verified',len(admin['staticFiles']))]:
        require(type(installed_admin[key]) is int and installed_admin[key]==count,
                'admin recorded installed verification count mismatch')
    require(document('notebookConfig')['Labels']['org.opencontainers.image.revision']==components['notebook']['parentNotebookCommit'],
            'notebook parent source mismatch')
    require(candidate['sdkPackages']['notebookSdk']['sourceCommit']!=candidate['sdkPackages']['currentSdk']['sourceCommit'],
            'historical notebook cannot assert matched current SDK matrix')
    return {'status':'compatibility-integrity-verified','productionQualified':False,
        'qualifiedScopes':SCOPES,'policyHash':compiled['policyHash'],'observedAt':receipt['reviewedAt'],
        'verifiedArtifacts':len(raw),'verifiedSdkModules':counts,'verifiedAdminModules':len(admin['backendModules']),
        'verifiedAdminStaticAssets':len(admin['staticFiles']),
        'recordedAdminInstalledFiles':{'backend':installed_admin['admin_source_files_verified'],
                                     'static':installed_admin['admin_static_files_verified']},
        'verifiedImages':{k:v['image'] for k,v in components.items()},'liveActions':False,
        'qualificationAuthority':'existing independently Root-reviewed hardware and activation receipts',
        'operationalHeartbeat':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,default=ROOT/'platform-staging/releases/qualification-20261009.json')
    parser.add_argument('--artifact-root',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=verify_candidate(compiler._decode_json(read_bytes(args.inventory)),ROOT,args.artifact_root)
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,tarfile.TarError) as error:
        print(json.dumps({'status':'unverified','productionQualified':False,'error':str(error),'liveActions':False},sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
