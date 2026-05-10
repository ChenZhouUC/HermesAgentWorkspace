---
name: github-copilot
description: Usage tips, quirks, and troubleshooting for GitHub Copilot IDE integrations, including rate limit mitigation.
---

# GitHub Copilot Troubleshooting & Quirks

## Rate Limits, Quotas & Usage-Based Billing (June 2026 Update)

**Major Architectural Change (June 1, 2026):** GitHub is shifting Copilot (Free/Pro/Pro+) from a black-boxed "Premium Requests" (PRU) system to strict usage-based billing. Tokens are tracked via **GitHub AI Credits**.

This change was driven by users exploiting the old "per-request" flat rate for heavy Agentic multi-turn loops and massive context injections (e.g., reviewing whole repositories), which severely misaligned with underlying model API costs.

### Subscription Tier Differences (Post-June 2026)

- **Pro ($10/mo):** Includes $10 in AI Credits (expires monthly). Access to standard premium models.
- **Pro+ ($39/mo):** Includes $39 in AI Credits. **Exclusive access to the highest-tier reasoning models** (e.g., full o1, top-tier Claude).
- **Overage (Pay-as-you-go):** When credits deplete, both plans stop working until the next cycle _unless_ you enable overage billing to buy extra tokens at raw API rates.

_(Note: Basic ghost-text code completions remain unlimited; credits are consumed by Chat, Workspace agents, and complex reviews.)_

### 1. Session Usage Limit (1-Hour Window)

**Symptom:** `"You've used over 50% of your session usage limit. Your limit resets in 1 hour."`
**Cause:** The user has sent too much context (tokens) within the _current_ chat session. This is highly sensitive to:

- Using expensive models (Claude 3.5 Sonnet, o1-preview, GPT-4o).
- Attaching very large files via `#file` or `@workspace`.
- Maintaining a long chat history without clearing it.

**Mitigation (Immediate Fixes):**

1. **Start a New Chat (`+`):** Drops accumulated conversation history, resetting the token payload per request.
2. **Downgrade the Model:** Switch to a lighter version like `GPT-4o-mini`.
3. **Targeted Context:** Highlight specific code blocks instead of dropping entire files.

### 2. Premium Limit Exhaustion

**Symptom:** Forced model downgrade, features disabled, or logs showing rate limits.
**Cause:**

- _Pre-June 2026:_ Exhausted your black-boxed "Premium Requests" for the week. (GitHub temporarily increased multipliers on complex models to throttle usage before the transition).
- _Post-June 2026:_ Your monthly AI Credits balance is $0.
  **Mitigation:** Wait for the billing cycle to reset, upgrade from Pro to Pro+ for a larger upfront balance, or enable overage billing.
