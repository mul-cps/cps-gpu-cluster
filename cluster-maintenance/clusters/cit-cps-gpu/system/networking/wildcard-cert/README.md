Manual integration of the pre-issued `*.dshl.unileoben.ac.at` wildcard certificate.

## Steps
1. Build a fullchain (leaf + intermediate):
   ```bash
   curl -sL http://crt.harica.gr/HARICA-GEANT-TLS-R1.cer \
     | openssl x509 -inform der -out /tmp/harica-geant-r1.pem
   { cat /path/to/Data_Science_Hub_Leoben-Wildcard-Certificate.pem; echo; cat /tmp/harica-geant-r1.pem; } > /tmp/dshl-fullchain.pem
   ```
2. Create the TLS secret in `cert-manager` (no cert-manager issuance involved):
   ```bash
   kubectl -n cert-manager create secret tls dshl-wildcard \
     --cert=/tmp/dshl-fullchain.pem \
     --key=/path/to/DSHL-2048-Private-Key.pem
   ```
3. Copy the secret to namespaces that need it (example):
   ```bash
   for ns in jupyterhub jupyterhub-test cattle-system; do
     kubectl get secret dshl-wildcard -n cert-manager -o json \
     | jq 'del(.metadata | .namespace,.creationTimestamp,.resourceVersion,.uid,.selfLink,.managedFields,.annotations,.ownerReferences)' \
     | kubectl apply -n "$ns" -f -
   done
   ```
4. Verify:
   ```bash
   kubectl -n cert-manager get secret dshl-wildcard
   kubectl -n jupyterhub get secret dshl-wildcard
   ```
