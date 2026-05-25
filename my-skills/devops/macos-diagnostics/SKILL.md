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

## 4. Screen State (Lock & Sleep) Diagnostics

To determine if the macOS system is currently locked (useful for knowing if the user is active, or if certain background tasks might be suspended):

- **Command (pmset - User Activity)**:

  ```bash
  pmset -g useractivity
  ```

  _Indicator_: `Level = 'PresentActive'` means the user is currently active (unlocked).

- **Command (Quartz - GUI Session)**:
  ```bash
  /usr/bin/python3 -c "import Quartz; print(Quartz.CGSessionCopyCurrentDictionary().get('CGSSessionScreenIsLocked', 'Unlocked'))"
  ```
  _Pitfall_: You **must** use the macOS system Python (`/usr/bin/python3`) to run this. If you use a custom `uv` or `pyenv` virtual environment, it will crash with `ModuleNotFoundError` because it lacks the built-in `pyobjc` (`Quartz`) framework.

## 5. Application Conflicts & Crash Debugging

Use these patterns when background applications, menu bar utilities, or peripheral drivers on macOS crash, hang, or misbehave (particularly around system sleep/wake transitions).

### Logitech Options+ (`logioptionsplus_agent`)

- **Quirk**: Highly sensitive to macOS system power assertions and display sleep transitions. Often crashes or hangs when the Mac wakes from sleep, or when third-party power-management apps (like Amphetamine) force system state changes.
- **Symptom**: Custom mouse/keyboard bindings stop working silently; the mouse tracking feels "laggy". Two failure modes:
  1. **Really dead** — `logioptionsplus_agent` process is gone.
  2. **Alive but broken** — process is still running (visible in `pgrep`) but internal state (Bluetooth session, key mapping context) was corrupted by a display reconfiguration event. `pgrep` alone misses this case; the only fix is to force-restart.
- **Diagnostics**: Run `pgrep -il logi` (or `ps -ef | grep -i logi`) to check if `logioptionsplus_agent` is alive. If it is alive but bindings still don't work, you are in the "alive but broken" mode — proceed to force-restart.
- **Fix/Workaround** (handles both failure modes; kill is a no-op if the process is already dead):
  ```bash
  pkill -9 -f "logioptionsplus_agent --launchd"
  # Logi's own KeepAlive (or the watchdog below) will bring it back in 1-2s.
  ```
- **Automated recovery**: This repo ships an optional pair of LaunchAgents (`~/.hermes/scripts/install_logi_watchdog_launchd`):
  - `ai.hermes.logi-watchdog` — bash polling (1s) for the "really dead" case.
  - `ai.hermes.logi-display-reactor` — Swift NSWorkspace subscriber (`didWakeNotification` + `screenIsUnlocked` distributed notification) that SIGKILLs the agent on every screen wake / unlock, handling the "alive but broken" case. 30s debounce to coalesce the unlock+wake notification pair.

  See `README.md` → "Logi Options+ 看门狗 (可选)" for install / ops. Once installed, manual intervention is rarely needed.

### Amphetamine

- **Quirk**: If Amphetamine is configured to handle Screen Lock or Screen Saver overrides (e.g., "Lock Screen After Inactivity", "Allow Display Sleep When Screen Is Locked"), its transitions can cause a "black screen flash" and instantly crash sensitive input daemons like Logi Options+. See `references/amphetamine-logi-options-crash.md` for the exact plist keys and recovery commands.
- **Diagnostics**: Read the active plist configuration to see if lock/sleep interventions are enabled:
  ```bash
  defaults read com.if.Amphetamine | grep -iE 'screen|sleep'
  ```
- **Fix/Workaround**: Restrict Amphetamine strictly to "keeping the Mac awake" and disable its screen lock/display sleep overrides. Let macOS native `System Settings -> Lock Screen` handle locking.

### General Debugging Pattern for Background Daemons

1. Isolate the crash pattern (e.g., "happens after sleep" or "happens when X app runs").
2. Check `defaults read` for the suspect app to see if it is intervening in OS-level domains (power, sleep, lock).
3. If an input/driver daemon crashes, find its exact binary name and use `killall <daemon> && open -a "<App.app>"` for a quick, scriptable reset.
