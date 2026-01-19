terraform {
  required_providers {
    coder = {
      source = "coder/coder"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
    }
  }
}

provider "coder" {}

variable "namespace" {
  type        = string
  description = "The Kubernetes namespace for workspaces"
  default     = "coder"
}

variable "use_kubeconfig" {
  type        = bool
  default     = false
}

provider "kubernetes" {
  config_path = var.use_kubeconfig ? "~/.kube/config" : null
}

data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

resource "coder_agent" "main" {
  os             = "linux"
  arch           = "amd64"
  startup_script = <<-EOT
    #!/bin/bash
    set -e
    curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone --prefix=/tmp/code-server
    /tmp/code-server/bin/code-server --auth none --port 13337 >/tmp/code-server.log 2>&1 &
  EOT

  metadata {
    display_name = "GPU"
    key          = "gpu"
    script       = "nvidia-smi --query-gpu=name --format=csv,noheader | head -n1"
    interval     = 60
    timeout      = 5
  }

  metadata {
    display_name = "GPU Utilization"
    key          = "gpu_util"
    script       = "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -n1"
    interval     = 10
    timeout      = 1
  }
}

resource "coder_app" "code-server" {
  agent_id     = coder_agent.main.id
  slug         = "code-server"
  display_name = "VS Code"
  icon         = "/icon/code.svg"
  url          = "http://localhost:13337?folder=/home/coder"
  subdomain    = false
  share        = "owner"

  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 3
    threshold = 10
  }
}

resource "coder_app" "desktop" {
  agent_id     = coder_agent.main.id
  slug         = "desktop"
  display_name = "Desktop (noVNC)"
  icon         = "/icon/desktop.svg"
  url          = "http://localhost:6080"
  subdomain    = false
  share        = "owner"
}

resource "kubernetes_persistent_volume_claim_v1" "home" {
  metadata {
    name      = "coder-${data.coder_workspace.me.id}-home"
    namespace = var.namespace
    labels = {
      "app.kubernetes.io/name"     = "coder-pvc"
      "com.coder.resource"         = "true"
      "com.coder.workspace.id"     = data.coder_workspace.me.id
      "com.coder.user.username"    = data.coder_workspace_owner.me.name
    }
  }
  wait_until_bound = false
  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "longhorn-fast"
    resources {
      requests = {
        storage = "30Gi"
      }
    }
  }
}

resource "kubernetes_deployment" "main" {
  count            = data.coder_workspace.me.start_count
  wait_for_rollout = false
  
  metadata {
    name      = "coder-${data.coder_workspace.me.id}"
    namespace = var.namespace
    labels = {
      "app.kubernetes.io/name"     = "coder-workspace"
      "com.coder.workspace.id"     = data.coder_workspace.me.id
      "com.coder.user.username"    = data.coder_workspace_owner.me.name
    }
  }

  spec {
    replicas = 1
    
    selector {
      match_labels = {
        "app.kubernetes.io/name"     = "coder-workspace"
        "app.kubernetes.io/instance" = "coder-workspace-${data.coder_workspace.me.id}"
      }
    }

    strategy {
      type = "Recreate"
    }

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name"     = "coder-workspace"
          "app.kubernetes.io/instance" = "coder-workspace-${data.coder_workspace.me.id}"
          "com.coder.workspace.id"     = data.coder_workspace.me.id
        }
      }

      spec {
        runtime_class_name = "nvidia"

        node_selector = {
          "accelerator" = "nvidia"
        }

        security_context {
          run_as_user = 0
          fs_group    = 100
        }

        container {
          name              = "dev"
          image             = "ghcr.io/mul-cps/cps-jupyter-notebook:latest-desktop-ros2"
          image_pull_policy = "Always"
          command           = ["sh", "-c", coder_agent.main.init_script]
          
          security_context {
            allow_privilege_escalation = true
            run_as_user                = 0
          }

          env {
            name  = "CODER_AGENT_TOKEN"
            value = coder_agent.main.token
          }

          env {
            name  = "NVIDIA_VISIBLE_DEVICES"
            value = "all"
          }

          env {
            name  = "NVIDIA_DRIVER_CAPABILITIES"
            value = "compute,utility,graphics"
          }

          env {
            name  = "GRANT_SUDO"
            value = "yes"
          }

          env {
            name  = "NB_UID"
            value = "1000"
          }

          resources {
            requests = {
              cpu               = "8"
              memory            = "32Gi"
              "nvidia.com/gpu"  = "1"
            }
            limits = {
              cpu               = "16"
              memory            = "64Gi"
              "nvidia.com/gpu"  = "1"
            }
          }

          volume_mount {
            mount_path = "/home/coder"
            name       = "home"
          }

          volume_mount {
            mount_path = "/home/coder/shared"
            name       = "shared"
          }

          volume_mount {
            mount_path = "/home/coder/cps_persistent1_shared"
            name       = "cps-persistent1-shared"
          }
        }

        volume {
          name = "home"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.home.metadata[0].name
          }
        }

        volume {
          name = "shared"
          persistent_volume_claim {
            claim_name = "coder-shared-storage"
          }
        }

        volume {
          name = "cps-persistent1-shared"
          persistent_volume_claim {
            claim_name = "cps-persistent1-shared-pvc"
          }
        }
      }
    }
  }
}
