import json

def load_json(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def check_orphans():
    pvcs_data = load_json('pvcs.json')
    pods_data = load_json('pods.json')
    pvs_data = load_json('pvs.json')

    # key: (namespace, name) -> pvc_item
    all_pvcs = {}
    for item in pvcs_data['items']:
        ns = item['metadata']['namespace']
        name = item['metadata']['name']
        all_pvcs[(ns, name)] = item

    # Find mounted PVCs
    mounted_pvcs = set()
    for pod in pods_data['items']:
        # Check if pod is running or pending (not succeeded/failed, although succeeded pods might need their data?)
        # Usually we only care about active pods holding on to PVCs. 
        # But let's assume if it's referenced in a pod that is not Terminating, it's used.
        # Actually simplest is just valid reference in any pod.
        
        ns = pod['metadata']['namespace']
        volumes = pod.get('spec', {}).get('volumes', [])
        for vol in volumes:
            if 'persistentVolumeClaim' in vol:
                if vol['persistentVolumeClaim'] is None:
                     continue
                pvc_name = vol['persistentVolumeClaim']['claimName']
                mounted_pvcs.add((ns, pvc_name))

    orphaned_pvcs = []
    for key, item in all_pvcs.items():
        if key not in mounted_pvcs:
            orphaned_pvcs.append(item)

    # Check PVs
    orphaned_pvs = []
    for item in pvs_data['items']:
        status = item['status']['phase']
        if status in ['Released', 'Available']:
            orphaned_pvs.append(item)

    print(f"Found {len(orphaned_pvcs)} potentially orphaned PVCs:")
    for pvc in orphaned_pvcs:
        ns = pvc['metadata']['namespace']
        name = pvc['metadata']['name']
        print(f"  PVC: {ns}/{name} (Status: {pvc['status']['phase']})")

    print(f"\nFound {len(orphaned_pvs)} potentially orphaned PVs:")
    for pv in orphaned_pvs:
        name = pv['metadata']['name']
        claim = pv['spec'].get('claimRef', {})
        claim_ns = claim.get('namespace', '<none>')
        claim_name = claim.get('name', '<none>')
        print(f"  PV: {name} (Status: {pv['status']['phase']}, Claim: {claim_ns}/{claim_name})")

if __name__ == "__main__":
    check_orphans()
