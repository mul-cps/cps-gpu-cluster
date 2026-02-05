"""
Dynamic Profile Generation for CPS GPU Cluster JupyterHub

This module generates profile options based on user groups and available resources.
"""

import os

# Profile list for KubeSpawner
PROFILE_LIST = [
    {
        'display_name': 'CPU (Default)',
        'slug': 'cpu-default',
        'description': 'Standard CPU-only environment for development and testing',
        'default': True,
        'kubespawner_override': {
            'image': 'quay.io/jupyter/scipy-notebook:2024-10-07',
            'cpu_limit': 2,
            'mem_limit': '2G',
            'cpu_guarantee': 0.1,
            'mem_guarantee': '512M',
            'extra_resource_limits': {},
            'extra_resource_guarantees': {},
            'node_selector': {},
            'tolerations': []
        }
    },
    {
        'display_name': 'GPU: PyTorch (1×)',
        'slug': 'gpu-pytorch-single',
        'description': 'PyTorch environment with single NVIDIA A100 GPU',
        'kubespawner_override': {
            'image': 'nvcr.io/nvidia/pytorch:24.11-py3',
            'cpu_limit': 16,
            'mem_limit': '64G',
            'cpu_guarantee': 2,
            'mem_guarantee': '8G',
            'extra_resource_limits': {
                'nvidia.com/gpu': '1'
            },
            'extra_resource_guarantees': {
                'nvidia.com/gpu': '1'
            },
            'node_selector': {
                'nvidia.com/gpu.product': 'NVIDIA-A100-PCIE-40GB'
            },
            'tolerations': [
                {
                    'key': 'nvidia.com/gpu',
                    'operator': 'Exists',
                    'effect': 'NoSchedule'
                }
            ]
        }
    },
    {
        'display_name': 'GPU: TensorFlow (1×)',
        'slug': 'gpu-tensorflow-single',
        'description': 'TensorFlow environment with single NVIDIA A100 GPU',
        'kubespawner_override': {
            'image': 'nvcr.io/nvidia/tensorflow:24.11-tf2-py3',
            'cpu_limit': 16,
            'mem_limit': '64G',
            'cpu_guarantee': 2,
            'mem_guarantee': '8G',
            'extra_resource_limits': {
                'nvidia.com/gpu': '1'
            },
            'extra_resource_guarantees': {
                'nvidia.com/gpu': '1'
            },
            'node_selector': {
                'nvidia.com/gpu.product': 'NVIDIA-A100-PCIE-40GB'
            },
            'tolerations': [
                {
                    'key': 'nvidia.com/gpu',
                    'operator': 'Exists',
                    'effect': 'NoSchedule'
                }
            ]
        }
    },
    {
        'display_name': 'GPU: PyTorch (2×)',
        'slug': 'gpu-pytorch-dual',
        'description': 'PyTorch environment with dual NVIDIA A100 GPUs',
        'kubespawner_override': {
            'image': 'nvcr.io/nvidia/pytorch:24.11-py3',
            'cpu_limit': 32,
            'mem_limit': '128G',
            'cpu_guarantee': 4,
            'mem_guarantee': '16G',
            'extra_resource_limits': {
                'nvidia.com/gpu': '2'
            },
            'extra_resource_guarantees': {
                'nvidia.com/gpu': '2'
            },
            'node_selector': {
                'nvidia.com/gpu.product': 'NVIDIA-A100-PCIE-40GB'
            },
            'tolerations': [
                {
                    'key': 'nvidia.com/gpu',
                    'operator': 'Exists',
                    'effect': 'NoSchedule'
                }
            ]
        }
    },
    {
        'display_name': 'GPU: TensorFlow (2×)',
        'slug': 'gpu-tensorflow-dual',
        'description': 'TensorFlow environment with dual NVIDIA A100 GPUs',
        'kubespawner_override': {
            'image': 'nvcr.io/nvidia/tensorflow:24.11-tf2-py3',
            'cpu_limit': 32,
            'mem_limit': '128G',
            'cpu_guarantee': 4,
            'mem_guarantee': '16G',
            'extra_resource_limits': {
                'nvidia.com/gpu': '2'
            },
            'extra_resource_guarantees': {
                'nvidia.com/gpu': '2'
            },
            'node_selector': {
                'nvidia.com/gpu.product': 'NVIDIA-A100-PCIE-40GB'
            },
            'tolerations': [
                {
                    'key': 'nvidia.com/gpu',
                    'operator': 'Exists',
                    'effect': 'NoSchedule'
                }
            ]
        }
    },
    {
        'display_name': 'GPU: MIG 1g.5gb',
        'slug': 'gpu-mig-1g5',
        'description': 'MIG slice environment (1 compute instance, 5GB memory)',
        'kubespawner_override': {
            'image': 'nvcr.io/nvidia/pytorch:24.11-py3',
            'cpu_limit': 8,
            'mem_limit': '32G',
            'cpu_guarantee': 1,
            'mem_guarantee': '4G',
            'extra_resource_limits': {
                'nvidia.com/mig-1g.5gb': '1'
            },
            'extra_resource_guarantees': {
                'nvidia.com/mig-1g.5gb': '1'
            },
            'node_selector': {
                'nvidia.com/gpu.product': 'NVIDIA-A100-PCIE-40GB'
            },
            'tolerations': [
                {
                    'key': 'nvidia.com/gpu',
                    'operator': 'Exists',
                    'effect': 'NoSchedule'
                }
            ]
        }
    }
]

def options_from_form(form_data):
    """
    Parse form data from the custom UI and return spawner options
    """
    profile = form_data.get('profile', ['cpu-default'])[0]
    custom_image = form_data.get('custom_image', [''])[0].strip()
    custom_gpus = form_data.get('custom_gpus', ['0'])[0]
    
    options = {
        'profile': profile,
        'custom_image': custom_image if custom_image else None,
        'custom_gpus': int(custom_gpus) if custom_gpus.isdigit() else 0
    }
    
    return options

async def apply_profile_settings(spawner):
    """
    Apply profile settings to the spawner before pod creation
    """
    user_options = spawner.user_options
    profile_name = user_options.get('profile', 'cpu-default')
    custom_image = user_options.get('custom_image')
    custom_gpus = user_options.get('custom_gpus', 0)
    
    # Find the selected profile
    selected_profile = None
    for profile in PROFILE_LIST:
        if profile['slug'] == profile_name:
            selected_profile = profile
            break
    
    if not selected_profile:
        selected_profile = PROFILE_LIST[0]  # Fallback to default
    
    # Apply profile settings
    override = selected_profile['kubespawner_override']
    
    # Override image if custom image specified (admin only)
    if custom_image and spawner.user.admin:
        spawner.image = custom_image
    else:
        spawner.image = override.get('image', spawner.image)
    
    # Set resource limits
    spawner.cpu_limit = override.get('cpu_limit', 2)
    spawner.mem_limit = override.get('mem_limit', '2G')
    spawner.cpu_guarantee = override.get('cpu_guarantee', 0.1)
    spawner.mem_guarantee = override.get('mem_guarantee', '512M')
    
    # Set GPU resources
    spawner.extra_resource_limits = override.get('extra_resource_limits', {}).copy()
    spawner.extra_resource_guarantees = override.get('extra_resource_guarantees', {}).copy()
    
    # Override GPU count if custom specified and user has admin access
    if custom_gpus > 0 and spawner.user.admin:
        spawner.extra_resource_limits['nvidia.com/gpu'] = str(custom_gpus)
        spawner.extra_resource_guarantees['nvidia.com/gpu'] = str(custom_gpus)
    
    # Set node selector and tolerations
    spawner.node_selector = override.get('node_selector', {})
    spawner.tolerations = override.get('tolerations', [])
    
    # Set environment variables for GPU images
    if spawner.extra_resource_limits.get('nvidia.com/gpu'):
        spawner.environment.update({
            'NVIDIA_VISIBLE_DEVICES': 'all',
            'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility',
            'CUDA_DEVICE_ORDER': 'PCI_BUS_ID'
        })
    
    return spawner

# Legacy function for compatibility
def get_profiles():
    """Return profile list (compatibility function)"""
    return PROFILE_LIST
