# JupyterHub Deep Dive - CPS GPU Cluster

## What is JupyterHub?

### Overview

**JupyterHub** is a multi-user server that manages and proxies multiple instances of the single-user Jupyter notebook server. It enables organizations to provide Jupyter notebooks as a service to groups of users (students, researchers, data scientists) without requiring local installation or configuration.

**Key Features:**
- 🌐 **Web-based**: Access from any browser, anywhere
- 👥 **Multi-tenant**: Supports hundreds to thousands of concurrent users
- 🔐 **Centralized Authentication**: Integrates with institutional SSO/LDAP
- 💻 **Pre-configured Environments**: Users get consistent, ready-to-use environments
- 🎯 **Resource Management**: Control CPU, RAM, GPU allocation per user
- 📦 **Persistent Storage**: User work is saved and survives restarts
- 🔧 **Customizable**: Flexible profile system for different workload types

### Why JupyterHub?

**Traditional Approach Problems:**
- ❌ Students install Jupyter locally → different versions, package conflicts
- ❌ "Works on my machine" syndrome
- ❌ GPU access requires physical lab workstations
- ❌ Limited to lab hours and physical presence
- ❌ Difficult to provide uniform datasets
- ❌ No centralized backup of student work

**JupyterHub Solutions:**
- ✅ Single web interface for all users
- ✅ Pre-configured environments with all required packages
- ✅ Remote GPU access from any location
- ✅ 24/7 availability
- ✅ Shared datasets accessible to all users
- ✅ Automatic backup of user notebooks and data

---

## Universities & Organizations Using JupyterHub

### Major Deployments

**🎓 Universities:**

1. **UC Berkeley** (JupyterHub birthplace)
   - **DataHub**: Serves 4,000+ students
   - **Data 8**: Foundations of Data Science course
   - 100% cloud-based data science education

2. **University of California System**
   - Used across multiple UC campuses
   - Supports data science and computational courses
   - Integrated with campus authentication

3. **Purdue University**
   - Engineering courses using JupyterHub
   - HPC cluster integration
   - Research and teaching use

4. **Stanford University**
   - Stanford Online courses
   - Research computing platform
   - GPU-enabled notebooks for ML courses

5. **MIT (Massachusetts Institute of Technology)**
   - OpenCourseWare integration
   - Research computing
   - Course 6 (EECS) computational assignments

6. **University of Edinburgh**
   - Noteable platform (JupyterHub-based)
   - Campus-wide deployment
   - Data science education

7. **TU Delft (Netherlands)**
   - Engineering education
   - Scientific computing courses
   - 3,000+ active users

8. **University of Toronto**
   - STA130 statistics course
   - JupyterHub@UofT platform
   - Integrated with institutional systems

9. **Australian National University (ANU)**
   - Computational science courses
   - Research computing
   - GPU-accelerated workflows

10. **ETH Zürich (Switzerland)**
    - Computational science and engineering
    - JupyterLab-based teaching environment

**🏢 Organizations:**

- **Netflix**: Data science and ML workflows
- **NASA**: Satellite data analysis and visualization
- **CERN**: Particle physics data analysis
- **Bloomberg**: Financial data analysis platform
- **Capital One**: Data science and ML model development
- **Two Sigma**: Quantitative research platform

**📚 Large-Scale Platforms:**

- **mybinder.org**: Free public JupyterHub (10,000+ weekly users)
- **Google Colab**: Google's JupyterHub variant (millions of users)
- **Kaggle Kernels**: Data science competition platform
- **Microsoft Azure Notebooks**: Cloud-based JupyterHub

---

## Typical Use Cases

### 1. Education & Teaching

**Scenario: Introduction to Machine Learning Course**

```
Week 1: Python Basics
├─ Student opens jupyterhub.university.edu
├─ Logs in with university credentials
├─ Selects "CPU Profile" (no GPU needed yet)
├─ Gets notebook pre-loaded with Week 1 exercises
└─ Writes code, executes cells, submits assignment

Week 8: Deep Learning with PyTorch
├─ Student selects "GPU PyTorch Single" profile
├─ Gets 1× A100 GPU + 64 GB RAM
├─ Trains neural network on CIFAR-10 dataset
├─ Training takes 15 minutes (vs. hours on laptop)
└─ Saves trained model to persistent storage
```

**Advantages:**
- No local setup required
- Uniform environment for all students
- Instant access to GPUs when needed
- Teaching assistant can view student notebooks for help
- Automatic grading via nbgrader integration

### 2. Research & Data Analysis

**Scenario: Genomics Research Project**

```
Researcher Workflow:
1. Login to JupyterHub
2. Select "GPU TensorFlow Single" profile
3. Access shared dataset (/datasets/genomics/)
4. Run protein folding prediction model
5. Export results to persistent home directory
6. Share notebook with collaborators via Git
```

**Benefits:**
- Access to powerful compute from office/home/conference
- Reproducible research (environment is defined in code)
- No need to manage dependencies
- Collaboration-friendly
- Scales from exploratory analysis to production runs

### 3. Workshops & Tutorials

**Scenario: "Deep Learning for Computer Vision" Workshop**

```
Workshop Setup (Instructor):
├─ Creates template notebook with exercises
├─ Pre-loads datasets into shared storage
├─ Creates workshop-specific profile (1× GPU, 32 GB RAM)
└─ Shares URL: jupyterhub.cps.unileoben.ac.at

Workshop Day (Participants):
├─ 30 participants join simultaneously
├─ Each gets identical environment in seconds
├─ All have GPU access for hands-on exercises
├─ No "installation troubleshooting" delays
└─ Workshop finishes on time!
```

**Why This Works:**
- Zero setup time for participants
- Guaranteed identical environments
- Real GPU access for hands-on learning
- Scales to large groups
- Participants can continue working after workshop

### 4. Student Projects & Thesis Work

**Scenario: Master's Thesis - Sentiment Analysis with Transformers**

```
Student Journey (6 months):
├─ Month 1-2: Exploratory analysis (CPU profile)
│   └─ Data cleaning, EDA, baseline models
├─ Month 3-4: Model development (GPU single)
│   └─ Fine-tune BERT models, hyperparameter search
├─ Month 5: Large-scale training (GPU dual)
│   └─ Train final model on full dataset
└─ Month 6: Thesis writing (CPU profile)
    └─ Generate figures, write notebook-based analysis

All work saved in /home/student123/
├─ notebooks/
├─ data/
├─ models/
└─ thesis-figures/
```

**Benefits:**
- Persistent workspace for entire project duration
- Flexible resource allocation (CPU ↔ GPU as needed)
- No data loss (NFS-backed storage)
- Reproducible results (environment captured in notebook)

---

## CPS GPU Cluster JupyterHub Architecture

### Deployment Overview

```
┌───────────────────────────────────────────────────────────────┐
│                    External World                             │
│                                                               │
│  Users: Students, Researchers, Faculty                        │
└──────────────────┬────────────────────────────────────────────┘
                   │
                   │ HTTPS (10.21.0.50)
                   ▼
┌───────────────────────────────────────────────────────────────┐
│              Ingress Layer (NGINX)                            │
│  Host: jupyterhub.cps.unileoben.ac.at                        │
│  TLS: Wildcard certificate (*.cps.unileoben.ac.at)           │
└──────────────────┬────────────────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────┐
│            JupyterHub Namespace (Kubernetes)                  │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  JupyterHub Proxy (ConfigurableHTTPProxy)          │     │
│  │  - Routes user requests to correct notebook pod    │     │
│  │  - Handles /user/<username>/ paths                 │     │
│  └───────────┬─────────────────────────────────────────┘     │
│              │                                               │
│              ▼                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  JupyterHub Hub (Control Plane)                    │     │
│  │  ┌────────────────────────────────────────────┐    │     │
│  │  │ Components:                                 │    │     │
│  │  │ • Authentication (OAuth2 with Authentik)   │    │     │
│  │  │ • User management                          │    │     │
│  │  │ • Notebook spawner (KubeSpawner)           │    │     │
│  │  │ • Admin dashboard                          │    │     │
│  │  └────────────────────────────────────────────┘    │     │
│  │                                                     │     │
│  │  Database: PostgreSQL                               │     │
│  │  ├─ User sessions                                   │     │
│  │  ├─ Server state                                    │     │
│  │  └─ OAuth tokens                                    │     │
│  └───────────┬─────────────────────────────────────────┘     │
│              │                                               │
│              │ Spawns pods via Kubernetes API               │
│              ▼                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │         User Notebook Pods (Jupyter Labs)          │     │
│  │                                                     │     │
│  │  Pod: jupyter-alice                                │     │
│  │  ├─ Profile: GPU PyTorch Single                    │     │
│  │  ├─ Resources: 1× GPU, 16 vCPU, 64 GB             │     │
│  │  ├─ Image: pytorch-notebook:2025-11-06            │     │
│  │  ├─ Storage: /home/jovyan (NFS PVC)               │     │
│  │  └─ Scheduled on: k3s-wk-gpu3                     │     │
│  │                                                     │     │
│  │  Pod: jupyter-bob                                  │     │
│  │  ├─ Profile: CPU Default                           │     │
│  │  ├─ Resources: 2 vCPU, 2 GB RAM                   │     │
│  │  ├─ Image: datascience-notebook:2025-11-06        │     │
│  │  ├─ Storage: /home/jovyan (NFS PVC)               │     │
│  │  └─ Scheduled on: k3s-wk-gpu1                     │     │
│  │                                                     │     │
│  │  Pod: jupyter-carol                                │     │
│  │  ├─ Profile: GPU Dual TensorFlow                   │     │
│  │  ├─ Resources: 2× GPU, 32 vCPU, 128 GB            │     │
│  │  ├─ Image: tensorflow-notebook:2025-11-06         │     │
│  │  ├─ Storage: /home/jovyan (NFS PVC)               │     │
│  │  └─ Scheduled on: k3s-wk-gpu2                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Component Deep Dive

#### 1. Hub (Control Plane)

**Role**: Central orchestrator and API server

**Responsibilities:**
- **Authentication**: Verify user identity via OAuth2
- **Authorization**: Check group membership for GPU access
- **Spawning**: Create/start user notebook pods
- **Routing**: Update proxy with user → pod mappings
- **Admin UI**: Dashboard for monitoring active users

**Configuration Highlights:**
```python
c.JupyterHub.authenticator_class = 'oauthenticator.generic.GenericOAuthenticator'
c.GenericOAuthenticator.client_id = "vUhzKqEF0UxPtZNM8aRbA1ncaehhIAIA2x9r83FI"
c.GenericOAuthenticator.oauth_callback_url = "https://jupyterhub.cps.unileoben.ac.at/hub/oauth_callback"
c.GenericOAuthenticator.authorize_url = "https://auth.cps.unileoben.ac.at/application/o/authorize/"

# Admin groups
c.GenericOAuthenticator.admin_groups = ["jupyter_admin"]

# Allow all authenticated users
c.GenericOAuthenticator.allow_all = True
```

**Deployment:**
- **Replicas**: 1 (stateful, uses database)
- **Resources**: 4 vCPU, 8 GB RAM
- **Storage**: Config mounted from ConfigMap
- **Database**: PostgreSQL for persistence

#### 2. Proxy (ConfigurableHTTPProxy)

**Role**: Dynamic reverse proxy for user notebooks

**How It Works:**
```
1. User requests: https://jupyterhub.cps.unileoben.ac.at/user/alice/
2. Proxy checks routing table:
   /user/alice/ → http://jupyter-alice:8888
3. Proxy forwards request to Alice's notebook pod
4. Response streams back through proxy to user
```

**Dynamic Routing:**
- Hub updates proxy routing table via REST API
- Proxy adds routes when pods start
- Proxy removes routes when pods stop
- Supports WebSocket for notebook kernel communication

**Deployment:**
- **Replicas**: 1 (can be scaled for HA)
- **Service**: ClusterIP (accessed via Ingress)
- **Health Checks**: Liveness/readiness probes
- **Metrics**: Prometheus metrics endpoint

#### 3. User Schedulers

**Role**: Optimize pod placement across GPU workers

**Why Needed:**
- Default Kubernetes scheduler may not optimize for JupyterHub workloads
- User schedulers understand JupyterHub-specific constraints
- Prevent GPU over-subscription
- Balance load across nodes

**Configuration:**
- **Replicas**: 2 (for load distribution)
- **Resources**: 1 vCPU, 512 MB RAM each
- **Scheduling Plugins**: Custom JupyterHub plugins

#### 4. User Notebook Pods

**Lifecycle:**

```
User Clicks "Start My Server"
         ↓
Hub calls KubeSpawner.start()
         ↓
Spawner creates Pod YAML
         ↓
kubectl create pod jupyter-<username>
         ↓
Kubernetes schedules pod to worker node
         ↓
Container runtime pulls image (if needed)
         ↓
Pod starts, JupyterLab server launches
         ↓
Hub adds route to proxy
         ↓
User redirected to /user/<username>/lab
         ↓
User sees JupyterLab interface!
```

**Pod Specification Example:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: jupyter-alice
  namespace: jupyterhub
  labels:
    app: jupyterhub
    component: singleuser-server
    hub.jupyter.org/username: alice
spec:
  # GPU node selection
  nodeSelector:
    nvidia.com/gpu.present: "true"
  
  # Don't schedule on MIG node for full GPU profiles
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: nvidia.com/mig.capable
            operator: NotIn
            values: ["true"]
  
  # Use NVIDIA container runtime
  runtimeClassName: nvidia
  
  containers:
  - name: notebook
    image: quay.io/jupyter/pytorch-notebook:2025-11-06
    
    # Resource allocation
    resources:
      requests:
        cpu: "8"
        memory: "32Gi"
        nvidia.com/gpu: "1"
      limits:
        cpu: "16"
        memory: "64Gi"
        nvidia.com/gpu: "1"
    
    # Persistent storage
    volumeMounts:
    - name: home
      mountPath: /home/jovyan
    
    # Environment variables
    env:
    - name: JUPYTERHUB_USER
      value: alice
    - name: NVIDIA_VISIBLE_DEVICES
      value: all
    - name: CUDA_VISIBLE_DEVICES
      value: all
  
  volumes:
  - name: home
    persistentVolumeClaim:
      claimName: claim-alice
```

---

## User Profile System

### Profile Selection UI

**Custom HTML/JavaScript Profile Selector:**

```
┌─────────────────────────────────────────────────────┐
│          Select a Profile to Start                  │
│  For longer CLI workloads, use tmux in Terminal     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌────────────────┐  ┌────────────────────────┐   │
│  │ CPU (Default) ✓│  │ GPU: PyTorch (1×)      │   │
│  │ 2 vCPU (shared)│  │ 1× GPU • 16 vCPU • 64G │   │
│  │ 2 GiB          │  │                        │   │
│  └────────────────┘  └────────────────────────┘   │
│                                                     │
│  ┌────────────────────────┐  ┌──────────────────┐ │
│  │ GPU: TensorFlow (1×)   │  │ GPU: PyTorch (2×)│ │
│  │ 1× GPU • 16 vCPU • 64G │  │ 2× GPU • 32 vCPU │ │
│  └────────────────────────┘  └──────────────────┘ │
│                                                     │
│  ┌──────────────────────┐  ┌────────────────────┐ │
│  │ GPU: TensorFlow (2×) │  │ GPU: MIG 1g.5gb    │ │
│  │ 2× GPU • 32 vCPU     │  │ 1× MIG • 6 vCPU    │ │
│  └──────────────────────┘  └────────────────────┘ │
│                                                     │
│  Optional: Custom Image                             │
│  [registry/repo:tag (admins only)    ] [0 × GPU ▼] │
│                                                     │
│                         [Start Server Button]       │
└─────────────────────────────────────────────────────┘
```

**Profile Visibility Logic:**
```python
# Show all profiles to authenticated users
# GPU profiles enabled for everyone (controlled by Authentik groups)

if user in allowed_gpu_groups:
    # User can select GPU profiles
    show_profiles = all_profiles
else:
    # Show all, but Authentik group will control actual access
    show_profiles = all_profiles
```

### Profile Specifications

#### Profile 1: CPU Default

**Target Users**: Students in intro courses, light data analysis

```python
profile = {
    'slug': 'cpu-default',
    'display_name': 'CPU (Default)',
    'description': '2 vCPU (shared) • 2 GiB',
    'image': 'quay.io/jupyter/datascience-notebook:2025-11-06',
    'resources': {
        'requests': {'cpu': 0.5, 'memory': '1G'},
        'limits': {'cpu': 2.0, 'memory': '2G'}
    },
    'default': True
}
```

**Pre-installed Libraries:**
- NumPy, Pandas, Matplotlib, Seaborn
- SciPy, Scikit-learn
- Jupyter widgets, ipywidgets
- R kernel (optional)

**Use Cases:**
- Data cleaning and EDA
- Statistical analysis
- Basic machine learning (small datasets)
- Visualization

#### Profile 2: GPU PyTorch Single

**Target Users**: ML course students, researchers training models

```python
profile = {
    'slug': 'gpu-pytorch-single',
    'display_name': 'GPU: PyTorch (1×)',
    'description': '1× GPU • 16 vCPU • 64 GiB',
    'image': 'quay.io/jupyter/pytorch-notebook:2025-11-06',
    'resources': {
        'requests': {'cpu': 8, 'memory': '32G', 'nvidia.com/gpu': 1},
        'limits': {'cpu': 16, 'memory': '64G', 'nvidia.com/gpu': 1}
    },
    'runtime_class': 'nvidia'
}
```

**Pre-installed Libraries:**
- PyTorch + torchvision + torchaudio
- CUDA 12.2 toolkit
- CuPy, Numba
- Transformers (Hugging Face)
- Lightning, Ignite
- TensorBoard

**GPU Details:**
- **1× NVIDIA A100 40GB** (exclusive access)
- CUDA Compute Capability: 8.0
- Tensor Cores enabled
- Mixed precision (FP16/BF16) support

**Typical Workflows:**
```python
# In notebook
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
# Output: NVIDIA A100-PCIE-40GB

# Train model
model = MyModel().cuda()
optimizer = torch.optim.Adam(model.parameters())

for epoch in range(100):
    outputs = model(inputs.cuda())
    loss = criterion(outputs, labels.cuda())
    loss.backward()
    optimizer.step()
```

#### Profile 3: GPU TensorFlow Single

**Target Users**: Deep learning courses, TensorFlow users

```python
profile = {
    'slug': 'gpu-tensorflow-single',
    'display_name': 'GPU: TensorFlow (1×)',
    'description': '1× GPU • 16 vCPU • 64 GiB',
    'image': 'quay.io/jupyter/tensorflow-notebook:2025-11-06',
    'resources': {
        'requests': {'cpu': 8, 'memory': '32G', 'nvidia.com/gpu': 1},
        'limits': {'cpu': 16, 'memory': '64G', 'nvidia.com/gpu': 1}
    },
    'runtime_class': 'nvidia'
}
```

**Pre-installed Libraries:**
- TensorFlow 2.x + Keras
- CUDA 12.2, cuDNN
- TensorFlow Datasets
- TensorFlow Addons
- Keras Tuner

**Auto GPU Configuration:**
```python
import tensorflow as tf

# TensorFlow auto-detects GPU
gpus = tf.config.list_physical_devices('GPU')
print(f"GPUs available: {len(gpus)}")
# Output: 1

# Mixed precision for A100
tf.keras.mixed_precision.set_global_policy('mixed_float16')
```

#### Profile 4-5: GPU Dual Profiles

**Target Users**: Advanced research, multi-GPU training

**Resources:**
- **2× NVIDIA A100 40GB** (exclusive node)
- 32 vCPU guarantee, 128 GB RAM
- Scheduled only to nodes with 2 available GPUs

**Use Cases:**
- Distributed training (DataParallel, DistributedDataParallel)
- Large batch sizes
- Model parallelism
- Ensemble training

**Multi-GPU Example:**
```python
# PyTorch Dual GPU
import torch
import torch.nn as nn

model = MyLargeModel()
if torch.cuda.device_count() > 1:
    print(f"Using {torch.cuda.device_count()} GPUs")
    model = nn.DataParallel(model)
model = model.cuda()

# Training automatically uses both GPUs
```

#### Profile 6-7: MIG Profiles

**Target Users**: Students with smaller workloads, development/testing

**MIG (Multi-Instance GPU):**
- Partitions single A100 into smaller, isolated GPU instances
- Provides hardware-level isolation
- Enables more concurrent users

**MIG 1g.5gb Slice:**
- 1/7th of A100 compute
- 5 GB GPU memory
- 6 vCPU, 24 GB RAM
- Resource key: `nvidia.com/mig-1g.5gb`

**MIG 2g.10gb Slice:**
- 2/7th of A100 compute
- 10 GB GPU memory
- 10 vCPU, 40 GB RAM
- Resource key: `nvidia.com/mig-2g.10gb`

**When to Use MIG:**
- Small model training (fits in 5-10 GB)
- Inference workloads
- Development/debugging
- Learning CUDA programming
- Cost-conscious research

**Scheduling:**
```python
# MIG profiles ONLY schedule to k3s-wk-gpu1
node_selector = {"nvidia.com/mig.capable": "true"}

# Full GPU profiles avoid MIG node
node_affinity = {
    "nodeAffinity": {
        "requiredDuringSchedulingIgnoredDuringExecution": {
            "nodeSelectorTerms": [{
                "matchExpressions": [{
                    "key": "nvidia.com/mig.capable",
                    "operator": "NotIn",
                    "values": ["true"]
                }]
            }]
        }
    }
}
```

---

## Authentication & Authorization Flow

### Complete OAuth2 Flow

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: User visits JupyterHub                              │
│  https://jupyterhub.cps.unileoben.ac.at                      │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 2: JupyterHub checks authentication                    │
│  No active session → Redirect to OAuth provider              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 3: Redirect to Authentik SSO                           │
│  https://auth.cps.unileoben.ac.at/application/o/authorize/   │
│  with parameters:                                             │
│  - client_id: vUhzKqEF0UxPtZNM8aRbA1ncaehhIAIA2x9r83FI       │
│  - redirect_uri: .../hub/oauth_callback                      │
│  - scope: openid profile email groups                        │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 4: User authenticates with Authentik                   │
│  - Username: alice@unileoben.ac.at                           │
│  - Password: ********                                        │
│  - MFA (if enabled)                                          │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 5: Authentik checks user permissions                   │
│  User "alice" is member of:                                  │
│  - cpsHPCAccess (GPU access group)                          │
│  - cps-students (general access)                            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 6: Authentik generates authorization code              │
│  Redirect back to JupyterHub with code                       │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 7: JupyterHub exchanges code for access token          │
│  POST https://auth.cps.unileoben.ac.at/.../token/            │
│  Returns: access_token, refresh_token                        │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 8: JupyterHub fetches user info                        │
│  GET https://auth.cps.unileoben.ac.at/.../userinfo/          │
│  Returns:                                                     │
│  {                                                            │
│    "preferred_username": "alice",                            │
│    "email": "alice@unileoben.ac.at",                        │
│    "groups": ["cpsHPCAccess", "cps-students"]               │
│  }                                                            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 9: JupyterHub creates/updates user record              │
│  Database stores:                                             │
│  - Username: alice                                            │
│  - Email: alice@unileoben.ac.at                              │
│  - Groups: [cpsHPCAccess, cps-students]                      │
│  - Admin: False (not in jupyter_admin group)                 │
│  - OAuth tokens (encrypted)                                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 10: Create session & redirect to Hub home              │
│  User sees: "Start My Server" button                         │
│  Profile selector shows GPU options (user in cpsHPCAccess)   │
└──────────────────────────────────────────────────────────────┘
```

### Group-Based Access Control

**Configuration:**
```python
# Admin access
c.GenericOAuthenticator.admin_groups = ["jupyter_admin"]

# All authenticated users allowed
c.GenericOAuthenticator.allow_all = True

# Custom access logic for GPU profiles
ALLOWED_GPU_GROUPS = {'cpsHPCAccess', 'jupyter_admin'}

def user_has_gpu_access(spawner):
    group_names = {getattr(g, "name", g) for g in spawner.user.groups}
    return bool(spawner.user.admin) or bool(group_names & ALLOWED_GPU_GROUPS)
```

**Access Matrix:**

| User Group | CPU Profile | GPU Profiles | MIG Profiles | Admin Panel |
|-----------|-------------|--------------|--------------|-------------|
| (none) | ❌ | ❌ | ❌ | ❌ |
| cps-students | ✅ | ❌ | ❌ | ❌ |
| cpsHPCAccess | ✅ | ✅ | ✅ | ❌ |
| jupyter_admin | ✅ | ✅ | ✅ | ✅ |

**Adding GPU Access for New Users:**

```bash
# In Authentik admin panel:
1. Navigate to Directory → Groups
2. Select "cpsHPCAccess" group
3. Click "Add existing user"
4. Search for student email
5. Click "Add"

# Next login, student automatically gets GPU access!
```

---

## Storage Architecture

### Persistent Volume Claim (PVC) Strategy

**Per-User PVC:**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: claim-alice
  namespace: jupyterhub
spec:
  accessModes:
    - ReadWriteMany  # NFS allows multiple pods
  storageClassName: nfs-client
  resources:
    requests:
      storage: 10Gi  # Default quota per user
```

**Directory Structure:**
```
NFS Server: 10.21.x.x:/export/jupyterhub
├── claim-alice/
│   ├── .jupyter/          (JupyterLab settings)
│   ├── .local/            (pip packages)
│   ├── notebooks/         (User's notebooks)
│   ├── data/              (User's datasets)
│   └── .bashrc            (Shell customization)
├── claim-bob/
│   ├── ...
└── claim-carol/
    └── ...
```

**Mounted in Pod:**
```
Pod: jupyter-alice
  Container: notebook
    Volume Mounts:
      - /home/jovyan → PVC claim-alice
      
User sees:
/home/jovyan/
├── notebooks/
│   ├── Week1_Python_Basics.ipynb
│   ├── Week2_NumPy_Tutorial.ipynb
│   └── FinalProject.ipynb
├── data/
│   ├── dataset.csv
│   └── images/
└── .jupyter/
```

### Shared Datasets

**Optional Shared Volume:**
```yaml
# Mounted read-only in all user pods
volumeMounts:
- name: shared-datasets
  mountPath: /datasets
  readOnly: true

volumes:
- name: shared-datasets
  nfs:
    server: 10.21.x.x
    path: /export/datasets
```

**Usage in Notebook:**
```python
import pandas as pd

# Read from shared datasets
df = pd.read_csv('/datasets/genomics/sample_data.csv')

# Write to user's home (persistent)
results.to_csv('/home/jovyan/data/my_results.csv')
```

### Scratch Storage (High-IOPS)

**Local NVMe for Temporary Data:**
```yaml
volumeMounts:
- name: scratch
  mountPath: /scratch

volumes:
- name: scratch
  emptyDir: {}  # Local disk on worker node
```

**Use Cases:**
- Temporary training checkpoints
- Data augmentation cache
- Build artifacts
- Large temporary arrays

**Important**: Data in `/scratch` is **ephemeral** (deleted when pod stops)!

---

## Customization & Extensions

### Custom Jupyter Images

**Building Custom Images:**
```dockerfile
# Custom image for Bioinformatics course
FROM quay.io/jupyter/pytorch-notebook:2025-11-06

# Install bioinformatics tools
USER root
RUN apt-get update && apt-get install -y \
    samtools \
    bcftools \
    bedtools

USER jovyan

# Install Python packages
RUN pip install --no-cache-dir \
    biopython \
    pysam \
    scikit-bio \
    pyvcf

# Install Jupyter extensions
RUN jupyter labextension install \
    @jupyter-widgets/jupyterlab-manager

# Set default working directory
WORKDIR /home/jovyan/notebooks
```

**Deploying Custom Image:**
```yaml
# In values.yaml, add custom profile:
singleuser:
  profileList:
    - display_name: "Bioinformatics (GPU)"
      slug: bio-gpu
      description: "Bioinformatics tools + GPU"
      kubespawner_override:
        image: registry.cps.unileoben.ac.at/bio-gpu:latest
        cpu_limit: 16
        mem_limit: "64G"
        extra_resource_limits:
          nvidia.com/gpu: "1"
```

### JupyterLab Extensions

**Pre-installed Extensions:**
- **Git**: Version control integration
- **GitHub**: Push/pull from GitHub repos
- **Variable Inspector**: View variables in memory
- **Table of Contents**: Notebook navigation
- **Code Formatter**: Black, autopep8 integration
- **Debugger**: Visual debugging for notebooks
- **Language Server Protocol (LSP)**: Autocomplete, linting

**Installing Additional Extensions:**
```python
# In custom image or via postStart hook
!jupyter labextension install @jupyterlab/latex
!jupyter labextension install @jupyterlab/git
```

### Lifecycle Hooks

**PostStart Hook (Install tmux):**
```yaml
# In values.yaml
singleuser:
  lifecycleHooks:
    postStart:
      exec:
        command:
          - "bash"
          - "-c"
          - |
            # Install tmux if not present
            if ! command -v tmux &> /dev/null; then
              conda install -y -c conda-forge tmux
            fi
            
            # Create default tmux config
            cat > ~/.tmux.conf <<EOF
            set -g mouse on
            set -g history-limit 10000
            EOF
```

**PreStop Hook (Save State):**
```yaml
preStop:
  exec:
    command:
      - "bash"
      - "-c"
      - |
        # Save running notebooks
        jupyter nbconvert --to notebook --execute --inplace ~/notebooks/*.ipynb
```

---

## Admin Operations

### Admin Dashboard

**Accessing Admin Panel:**
```
https://jupyterhub.cps.unileoben.ac.at/hub/admin
```

**Admin Capabilities:**
- View all active users and servers
- Stop/start any user's server
- Access user notebooks (for support)
- Edit server resources (emergency override)
- View server logs
- Broadcast announcements

**Admin User Creation:**
```bash
# Method 1: Via Authentik groups
# Add user to "jupyter_admin" group in Authentik

# Method 2: Via kubectl (emergency)
kubectl exec -it -n jupyterhub deployment/hub -- bash
jupyterhub token --user=alice --admin
```

### Monitoring Active Users

**Via kubectl:**
```bash
# List all user pods
kubectl get pods -n jupyterhub -l component=singleuser-server

# Get resource usage
kubectl top pods -n jupyterhub -l component=singleuser-server

# Example output:
NAME              CPU(cores)   MEMORY(bytes)   
jupyter-alice     2000m        45Gi            
jupyter-bob       100m         1.5Gi           
jupyter-carol     8000m        120Gi
```

**Via JupyterHub API:**
```python
import requests

# Get admin API token
token = "your-admin-token"

# List users
resp = requests.get(
    "https://jupyterhub.cps.unileoben.ac.at/hub/api/users",
    headers={"Authorization": f"token {token}"}
)

users = resp.json()
for user in users:
    print(f"{user['name']}: {len(user['servers'])} servers")
```

### Culling Idle Servers

**Auto-stop inactive notebooks:**
```yaml
# In values.yaml
cull:
  enabled: true
  timeout: 3600        # Stop after 1 hour idle
  every: 600           # Check every 10 minutes
  maxAge: 28800        # Force stop after 8 hours (even if active)
  removeNamedServers: true
```

**Behavior:**
- User's work is saved (persistent PVC)
- Pod is deleted to free resources
- User can restart server anytime
- All files remain intact

---

## Performance & Scalability

### Current Capacity

**Maximum Concurrent Users:**

| Profile Type | Users per Node | Total Capacity |
|--------------|----------------|----------------|
| CPU Default | ~50 | ~200 (across 4 workers) |
| GPU Single | 2 | 6 (3 nodes × 2 GPUs) |
| GPU Dual | 1 | 3 (3 nodes × 1 dual alloc) |
| MIG 1g.5gb | 14 | 14 (1 node × 14 slices) |
| MIG 2g.10gb | 6 | 6 (1 node × 6 slices) |

**Mixed Workload Example:**
```
Scenario: 150 students in class

├─ 100 students: CPU profile (fits easily)
├─ 30 students: MIG 1g.5gb (all 14 slots used, queue forms)
├─ 15 students: GPU single (uses all 6 GPUs, some queue)
└─ 5 students: GPU dual (uses 5 GPUs, 1 GPU remains free)

Queue depth: ~20 students waiting
Wait time: ~5-15 minutes (depends on how long others use GPUs)
```

### Scaling Strategies

**Horizontal Scaling (Add Nodes):**
```bash
# Provision new GPU worker via Terraform
tofu apply -var="worker_count=5"

# New capacity:
- 8 → 10 GPUs (2 more full GPUs)
- More CPU/RAM for default profile
```

**Vertical Scaling (Profile Limits):**
```yaml
# Reduce per-profile allocation to fit more users
gpu-pytorch-single:
  cpu_limit: 12      # Was 16
  mem_limit: "48G"   # Was 64G
  
# Result: Slightly less performant, but more concurrent users
```

**MIG Partitioning (More Slices):**
```bash
# Configure 2nd node for MIG
# Double MIG capacity: 14 → 28 concurrent small jobs
```

### Resource Efficiency

**GPU Utilization Tracking:**
```python
# Monitor GPU usage
kubectl exec -it -n gpu-operator deployment/dcgm-exporter -- \
  nvidia-smi dmon -s u -c 1

# Example output showing utilization
# gpu   pwr gtemp mtemp   sm   mem   enc   dec
#   0    75    45    55   95    82     0     0  ← High utilization, user training
#   1    25    30    35    5    12     0     0  ← Low utilization, user idle?
```

**Idle Detection & Notifications:**
```python
# Custom script to notify users of idle GPUs
if gpu_util < 10% for 30 minutes:
    send_email(user, "Your GPU is idle. Please stop server if not needed.")
```

---

## Security & Best Practices

### Network Policies

**Isolate User Pods:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: user-pod-isolation
  namespace: jupyterhub
spec:
  podSelector:
    matchLabels:
      component: singleuser-server
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          component: proxy  # Only proxy can reach user pods
  egress:
  - to:
    - namespaceSelector: {}  # Allow internet access for pip install, etc.
```

### Resource Quotas

**Prevent Resource Exhaustion:**
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: jupyterhub-quota
  namespace: jupyterhub
spec:
  hard:
    requests.cpu: "200"       # Max 200 CPU cores requested
    requests.memory: "1Ti"    # Max 1 TB RAM requested
    requests.nvidia.com/gpu: "8"  # Max 8 GPUs (all GPUs)
    persistentvolumeclaims: "200"  # Max 200 PVCs (users)
```

### Audit Logging

**Track User Activity:**
```python
# JupyterHub logs all spawns/stops
# Example log entries:
[I 2025-11-12 14:23:45] User alice requested server start (profile: gpu-pytorch-single)
[I 2025-11-12 14:24:12] Spawned jupyter-alice on k3s-wk-gpu3
[I 2025-11-12 16:45:30] User alice's server stopped (8h 21m runtime)
```

**Export to SIEM:**
```yaml
# Forward logs to central logging
logging:
  enabled: true
  outputs:
    - type: elasticsearch
      host: logs.cps.unileoben.ac.at
      index: jupyterhub-logs
```

---

## Troubleshooting Common Issues

### Issue 1: "Server Failed to Start"

**Symptom**: User clicks "Start My Server", gets error

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -n jupyterhub | grep jupyter-<username>

# View pod events
kubectl describe pod jupyter-<username> -n jupyterhub

# Common causes:
# - Image pull failure (registry down, invalid image)
# - Insufficient resources (no GPU available)
# - PVC mount failure (NFS down)
# - Node selector mismatch (MIG vs. full GPU)
```

**Solutions:**
```bash
# Image pull issue: Check image exists
docker pull quay.io/jupyter/pytorch-notebook:2025-11-06

# Resource issue: Check node capacity
kubectl describe nodes | grep -A5 "Allocated resources"

# NFS issue: Check NFS server
showmount -e 10.21.x.x

# Force restart: Delete pod
kubectl delete pod jupyter-<username> -n jupyterhub
```

### Issue 2: GPU Not Detected in Notebook

**Symptom**: `torch.cuda.is_available()` returns `False`

**Diagnosis:**
```bash
# Check GPU allocation to pod
kubectl describe pod jupyter-<username> -n jupyterhub | grep -A5 "Limits:"

# Check runtime class
kubectl get pod jupyter-<username> -n jupyterhub -o yaml | grep runtimeClassName

# Check environment variables
kubectl exec jupyter-<username> -n jupyterhub -- env | grep NVIDIA
```

**Solutions:**
```bash
# Verify GPU Operator running
kubectl get pods -n gpu-operator

# Check node has GPUs
kubectl describe node k3s-wk-gpu3 | grep nvidia.com/gpu

# Verify runtime class exists
kubectl get runtimeclass nvidia

# Restart pod with correct profile
# (delete pod via admin panel, user restarts with GPU profile)
```

### Issue 3: "Out of Memory" Errors

**Symptom**: Notebook kernel crashes, OOMKilled in logs

**Diagnosis:**
```bash
# Check pod resource limits
kubectl top pod jupyter-<username> -n jupyterhub

# Check pod events for OOMKilled
kubectl get events -n jupyterhub --field-selector involvedObject.name=jupyter-<username>
```

**Solutions:**
1. **User-side**: Optimize code (release memory, use generators)
2. **Admin-side**: Increase profile memory limit
3. **Temporary**: Override resources for specific user
```python
# In JupyterHub admin panel
c.Spawner.mem_limit = "128G"  # Temporary override
```

### Issue 4: Slow Notebook Performance

**Symptom**: Cells take long to execute, UI laggy

**Diagnosis:**
```bash
# Check CPU/memory usage
kubectl top pod jupyter-<username> -n jupyterhub

# Check GPU utilization
kubectl exec jupyter-<username> -n jupyterhub -- nvidia-smi

# Check I/O wait
kubectl exec jupyter-<username> -n jupyterhub -- iostat -x 1 5
```

**Solutions:**
- High CPU: Upgrade to larger profile
- Low GPU util: Code not using GPU properly
- High I/O wait: Use scratch storage (`/scratch`)
- Network latency: Check if downloading large datasets repeatedly

---

## Cost & Resource Management

### Chargeback Model (Example)

**GPU Hour Pricing:**
```
A100 Full GPU: 8 compute units/hour
MIG 1g.5gb:   1 compute unit/hour
MIG 2g.10gb:  2 compute units/hour
CPU profile:  0.1 compute units/hour
```

**Monthly Usage Report:**
```
User: alice@unileoben.ac.at
Month: November 2025

Profile Usage:
- CPU Default:    25 hours  →   2.5 CU
- GPU Single:     40 hours  → 320.0 CU
- GPU Dual:       10 hours  → 160.0 CU
Total:            75 hours  → 482.5 CU

Cost: 482.5 CU × €0.50/CU = €241.25
```

### Budgets & Alerts

**Implementation:**
```python
# Custom spawner hook to check budget
async def pre_spawn_hook(spawner):
    user = spawner.user.name
    
    # Check remaining budget
    budget = get_user_budget(user)
    
    if budget.remaining <= 0:
        raise Exception(f"Budget exceeded! Contact admin to increase quota.")
    
    # Warn if low
    if budget.remaining < 10:  # 10 CU
        spawner.log.warning(f"User {user} has only {budget.remaining} CU remaining")

c.Spawner.pre_spawn_hook = pre_spawn_hook
```

---

## Future Roadmap

### Phase 1: Enhanced Features (3 months)
- [ ] Integration with course management (Moodle/Canvas)
- [ ] Automated assignment distribution via nbgrader
- [ ] Real-time collaboration (multiple users in same notebook)
- [ ] JupyterLab 4.x upgrade

### Phase 2: Advanced Capabilities (6 months)
- [ ] Dask/Ray integration for distributed computing
- [ ] MLflow integration for experiment tracking
- [ ] GPU time-slicing for over-subscription
- [ ] Auto-scaling based on demand

### Phase 3: Platform Expansion (12 months)
- [ ] R Studio integration (Posit Workbench)
- [ ] VS Code server option
- [ ] Dedicated compute nodes for long-running jobs
- [ ] Integration with HPC batch scheduler (Slurm)

---

## Conclusion

JupyterHub on the CPS GPU Cluster provides a **production-grade, scalable platform** for AI/ML education and research at Montanuniversität Leoben. 

**Key Achievements:**
- ✅ Zero-setup access to GPU resources
- ✅ Institutional SSO integration (Authentik)
- ✅ Flexible profile system (CPU → MIG → Full GPU)
- ✅ Persistent user storage
- ✅ Ready for 200+ concurrent users
- ✅ Following best practices from top universities

**Impact:**
- **Education**: Enable GPU-accelerated ML courses without local hardware
- **Research**: Provide on-demand compute for research projects
- **Collaboration**: Shared platform for interdisciplinary work
- **Innovation**: Lower barrier to entry for AI/ML experimentation

**Join the Community:**
- GitHub: https://github.com/jupyterhub/jupyterhub
- Forum: https://discourse.jupyter.org
- Slack: Jupyter community workspace
- Docs: https://jupyterhub.readthedocs.io

---

**Questions? Contact:**
- Platform Admin: admin@cps.unileoben.ac.at
- Documentation: https://docs.cps.unileoben.ac.at/jupyterhub
- Support: Submit ticket at https://support.cps.unileoben.ac.at
