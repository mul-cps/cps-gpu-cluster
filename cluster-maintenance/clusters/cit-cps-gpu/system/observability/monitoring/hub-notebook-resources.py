"""Execute inside a Jupyter kernel. The runner supplies the EXPECTED contract."""
import ctypes as ct
import json
import os
from pathlib import Path
import tempfile

cgroups = Path("/sys/fs/cgroup")
quota, period = (cgroups / "cpu.max").read_text().split()
cpus = len(os.sched_getaffinity(0))
if quota != "max":
    cpus = min(cpus, int(quota) / int(period))
assert cpus >= EXPECTED["cpu"], "CPU capacity"
memory_limit = (cgroups / "memory.max").read_text().strip()
if memory_limit == "max":
    memory_limit = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
memory_limit = int(memory_limit)
assert memory_limit >= EXPECTED["memory"], "RAM capacity"
sample = bytearray(4 << 20)
sample[::4096] = b"x" * (len(sample) // 4096)
assert sample[-4096] == ord("x"), "RAM access"

home = Path.home()
disk = os.statvfs(home)
home_available = disk.f_bavail * disk.f_frsize
assert home_available >= EXPECTED["home"], "home filesystem capacity"
with tempfile.TemporaryFile(dir=home) as probe_file:
    content = b"JupyterHub lifecycle storage probe"
    probe_file.write(content)
    probe_file.flush()
    os.fsync(probe_file.fileno())
    probe_file.seek(0)
    assert probe_file.read() == content, "home read and write"

cuda = ct.CDLL("libcuda.so.1")
assert cuda.cuInit(0) == 0, "CUDA init"
device_count = ct.c_int()
assert cuda.cuDeviceGetCount(ct.byref(device_count)) == 0
assert device_count.value == EXPECTED["gpus"], "GPU count"
memory_cap = EXPECTED.get("vram_mib")
if memory_cap:
    assert int(os.environ["NVIDIA_GPU_MEMORY_REQUEST"]) == memory_cap, "VRAM request"
    assert int(os.environ["NVIDIA_GPU_MEMORY_LIMIT"]) == memory_cap, "VRAM limit"
devices = []
vram = []
for index in range(device_count.value):
    device = ct.c_int()
    assert cuda.cuDeviceGet(ct.byref(device), index) == 0
    devices.append(device)
    memory = ct.c_size_t()
    assert cuda.cuDeviceTotalMem_v2(ct.byref(memory), device) == 0
    if not memory_cap:
        assert memory.value >= 40_000_000_000, "whole-device memory"
    vram.append(memory.value)
    context = ct.c_void_p()
    assert cuda.cuCtxCreate_v2(ct.byref(context), 0, device) == 0
    try:
        address = ct.c_uint64()
        sample_bytes = ct.c_size_t(64 << 20)
        assert cuda.cuMemAlloc_v2(ct.byref(address), sample_bytes) == 0
        try:
            assert cuda.cuMemsetD8_v2(address, ct.c_ubyte(19), sample_bytes) == 0
            assert cuda.cuCtxSynchronize() == 0
        finally:
            assert cuda.cuMemFree_v2(address) == 0
        if memory_cap:
            excess = cuda.cuMemAlloc_v2(ct.byref(address), ct.c_size_t((memory_cap + 64) << 20))
            if excess == 0:
                cuda.cuMemFree_v2(address)
            assert excess == 2, "VRAM cap enforcement"
    finally:
        assert cuda.cuCtxDestroy_v2(context) == 0

if EXPECTED.get("peer"):
    peer = ct.c_int()
    for source, target in ((0, 1), (1, 0)):
        assert cuda.cuDeviceCanAccessPeer(ct.byref(peer), devices[source], devices[target]) == 0
        assert peer.value == 1, "GPU peer access"

framework = EXPECTED["framework"]
if framework == "pytorch":
    import torch
    assert torch.cuda.device_count() == device_count.value
    for index in range(device_count.value):
        assert torch.ones(32, device=f"cuda:{index}").sum().item() == 32
else:
    import tensorflow as tf
    physical = tf.config.list_physical_devices("GPU")
    assert len(physical) == device_count.value
    for device in physical:
        tf.config.experimental.set_memory_growth(device, True)
    for index in range(device_count.value):
        with tf.device(f"/GPU:{index}"):
            total = tf.reduce_sum(tf.ones(32))
        assert float(total.numpy()) == 32 and "GPU" in total.device

print("RESOURCE_RECEIPT " + json.dumps({
    "cpuCapacity": cpus, "memoryBytes": memory_limit, "homeFreeBytes": home_available,
    "cudaDevices": device_count.value, "deviceMemoryBytes": vram, "vramCapMiB": memory_cap,
    "homeWritable": True, "framework": framework,
}))
