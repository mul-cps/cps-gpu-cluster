"""Read public Hub status or verify a named notebook owned by a probe account."""
import argparse
import json
import signal
from pathlib import Path
import sys
import time
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

import httpx
import websocket


HUBS = {
    "cit": "https://jhub.dshl.unileoben.ac.at",
    "cps": "https://jupyterhub.dshl.unileoben.ac.at",
}
PROFILE_CASES = {
    "cit-shared": ("cit", [
        ("2g", {"profile": "gpu-mujoco-xpra", "gpu_memory_gib": "2", "session_duration_hours": "2"}, 1),
        ("5g", {"profile": "gpu-mujoco-xpra", "gpu_memory_gib": "5", "session_duration_hours": "2"}, 1),
    ]),
    "cit-research": ("cit", [
        (name.removeprefix("gpu-"), {"profile": name}, capacity)
        for name, capacity in (("gpu-large-pytorch", 1), ("gpu-large-tf", 1),
                               ("gpu-xlarge-pytorch", 2), ("gpu-xlarge-tf", 2))
    ]),
    "cps-poweruser": ("cps", [
        (name.removeprefix("gpu-"), {"profile": name}, capacity)
        for name, capacity in (("gpu-pytorch-single", 1), ("gpu-tensorflow-single", 1),
                               ("gpu-pytorch-dual", 2), ("gpu-tensorflow-dual", 2))
    ]),
}
PROBE_OWNERS = {
    "cit-shared": "cit-spawn-health-student",
    "cit-research": "cit-spawn-health-research",
    "cps-poweruser": "cps-spawn-health-poweruser",
}
CREDENTIALS = Path("/run/hub-probe")
GIB = 1 << 30
NOTEBOOK_TEST = Path(__file__).with_name("hub-notebook-resources.py")


def resource_contract(check, case, gpus):
    if check == "cit-shared":
        return {"cpu": 8, "memory": 24_000_000_000, "home": 24 * GIB, "gpus": gpus,
                "vram_mib": int(case[0]) * 1024, "framework": "pytorch"}
    framework = "tensorflow" if "tensorflow" in case or case.endswith("-tf") else "pytorch"
    if check == "cit-research":
        return {"cpu": 24 * gpus, "memory": (96 if gpus == 1 else 128) * 1_000_000_000,
                "home": 100_000_000_000, "gpus": gpus, "peer": gpus == 2, "framework": framework}
    return {"cpu": 16 * gpus, "memory": 64 * gpus * GIB, "home": 10 * GIB,
            "gpus": gpus, "framework": framework}


class ProbeFailure(RuntimeError):
    """A failed named check with no credentials or response bodies."""


class ProbeUnavailable(ProbeFailure):
    """The request can be retried without changing the probe identity."""


def request(client, method, path, statuses, stage, **options):
    try:
        result = client.request(method, path, **options)
    except httpx.TransportError:
        raise ProbeUnavailable(stage) from None
    except httpx.HTTPError:
        raise ProbeFailure(stage) from None
    if result.status_code not in statuses:
        failure = ProbeUnavailable if result.status_code in {429, 500, 502, 503, 504} else ProbeFailure
        raise failure(f"{stage} HTTP {result.status_code}")
    return result


def require_dex_redirect(response):
    location = urlsplit(response.headers.get("location", ""))
    if location.scheme != "https" or location.netloc != "dex.dshl.unileoben.ac.at":
        raise ProbeFailure("federated redirect")


def check_route(client):
    request(client, "GET", "/hub/health", {200}, "public health")
    request(client, "GET", "/hub/login", {200, 302, 303}, "login page")
    response = request(client, "GET", "/hub/oauth_login", {302, 303}, "OAuth redirect")
    require_dex_redirect(response)


def get_server(client, user_api, server_name):
    result = request(client, "GET", user_api, {200}, "read server").json()
    return result["servers"].get(server_name, {})


def wait_ready(client, user_api, server_name, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = get_server(client, user_api, server_name)
        if state.get("ready"):
            return state
        if not state.get("pending"):
            raise ProbeFailure("spawn exited before Ready")
        time.sleep(2)
    raise ProbeFailure("spawn Ready deadline")


def stop(client, user_api, named_api, server_name):
    deadline = time.monotonic() + 75
    send_stop = True
    while time.monotonic() < deadline:
        try:
            if send_stop:
                request(client, "DELETE", named_api, {202, 204, 404}, "stop", json={"remove": False})
                send_stop = False
            state = get_server(client, user_api, server_name)
        except ProbeUnavailable:
            time.sleep(2)
            continue
        pending = state.get("pending")
        if not state.get("ready") and not pending:
            return
        send_stop = pending != "stop"
        time.sleep(2)
    raise ProbeFailure("stop deadline")


def check_resources(client, prefix, expected):
    response = request(client, "POST", prefix + "api/kernels", {201}, "start Python kernel",
                       json={"name": "python3"})
    kernel = prefix + "api/kernels/" + quote(response.json()["id"], safe="")
    session, message_id = uuid4().hex, uuid4().hex
    payload = {
        "channel": "shell", "parent_header": {}, "metadata": {}, "buffers": [],
        "header": {"username": "probe", "session": session, "msg_id": message_id,
                   "msg_type": "execute_request", "version": "5.3"},
        "content": {
            "code": f"EXPECTED = {expected!r}\n" + NOTEBOOK_TEST.read_text(),
            "silent": False, "store_history": False, "user_expressions": {},
            "allow_stdin": False, "stop_on_error": True,
        },
    }
    origin = str(client.base_url).rstrip("/")
    ws_url = "wss://" + urlsplit(origin).netloc + kernel + "/channels?" + urlencode({"session_id": session})
    try:
        socket = websocket.create_connection(ws_url,
                                             header={"Authorization": client.headers["authorization"]},
                                             timeout=8, redirect_limit=0)
        try:
            socket.send(json.dumps(payload))
            deadline = time.monotonic() + 45
            executed = False
            receipt = None
            while time.monotonic() < deadline:
                event = json.loads(socket.recv())
                if event.get("parent_header", {}).get("msg_id") != message_id:
                    continue
                kind = event.get("msg_type")
                if kind == "execute_reply":
                    executed = event["content"].get("status") == "ok"
                    if not executed:
                        raise ProbeFailure("notebook resource assertion")
                if kind == "stream":
                    for line in event["content"].get("text", "").splitlines():
                        if line.startswith("RESOURCE_RECEIPT "):
                            receipt = json.loads(line.removeprefix("RESOURCE_RECEIPT "))
                if executed and receipt is not None:
                    return receipt
            raise ProbeFailure("notebook resource verification")
        finally:
            socket.close()
    except (OSError, ValueError, websocket.WebSocketException):
        raise ProbeFailure("notebook kernel connection") from None
    finally:
        request(client, "DELETE", kernel, {204, 404}, "stop Python kernel")


def run_profile(client, owner, server_name, options, expected, role):
    principal = request(client, "GET", "/hub/api/user", {200}, "probe identity").json()
    if principal.get("kind") != "user" or principal.get("name") != owner:
        raise ProbeFailure("probe identity does not match the configured owner")
    groups = principal.get("groups")
    if not isinstance(groups, list) or principal.get("admin") is not False:
        raise ProbeFailure("probe identity lacks a scoped group model")
    if role == "cit-shared" and set(groups) & {"jhub-admins", "jhub-powerusers"}:
        raise ProbeFailure("shared probe identity is elevated")
    if role == "cit-research" and "jhub-powerusers" not in groups:
        raise ProbeFailure("CIT probe lacks the research profile group")
    if role == "cps-poweruser" and "app_jupyterhub_poweruser" not in groups:
        raise ProbeFailure("CPS probe lacks the dedicated profile group")
    user_api = "/hub/api/users/" + quote(owner, safe="")
    named_api = user_api + "/servers/" + quote(server_name, safe="")
    prefix = "/user/" + quote(owner, safe="") + "/" + quote(server_name, safe="") + "/"
    existing = get_server(client, user_api, server_name)
    if existing.get("ready") or existing.get("pending"):
        stop(client, user_api, named_api, server_name)
        raise ProbeFailure("previous probe server was still present and has been stopped")
    try:
        request(client, "POST", named_api, {201, 202}, "spawn", json=options)
        state = wait_ready(client, user_api, server_name, 180)
        if any(state.get("user_options", {}).get(key) != value for key, value in options.items()):
            raise ProbeFailure("Hub returned mismatched spawn options")
        if state.get("url") != prefix:
            raise ProbeFailure("Hub returned unexpected server route")
        return check_resources(client, prefix, expected)
    finally:
        stop(client, user_api, named_api, server_name)


def interrupted(signum, frame):
    raise ProbeFailure("probe was terminated")


def main():
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("route", *PROFILE_CASES))
    parser.add_argument("--hub", choices=tuple(HUBS))
    parser.add_argument("--case")
    parser.add_argument("--visibility-only", action="store_true",
                        help="Check GPU UUID visibility without creating a CUDA context.")
    args = parser.parse_args()
    if args.check == "route" and args.visibility_only:
        parser.error("--visibility-only requires a notebook profile")
    case = args.case
    try:
        if args.check == "route":
            with httpx.Client(base_url=HUBS[args.hub], timeout=12, follow_redirects=False) as client:
                check_route(client)
            print(json.dumps({"check": "route", "hub": args.hub, "result": "passed"}))
        else:
            source, cases = PROFILE_CASES[args.check]
            matching = [row for row in cases if args.case is None or row[0] == args.case]
            if not matching:
                parser.error("--case must name a configured profile")
            owner = (CREDENTIALS / "username").read_text().strip()
            token = (CREDENTIALS / "token").read_text().strip()
            if owner != PROBE_OWNERS[args.check] or not token:
                raise ProbeFailure("credentials do not name the configured monitoring identity")
            with httpx.Client(base_url=HUBS[source], timeout=12, follow_redirects=False,
                              headers={"Authorization": "token " + token}) as client:
                for case, options, devices in matching:
                    expected = resource_contract(args.check, case, devices)
                    if args.visibility_only:
                        expected["gpu_visibility_only"] = True
                    receipt = run_profile(client, owner, "spawn-health-" + case, options, expected, args.check)
                    print(json.dumps({"check": args.check, "hub": source, "case": case,
                                      "result": "passed", "resources": receipt, "serverStopped": True}),
                          flush=True)
    except ProbeFailure as error:
        print(json.dumps({"check": args.check, "case": case, "result": "failed", "stage": str(error)}))
        return 1
    except (KeyError, OSError, ValueError, TypeError):
        print(json.dumps({"check": args.check, "case": case, "result": "failed", "stage": "invalid API or configuration"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
