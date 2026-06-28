---
name: github-copilot-ecosystem
category: software-development
description: GitHub Copilot subscription tiers, 2026 billing model (AI Credits), CLI configuration, and common troubleshooting.
trigger: User asks about GitHub Copilot pricing, tiers (Pro/Pro+/Max/Business), subscription changes, CLI banner/config issues, or AI Credits consumption.
---

# GitHub Copilot Ecosystem

## 2026 Pricing Overhaul (June 1, 2026)

GitHub switched Copilot from flat-rate unlimited billing to **usage-based AI Credits** model.

### Tier Comparison

| Tier     | Price       | AI Credits                    | Premium Models | Notes                                                                                     |
| -------- | ----------- | ----------------------------- | -------------- | ----------------------------------------------------------------------------------------- |
| Free     | $0          | Limited (2K completions)      | No             | Chat/Agent severely limited                                                               |
| Pro      | $10/mo      | ~$10-15 credits               | No             | Inline completions free. Chat/Agent burn credits fast — heavy users blow through in days. |
| Pro+     | $39/mo      | High (~1500 premium requests) | Yes            | Premium models (Opus, Sonnet 4.5+), priority access.                                      |
| Max      | $100/mo     | Highest                       | Yes + Priority | Latest models first.                                                                      |
| Business | $19/user/mo | Pool-based                    | Varies         | Org-managed, policy control.                                                              |

**Key rule**: Inline code completions are **free/unlimited** on all paid tiers. Only Chat, Agent mode, code review, CLI, and Cloud Agent consume AI Credits.

### Downgrade Guidance (Pro+ → Pro)

- You lose premium model access and the majority of your AI Credits pool.
- If user mainly uses IDE completions: **downgrade is safe** — completions don't burn credits.
- For heavy Agent/Chat work: recommend keeping API fallback (OpenRouter + Claude Sonnet at ~$3/M tokens) instead of paying $39/mo for Pro+ credits. Community feedback: "$39 for 3 days of light coding" is common complaint.

## Copilot CLI (`@github/copilot`)

### Config Location

- `~/.copilot/settings.json` — primary user config (JSONC)
- `~/.copilot/config.json` — auto-managed app state (auth, plugins). Do not edit directly.
- `~/.copilot/copilot-instructions.md` — global custom instructions
- Override path: `export COPILOT_HOME=/path/to/my/copilot-config`

### Banner Behavior (v1.0+)

In v1.0.x, the animated ASCII splash banner changed to **show only on first launch**. Subsequent launches skip it unless forced.

**To force banner every time**: `copilot --banner`
**Permanent fix**: add alias in `.zshrc`: `alias copilot="copilot --banner"`

### Common CLI Flags

- `--experimental` / `--no-experimental`: Toggle agent mode
- `--screen-reader`: Accessibility mode (changes banner rendering)
- `--allow-all-tools`: Skip tool approval prompts
- `--allow-all-paths`: Skip path approval prompts

### Known Issues

- **Banner missing border / rendering degraded**: Often triggered by experimental mode or terminal capability detection. Force `TERM=xterm-256color` or `COLORTERM=truecolor` before launching.
- **Banner position in experimental mode**: Known issue (#1694) — banner clears console and renders at bottom instead of inline. No config workaround; official rendering change in 1.0.x.
- **sharp binding errors on update**: Node.js version mismatches during `npm i -g @github/copilot` can break sharp (image processing). Reinstall with `npm install -g --include=optional @github/copilot`.

### settings.json Keys

Common user-editable keys: `model`, `effortLevel`, `mouse`, `experimental`, `footer` (object with sub-keys), `allowedUrls`, `includeCoAuthoredBy`, `compactPaste`, `updateTerminalTitle`, `respectGitignore`.

## See Also

- `references/pricing-and-cli-notes.md` — detailed research transcripts, issue links, changelog excerpts
- `hermes-agent` skill for how to configure Hermes itself with Copilot ACP integration
