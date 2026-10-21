"""Check CPS PyTorch consumers and actual Helm-rendered image pullers."""
import os
from pathlib import Path
import subprocess
import unittest

import yaml

from test_notebook_cpu_runtime import CPU_IMAGE, VALUES, profiles


DIGEST = 'sha256:3910644e2e541f9cde6bed75a01f1bbdcc293a2d57a3f8862cbc99c7eeca30f3'
IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook@' + DIGEST
PULL_IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook:latest-pytorch-code@' + DIGEST
RESOURCES = {
    'gpu-pytorch-single': (16, 8, '64G', '32G', 1, None),
    'gpu-pytorch-dual': (32, 16, '128G', '64G', 2, None),
    'gpu-3gb': (4, 2, '16G', '8G', 1, 3072),
    'gpu-5gb': (6, 3, '24G', '12G', 1, 5120),
    'gpu-8gb': (8, 4, '32G', '16G', 1, 8192),
    'gpu-10gb': (10, 5, '40G', '20G', 1, 10240),
    'gpu-12gb': (12, 6, '48G', '24G', 1, 12288),
    'gpu-20gb': (16, 8, '64G', '32G', 1, 20480),
    'gpu-student': (6, 3, '24G', '12G', 1, 5120),
    'gpu-slurm': (8, 4, '32G', '16G', 0, None),
}


class NotebookPyTorchRuntimeTests(unittest.TestCase):
    def test_exact_ten_pytorch_profiles_select_published_image(self):
        table = profiles()
        for slug in RESOURCES:
            with self.subTest(slug=slug):
                self.assertEqual(table[slug]['image'], IMAGE)
        self.assertEqual({slug for slug, row in table.items() if row['image'] == IMAGE}, set(RESOURCES))

    def test_cpu_and_other_profile_images_remain_separate(self):
        prefix = 'ghcr.io/mul-cps/cps-jupyter-notebook:'
        expected = {
            'cpu-default': CPU_IMAGE,
            'dask-cluster': 'nvcr.io/nvidia/rapidsai/base:24.08-cuda12.2-py3.10',
            'cpu-desktop': prefix + 'latest-desktop-ros2',
            'gpu-tensorflow-single': prefix + 'latest-tf-code',
            'gpu-tensorflow-dual': prefix + 'latest-tf-code',
            'gpu-desktop-ros2': prefix + 'latest-desktop-ros2',
            'gpu-desktop-5gb': prefix + 'latest-desktop-ros2',
            'gpu-desktop-xpra': prefix + 'latest-desktop-ros2-xpra',
            'gpu-comfyui': prefix + 'main-comfyui',
        }
        self.assertEqual({slug: row['image'] for slug, row in profiles().items() if slug not in RESOURCES}, expected)

    def test_existing_pytorch_resource_limits_and_scheduling_are_preserved(self):
        table = profiles()
        fields = ('cpu_limit', 'cpu_guarantee', 'mem_limit', 'mem_guarantee', 'gpu', 'memory_mib')
        for slug, expected in RESOURCES.items():
            with self.subTest(slug=slug):
                row = table[slug]
                self.assertEqual(tuple(row.get(key) for key in fields), expected)
                self.assertEqual(row['runtime_class'], None if slug == 'gpu-slurm' else 'nvidia')
                if slug == 'gpu-slurm':
                    self.assertEqual(row['scheduler_name'], 'slurm-bridge-scheduler')
                else:
                    self.assertEqual(row['resource_key'], 'nvidia.com/gpu')

    def test_both_rendered_helm_pullers_select_the_same_immutable_bytes(self):
        chart = Path(os.environ.get('JUPYTERHUB_CHART', Path.home() / '.cache/helm/jupyterhub-4.4.2.tgz'))
        result = subprocess.run(['helm', 'template', 'jupyterhub', str(chart), '--namespace', 'jupyterhub',
                                 '-f', str(VALUES)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        images = {}
        for document in yaml.safe_load_all(result.stdout):
            if document and document['kind'] == 'DaemonSet':
                for container in document['spec']['template']['spec'].get('initContainers', []):
                    if container['name'] == 'image-pull-cps-pytorch':
                        images[document['metadata']['name']] = container['image']
        self.assertEqual(images, {'continuous-image-puller': PULL_IMAGE, 'hook-image-puller': PULL_IMAGE})


if __name__ == '__main__':
    unittest.main()
