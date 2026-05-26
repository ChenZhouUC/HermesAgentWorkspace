---
name: editor-configs
description: "Editor and IDE configuration workflows (MacVim GUI, VS Code, etc)."
category: software-development
---

# Editor Configurations

This skill covers techniques for configuring editors, starting with MacVim GUI.

- See `references/git-delta-theme-setup.md` for configuring `git-delta` UI themes and side-by-side diff layouts.

## MacVim Operations and Customization

This covers techniques for configuring MacVim GUI elements via `~/.gvimrc` (or `if has("gui_running")` in `~/.vimrc`), which differ from standard terminal Vim.

### GUI Options (`guioptions`)

MacVim's GUI components are toggled using single-character flags in the `guioptions` (or `go`) setting.
A typical user configuration might look like: `set guioptions+=Taegbrk`

- `T`: Show Toolbar (top row of icons).
- `a`: Autoselect (visually selected text is automatically copied to the system `"*` clipboard).
- `e`: Use macOS native GUI tab pages instead of text-based tabs.
- `g`: Grey out inactive menu items instead of hiding them entirely.
- `b`: Show bottom horizontal scrollbar.
- `r`: Show right-hand vertical scrollbar.
- `k`: Keep window size stable when adding/removing GUI components.

To hide the toolbar completely to save screen space, remove the `T`:
`set guioptions-=T`

### Customizing the Toolbar (ToolBar Menu)

The MacVim toolbar cannot be customized via macOS "Right-click -> Customize Toolbar". It is controlled via standard Vim menu commands targeting the special `ToolBar` menu.

1. **Remove existing buttons**: `aunmenu`
   ```vim
   " Remove all default toolbar buttons to start fresh
   aunmenu ToolBar.*
   " Remove a specific button
   aunmenu ToolBar.Save
   ```
2. **Add a button**: `amenu`
   ```vim
   " Add a custom button with an icon path or named system icon
   amenu icon=/path/to/icon.png ToolBar.MyCommand :!python3 %<CR>
   amenu icon=Save ToolBar.MySave :w<CR>
   ```
3. **Add tooltips**: `tmenu`
   ```vim
   tmenu ToolBar.MyCommand Run Current Script
   ```
4. **Add separators**:
   ```vim
   amenu ToolBar.-sep1- <Nop>
   ```
