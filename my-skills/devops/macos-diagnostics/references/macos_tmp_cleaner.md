# macOS /tmp Directory Cleaning Behavior

macOS manages `/tmp` (which symlinks to `/private/tmp`) via a system LaunchDaemon, not cron.

- **Daemon:** `com.apple.tmp_cleaner`
- **Executable:** `/usr/libexec/tmp_cleaner`
- **Trigger:** Runs daily at midnight (`StartCalendarInterval` Hour 0).
- **Behavior:** Deletes files and empty directories with `atime`, `mtime`, and `ctime` strictly greater than 3 days (`daily_clean_tmps_days="3"`).
- **Restart:** Rebooting macOS also completely clears `/tmp`.
