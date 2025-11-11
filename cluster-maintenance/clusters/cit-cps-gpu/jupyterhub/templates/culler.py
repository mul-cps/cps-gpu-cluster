"""
Enhanced Culler Configuration for CPS GPU Cluster JupyterHub

This module provides optimized idle culling logic with GPU-aware handling.
"""

# Enhanced culler settings with GPU awareness
culler_config = {
    # Base timeout (seconds) - 4 hours for GPU pods, 2 hours for CPU pods
    'timeout': 7200,  # 2 hours default
    
    # Poll interval (seconds) - check every 10 minutes
    'every': 600,
    
    # Concurrency limits
    'concurrency': 10,
    'max_age': 0,
    
    # Remove named servers that have been inactive
    'remove_named_servers': True,
    
    # GPU-aware timeout logic
    'timeout_func': '''
def gpu_aware_timeout(spawner, pod):
    """
    Dynamic timeout based on resource allocation
    Returns timeout in seconds
    """
    # Get resource limits from spawner config
    gpu_limit = 0
    if hasattr(spawner, 'extra_resource_limits'):
        limits = spawner.extra_resource_limits or {}
        gpu_limit = int(limits.get('nvidia.com/gpu', 0))
        # Also check for MIG resources
        for key in limits:
            if 'mig-' in key:
                gpu_limit = max(gpu_limit, int(limits[key]))
    
    # GPU pods get longer timeout
    if gpu_limit > 0:
        if gpu_limit >= 2:
            return 21600  # 6 hours for dual-GPU
        else:
            return 14400  # 4 hours for single GPU
    else:
        return 7200   # 2 hours for CPU-only
    ''',
    
    # Additional GPU-specific handling
    'pre_cull_hook': '''
def pre_cull_gpu_cleanup(spawner, pod):
    """
    Perform GPU-specific cleanup before culling
    """
    import logging
    logger = logging.getLogger('jhub.culler')
    
    try:
        # Check if pod has GPU resources
        containers = pod.spec.containers if pod.spec else []
        has_gpu = False
        
        for container in containers:
            if container.resources and container.resources.limits:
                limits = container.resources.limits
                if any('nvidia.com/gpu' in str(k) or 'mig-' in str(k) for k in limits.keys()):
                    has_gpu = True
                    break
        
        if has_gpu:
            logger.info(f"Culling GPU pod: {pod.metadata.name}")
            # Could add additional GPU cleanup logic here
            # e.g., clearing GPU memory, notifying monitoring systems
        
        return True  # Proceed with culling
        
    except Exception as e:
        logger.error(f"Error in pre_cull_gpu_cleanup: {e}")
        return True  # Don't block culling on errors
    ''',
    
    # Resource-aware culling priority
    'cull_priority_func': '''
def gpu_cull_priority(spawner, pod):
    """
    Return priority for culling (higher = cull sooner)
    GPU resources should be freed up more aggressively when idle
    """
    priority = 0
    
    try:
        # Base priority on idle time
        import datetime
        if hasattr(pod.metadata, 'annotations'):
            last_activity = pod.metadata.annotations.get('jupyterhub.alpha.kubernetes.io/last-activity')
            if last_activity:
                from dateutil.parser import parse as parse_date
                last_active = parse_date(last_activity)
                idle_time = (datetime.datetime.now(datetime.timezone.utc) - last_active).total_seconds()
                priority += int(idle_time / 3600)  # 1 point per hour idle
        
        # Higher priority for GPU resources (free them up faster)
        containers = pod.spec.containers if pod.spec else []
        for container in containers:
            if container.resources and container.resources.limits:
                limits = container.resources.limits
                gpu_count = 0
                for k, v in limits.items():
                    if 'nvidia.com/gpu' in str(k) or 'mig-' in str(k):
                        gpu_count += int(v)
                
                if gpu_count >= 2:
                    priority += 20  # High priority for dual-GPU
                elif gpu_count >= 1:
                    priority += 10  # Medium priority for single GPU
        
        return priority
        
    except Exception:
        return priority
    '''
}

# Export for use in values.yaml
def get_culler_config():
    """Return the culler configuration dictionary"""
    return culler_config
