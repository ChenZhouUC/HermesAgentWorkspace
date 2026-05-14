---
name: embedded-linux-diagnostics
description: "Diagnose true hardware specifications (RAM, Storage, Model) on embedded Linux and Edge AI boards (Sophgo, Rockchip) where standard tools like free and df are misleading."
category: devops
---

# Embedded Linux & Edge AI Diagnostics

Use this skill when inspecting or troubleshooting Edge AI nodes (e.g., Rockchip RK35xx, Sophgo BM168x/CV186x) and embedded Linux systems.

## 🚨 Critical Pitfalls & Workarounds

### 1. Memory (`free -h` lies)

- **Issue**: Standard `free -h` only shows RAM available to the Linux kernel. On Edge AI boards, large chunks of physical RAM are permanently "hard-reserved" by the bootloader for the NPU/TPU/VPU.
- **Fix**: To find true physical memory and reserved CMA (Contiguous Memory Allocator) pools, use:
  - `dmesg | grep -i "reserved" | grep -i "mem"`
  - `cat /sys/kernel/debug/ion/cma` (Specific to Sophgo/Android-based ION memory allocators)
  - `dmesg | grep -i "Memory:"` (Look at the kernel boot lines for total available vs reserved)

### 2. Storage (`df -h` on `/` lies)

- **Issue**: The root partition `/` is often an OverlayFS slice and may show a small capacity (e.g., 8GB) even if the physical eMMC is much larger (e.g., 32GB or 64GB).
- **Fix**: Do NOT rely solely on `df -h` for total disk capacity.
  - Use `lsblk -d` to see the true physical block device sizes.
  - Use `df -h` to find the actual data mount points (often `/data` or `/userdata` hold the bulk of the storage).

### 3. Hardware Model Probing

- **Issue**: Standard DTB paths like `cat /proc/device-tree/model` do not reliably exist across all board support packages (BSPs). For example, newer Sophgo boards (BM1688 / 7.2T) expose it, but older kernel BSPs (BM1684X / 32T on kernel 5.4) do not and return "No such file".
- **Fix**: Use vendor-specific SMI (System Management Interface) tools when available. For Sophgo, always rely on `bm-smi` (usually located at `/opt/sophon/libsophon-current/bin/bm-smi`) for authoritative model, TPU utilization, and memory stats.
