# Build only from an operator-reviewed image containing Python3 and the pinned
# R615 nvidia-smi/libnvidia-ml userland. No package/network installation here.
ARG SERVICE_BASE_IMAGE
FROM ${SERVICE_BASE_IMAGE}
ARG SERVICE_BASE_IMAGE
USER 0:0
ENV PYTHONDONTWRITEBYTECODE=1
COPY node_agent.py driver_loader.py source-snapshot.json /opt/native/
RUN python3 -c "import re,sys; assert re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', sys.argv[1]) and not sys.argv[1].endswith('0'*64)" "${SERVICE_BASE_IMAGE}" \
 && python3 -c "import ctypes,shutil; assert shutil.which('nvidia-smi'); ctypes.CDLL('libnvidia-ml.so.1')" \
 && python3 -c "import sys; from pathlib import Path; sys.path.insert(0,'/opt/native'); from node_agent import snapshot_sources; [(Path('/opt/native')/n).write_text(v) for n,v in snapshot_sources().items()]"
CMD ["python3", "/opt/native/node_agent.py"]
