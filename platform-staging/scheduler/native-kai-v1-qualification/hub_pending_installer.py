# Replace the qualified native installer call only in Root's fenced CIT extraConfig.
# Never append a second native adapter over the existing qualified hook.
import json
from pathlib import Path
from cps_compute_hub.native_pending_hub import install_pending_native_hub_configuration

pilot_path = Path('/var/run/cps-kai-pilot/hub-pending.json')
if pilot_path.exists():
    install_pending_native_hub_configuration(c, json.loads(pilot_path.read_text()))
