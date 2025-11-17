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

## Usage

Reference the imported TLS secret directly in your Ingress resources:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
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
    secretName: wildcard-cps-cert  # Use the imported secret
```

## Certificate Renewal

- **Imported certificate**: Manually renew and update the Secret
- **Let's Encrypt**: Use cert-manager with ACME for automatic renewal

## Verification

```bash
# Check certificate secret
kubectl get secret wildcard-cps-cert -n cert-manager
```

## Security Note

**Do NOT commit real certificates/keys to Git in production!**

For production deployments:
- Use sealed-secrets or external secrets management
- Or deploy certificates manually outside of GitOps
- Or use Let's Encrypt with DNS-01 automation
