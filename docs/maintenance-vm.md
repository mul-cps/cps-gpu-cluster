# Maintenance VM

The maintenance VM is a lightweight utility server designed for cluster administration, debugging, and operational tasks. It comes pre-configured with all necessary tools for managing the K3s GPU cluster.

## Purpose

The maintenance VM serves as:
- **Central management point** for cluster operations
- **Jump box** for SSH access to cluster nodes
- **Debugging station** with comprehensive tooling
- **Development environment** for infrastructure changes
- **Isolated workspace** separate from production nodes

## Specifications

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 50 GB
- **Network**: VLAN 633, static IP (10.21.0.42)
- **Auto-start**: Disabled (manual start when needed)

## Pre-installed Tools

### Infrastructure as Code
- **OpenTofu** (Terraform fork) - Infrastructure provisioning
- **Ansible** + ansible-lint - Configuration management
- **Git** + Git LFS - Version control

### Kubernetes Management
- **kubectl** - Kubernetes CLI with useful plugins via krew:
  - `ctx` - Context switcher
  - `ns` - Namespace switcher
  - `whoami` - Show current user
  - `tree` - Resource hierarchy
  - `tail` - Tail logs from multiple pods
  - `view-secret` - Decode secrets
  - `resource-capacity` - Resource usage
- **k9s** - Terminal-based Kubernetes UI
- **helm** - Kubernetes package manager
- **kubectx/kubens** - Quick context/namespace switching

### Container Tools
- **Docker** + Docker Compose - Container runtime and orchestration

### Network Debugging
- **tcpdump** - Packet capture and analysis
- **nmap** - Network scanner
- **netcat** - Network utility
- **iperf3** - Network performance testing
- **mtr** - Network diagnostic tool
- **iftop** - Network bandwidth monitoring

### System Debugging
- **strace** - System call tracer
- **lsof** - List open files
- **sysstat** - Performance monitoring
- **htop/iotop** - Process monitoring
- **ncdu** - Disk usage analyzer
- **stress-ng** - Stress testing

### Modern CLI Tools
- **jq** - JSON processor
- **yq** - YAML processor
- **ripgrep** (rg) - Fast grep alternative
- **fd** - Fast find alternative
- **bat** - Cat with syntax highlighting
- **fzf** - Fuzzy finder
- **httpie** - User-friendly HTTP client

### Load Testing
- **siege** - HTTP load testing
- **wrk** - HTTP benchmarking

## Workspace Structure

The maintenance VM includes a pre-configured workspace at `~/workspace`:

```
~/workspace/
├── terraform/     # Terraform/OpenTofu configurations
├── ansible/       # Ansible playbooks and inventories
├── kubernetes/    # Kubernetes manifests
├── scripts/       # Custom maintenance scripts
├── tmp/           # Temporary files
└── README.md      # Workspace documentation
```

## Maintenance Scripts

Located in `/opt/maintenance-tools/scripts/`:

### cluster-health.sh
Comprehensive cluster health check showing:
- Node status
- System pods
- GPU operator status
- PersistentVolumeClaims
- Resource usage
- Recent events

```bash
/opt/maintenance-tools/scripts/cluster-health.sh
```

### check-gpus.sh
Check GPU status across all GPU worker nodes:
```bash
/opt/maintenance-tools/scripts/check-gpus.sh
```

### quick-deploy.sh
Quick deployment helper for testing:
```bash
/opt/maintenance-tools/scripts/quick-deploy.sh nginx nginx:latest 3
```

### cleanup-failed-pods.sh
Clean up failed/completed pods across all namespaces:
```bash
/opt/maintenance-tools/scripts/cleanup-failed-pods.sh
```

## Deployment

### Enable Maintenance VM

The maintenance VM is optional and controlled by variables in `terraform.tfvars`:

```hcl
# Uncomment to enable maintenance VM
maintenance_mac = "00:16:3e:63:79:2d"  # cit-vm-42
maintenance_ip  = "10.21.0.42/16"      # k3s-maintenance
```

**Note**: You'll need to request the MAC address and IP from MUL network administration for VLAN 633.

### Deploy with Terraform

```bash
cd bootstrap-cluster/terraform

# Plan the deployment
tofu plan -out=tfplan

# Apply the changes
tofu apply tfplan
```

### Configure with Ansible

After the VM is created, run the maintenance VM playbook:

```bash
cd bootstrap-cluster/ansible

# Configure only the maintenance VM
ansible-playbook -i inventory.ini playbooks/05-maintenance-vm.yml

# Or run the full site playbook (includes maintenance if present)
ansible-playbook -i inventory.ini playbooks/site.yml
```

**Note**: The Ansible playbook will automatically:
- Install all required tools
- Fetch the kubeconfig from the first control plane node
- Configure kubectl to access the cluster
- Set up autocompletion for kubectl and helm
- Create maintenance scripts and workspace

## Usage

### Connect to Maintenance VM

```bash
ssh ubuntu@10.21.0.42
# or
ssh ubuntu@k3s-maintenance
```

### Interactive Cluster Management

```bash
# Launch k9s for interactive cluster management
k9s

# Switch kubectl context
kubectx

# Switch namespace
kubens
```

### Cluster Operations

```bash
# Check cluster health
/opt/maintenance-tools/scripts/cluster-health.sh

# View all nodes
kubectl get nodes -o wide

# Check GPU availability
kubectl get nodes -o json | jq '.items[].status.capacity | select(."nvidia.com/gpu")'

# View GPU operator status
kubectl get pods -n gpu-operator

# Check running workloads
kubectl get pods -A

# Use kubectl autocompletion (already configured)
kubectl get po<TAB>  # Will autocomplete to 'pods'
kubectl get nodes -n <TAB>  # Will show available namespaces
```

### SSH to Cluster Nodes

The maintenance VM has SSH access to all cluster nodes:

```bash
# Control plane nodes
ssh ubuntu@k3s-cp1
ssh ubuntu@k3s-cp2
ssh ubuntu@k3s-cp3

# GPU worker nodes
ssh ubuntu@k3s-wk-gpu1
ssh ubuntu@k3s-wk-gpu2
ssh ubuntu@k3s-wk-gpu3
ssh ubuntu@k3s-wk-gpu4
```

### Network Debugging

```bash
# Check connectivity to a node
ping k3s-cp1

# Trace route to external service
mtr google.com

# Scan cluster network
nmap -sn 10.21.0.0/16

# Monitor network traffic
sudo iftop -i eth0

# Test network performance between nodes
# On maintenance VM:
iperf3 -s

# On target node:
iperf3 -c k3s-maintenance
```

### Container Operations

```bash
# Run temporary debug container
docker run -it --rm ubuntu:24.04 bash

# Build custom images
docker build -t my-image:latest .

# Use Docker Compose for multi-container apps
docker-compose up -d
```

### Infrastructure Management

```bash
# Navigate to workspace
cd ~/workspace/terraform

# Clone cluster repository
git clone <repository-url>

# Make infrastructure changes
tofu plan
tofu apply

# Run Ansible playbooks
cd ~/workspace/ansible
ansible-playbook -i inventory.ini site.yml
```

## Useful Aliases

The maintenance VM comes with pre-configured bash aliases:

- `k` - Short for `kubectl`
- `kgp` - Get all pods in all namespaces
- `kgn` - Get nodes with wide output
- `tf` - Short for `tofu` (Terraform)
- `ll` - Detailed directory listing
- `dps` - Docker ps
- `dlog` - Follow docker logs

## Best Practices

1. **Use the maintenance VM for cluster operations** - Avoid making changes directly from your workstation
2. **Keep it updated** - Regularly update tools and packages
3. **Document changes** - Use Git to track infrastructure changes
4. **Test before production** - Use quick-deploy.sh to test configurations
5. **Monitor resources** - The VM is lightweight, avoid running heavy workloads
6. **Backup configurations** - Store Terraform/Ansible code in Git
7. **Use tmux** - For long-running operations, use tmux sessions

## Troubleshooting

### Can't connect to maintenance VM

Check VM status in Proxmox:
```bash
# On Proxmox host
qm status <vm-id>
qm start <vm-id>
```

### kubectl not working

The Ansible playbook automatically configures kubectl, but if you need to set it up manually:

```bash
# Copy kubeconfig from control plane
scp ubuntu@k3s-cp1:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update server address
sed -i 's/127.0.0.1/k3s-cp1/' ~/.kube/config

# Set correct permissions
chmod 600 ~/.kube/config

# Set KUBECONFIG environment variable
echo 'export KUBECONFIG=$HOME/.kube/config' >> ~/.bashrc
source ~/.bashrc
```

2. Verify cluster connectivity:
```bash
kubectl cluster-info
kubectl get nodes
```

### Tools not in PATH

Some tools may require PATH updates:
```bash
# Add to ~/.bashrc
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"
export PATH="/usr/local/bin:$PATH"

# Reload shell
source ~/.bashrc
```

### Disk space issues

Clean up Docker and temporary files:
```bash
# Clean Docker
docker system prune -a

# Clean apt cache
sudo apt-get clean

# Check disk usage
ncdu /
```

## Disabling the Maintenance VM

To disable the maintenance VM without destroying other resources:

1. Comment out the maintenance VM variables in `terraform.tfvars`:
```hcl
# maintenance_mac = "00:16:3e:63:79:2d"
# maintenance_ip  = "10.21.0.42/16"
```

2. Apply the changes:
```bash
cd bootstrap-cluster/terraform
tofu plan -out=tfplan
tofu apply tfplan
```

The maintenance VM will be destroyed, but all other cluster resources remain intact.

## Security Considerations

- The maintenance VM has SSH access to all cluster nodes - protect SSH keys
- Docker daemon runs with elevated privileges - be cautious with container operations
- The VM is on the same VLAN as cluster nodes - apply appropriate firewall rules
- Regularly update packages: `sudo apt update && sudo apt upgrade`
- Consider enabling UFW firewall: `sudo ufw enable`

## Additional Resources

- [K3s Documentation](https://docs.k3s.io/)
- [OpenTofu Documentation](https://opentofu.org/docs/)
- [Ansible Documentation](https://docs.ansible.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [k9s Documentation](https://k9scli.io/)
