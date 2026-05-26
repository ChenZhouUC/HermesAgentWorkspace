# git-delta Configuration & Themes

When configuring `git-delta` for syntax highlighting in git, chezmoi, or AI agent outputs, users often find the default `syntax-theme` insufficient because it only colors text without altering the background, layout, or borders.

## The Right Way: Use Features

Delta maintains a repository of community themes that bundle syntax colors, background styling, and layout features (like side-by-side) into named `features`.

1. **Download the themes file:**

   ```bash
   curl -o ~/.delta-themes.gitconfig https://raw.githubusercontent.com/dandavison/delta/main/themes.gitconfig
   ```

2. **Include and apply it in `~/.gitconfig`:**
   Instead of using `syntax-theme`, use `features` combined with the downloaded file.

   ```ini
   [include]
       path = ~/.delta-themes.gitconfig

   [core]
       pager = delta

   [interactive]
       diffFilter = delta --color-only

   [delta]
       # Use a global layout feature instead of a raw syntax-theme
       features = chameleon

       # Recommended overrides
       side-by-side = true
       line-numbers = true
       navigate = true
   ```

### Recommended Themes (Features)

- `chameleon`: (Highly recommended) Elegant dark grey background with smooth line-number transitions.
- `zebra-dark`: Alternating background shades per line, excellent for intensive code review.
- `arctic-fox`: Cool, dark theme similar to Nord.
- `zebra-light`: The best option for light-mode terminals.

To preview available themes with their full layout (not just text coloring), use:

```bash
delta --show-themes
```

_(Do not use `--show-syntax-themes` if you want to see the full UI layout applied.)_
