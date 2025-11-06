#!/usr/bin/env bash
# Quick reference script for maintenance VM operations
# This script can be sourced or executed to display helpful commands

cat << 'EOF'
╔════════════════════════════════════════════════════════════════════╗
║              K3s GPU Cluster - Maintenance VM Quick Reference      ║
╚════════════════════════════════════════════════════════════════════╝

DEPLOYMENT
──────────
# Enable in terraform.tfvars (uncomment):
  maintenance_mac = "00:16:3e:63:79:2d"
  maintenance_ip  = "10.21.0.42/16"

# Deploy with Terraform:
  cd bootstrap-cluster/terraform
  tofu plan -out=tfplan
  tofu apply tfplan

# Configure with Ansible:
  cd bootstrap-cluster/ansible
  ansible-playbook -i inventory.ini playbooks/05-maintenance-vm.yml

CONNECTION
──────────
  ssh ubuntu@10.21.0.42
  ssh ubuntu@k3s-maintenance

MAINTENANCE SCRIPTS
───────────────────
  /opt/maintenance-tools/scripts/cluster-health.sh       # Full cluster health check
  /opt/maintenance-tools/scripts/check-gpus.sh           # GPU status on all workers
  /opt/maintenance-tools/scripts/quick-deploy.sh         # Quick test deployment
  /opt/maintenance-tools/scripts/cleanup-failed-pods.sh  # Clean up failed pods

KUBERNETES COMMANDS
───────────────────
  k9s                           # Interactive cluster UI
  kubectl get nodes -o wide     # List all nodes
  kubectl get pods -A           # List all pods
  kubectx                       # Switch kubectl context
  kubens                        # Switch namespace
  kubectl top nodes             # Node resource usage
  kubectl get events -A         # Recent events
  
  # kubectl is pre-configured and connected to the cluster
  # Autocompletion is enabled: kubectl get po<TAB>

GPU COMMANDS
────────────
  kubectl get nodes -o json | jq '.items[].status.capacity | select(."nvidia.com/gpu")'
  kubectl get pods -n gpu-operator
  kubectl describe nodes | grep -A5 "nvidia.com/gpu"

CLUSTER NODE ACCESS
───────────────────
  # Control Plane
  ssh ubuntu@k3s-cp1
  ssh ubuntu@k3s-cp2
  ssh ubuntu@k3s-cp3

  # GPU Workers
  ssh ubuntu@k3s-wk-gpu1
  ssh ubuntu@k3s-wk-gpu2
  ssh ubuntu@k3s-wk-gpu3
  ssh ubuntu@k3s-wk-gpu4

NETWORK DEBUGGING
─────────────────
  ping k3s-cp1                  # Test connectivity
  mtr google.com                # Network trace
  nmap -sn 10.21.0.0/16        # Network scan
  sudo iftop -i eth0           # Network traffic
  iperf3 -s                    # Network performance (server)

USEFUL ALIASES
──────────────
  k      = kubectl
  kgp    = kubectl get pods -A
  kgn    = kubectl get nodes -o wide
  tf     = tofu
  ll     = ls -lah
  dps    = docker ps
  dlog   = docker logs -f

WORKSPACE
─────────
  ~/workspace/terraform/        # Infrastructure code
  ~/workspace/ansible/          # Configuration management
  ~/workspace/kubernetes/       # K8s manifests
  ~/workspace/scripts/          # Custom scripts

COMMON WORKFLOWS
────────────────
  # Check cluster health
  /opt/maintenance-tools/scripts/cluster-health.sh

  # Deploy test workload
  kubectl create deployment nginx --image=nginx --replicas=2
  kubectl expose deployment nginx --port=80 --type=NodePort

  # Debug pod issues
  kubectl get pods -A | grep -v Running
  kubectl describe pod <pod-name> -n <namespace>
  kubectl logs <pod-name> -n <namespace> --tail=50

  # Check GPU availability
  /opt/maintenance-tools/scripts/check-gpus.sh
  kubectl get nodes -o json | jq '.items[] | {name:.metadata.name, gpu:.status.capacity["nvidia.com/gpu"]}'

  # Infrastructure changes
  cd ~/workspace/terraform
  git pull
  tofu plan
  tofu apply

TROUBLESHOOTING
───────────────
  # VM won't start
  # On Proxmox: qm status <vm-id> && qm start <vm-id>

  # kubectl not working (usually auto-configured by Ansible)
  scp ubuntu@k3s-cp1:/etc/rancher/k3s/k3s.yaml ~/.kube/config
  sed -i 's/127.0.0.1/k3s-cp1/' ~/.kube/config
  chmod 600 ~/.kube/config
  echo 'export KUBECONFIG=$HOME/.kube/config' >> ~/.bashrc

  # Disk space low
  docker system prune -a
  sudo apt-get clean
  ncdu /

  # Network issues
  sudo systemctl status systemd-networkd
  ip addr show
  ip route show
  
  # Reload shell configuration
  source ~/.bashrc

DOCUMENTATION
─────────────
  Full documentation: docs/maintenance-vm.md
  Workspace README: ~/workspace/README.md

EOF
