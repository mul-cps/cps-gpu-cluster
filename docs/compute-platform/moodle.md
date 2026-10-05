# Moodle integration

**Status: planned / not deployed**

Local course CRUD is the active v1 provider. The admin application has async
`CourseProvider` reads for Course, CourseTerm, CourseMembership, CourseGroup and
CourseGrouping. Each record retains its internal ID plus `source` and optional
`external_id`. Explicit local imports preserve references; changing a provider
setting or matching names never transfers source ownership automatically.

```yaml
courseProviders:
  local:
    enabled: true
  moodle:
    enabled: false
    baseUrl: null
    authSecretRef: null
    syncInterval: 10m
    readOnly: true
```

The disabled Moodle scaffold does not initialize a provider, look up secrets,
perform requests or schedule work. Enabling the unfinished provider fails startup
with a clear configuration error. The console shows **Integrations → Moodle →
Planned / Not configured** with documentation. No Moodle credentials, dependencies,
CRDs, synchronization workloads, LTI login or setup wizard are installed.

| Future data | Authority |
| --- | --- |
| Official enrolment | MUonline/CAMPUSonline |
| Teaching roster, roles and assignment groups/groupings | Moodle |
| Compute entitlements, scheduling and resource limits | Shared compute policy |
| Research projects and workspace lifecycle | Jupyter admin consoles |

The university enrolment bridge is an **ICT dependency**. The planned path is
read-only [Moodle External Services](https://moodledev.io/docs/5.1/apis/subsystems/external)
into the course-provider boundary, followed later by optional
[LTI 1.3 workspace links](https://docs.moodle.org/501/en/mod/lti).
Authentik remains the login authority through the existing authentication paths.
Grade return and direct CAMPUSonline integration are later work.

A source handover requires explicit person/course mapping and a reviewed migration.
Backend capabilities must protect externally managed fields, including direct API
requests. A fake provider is tested against the same source-neutral reconciler;
that test does not establish a working Moodle integration.
