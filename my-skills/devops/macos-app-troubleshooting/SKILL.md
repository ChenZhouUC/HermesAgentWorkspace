---
name: macos-app-troubleshooting
description: Known conflicts, crashes, and workarounds for macOS background apps and daemons (Logi Options+, Amphetamine).
category: devops
---

# macOS App Troubleshooting & Conflicts

Use this skill when diagnosing why background applications, menu bar utilities, or peripheral drivers on macOS crash, hang, or misbehave, particularly around system sleep/wake transitions.

## Logitech Options+ (`logioptionsplus_agent`)

- **Quirk**: Highly sensitive to macOS system power assertions and display sleep transitions. Often crashes or hangs when the Mac wakes from sleep, or when third-party power-management apps (like Amphetamine) force system state changes (e.g., locking the screen or forcing display sleep).
- **Symptom**: Custom mouse/keyboard bindings stop working silently; the mouse tracking feels "laggy" or drops back to default macOS drivers.
- **Diagnostics**: Run `ps -ef | grep -i logi` or `pgrep -il logi` to check if `logioptionsplus_agent` has recently crashed or restarted.
- **Fix/Workaround**: Instead of rebooting or reinstalling, restart the daemon via terminal:
  ```bash
  killall logioptionsplus_agent && open -a "Logi Options+"
  ```
- **Automated recovery**: This repo ships an optional LaunchAgent watchdog (`~/.hermes/scripts/install_logi_watchdog_launchd`) that polls every second and restarts the daemon within 2–3 seconds. See `README.md` → "Logi Options+ 看门狗 (可选)". Once installed, the manual `killall` step above is unnecessary.

## Amphetamine

- **Quirk**: If Amphetamine is configured to handle Screen Lock or Screen Saver overrides (e.g., "Lock Screen After Inactivity", "Allow Display Sleep When Screen Is Locked"), its transitions can cause a "black screen flash" and instantly crash sensitive input daemons like Logi Options+.
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
