---
name: system-hardware-diagnostics
description: "Use when diagnosing macOS hardware/OS issues or embedded Edge AI boards such as Rockchip/Sophgo, including APFS, memory pressure, CMA, and OverlayFS bypass."
---

# System & Hardware Diagnostics

Use this skill when diagnosing system performance, memory consumption, or storage space via the terminal on either macOS or embedded Edge AI Linux boards.

## 1. macOS Diagnostics

### Storage Analysis (APFS)

macOS uses APFS with a system volume (read-only) and a data volume sharing the same physical container.

- **Command**: `df -h / /System/Volumes/Data`
- **Pitfall**: Do not just check `/`. Always check `/System/Volumes/Data` to see the actual user capacity.

For macOS `/tmp` lifecycle details, see [`references/macos_tmp_cleaner.md`](references/macos_tmp_cleaner.md).

### Memory (RAM) Analysis

macOS memory management relies on aggressive caching and compression.

- **Total Physical Memory**: `sysctl hw.memsize`
- **Memory Pressure**: Never claim the system is out of memory simply because Free RAM is low. Evaluate **Swap Rate** and **Wired Memory**. As long as swapping/paging is low, the system is healthy.
- **Top 15 Processes (Memory)**: `top -l 1 -s 0 -o mem -n 15 | awk '/^PID/{p=1} p'`

### Application Conflicts (Logitech & Amphetamine)

- **Logitech Options+**: Highly sensitive to display sleep. If it breaks after wake, restart it: `pkill -9 -f "logioptionsplus_agent --launchd"`
- **Amphetamine**: Screen Lock overrides cause input daemon crashes. Restrict it strictly to keeping the Mac awake.

See [`references/amphetamine-logi-options-crash.md`](references/amphetamine-logi-options-crash.md) for the conflict and recovery workflow.

### Programmatic Sleep Prevention

- **Use native `caffeinate`**: `caffeinate -di -t 3600 &` (1 hour background). Do not attempt to script Amphetamine.

See [`references/sleep-and-lock-state.md`](references/sleep-and-lock-state.md) for assertion and lock-state probes.

## 2. Embedded Linux & Edge AI Boards (Rockchip / Sophgo)

### Memory (`free -h` lies)

- **Issue**: Standard `free -h` only shows RAM available to the Linux kernel. Large chunks are hard-reserved for the NPU/TPU/VPU.
- **Fix**: Check `dmesg | grep -i "reserved" | grep -i "mem"` or `cat /sys/kernel/debug/ion/cma`.

### Storage (`df -h` on `/` lies)

- **Issue**: The root partition `/` is often an OverlayFS slice.
- **Fix**: Use `lsblk -d` to see true physical block sizes and `df -h` for `/data` or `/userdata`.

### Hardware Model Probing

- **Fix**: Use vendor-specific SMI tools. For Sophgo, use `bm-smi` (`/opt/sophon/libsophon-current/bin/bm-smi`) for authoritative model and TPU utilization.

See [`references/bypassing_cma_overlayfs.md`](references/bypassing_cma_overlayfs.md) for the full physical-memory and storage workflow.
