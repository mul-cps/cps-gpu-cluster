#!/usr/bin/env python3
"""GPU2-only installation; exact loaded-baseline guard, no service restart."""
import json
import pathlib
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
payload = {name: (ROOT / name).read_text() for name in ['baseline.profile', 'cri-containerd.apparmor.d']}
remote = r'''
import hashlib,json,pathlib,platform,subprocess,sys
p=json.load(sys.stdin)
assert platform.node()=='k3s-wk-gpu2'
assert 'v1.34.9+k3s1' in subprocess.check_output(['/usr/local/bin/k3s','--version'],text=True)
assert 'v2.2.5-k3s2' in subprocess.check_output(['/usr/local/bin/k3s','crictl','version'],text=True)
assert pathlib.Path('/proc/sys/kernel/apparmor_restrict_unprivileged_unconfined').read_text().strip()=='1'
profiles=list(pathlib.Path('/sys/kernel/security/apparmor/policy/profiles').glob('cri-containerd.apparmor.d.*'))
assert len(profiles)==1
raw=(profiles[0]/'raw_data').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='8fd644921ce685e50f6dc8f57db6adb3fa0433d3fae7fa39cfdd673bd951dd82'
compiled=subprocess.check_output(['apparmor_parser','-S','-K','-c0'],input=p['baseline.profile'].encode())
assert compiled==raw
subprocess.run(['apparmor_parser','-Q','-K'],input=p['cri-containerd.apparmor.d'].encode(),check=True)
target=pathlib.Path('/etc/apparmor.d/cri-containerd.apparmor.d')
assert not target.exists()
backup=pathlib.Path('/var/lib/cps-apparmor-compat');backup.mkdir(mode=0o700,exist_ok=False)
(backup/'original.raw').write_bytes(raw)
(backup/'baseline.profile').write_text(p['baseline.profile'])
target.write_text(p['cri-containerd.apparmor.d']);target.chmod(0o644)
try:
 subprocess.run(['apparmor_parser','-r','-K',str(target)],check=True)
except BaseException:
 subprocess.run(['apparmor_parser','-r','-B',str(backup/'original.raw')],check=True)
 target.unlink()
 raise
# apparmor.service loads /etc/apparmor.d on boot. Make ordering explicit.
dropin=pathlib.Path('/etc/systemd/system/k3s-agent.service.d/30-apparmor-compat.conf')
assert not dropin.exists()
dropin.parent.mkdir(parents=True,exist_ok=True)
dropin.write_text('[Unit]\nRequires=apparmor.service\nAfter=apparmor.service\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
print(json.dumps({'installed':str(target),'profile_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'backup':str(backup),'dropin':str(dropin),'service_restarted':False}))
'''
subprocess.run(['ssh','-i','/home/bjoern/.ssh/id_ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','ubuntu@10.21.0.43','sudo python3 -c '+shlex.quote(remote)],input=json.dumps(payload),text=True,check=True)
