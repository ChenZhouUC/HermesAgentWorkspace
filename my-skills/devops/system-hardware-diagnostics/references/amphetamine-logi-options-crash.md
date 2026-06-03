# Amphetamine / Logi Options+ Crash Conflict

When Amphetamine manages display sleep or screen locking, it overrides macOS native power assertions. This often triggers a rapid `sleep -> wake -> lock` sequence.
The Logitech Options+ Agent (`logioptionsplus_agent`) hooks into `CoreGraphics` and `IOKit` to capture mouse events. When the display server state flickers too quickly during Amphetamine's intervention, the Logi daemon loses its CGEventTap and either crashes outright or goes into an unresponsive zombie state.

## Problematic Preference Keys

Inspect Amphetamine's preferences to see if it is intervening in screen lock / display sleep:

```bash
defaults read com.if.Amphetamine | grep -iE 'screen|sleep|lock'
```

The keys that cause the crash loop when enabled:

- `"Lock Screen After Inactivity" = 1`
- `"Allow Display Sleep When Screen Is Locked" = 1`
- `"Lock Screen For CDM" = 1`

## Mitigation

1. **Disable screen lock in Amphetamine**: Preferences → Sessions → Screen Saver / Screen Lock. Disable any setting that lets Amphetamine trigger the screen saver/lock. Let macOS handle sleep/locking natively via System Settings.
2. **Disable display sleep in Amphetamine**: Preferences → Sessions → Display Sleep, uncheck "Allow display sleep when screen is locked".
3. **Quick recovery**: If the mouse starts lagging or loses custom buttons, the daemon has crashed. Restart it without rebooting:
   ```bash
   killall logioptionsplus_agent && open -a "Logi Options+"
   ```
