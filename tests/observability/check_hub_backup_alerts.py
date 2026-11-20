#!/usr/bin/env python3
"""Validate Hub backup alerts with promtool and six synthetic metric scenarios."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'docker.io/rancher/prom-prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--podman', action='store_true', help='Use pinned matching Prometheus image; pull it before running')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        rule = yaml.safe_load((ROOT / 'platform-staging/hub-backups/alerts.yaml').read_text())
        (temporary / 'rules.yaml').write_text(yaml.safe_dump(rule['spec']))
        shutil.copyfile(ROOT / 'tests/observability/hub-backup-promtool-cases.yaml', temporary / 'cases.yaml')
        if args.podman:
            prefix = ['podman', 'run', '--rm', '--pull=never', '--network=none',
                      '--user=0', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                      '--security-opt=label=disable', '--memory=256m', '--cpus=1',
                      '-v', str(temporary) + ':/qualification:ro', '-w', '/qualification',
                      '--entrypoint=promtool', IMAGE]
        else:
            prefix = ['promtool']
        for command in [['check','rules','rules.yaml'],['test','rules','cases.yaml']]:
            subprocess.run(prefix + command, cwd=temporary, check=True)


if __name__ == '__main__':
    main()
