import json
import subprocess

def kube(*args, **kwargs):
    return subprocess.check_output(["kubectl","-n","cattle-monitoring-system",*args], **kwargs)

current = json.loads(kube("get","alertmanagerconfig","cluster-admin-email","-o","json"))
routes = current["spec"]["route"]
assert routes["receiver"] == "admin-mail"
emails = next(r["emailConfigs"] for r in current["spec"]["receivers"] if r["name"] == "admin-mail")
assert len(emails) == 1 and emails[0]["sendResolved"]
emails[0]["headers"] = [{"key":"Subject","value":'{{ if eq .Status "resolved" }}[RESOLVED]{{ else }}[CRITICAL]{{ end }} CPS/CIT · {{ .GroupLabels.alertname }}{{ with .GroupLabels.namespace }} · {{ . }}{{ end }}'}]
routes.update(groupBy=["alertname","namespace"], groupWait="5s", groupInterval="1m", repeatInterval="4h")
routes["matchers"] = [
    {"name":"severity","matchType":"=","value":"critical"},
    {"name":"alertname","matchType":"!~","value":"InfoInhibitor|Watchdog|AlertmanagerAdminEmailProbe"},
]
patch = {"metadata":{"resourceVersion":current["metadata"]["resourceVersion"]},
         "spec":{"route":routes,"receivers":current["spec"]["receivers"]}}
kube("patch","alertmanagerconfig","cluster-admin-email","--type=merge","--patch-file=/dev/stdin",
     input=json.dumps(patch).encode())
print("Administrator email route now matches critical alerts and delivers resolved notifications")
