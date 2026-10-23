# Native reservation cleanup retry

The deployed binder performed one full reservation reconciliation at startup.
Its Pod event callback could run before native cleanup proof became available.
A safe deletion hold returned without scheduling another check; after the last
Pod event, the reservation could remain indefinitely and block the next GPU run.

The native-only manager runnable reconciles reservations every five seconds on
the elected binder. It retries holds and errors until the existing Source API
authorizes exact UID/resource-version deletion. Neither TTL nor Pod absence is
new authority. Startup behavior and non-native configurations remain unchanged.
The runnable stops on manager cancellation. No permissions, protocol fields,
driver settings or GPU isolation rules are changed.

`full-native-binder.patch` applies to the exact upstream revision recorded in
`verification.json`; `cleanup-retry.patch` isolates the change from the preserved
deployed native overlay. Dependencies are unchanged. Build with CGO disabled,
`-trimpath -buildvcs=false -ldflags=-buildid=`; two builds matched byte-for-byte.
The container inherits the previous deployed image and replaces only its binder
executable. CPU tests passed; live automatic cleanup qualification is pending.
