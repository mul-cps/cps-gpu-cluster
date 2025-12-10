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
    
    # Install JupyterHub and Dask packages
    pip install --no-cache-dir jupyterhub jupyterhub-singleuser jupyter-server-proxy dask-kubernetes
    
    # Install code-server
    curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone --prefix=/tmp/code-server
    /tmp/code-server/bin/code-server --auth none --port 13337 >/tmp/code-server.log 2>&1 &
  EOT

  metadata {
    display_name = "CPU Usage"
    key          = "cpu_usage"
    script       = "coder stat cpu"
    interval     = 10
    timeout      = 1
  }

  metadata {
    display_name = "RAM Usage"
    key          = "ram_usage"
    script       = "coder stat mem"
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

resource "kubernetes_persistent_volume_claim" "home" {
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
        storage = "20Gi"
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
        # ServiceAccount for Dask operator access
        service_account_name = "dask-sa"

        security_context {
          run_as_user = 1001  # RapidsAI uses UID 1001
          fs_group    = 100
        }

        container {
          name              = "dev"
          image             = "nvcr.io/nvidia/rapidsai/base:24.08-cuda12.2-py3.10"
          image_pull_policy = "Always"
          command           = ["sh", "-c", coder_agent.main.init_script]
          
          security_context {
            run_as_user = 1001
          }

          env {
            name  = "CODER_AGENT_TOKEN"
            value = coder_agent.main.token
          }

          env {
            name  = "DASK_KUBERNETES__OPERATOR__NAMESPACE"
            value = "dask-compute"
          }

          resources {
            requests = {
              cpu    = "1"
              memory = "4Gi"
            }
            limits = {
              cpu    = "2"
              memory = "8Gi"
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
            claim_name = kubernetes_persistent_volume_claim.home.metadata[0].name
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
