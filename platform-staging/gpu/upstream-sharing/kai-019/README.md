# KAI 0.19.0 staging render

The comparison uses the active KAI 0.18.1 release values and changes the KAI
version while retaining NvFractions and the separately installed Fractioning
release. The upstream candidate bundles Fractioning 0.1.9, as verified in its
Chart.lock. The reference render includes its CRD upgrade Job. Enabling the
bundled release would change ownership of live Fractioning resources.

Download the KAI 0.18.1 and 0.19.0 and Fractioning 0.1.9 OCI packages into a
directory, then pass that directory and a new output directory to
`render-comparison.sh`. It needs Helm, kubectl, jq, skopeo and Python with PyYAML.
It captures the installed manifest and hooks, renders the rollback chart and
candidate, records live admission objects and queues, and compares CRD stored
versions and default queues. The image lock verifies registry digests for the
currently enabled KAI components, KAI hooks and Fractioning images.

The comparison is read-only. The KAI operator manages admission webhooks,
so the candidate chart template alone cannot establish webhook behavior.
The remaining staging checks include the operator-reconciled webhooks and
images, placement, preemption, borrowing, device UUID and NRI failure behavior.
