# Known Conflict: Logitech Options+ vs. Amphetamine

## Symptom

Logi Options+ (`logioptionsplus_agent`) crashes or quits in the background, causing the mouse to lose custom keybinds and smooth scrolling (reverting to raw macOS input). This typically happens when the Mac transitions to a locked state or display sleep.

## Root Cause

Amphetamine's explicit macOS power assertions for locking the screen or forcing display sleep conflict with Logitech's background daemon, causing the Logi agent to crash during the state transition.

## Diagnostic Checks

Check Amphetamine's settings for screen lock/sleep enforcement:

```bash
defaults read com.if.Amphetamine | grep -i screen
```

Watch for `1` on:

- `"Allow Display Sleep When Screen Is Locked"`
- `"Lock Screen After Inactivity"`
- `"Lock Screen For CDM"`

Check if the Logi daemon is running:

```bash
pgrep -l logioptions
```

## Resolution

1. **Fix (Recommended):** Prevent Amphetamine from enforcing screen locks. In Amphetamine Preferences -> Sessions -> Screen Saver / Screen Lock, disable options that lock the screen or force display sleep. Let native macOS Settings handle locking.
2. **Fast Restart (Workaround):** If the daemon has crashed, restart it via terminal:

```bash
killall logioptionsplus_agent && open -a "Logi Options+"
```
