# CIT Hub publisher pin

The live CIT Hub replacement verified this publisher with the current
image and Deployment identity. The component includes the immutable
publisher ConfigMap and changes the Hub's named publisher mount after
checking the image, volume position, and previous reference.

Include this component when rendering the current CIT Helm release as a
GitOps base. The chart release still contains the earlier reference.
The patch targets the Helm render before Kubernetes applies it. A new
Hub image or a changed volume list requires a fresh publisher render
and provenance verification.

The publisher document contains process and acknowledgment references.
The Hub continues to use its existing Secrets for credentials.
