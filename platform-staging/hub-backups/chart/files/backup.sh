#!/bin/sh
set -eu
umask 077
# The optional init container has a projected API token but no database secret
# or backup PVC. Its credentials are never mounted in the database container.
if [ "${FRESH_CONFIGURATION_CAPTURE:-false}" = true ]; then
    python3 - <<'PY'
import ctypes, datetime, ipaddress, json, os, pathlib, re, shutil, ssl, tempfile, urllib.request
root=pathlib.Path(os.environ['FRESH_CAPTURE_DIRECTORY']); work=None; published=None
def required(value):
    if not isinstance(value,str) or not value: raise ValueError('Missing provenance')
    return value
def private_write(name,value):
    path=work/name
    with path.open('xb') as stream:
        os.chmod(path,0o600); stream.write(value); stream.flush(); os.fsync(stream.fileno())
def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
try:
    host=str(ipaddress.IPv4Address(os.environ['FRESH_API_HOST']))
    port=int(os.environ['FRESH_API_PORT'])
    if not 1 <= port <= 65535: raise ValueError('Invalid API port')
    namespace=os.environ['FRESH_API_NAMESPACE']
    names=json.loads(os.environ['FRESH_API_RESOURCES'])
    kinds={'deployments':('apps/v1','Deployment'),'statefulsets':('apps/v1','StatefulSet'), 'configmaps':('v1','ConfigMap'),'secrets':('v1','Secret'),'pods':('v1','Pod')}
    if set(names)!=set(kinds) or not (names['deployments'] or names['statefulsets']): raise ValueError('Incomplete capture scope')
    for resource,values in names.items():
        if not isinstance(values,list) or len(values)!=len(set(values)) or (resource in ('configmaps','secrets','pods') and not values): raise ValueError('Incomplete capture scope')
        if any(not isinstance(v,str) or not re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?',v) for v in values): raise ValueError('Invalid object name')
    if not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?',namespace): raise ValueError('Invalid namespace')
    capture_image=required(os.environ['FRESH_CAPTURE_IMAGE'])
    if not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',capture_image): raise ValueError('Mutable capture image')
    token=pathlib.Path(os.environ['FRESH_API_TOKEN_FILE']).read_text().strip()
    required(token)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=os.environ['FRESH_API_CA_FILE'])))
    work=pathlib.Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    lists={key:[] for key in ('workloads.json','configmaps.json','secrets.json')}; records=[]; images=[]; rows=[]
    for resource,values in names.items():
        api,kind=kinds[resource]; prefix='/apis/apps/v1' if api=='apps/v1' else '/api/v1'
        for name in values:
            request=urllib.request.Request('https://'+host+':'+str(port)+prefix+'/namespaces/'+namespace+'/'+resource+'/'+name,headers={'Authorization':'Bearer '+token})
            with opener.open(request,timeout=15) as response:
                raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024: raise ValueError('Oversized API object')
            obj=json.loads(raw); meta=obj['metadata']
            if obj.get('apiVersion')!=api or obj.get('kind')!=kind or meta.get('name')!=name or meta.get('namespace')!=namespace: raise ValueError('Object identity mismatch')
            record={'resource':resource,'name':name,'uid':required(meta.get('uid')),'resource_version':required(meta.get('resourceVersion'))}
            records.append(record)
            if resource=='pods':
                declared=obj['spec']['containers']; statuses=obj['status']['containerStatuses']
                if not declared or len({c['name'] for c in declared})!=len(declared) or {c['name'] for c in declared}!={c['name'] for c in statuses} or len(statuses)!=len(declared): raise ValueError('Incomplete running images')
                containers=[]
                for item in sorted(statuses,key=lambda c:c['name']):
                    image=required(item.get('imageID'))
                    if not re.fullmatch(r'(?:[a-z-]+://)?[^\s@]+@sha256:[a-f0-9]{64}',image): raise ValueError('Missing immutable running image')
                    containers.append({'name':item['name'],'image_id':image})
                images.append({'name':name,'uid':record['uid'],'resource_version':record['resource_version'],'containers':containers})
                rows.append(name+'\t'+' '.join(c['name']+'='+c['image_id'] for c in containers)+'\n')
            else:
                filename='workloads.json' if resource in ('deployments','statefulsets') else resource+'.json'
                lists[filename].append(obj)
    for name,items in lists.items(): private_write(name,(json.dumps({'apiVersion':'v1','kind':'List','items':items},sort_keys=True,separators=(',',':'))+'\n').encode())
    private_write('running-images.txt',''.join(rows).encode())
    snapshot={'schema_version':1,'source':'kubernetes-api','observed_live':True,'namespace':namespace,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'capture_image':capture_image,'resources':names,'objects':records,'pod_images':images}
    private_write('snapshot.json',(json.dumps(snapshot,sort_keys=True,separators=(',',':'))+'\n').encode())
    sync(work)
    target=root/'complete'
    identity=work.stat()
    # No pre-check/rename race can replace an existing completed capture.
    libc=ctypes.CDLL(None,use_errno=True); rename=getattr(libc,'renameat2',None)
    if rename is None: raise OSError('Atomic no-replace publication unavailable')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]; rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(work),-100,os.fsencode(target),1): raise OSError(ctypes.get_errno(),'Atomic publication failed')
    published=(target,identity); work=None; sync(root)
except (OSError,ValueError,KeyError,TypeError):
    if work is not None: shutil.rmtree(work)
    if published is not None:
        target,identity=published
        info=target.lstat()
        if (info.st_dev,info.st_ino)==(identity.st_dev,identity.st_ino): shutil.rmtree(target)
    raise SystemExit('Fresh Hub API capture failed; no complete capture published')
PY
    exit $?
fi
backup_root=${BACKUP_DIRECTORY:-/backup}
work=$(mktemp -d "$backup_root/.partial-XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
fail() { echo 'Hub backup failed; no complete bundle published' >&2; exit 1; }
# Metadata is restricted before JSON interpolation; missing versions stay null.
metadata() { case "$1" in *[!a-zA-Z0-9./:_@+-]*) fail ;; esac; }
json_value() { if [ -n "$1" ]; then printf '"%s"' "$1"; else printf null; fi; }
for value in "$BACKUP_OWNER" "$BACKUP_IMAGE" "${BACKUP_HUB_IMAGE:-}" "${BACKUP_HUB_CHART_VERSION:-}" "${BACKUP_HUB_APP_VERSION:-}"; do
    metadata "$value"
done
files='hub.pgdump'
mode=logical
snapshot=null
scope='Logical Hub database only; roles, ACLs, configuration, NFS and off-host durability require independent backups'
case "${ROLE_CAPTURE_ENABLED:-false}" in
true)
    [ -n "${ROLE_CAPTURE_PGUSER:-}" ] && [ -n "${ROLE_CAPTURE_PGPASSWORD:-}" ] || fail
    case "${FRESH_API_CAPTURE_ENABLED:-false}" in
    false)
    [ -n "${BACKUP_CONFIGURATION_SECRET_REF:-}" ] && [ -n "${BACKUP_CONFIGURATION_UID:-}" ] &&
        [ -n "${BACKUP_CONFIGURATION_RESOURCE_VERSION:-}" ] && [ -n "${BACKUP_CONFIGURATION_CAPTURED_AT:-}" ] || fail
    for value in "$BACKUP_CONFIGURATION_SECRET_REF" "$BACKUP_CONFIGURATION_UID" "$BACKUP_CONFIGURATION_RESOURCE_VERSION" "$BACKUP_CONFIGURATION_CAPTURED_AT"; do
        metadata "$value"
    done
    snapshot=$(printf '{"source":"operator-supplied-secret-snapshot","observed_live":false,"secret_ref":"%s","uid":"%s","resource_version":"%s","captured_at":"%s"}' "$BACKUP_CONFIGURATION_SECRET_REF" "$BACKUP_CONFIGURATION_UID" "$BACKUP_CONFIGURATION_RESOURCE_VERSION" "$BACKUP_CONFIGURATION_CAPTURED_AT")
    ;;
    true)
        configuration=${PROTECTED_CONFIGURATION_DIRECTORY:-/fresh-configuration/complete}
        [ -f "$configuration/snapshot.json" ] && [ -s "$configuration/snapshot.json" ] || fail
        snapshot=$(cat "$configuration/snapshot.json") || fail
        ;;
    *) fail ;;
    esac
    export PGUSER="$ROLE_CAPTURE_PGUSER" PGPASSWORD="$ROLE_CAPTURE_PGPASSWORD"
    # Confirm existing privilege, without creating or promoting a database role.
    if ! privileged=$(psql -X -Atc 'SELECT rolsuper FROM pg_roles WHERE rolname = current_user' 2>"$work/private-error"); then fail; fi
    [ "$privileged" = t ] || fail
    # Role hashes and all tool diagnostics remain private and never reach logs.
    pg_dumpall --roles-only --file="$work/roles.sql" > /dev/null 2>"$work/private-error" || fail
    [ -s "$work/roles.sql" ] || fail
    pg_dump --format=custom --create --file="$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
    configuration=${PROTECTED_CONFIGURATION_DIRECTORY:-/protected-configuration}
    for name in workloads.json configmaps.json secrets.json running-images.txt; do
        [ -f "$configuration/$name" ] && [ -s "$configuration/$name" ] || fail
        cp -L "$configuration/$name" "$work/$name" > /dev/null 2>"$work/private-error" || fail
    done
    files='hub.pgdump roles.sql workloads.json configmaps.json secrets.json running-images.txt'
    mode=roles-acls-configuration
    scope='Roles and Hub database owners/ACLs plus scoped configuration capture; coordinated capture, connected Hub/NFS restore and off-host durability remain unqualified'
    ;;
false)
    pg_dump --format=custom --no-owner --no-acl --file="$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
    ;;
*) fail ;;
esac
[ -s "$work/hub.pgdump" ] || fail
pg_restore --list "$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
stamp=$(date -u +%Y%m%dT%H%M%SZ)
version=$(pg_dump --version 2>"$work/private-error") || fail
case "$version" in 'pg_dump (PostgreSQL) '*) ;; *) fail ;; esac
version=${version#'pg_dump (PostgreSQL) '}
# Distro builds append packaging details after the numeric version token.
version=${version%% *}
case "$version" in ''|*[!0-9.]*) fail ;; esac
checksums=''
separator=''
for name in $files; do
    chmod 600 "$work/$name"
    checksum=$(sha256sum "$work/$name" 2>"$work/private-error") || fail
    checksum=${checksum%% *}
    [ "${#checksum}" = 64 ] || fail
    case "$checksum" in *[!a-f0-9]*) fail ;; esac
    checksums="$checksums$separator\"$name\":\"$checksum\""
    separator=,
    sync "$work/$name"
done
printf '{"owner":"%s","created_at":"%s","client_version":"%s","image":"%s","capture_mode":"%s","recovery_qualified":false,"hub":{"image":%s,"chart_version":%s,"app_version":%s},"configuration_snapshot":%s,"sha256":{%s},"scope":"%s"}\n' \
    "$BACKUP_OWNER" "$stamp" "$version" "$BACKUP_IMAGE" "$mode" \
    "$(json_value "${BACKUP_HUB_IMAGE:-}")" "$(json_value "${BACKUP_HUB_CHART_VERSION:-}")" "$(json_value "${BACKUP_HUB_APP_VERSION:-}")" \
    "$snapshot" "$checksums" "$scope" >"$work/manifest.json"
chmod 600 "$work/manifest.json"
rm -f "$work/private-error"
sync "$work/manifest.json"
# Random mktemp suffix prevents timestamp collisions; only complete bundles visible.
target="$backup_root/$stamp-$(basename "$work" | sed 's/^\.partial-//')"
mv "$work" "$target"
sync "$backup_root"
echo 'Hub PostgreSQL backup archive published and checksummed'
