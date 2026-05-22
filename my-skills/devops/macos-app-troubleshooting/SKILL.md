---
name: macos-app-troubleshooting
description: Known conflicts, crashes, and workarounds for macOS background apps and daemons (Logi Options+, Amphetamine).
category: devops
---

# macOS App Troubleshooting & Conflicts

Use this skill when diagnosing why background applications, menu bar utilities, or peripheral drivers on macOS crash, hang, or misbehave, particularly around system sleep/wake transitions.

## Logitech Options+ (`logioptionsplus_agent`)

- **Quirk**: Highly sensitive to macOS system power assertions and display sleep transitions. Often crashes or hangs when the Mac wakes from sleep, or when third-party power-management apps (like Amphetamine) force system state changes (e.g., locking the screen or forcing display sleep).
- **Symptom**: Custom mouse/keyboard bindings stop working silently; the mouse tracking feels "laggy" or drops back to default macOS drivers. Two failure modes:
  1. **Really dead** — `logioptionsplus_agent` process is gone.
  2. **Alive but broken** — process is still running (visible in `pgrep`) but internal state (Bluetooth session, key mapping context) was corrupted by a display reconfiguration event. `pgrep` alone misses this case; the only fix is to force-restart.
- **Diagnostics**: Run `ps -ef | grep -i logi` or `pgrep -il logi` to check if `logioptionsplus_agent` is alive. If it is alive but bindings still don't work, you are in the "alive but broken" mode — proceed to force-restart.
- **Fix/Workaround**: Instead of rebooting or reinstalling, force-restart the daemon. This handles both failure modes (kill is a no-op if process is already dead):
  ```bash
  pkill -9 -f "logioptionsplus_agent --launchd"
  # Logi's own KeepAlive (or the watchdog below) will bring it back in 1-2s.
  ```
- **Automated recovery**: This repo ships an optional pair of LaunchAgents (`~/.hermes/scripts/install_logi_watchdog_launchd`):
  - `ai.hermes.logi-watchdog` — bash polling (1s) for "really dead" case.
  - `ai.hermes.logi-display-reactor` — Swift NSWorkspace subscriber (`didWakeNotification` + `screenIsUnlocked` distributed notification) that SIGKILLs the agent on every screen wake / unlock, handling the "alive but broken" case. 30s debounce to coalesce the unlock+wake notification pair.

  See `README.md` → "Logi Options+ 看门狗 (可选)" for install / ops. Once installed, manual intervention is rarely needed.

## Amphetamine

- **Quirk**: If Amphetamine is configured to handle Screen Lock or Screen Saver overrides (e.g., "Lock Screen After Inactivity", "Allow Display Sleep When Screen Is Locked"), its transitions can cause a "black screen flash" and instantly crash sensitive input daemons like Logi Options+. See `references/amphetamine-logi-options-crash.md` for the exact plist keys and recovery commands.
- **Diagnostics**:
  Read the active plist configuration to see if lock/sleep interventions are enabled:
  ```bash
  defaults read com.if.Amphetamine | grep -iE 'screen|sleep'
  ```
- **Fix/Workaround**: To stabilize the system, restrict Amphetamine strictly to "keeping the Mac awake" and disable its screen lock/display sleep overrides. Let macOS native `System Settings -> Lock Screen` handle locking.

## General Debugging Pattern for Background Daemons

1. Isolate the crash pattern (e.g., "happens after sleep" or "happens when X app runs").
2. Check `defaults read` for the suspect app to see if it is intervening in OS-level domains (power, sleep, lock).
3. If an input/driver daemon crashes, find its exact binary name and use `killall <daemon> && open -a "<App.app>"` for a quick, scriptable reset.
