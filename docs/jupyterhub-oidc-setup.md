# JupyterHub OIDC Authentication Setup

This document describes the OIDC authentication configuration for the CPS GPU cluster JupyterHub instance.

## Overview

JupyterHub has been configured to use OIDC authentication with the existing CPS Authentik instance, replacing the previous dummy authenticator.

## Configuration Details

### Authentik Provider
- **Provider URL**: `https://auth.cps.unileoben.ac.at`
- **Application Name**: CPS-CIT-JupyterHub
- **Client Type**: Confidential
- **Client ID**: `vUhzKqEF0UxPtZNM8aRbA1ncaehhIAIA2x9r83FI`

### JupyterHub Configuration
- **Authenticator**: `oauthenticator.generic.GenericOAuthenticator`
- **Callback URL**: `https://jupyterhub.cps.unileoben.ac.at/hub/oauth_callback`
- **Scopes**: openid, profile, email
- **Group Management**: Enabled with auth_state_groups_key

### Access Control
- **Allowed Groups**: `cps-users` - Regular users who can access JupyterHub
- **Admin Groups**: `cps-admins` - Users with administrative privileges
- **Group Claims**: Retrieved from `groups` field in OIDC token

## Network Configuration

### Ingress
JupyterHub is accessible externally via:
- **URL**: https://jupyterhub.cps.unileoben.ac.at
- **TLS**: Let's Encrypt certificate (jupyterhub-tls secret)
- **Ingress Controller**: Traefik

## User Experience

1. Users navigate to https://jupyterhub.cps.unileoben.ac.at
2. They're redirected to Authentik for authentication
3. After successful login, they're redirected back to JupyterHub
4. Profile selection based on resource requirements:
   - **CPU Only**: 2 cores, 4GB RAM
   - **Single GPU**: 8 cores, 32GB RAM, 1x GPU
   - **Dual GPU**: 16 cores, 64GB RAM, 2x GPU  
   - **Research**: 32 cores, 128GB RAM, 4x GPU

## Security Features

- **TLS Encryption**: All traffic encrypted with Let's Encrypt certificates
- **Group-based Access**: Only members of `cps-users` can access the platform
- **Admin Separation**: Admin privileges require membership in `cps-admins`
- **OAuth 2.0 Flow**: Secure token-based authentication
- **Session Management**: Automatic session handling via JupyterHub

## Troubleshooting

### Common Issues

1. **Access Denied**: User not in `cps-users` group
   - Solution: Add user to the appropriate group in Authentik

2. **Certificate Errors**: TLS certificate not ready
   - Check: `kubectl get certificate -n jupyterhub`
   - Wait for cert-manager to issue certificate

3. **Redirect Loops**: Callback URL mismatch
   - Verify callback URL in Authentik matches JupyterHub configuration

### Useful Commands

```bash
# Check JupyterHub pod logs
kubectl logs -n jupyterhub deployment/hub

# Check ingress status
kubectl get ingress -n jupyterhub

# Check certificate status
kubectl get certificate -n jupyterhub

# Check authentication configuration
kubectl get configmap -n jupyterhub hub-config -o yaml
```

## Configuration Files

The OIDC configuration is managed via Fleet GitOps in:
- `cluster-maintenance/clusters/cit-cps-gpu/jupyterhub/values.yaml`

Key configuration sections:
- `hub.config.GenericOAuthenticator`: OIDC settings
- `ingress`: External access configuration
- `singleuser.profileList`: GPU resource profiles

## Testing

Use the provided test notebook to verify functionality:
- `docs/gpu-cluster-test.ipynb`

This notebook tests:
- Authentication status
- GPU detection and drivers
- PyTorch GPU integration
- Storage persistence
- Resource availability
