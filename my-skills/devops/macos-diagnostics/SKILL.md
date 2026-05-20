---
name: macos-diagnostics
description: Commands and concepts for diagnosing macOS system resources (CPU, Memory, Storage, Memory Pressure).
category: devops
---

# macOS System Diagnostics

Use this skill when diagnosing macOS system performance, memory consumption, or storage space via the terminal.

## 1. Storage Analysis (APFS)

macOS uses APFS with a system volume (read-only) and a data volume sharing the same physical container.

- **Command**: `df -h / /System/Volumes/Data`
- **Pitfall**: Do not just check `/` (which only shows the ~12GB immutable system). Always check `/System/Volumes/Data` to see the actual user capacity and utilization.

## 2. Memory (RAM) Analysis

macOS memory management relies on aggressive caching and compression. "Used" vs "Free" is highly misleading because the OS treats idle RAM as wasted RAM and fills it with File Cache.

- **Total Physical Memory**: `sysctl hw.memsize`
- **Quick Summary (Wired, Compressed, Unused)**: `top -l 1 -s 0 | grep PhysMem`
- **Top 15 Memory-Consuming Processes**:
  ```bash
  top -l 1 -s 0 -o mem -n 15 | awk '/^PID/{p=1} p'
  ```
  _(Note: Piping `top` to `awk` strips the massive verbose header and returns just the clean process table)._

### The "Memory Pressure" Concept

When explaining memory to users, **never** claim the system is out of memory simply because Free RAM is low (e.g., 14GB used out of 16GB). Instead, evaluate and explain **Memory Pressure**, which is determined by:

1. **Swap Rate** (Paging in/out of the SSD) - the primary indicator of RAM exhaustion (thrashing).
2. **Compression Activity** (CPU cost of compressing background apps).
3. **Wired Memory** (Locked by kernel/hardware/unified GPU, cannot be paged).
4. **File Cached Memory** (Purgeable memory ready to be released instantly).

As long as swapping/paging is low (Memory Pressure is "Green"), the system is perfectly healthy. Tools like iStat Menus and macOS Activity Monitor derive their metrics directly from these Mach kernel parameters.

## 3. CPU Diagnostics

- **Top 15 CPU-Consuming Processes**:
  ```bash
  top -l 1 -s 0 -o cpu -n 15 | awk '/^PID/{p=1} p'
  ```
