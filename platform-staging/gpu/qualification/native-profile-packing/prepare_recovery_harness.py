#!/usr/bin/env python3
"""Default-inert sibling preparation for one authenticated historical exception."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import prepare_harness as p
import recovery_history as r
import recovery_source_loader as loader
BASE_RENDER = p.render_sources

def bundle(model, control, agent, agent_sha, recovery, recovery_sha):
    paths = {'model': (model, r.MODEL_SHA), 'control': (control, r.CONTROL_SHA),
        'agent': (agent, agent_sha), 'recovery': (recovery, recovery_sha),
        'reader': (Path(r.__file__), p.sha(Path(r.__file__).read_bytes())),
        'baseline': (Path(r.__file__).with_name('recovery-baseline-journal-pins.json'), r.BASELINE_PIN)}
    sources = {key: {'raw': p.read_pinned(path, pin), 'sha256': pin} for key, (path, pin) in paths.items()}
    loader.load_sources(sources)
    return sources

def bootstrap(sources):
    raw = Path(loader.__file__).read_bytes()
    # Import-free source loader, with the exact sibling reader already loaded.
    code = raw.decode().replace('import recovery_history as r', '')
    return 'RECOVERY_SOURCES = ' + repr(sources) + '\n' + r'''
import types,sys
_recovery_reader = types.ModuleType('recovery_history')
_recovery_reader.__file__ = '/reviewed/recovery_history.py'
sys.modules[_recovery_reader.__name__] = _recovery_reader
exec(compile(RECOVERY_SOURCES['reader']['raw'], 'pinned-history-reader', 'exec'), _recovery_reader.__dict__)
_source_loader = types.ModuleType('pinned_history_source_loader')
_source_loader.r = _recovery_reader
''' + 'exec(compile(' + repr(code) + ", 'pinned-history-source-loader', 'exec'), _source_loader.__dict__)\n" + r'''
def _history_models():
    return _source_loader.load_sources(RECOVERY_SOURCES)
def _validate_history(value, targets, *, allow_current=False):
    loaded = _history_models()
    binding = {'pool': {k:value[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')}, 'targets':targets}
    _source_loader.validate(loaded, value, binding, allow_current=allow_current)
    return loaded
'''

def rewrite_host(host, validators):
    start = host.index("approved=c.get('retired_caps',[])")
    end = host.index("raw=read('/proc/driver/nvidia/gpus/", start)
    host = host[:start] + "history=c['terminal_history']\nrequire(all(history[k]==c[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')),'Current history epoch changed')\nloaded=_validate_history(history,c['targets'],allow_current=not c['targets'])\nmodels=loaded.models\n" + host[end:]
    start = host.index('retired=[];retired_uids=set()')
    end = host.index('epoch()\nprint(json.dumps', start)
    host = host[:start] + r'''
retired=loaded.reader.observe_history(history,inventory,
 binding={'pool':{k:history[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')},'targets':c['targets']},
 agent=loaded.agent,recovery_codec=loaded.codec,models=models,
 cleanup_validator=loaded.cleanup_validator,audit_body=loaded.audit_body,baseline=loaded.baseline,
 read=read,absent=absent,retired_mount=retired_mount,active_inodes=bound,allow_current=not c['targets'])
''' + host[end:]
    return bootstrap(validators) + '\n' + host

def historical_host_source(original_preflight, validators):
    """Local source only: no target UIDs needed for historical expiry observation."""
    key='activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py'
    p.require(p.sha(original_preflight)==p.SOURCE_PINS[key],'Exact original approved observer source required')
    tree=ast.parse(original_preflight)
    host=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='HOST_SOURCE'for t in n.targets))
    value=rewrite_host(ast.literal_eval(host.value),validators)
    compile(value,'historical-read-only-host-observer','exec')
    return value.encode()

def render_sources(sources, binding, history, validators, *, native_binary=None):
    loaded = loader.load_sources(validators)
    checked = loader.validate(loaded, history, binding)
    physical = checked['finite'] + [checked['recovered']]
    # The old finite probe implementations and target validators remain exact.
    out = BASE_RENDER(sources, binding, {**history, 'records': physical}, native_binary=native_binary)
    old_pre = out['run_group_acceptance.py']; pre = old_pre.decode()
    tree = ast.parse(pre)
    host_node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HOST_SOURCE' for t in n.targets))
    host = rewrite_host(ast.literal_eval(host_node.value),validators)
    lines = pre.splitlines(keepends=True)
    lines[host_node.lineno - 1:host_node.end_lineno] = ['HOST_SOURCE = ' + repr(host) + '\n']
    pre = ''.join(lines)
    whitelist = p.definition(pre, 'retired_whitelist')
    pre = p.replace(pre, whitelist, r'''
def retired_whitelist(generation):
    global TERMINAL_HISTORY
    parent=RETIRED_WHITELIST_PATH.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid==os.getuid() and stat.S_IMODE(parent.st_mode)==0o700,'Private explicit history parent required')
    fd=os.open(RETIRED_WHITELIST_PATH,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);raw=os.read(fd,1048577);after=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o600 and len(raw)<=1048576 and all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')) and hashlib.sha256(raw).hexdigest()==RETIRED_WHITELIST_SHA,'Stable pinned complete terminal history required')
    finally:os.close(fd)
    value=_recovery_reader.parse(raw)
    require(all(value[k]==v for k,v in {'node':NODE,'node_uid':NODE_UID,'boot_id':BOOT,'gpu_uuid':GPU,'driver_generation':generation}.items()),'Current history epoch required')
    loaded=_validate_history(value,BOUND_CONFIG['targets'])
    checked=_source_loader.validate(loaded,value,{'pool':{k:value[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')},'targets':BOUND_CONFIG['targets']})
    TERMINAL_HISTORY=value
    return checked['finite']+[checked['recovered']]
'''.strip())
    old_validate = "require(len(observed.get('retired_caps', [])) == len(retired)"
    start = pre.index(old_validate); start = pre.rfind('\n',0,start)+1
    end = pre.index('    # Fence API identity', start)
    pre = pre[:start] + "    _recovery_reader.validate_observed(TERMINAL_HISTORY,observed.get('retired_caps'))\n" + pre[end:]
    pre = p.replace(pre, "'controller_sha256': CONTROLLER_SHA, 'retired_caps': retired}",
        "'controller_sha256': CONTROLLER_SHA, 'retired_caps': retired, 'terminal_history': TERMINAL_HISTORY}")
    pre = pre.replace("CONTROLLER_SHA = 'f40ef40f71c9f1206f23fb7052fd69aafd103c0f03a24e6bf3987395dacfd179'", 'CONTROLLER_SHA = ' + repr(r.MODEL_SHA))
    new_whitelist = (p.canonical(history) + '\n').encode()
    pre = pre.replace(p.sha(out['retired-caps.json']), p.sha(new_whitelist))
    pre = bootstrap(validators) + '\n' + pre
    compile(pre, 'recovery-aware-preflight', 'exec')
    out['run_group_acceptance.py'] = pre.encode(); out['retired-caps.json'] = new_whitelist
    for name, raw in list(out.items()):
        if name != 'run_group_acceptance.py' and name.endswith('.py'):
            out[name] = raw.replace(p.sha(old_pre).encode(), p.sha(pre.encode()).encode())
    out['recovery_history.py'] = Path(r.__file__).read_bytes()
    out['recovery_source_loader.py'] = Path(loader.__file__).read_bytes()
    out['recovery-baseline-journal-pins.json'] = Path(r.__file__).with_name('recovery-baseline-journal-pins.json').read_bytes()
    out['run_retirement_witness.py'] = Path(__file__).with_name('run_recovery_retirement_witness.py').read_bytes()
    return out

def prepare(binding_path, binding_sha, source_root, output, validators, **native):
    original_validate, original_render = p.validate_retired, p.render_sources
    loaded = loader.load_sources(validators)
    classification=None
    def validate(value, binding, *, allow_current=False):
        nonlocal classification
        classification=loader.validate(loaded, value, binding, allow_current=allow_current)
        return value
    p.validate_retired = validate
    p.render_sources = lambda sources, binding, history, **kw: render_sources(sources, binding, history, validators, **kw)
    try:
        result = p.prepare(binding_path, binding_sha, source_root, output, **native)
    finally:
        p.validate_retired, p.render_sources = original_validate, original_render
    result.update(history_protocol='native-packing-terminal-history/v2', historical_recovery_count=1,
        historical_failed_normal_stop_preserved=True, recovery_qualifies_normal_stop=False,
        validator_source_pins={k:v['sha256'] for k,v in validators.items()})
    result.update(retired_count=len(classification['finite']),
        historical_finite_retirement_count=len(classification['finite']),
        historical_cleaned_count=len(classification['cleaned']),
        historical_physical_count=len(classification['finite'])+1,
        historical_journal_count=len(classification['finite'])+len(classification['cleaned'])+1)
    (output / 'preparation-receipt.json').write_bytes((p.canonical(result) + '\n').encode())
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    for key in ('binding','source-root','output','model-source','control-source','node-source','recovery-source','native-import-binary','native-import-build-receipt'):
        parser.add_argument('--'+key,type=Path)
    for key in ('binding','node-source','recovery-source','native-import-binary','native-import-build-receipt'):
        parser.add_argument('--'+key+'-sha256')
    args=parser.parse_args(argv)
    if not args.prepare:
        print(p.canonical({'state':'inert','api_calls':False,'gpu_calls':False,'hardware_qualification':False}));return 0
    p.require(all(vars(args).values()),'All exact reviewed inputs and validator pins required')
    validators=bundle(args.model_source,args.control_source,args.node_source,args.node_source_sha256,args.recovery_source,args.recovery_source_sha256)
    result=prepare(args.binding,args.binding_sha256,args.source_root,args.output,validators,
        native_binary_path=args.native_import_binary,native_binary_sha=args.native_import_binary_sha256,
        native_build_path=args.native_import_build_receipt,native_build_sha=args.native_import_build_receipt_sha256)
    print(p.canonical({'state':result['state'],'api_calls':False,'gpu_calls':False,'hardware_qualification':False}));return 0

if __name__=='__main__':main()
