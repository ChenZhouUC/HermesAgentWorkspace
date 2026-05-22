# Bug: Amphetamine Crash Loop with Logi Options+

## Symptoms

When using the Amphetamine app to keep a Mac awake, activating and then ending a session causes the screen to flash black. Subsequently, the Logitech Options+ daemon (`logioptionsplus_agent`) crashes in the background, causing the user's mouse to lose custom mappings and revert to default tracking/scrolling behavior.

## Root Cause

Amphetamine modifies system power assertions. If Amphetamine is configured to force the screen to lock or sleep upon session end (or during a trigger), the sudden system state change crashes the fragile `logioptionsplus_agent` process.

Specific problematic keys in `com.if.Amphetamine` preferences:

- `"Lock Screen After Inactivity" = 1`
- `"Allow Display Sleep When Screen Is Locked" = 1`
- `"Lock Screen For CDM" = 1`

## Workaround / Fix

1. **Disable Screen Lock in Amphetamine**: Open Amphetamine Preferences -> Sessions -> Screen Saver / Screen Lock. Ensure "Lock screen after inactivity" or any setting that allows the screen saver/lock to kick in via Amphetamine is **disabled**. Let macOS handle sleep/locking natively via System Settings.
2. **Disable Display Sleep in Amphetamine**: In Preferences -> Sessions -> Display Sleep, uncheck "Allow display sleep when screen is locked".
3. **Quick Recovery**: If the mouse starts lagging or loses custom buttons, the background daemon has crashed. Restart it via terminal without needing to reboot:
   `killall logioptionsplus_agent && open -a "Logi Options+"`
