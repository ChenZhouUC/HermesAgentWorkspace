---
name: browser-advanced-config
description: Advanced configuration, troubleshooting, and command-line parameters for web browsers (Chrome, Edge), especially overriding forced UI changes.
category: desktop-administration
---

# Browser Advanced Configuration

This skill covers advanced troubleshooting, configuration, and feature-flag overrides for web browsers, particularly Chromium-based browsers like Microsoft Edge and Google Chrome.

> ⚠ **Scope notes**
>
> - Recipes here are **Windows-focused** (Edge / Chrome shortcut targets). Reframe path/launch syntax for macOS / Linux when needed.
> - Specific flag names below were captured against Edge 2024–2025 builds. Microsoft renames or retires `--disable-features=…` flags between major releases — re-verify the flag still works (`edge://version` and a release-note search) before recommending it.

## Overriding Forced Features via Command Line

When browser developers (like Microsoft or Google) remove UI toggles or `chrome://flags` / `edge://flags` options for controversial features, you can often still override them using startup parameters in the application shortcut.

### Microsoft Edge: Disabling Forced Rounded Corners (vintage 2024/2025)

Microsoft introduced the "Project Phoenix" UI which forces rounded corners around web pages. This breaks "true fullscreen" (F11) by leaving a visible border/white line around the screen edge. The original UI toggles and the `edge://flags/#edge-rounded-containers` flag were removed.

**The Fix:**
You must append specific disable flags to the Edge shortcut target to revert to square corners and enable true fullscreen.

1. Right-click the Edge shortcut -> **Properties**.
2. In the **Target** field, append the following after a space:
   `--disable-features=msEdgeRoundedContainers,msVisualRejuvRoundedTabs`
3. Example Target:
   `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --disable-features=msEdgeRoundedContainers,msVisualRejuvRoundedTabs`
4. **Critical Pitfall:** The browser must be completely closed for startup parameters to take effect. Use Task Manager to kill all `msedge.exe` processes before relaunching via the modified shortcut.

## General Principles for Chromium Feature Flags

- Multiple features can be disabled simultaneously using a comma-separated list: `--disable-features=Feature1,Feature2`
- Enabled features use the inverse parameter: `--enable-features=Feature3`
