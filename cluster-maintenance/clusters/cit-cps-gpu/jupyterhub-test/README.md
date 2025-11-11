# JupyterHub Test Instance

This is a testing instance of JupyterHub for trying out configuration changes without affecting production.

## Setup Steps

### 1. Create Authentik OAuth Application

In Authentik, create a new OAuth2/OpenID Provider application:

1. Go to **Applications** → **Providers** → **Create**
2. **Name**: `JupyterHub Test`
3. **Type**: `OAuth2/OpenID Provider`
4. **Client Type**: `Confidential`
5. **Redirect URIs**: `https://jupyterhub-test.cps.unileoben.ac.at/hub/oauth_callback`
6. **Scopes**: `openid`, `profile`, `email`, `groups`

Save the **Client ID** and **Client Secret**.

### 2. Update values.yaml

Edit `values.yaml` and replace:
- `TEST_CLIENT_ID_FROM_AUTHENTIK` with the Client ID
- `TEST_CLIENT_SECRET_FROM_AUTHENTIK` with the Client Secret

### 3. Generate Proxy Secret Token

```bash
openssl rand -hex 32
```

Replace `GENERATE_NEW_TOKEN_WITH_openssl_rand_-hex_32` in `values.yaml` with the generated token.

### 4. Configure DNS

Add DNS record for `jupyterhub-test.cps.unileoben.ac.at` pointing to your cluster's ingress IP.

### 5. Deploy

Commit and push changes to Git. Fleet will automatically deploy:

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/jupyterhub-test/
git commit -m "Add JupyterHub test instance"
git push
```

### 6. Monitor Deployment

```bash
# Watch Fleet bundle status
kubectl -n fleet-local get bundles -w

# Check test instance pods
kubectl -n jupyterhub-test get pods

# Check logs
kubectl -n jupyterhub-test logs -l component=hub
```

## Differences from Production

- **Namespace**: `jupyterhub-test` (isolated from production)
- **Hostname**: `jupyterhub-test.cps.unileoben.ac.at`
- **OAuth App**: Separate Authentik application
- **Storage**: Separate PVCs (isolated user data)
- **PostgreSQL**: Separate database instance

## Testing Workflow

1. Make configuration changes in `jupyterhub-test/values.yaml`
2. Commit and push
3. Fleet deploys to test namespace
4. Test the changes at https://jupyterhub-test.cps.unileoben.ac.at
5. Once validated, copy changes to production `jupyterhub/values.yaml`

## Cleanup

To remove the test instance:

```bash
# Remove from Fleet
kubectl -n fleet-local delete bundle jupyterhub-test

# Or delete from Git (Fleet will clean up automatically)
git rm -r cluster-maintenance/clusters/cit-cps-gpu/jupyterhub-test/
git commit -m "Remove JupyterHub test instance"
git push
```
