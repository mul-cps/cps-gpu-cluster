[control_plane]
%{ for idx, ip in control_plane_ips ~}
k3s-cp${idx + 1} ansible_host=${ip} ansible_user=${vm_user}
%{ endfor ~}

[gpu_workers]
%{ for idx, ip in worker_ips ~}
k3s-wk-gpu${idx + 1} ansible_host=${ip} ansible_user=${vm_user}
%{ endfor ~}

%{ if length(maintenance_ips) > 0 ~}
[maintenance]
%{ for idx, ip in maintenance_ips ~}
k3s-maintenance ansible_host=${ip} ansible_user=${vm_user}
%{ endfor ~}

%{ endif ~}
[k3s_cluster:children]
control_plane
gpu_workers

[k3s_cluster:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
