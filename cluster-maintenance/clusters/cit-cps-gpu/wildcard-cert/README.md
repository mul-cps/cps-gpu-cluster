# Wildcard Certificate Configuration

This directory contains the cert-manager ClusterIssuer configuration for `*.cps.unileoben.ac.at`.

**IMPORTANT:** The TLS certificate secret is NOT stored in Git for security reasons. You must create it manually.

## Setup Instructions (REQUIRED)

### Step 1: Create the TLS Secret Manually

You must have your wildcard certificate files for `*.cps.unileoben.ac.at`:
- `fullchain.pem` (certificate + intermediate chain)
- `privkey.pem` (private key)

**Create the secret:**

```bash
kubectl create secret tls wildcard-cps-cert \
  --cert=fullchain.pem \
  --key=privkey.pem \
  -n cert-manager
```

### Step 2: Verify Secret Creation

```bash
kubectl get secret wildcard-cps-cert -n cert-manager
```

### Step 3: Deploy the ClusterIssuer

The ClusterIssuer will be deployed automatically by Fleet once you push the changes.

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/wildcard-cert/
git commit -m "Add wildcard cert ClusterIssuer"
git push
```

Fleet will deploy the ClusterIssuer which references the manually-created secret.

If you want automated certificate management with Let's Encrypt:

1. **Update `clusterissuer.yaml` to use ACME:**

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: wildcard-cert
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@unileoben.ac.at
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
    - dns01:
        # Configure your DNS provider here
        # Example for Cloudflare:
        cloudflare:
          email: your-email@unileoben.ac.at
          apiTokenSecretRef:
            name: cloudflare-api-token
            key: api-token
      selector:
        dnsZones:
        - "cps.unileoben.ac.at"
```

2. **Create DNS provider secret:**

```bash
kubectl create secret generic cloudflare-api-token \
  --from-literal=api-token=<your-api-token> \
  -n cert-manager
```

### Option 3: Manual Deployment (Without Git)

If you prefer not to commit the certificate to Git:

```bash
# Create the secret directly
kubectl create secret tls wildcard-cps-cert \
  --cert=fullchain.pem \
  --key=privkey.pem \
  -n cert-manager

# Remove wildcard-secret.yaml from kustomization
# Edit kustomization.yaml and remove the wildcard-secret.yaml line
```

## Usage

Once the ClusterIssuer is deployed, ingresses can reference it:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    cert-manager.io/cluster-issuer: wildcard-cert
spec:
  ingressClassName: nginx
  rules:
  - host: myapp.cps.unileoben.ac.at
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-app
            port:
              number: 80
  tls:
  - hosts:
    - myapp.cps.unileoben.ac.at
    secretName: myapp-tls  # cert-manager will create this
```

## Certificate Renewal

- **Imported certificate**: Manually renew and update the Secret
- **Let's Encrypt**: Automatic renewal by cert-manager

## Verification

```bash
# Check ClusterIssuer status
kubectl get clusterissuer wildcard-cert

# Check certificate secret
kubectl get secret wildcard-cps-cert -n cert-manager

# Test certificate in an ingress
kubectl describe certificate <cert-name> -n <namespace>
```

## Security Note

**Do NOT commit real certificates/keys to Git in production!**

For production deployments:
- Use sealed-secrets or external secrets management
- Or deploy certificates manually outside of GitOps
- Or use Let's Encrypt with DNS-01 automation
