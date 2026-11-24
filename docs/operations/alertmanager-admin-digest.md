# CPS GPU Alertmanager email digest

Alertmanager groups cluster warnings and critical alerts into one email. It collects the first group for two minutes and sends updates at most every 30 minutes. An unchanged firing group repeats after 24 hours. The email counts firing and resolved alerts, previews the affected resources, and links to the full list. Watchdog and InfoInhibitor stay suppressed. The explicit Loki route keeps the existing internal notification history.

The email links through Rancher to the existing authenticated Kubernetes Service proxy. Use the Rancher Monitoring sign-in link if there is no current session. Alertmanager keeps its internal service address for cluster traffic.

## Configuration references

- The Alertmanager Helm release is `cattle-monitoring-system/rancher-monitoring`.
- The private receiver is `cattle-monitoring-system/cluster-admin-email`.
- The SMTP password reference is `cattle-monitoring-system/alertmanager-admin-smtp`, key `password`. Rotate it with the existing relay credential.
- The existing internal route is `cattle-monitoring-system/cluster-alert-delivery`.

Keep receiver addresses and credential material in protected configuration. The repository Helm values select the private email route by its exact label in the monitoring namespace.

## Verification on 24 November 2026

Alertmanager sent one controlled firing email and one resolved email with zero SMTP failures. The administrator confirmed both arrived. Route tests verified the email and Loki receivers for warnings and critical alerts and confirmed Watchdog suppression. The installed Alertmanager template renderer validated subject, plain text, and escaped HTML against a grouped sample. The authenticated Rancher proxy served the Alertmanager page, its JavaScript, and its status API. The Alertmanager Pod kept its original UID and restart count.
