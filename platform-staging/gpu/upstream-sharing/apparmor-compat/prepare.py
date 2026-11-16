#!/usr/bin/env python3
"""Render the verified GPU2 daemon's installed template; add exact upstream rules."""
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
source = (ROOT / 'containerd-v2.2.5-k3s2-template.go').read_text()
profile = source.split('const defaultTemplate = `', 1)[1].split('`', 1)[0]
profile = profile.replace('{{if .Abi}}abi <{{.Abi}}>,\n{{end}}', 'abi <abi/3.0>,\n')
profile = profile.replace('{{range $value := .Imports}}\n{{$value}}\n{{end}}', '\n#include <tunables/global>\n')
profile = profile.replace('{{range $value := .InnerImports}}\n  {{$value}}\n{{end}}', '\n  #include <abstractions/base>\n')
profile = re.sub(r'{{if .RootlessKit}}.*?{{end}}', '', profile, flags=re.S)
profile = profile.replace('{{.Name}}', 'cri-containerd.apparmor.d').replace('{{.DaemonProfile}}', 'unconfined')
assert '{{' not in profile
fixed = profile
for rule in ('signal (send,receive)', 'ptrace (trace,tracedby,read,readby)'):
    original = f'  {rule} peer=cri-containerd.apparmor.d,'
    assert fixed.count(original) == 1
    fixed = fixed.replace(original, original + f'\n  {rule} peer=cri-containerd.apparmor.d//&unconfined,')
for name, data in [('baseline.profile', profile), ('cri-containerd.apparmor.d', fixed)]:
    (ROOT / name).write_text(data)
print(json.dumps({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ['containerd-v2.2.5-k3s2-template.go', 'baseline.profile', 'cri-containerd.apparmor.d']}, indent=2))
