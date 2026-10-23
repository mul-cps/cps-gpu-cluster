# Student workspace opening — 23 October 2026

Armin used the deployed CIT Compute addon with his ordinary student browser
session. While the course-owned shared CPU workspace was stopped, discovery
returned its membership context, fixed ceiling and stopped status, without an
unusable opening link. The current UI directs students to the course console.
Starting and stopping remain maintainer-controlled operations.

After a normal maintainer lifecycle start (19.843 seconds), discovery returned
running status and one Open workspace link. Armin clicked it, completed normal
JupyterHub OAuth consent, and reached the neutral named server's JupyterLab.
The Hub still identified him as Armin, non-admin. No student lifecycle,
administrative or broad server-access permissions were added.

The first running-state harness timed out on the normal OAuth consent page;
adding the normal Authorize click to the harness passed. This was not a product
permission failure. This receipt qualifies opening an already-running workspace,
not student-initiated server starts or full production readiness.
