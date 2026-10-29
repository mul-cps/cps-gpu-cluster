"""Delete one qualification Pod after verifying its exact Kubernetes UID.

This helper deliberately manages only the Pod API object. It never removes
controller state, retirement journals, host files, or evidence artifacts.
"""

import argparse
from contextlib import contextmanager
import json
import re
import selectors
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen


_DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
_DNS_SUBDOMAIN = re.compile(r"^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$")


def _validate_identity(namespace: str, name: str, expected_uid: str) -> None:
    if len(namespace) > 63 or not _DNS_LABEL.fullmatch(namespace):
        raise ValueError("invalid Kubernetes namespace")
    if len(name) > 253 or not _DNS_SUBDOMAIN.fullmatch(name):
        raise ValueError("invalid Kubernetes Pod name")
    try:
        parsed_uid = uuid.UUID(expected_uid)
    except (ValueError, AttributeError) as exc:
        raise ValueError("expected UID must be a canonical UUID") from exc
    if str(parsed_uid) != expected_uid:
        raise ValueError("expected UID must be a canonical UUID")


@contextmanager
def api_proxy():
    """Expose the configured API to this process on a temporary loopback port."""
    process = subprocess.Popen(
        ["kubectl", "proxy", "--address=127.0.0.1", "--port=0", "--append-server-path"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    try:
        if process.stdout is None:
            raise RuntimeError("kubectl proxy did not provide startup output")
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 10
            output = []
            proxy_url = None
            while time.monotonic() < deadline:
                if not selector.select(timeout=max(0, deadline - time.monotonic())):
                    break
                line = process.stdout.readline().strip()
                output.append(line)
                match = re.search(r"127\.0\.0\.1:(\d+)$", line)
                if match:
                    proxy_url = f"http://127.0.0.1:{match.group(1)}"
                    break
                if process.poll() is not None:
                    break
        if not proxy_url or process.poll() is not None:
            raise RuntimeError(f"kubectl API proxy failed to start: {'; '.join(output)}")
        yield proxy_url
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def cleanup_pod(namespace: str, name: str, expected_uid: str, *,
                run: Callable = subprocess.run) -> str:
    """Delete only the Pod whose live UID matches the supplied reviewed UID."""
    _validate_identity(namespace, name, expected_uid)
    get_result = run(
        ["kubectl", "get", "pod", name, "--namespace", namespace, "-o", "json"],
        check=True, capture_output=True, text=True, timeout=30,
    )
    try:
        actual_uid = json.loads(get_result.stdout)["metadata"]["uid"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("kubectl returned no readable Pod UID") from exc
    if actual_uid != expected_uid:
        raise RuntimeError("Pod UID changed; refusing to delete a replacement Pod")

    path = (f"/api/v1/namespaces/{quote(namespace, safe='')}/pods/"
            f"{quote(name, safe='')}")
    body = json.dumps({
        "apiVersion": "v1", "kind": "DeleteOptions",
        "preconditions": {"uid": expected_uid},
    }).encode()
    with api_proxy() as api_url:
        request = Request(f"{api_url}{path}", data=body, method="DELETE", headers={
            "Content-Type": "application/json",
        })
        with urlopen(request, timeout=30) as response:
            return response.read().decode()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--pod", required=True)
    parser.add_argument("--expected-uid", required=True,
                        help="UID captured from the reviewed qualification Pod")
    args = parser.parse_args(argv)
    try:
        output = cleanup_pod(args.namespace, args.pod, args.expected_uid)
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        print(f"qualification Pod cleanup refused or failed: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
