# Isolated restored-artifact ownership check

`scripts/compute-platform/verify-restored-artifacts.py` checks actual artifact
downloads from an already restored CPS/CIT pair. It performs authenticated GETs
only. It creates no credentials, restore fixtures, workflows, or storage objects.
Without `--execute` it is inert and does not import the recovery dependency.

The verifier composes the existing `e2x_course_hub.cps.recovery` bundle and private
file contract. Use a reviewed environment providing that module. The initial
compatible implementation is recovery commit
`64255bb4621e3ffe26d3db89c56af4df612d6b2b` (module raw SHA256
`710f2b3ab624e90a4d403be8e8d7c3bfba74aaac045d0a5961b5b0b6c153b2eb`).
The tool installs nothing. The paired bundle's file sizes and checksums are
validated before fixture tokens are read.

## Before connecting

Root must record routing isolation separately: exact restore namespace and
Service/Pod identities behind each port forward, restored Gateway configuration,
and artifact endpoint/bucket routing to the isolated object-store clone. A
loopback address or bucket name alone cannot establish isolation. This command
does not inspect Kubernetes, object-store credentials, or storage contents.

Use only pre-existing normal-user tokens scoped to the restored services. The
input and each token file must satisfy recovery's owned regular-file, mode 0600,
no-symlink and stable-read checks. Keep them outside Git in an owned private
directory. No token value appears in arguments or receipts. Keep the output
parent private; the output file must be new. The existing recovery writer creates
it mode 0600 without overwriting an existing file.

Prepare expected artifact bytes/hash and complete metadata from independently
retained fixture evidence, rather than copying expectations from the service
being checked. Record the original Workflow UID and the intended restored UID
mapping explicitly in the restore evidence. This verifier requires the supplied
exact UID, namespace, owner and S3 descriptor to match. It never rewrites a
Workflow, artifact key, or immutable provenance binding. If the restore cannot
preserve or explicitly map those bindings, stop with an open restore gate.

## Inputs

The input is a closed JSON object with `version: 1`, an explicit `bucket`, and
exactly two `sources`, `cps` and `cit`. Each source has these fields:

| Field | Required value |
| --- | --- |
| `namespace` | `restore-cps-<capture UUID first 8>` or matching `restore-cit-<same first 8>` from the composed bundle |
| `hub_origin`, `gateway_origin` | Distinct canonical `http[s]://127.0.0.1:<port>` or `http[s]://[::1]:<port>` origins, without paths or credentials; all four ports/origins must differ |
| `owner_label` | Exact Workflow owner label key from the restored Gateway configuration |
| `actors` | Exactly `own` and `foreign`, each containing `person`, `hub_user`, `token_file` |
| `artifacts` | Exactly `own` and `foreign`, each containing the fixture below |

`person` is the Gateway's canonical identity; `hub_user` is the Hub account name.
The two identities, Hub users and private token-file paths must differ within
each source. The tool requires both Hub identities to be non-admin and both
Gateway identities to be ordinary people under the captured source policy.

Each artifact fixture supplies the following closed object. These values are an
illustration; they are not live restore inputs:

```json
{
  "workflow": "cps-restored-own",
  "workflow_uid": "22222222-2222-4222-8222-222222222222",
  "artifact": "executed-notebook",
  "metadata_pointer": "/status/outputs/artifacts/0",
  "metadata": {
    "name": "executed-notebook",
    "s3": {
      "bucket": "restored-artifact-fixtures",
      "key": "run-artifacts/22222222-2222-4222-8222-222222222222/executed.ipynb",
      "endpoint": "isolated-object-store.example.invalid"
    }
  },
  "bytes": 123,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

The artifact kind is `snapshot` or `executed-notebook`. The pointer selects the
complete independently expected Argo descriptor; every field must match, not
only its bucket/key. Artifact keys are canonical relative keys; downloads are
bounded to 32 MiB. No presigned artifact URL is followed. Each source needs two
distinct Workflow names and UIDs, one owned by each actor.

After reviewing the private inputs and isolation evidence, run in the qualified
recovery environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python \
  scripts/compute-platform/verify-restored-artifacts.py \
  --execute \
  --bundle /PRIVATE/composed-recovery-bundle \
  --input /PRIVATE/restored-artifact-inputs.json \
  --output /PRIVATE/new-restored-artifact-receipt.json
```

The four fixed endpoints are the owning Hub's `/hub/api/user`, Gateway `/v1/me`,
Workflow detail and Workflow artifact download. The transport disables ambient
proxies and redirects. It sends Hub tokens only in authorization headers, with
the explicit source header on Gateway requests. All failures print a generic
message; response bodies, credentials and private input paths are suppressed.

For each fixture the owner must receive the exact Workflow namespace, name, UID,
owner label, full artifact metadata, bytes and SHA256. The other actor must get
403 on both detail and download. A foreign 200, including an empty body, fails.
Owner downloads must also retain private no-store/sandbox/nosniff headers.

## Evidence boundary

A successful receipt covers four fixture downloads and four paired ownership
denials. It contains hashes and byte counts, with no tokens or private paths.
`productionQualified`, `browser_oauth_qualified`, and
`off_host_recovery_qualified` remain false. Routing isolation is explicitly a
separate evidence requirement. Existing backup coordination, matching database
versions/fingerprints, restored NFS data, human browser OAuth and off-host restore
checks remain independent acceptance gates.

CPU tests use in-memory responses and mocked HTTP openers, without network,
credential files, storage reads or fixture writes:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover \
  -s tests/compute_platform -p test_restored_artifacts.py -v
```
