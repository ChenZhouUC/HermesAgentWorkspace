# macOS Sleep and Lock State Diagnostics

## Checking Sleep Assertions

To see what is currently preventing the Mac from sleeping (e.g., Amphetamine, caffeinate, WindowServer):
`pmset -g assertions`
Look for `PreventUserIdleSystemSleep` or `NoIdleSleepAssertion`.

## Checking Screen Lock Status

To programmatically check if the macOS screen is currently locked:
`ioreg -n Root -d1 | grep -i CGSSessionScreenIsLocked`
Returns `"CGSSessionScreenIsLocked"=Yes` if locked.

## Preventing Sleep (CLI Fallback)

When third-party GUI tools (like Amphetamine) block AppleScript or URL scheme automation due to macOS security restrictions (`errAEEventFailed` or timeout), fallback to the native `caffeinate` utility:
`caffeinate -di -t <seconds> &` (e.g., `7200` for 2 hours).

_Note: Use `background=true` in terminal if running via agent, and consider `notify_on_complete=true`._
