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

## Live reality differs from the steps above (documented 2026-07-23)

The actual source object in this cluster is `dshl-wildcard` in namespace
`ingress-nginx` (not `cert-manager`), and additional namespaces get it
via **Reflector auto-reflection** (`reflector.v1.k8s.emberstack.com/
reflection-allowed-namespaces` / `reflection-auto-namespaces` annotations
on the source), not the manual per-namespace copy loop in step 3. This
predates this repo's `system/utils/reflector` bundle and was set up by
`cit-teaching-platform`'s tooling (its namespaces `cit-auth`/`cit-jhub`
were the only ones originally on the allow-list).

`dex` was added to both annotation lists on 2026-07-23 (Dex IdP broker
work, see `docs/dex-idp-broker.md`) so Dex's ingress gets the real
wildcard cert instead of ingress-nginx's fake default cert. **A manual
`kubectl apply`'d copy of the source Secret (including its own Reflector
annotations) will NOT be adopted by Reflector** — it doesn't recognize an
object as its own reflection target unless Reflector itself created it
(with its own `reflector.v1.k8s.emberstack.com/reflects`/`reflected-at`
tracking annotations). If a target namespace's copy needs to be added or
fixed, add the namespace to the source's allow-list annotations and let
Reflector create the target from scratch — do not `kubectl apply` a copy
by hand first.

**Verification pitfall**: `curl -k` will succeed regardless of whether
the real cert or ingress-nginx's fake default cert is being served —
always verify with a plain `curl` (no `-k`) or `openssl s_client`,
which will fail loudly on a hostname mismatch if the real cert isn't
actually present in the target namespace.
