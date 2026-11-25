"""Send one weekday warning summary from Prometheus alert history."""
import argparse
from collections import Counter
from datetime import datetime, time, timedelta
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from storage_exporter import api_get

ZONE = ZoneInfo("Europe/Vienna")
PROMETHEUS = "http://rancher-monitoring-prometheus:9090/api/v1/query"
MAIL_CONFIG = (
    "/apis/monitoring.coreos.com/v1alpha1/namespaces/cattle-monitoring-system"
    "/alertmanagerconfigs/cluster-admin-email"
)


def business_window(now):
    last_day = now.date()
    if now.time() < time(9):
        last_day -= timedelta(days=1)
    while last_day.weekday() >= 5:
        last_day -= timedelta(days=1)
    first_day = last_day - timedelta(days=1)
    while first_day.weekday() >= 5:
        first_day -= timedelta(days=1)
    return datetime.combine(first_day, time(9), ZONE), datetime.combine(last_day, time(9), ZONE)


def fetch_warnings(start, end):
    span = int(end.timestamp() - start.timestamp())
    expr = ('max_over_time(ALERTS{severity="warning",alertstate="firing",'
            # CPSLatestBackupJobFailed supersedes the legacy compute alert until its held bundle can roll.
            'alertname!~"InfoInhibitor|Watchdog|AlertmanagerAdminEmailProbe|ComputeStateBackupJobFailed"}'
            f'[{span}s])')
    url = PROMETHEUS + "?" + urlencode({"query": expr, "time": end.timestamp()})
    with urlopen(url, timeout=30) as response:
        result = json.load(response)
    if result["status"] != "success":
        raise RuntimeError("Prometheus did not return warning history")
    return [item["metric"] for item in result["data"]["result"]]


def summarize(warnings, start, end):
    counts = Counter((item["alertname"], item.get("namespace") or item.get("pvc_namespace") or "cluster")
                     for item in warnings)
    lines = [f"{start:%a %d %b %H:%M %Z} to {end:%a %d %b %H:%M %Z}",
             f"{len(warnings)} warning series across {len(counts)} alert and namespace pairs", ""]
    for (name, namespace), count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:50]:
        lines.append(f"{count:>4}  {name}  [{namespace}]")
    if len(counts) > 50:
        lines.append(f"  …  {len(counts) - 50} further groups in Prometheus")
    lines.extend(["", "Cluster overview: " + os.getenv("DASHBOARD_URL", "Grafana / CPS Cluster Overview"),
                  "Review current alerts before assigning or opening an incident."])
    return "\n".join(lines)


def send(body, end, *, test=False):
    receiver = next(receiver for receiver in api_get(MAIL_CONFIG)["spec"]["receivers"]
                    if receiver["name"] == "admin-mail")
    settings = receiver["emailConfigs"][0]
    host, port = settings["smarthost"].rsplit(":", 1)
    message = EmailMessage()
    message["From"], message["To"] = settings["from"], settings["to"]
    purpose = "controlled test" if test else "warning digest"
    message["Subject"] = f"[CPS/CIT] {purpose} · {end:%Y-%m-%d}"
    test_suffix = "-test" if test else ""
    message["Message-ID"] = f"<cps-warning-digest-{end:%Y%m%d}{test_suffix}@cps.unileoben.ac.at>"
    message.set_content(body)
    password = Path("/smtp/password").read_text().strip()
    with smtplib.SMTP_SSL(host, int(port), timeout=20, context=ssl.create_default_context()) as server:
        server.login(settings["authUsername"], password)
        refused = server.send_message(message)
        if refused:
            raise RuntimeError("SMTP refused some digest recipients")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--test-delivery", action="store_true")
    args = parser.parse_args()
    start, end = business_window(datetime.now(ZONE))
    warnings = fetch_warnings(start, end)
    body = summarize(warnings, start, end)
    if args.preview:
        print(body)
    elif args.test_delivery:
        send("Controlled delivery test.\n\n" + body, end, test=True)
        print("SMTP accepted the test warning digest")
    elif warnings:
        send(body, end)
        print("SMTP accepted the business-day warning digest")
    else:
        print("No warning series in this business-day window")


if __name__ == "__main__":
    main()
