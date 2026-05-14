# Bypassing CMA and OverlayFS for True Hardware Specs

When diagnosing edge AI boxes (like RK3576, Sophgo CV186AH/BM1688, BM1684X), standard Linux commands like `free -h` and `df -h` often report misleading numbers because:

1. **Hardware Reserved Memory (CMA/ION)**: NPU/TPU and VPU drivers pre-allocate huge chunks of physical RAM at boot. `free -h` only shows what's left for the OS.
2. **OverlayFS**: Root filesystems are often mounted as `overlay`, masking the true size of the eMMC and other partitions.

## How to find the TRUE physical specs

**1. True Physical RAM & Reserved Memory:**

```bash
# Total physical RAM seen by the kernel at boot
dmesg | grep -i "Memory:" | head -n 1

# CMA / Reserved memory footprint
dmesg | grep -i "reserved" | grep -i "mem"

# Sophgo specific: ION/CMA pool size
cat /sys/kernel/debug/ion/cma
```

**2. True Physical Storage (eMMC/Disk):**

```bash
# Bypass mounts and read raw block device sizes directly
lsblk -d
```
