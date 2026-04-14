**Web Search Citations:** When using `web_search`, include the referenced URLs at the end of the response.
§
Hermes 配置：**双 API Key 架构**：主模型用付费 key，memorySearch/web search embedding 用 `${GEMINI_FREE_API_KEY}`（免费项目）
§
Hermes 配置：**Thinking 模型注意**：`gemini-3.1-pro-preview` 是 thinking 模型，`thinkingDefault: "off"` 对它无效（3.7 bug）。避免在 session 里通过 `/model` 切换到它，否则 thinking 标签会污染 session，引发 400 级联
§
Hermes 配置：**400 级联应急**：如出现 400 循环，运行 `python3 ~/.Hermes/workspace/scripts/fix-session-errors.py` 清理 session
§
Hermes 配置：**Compaction 模式**：`safeguard`（防止 compaction 在无真实对话时触发）
§
Hermes 配置 > 技术债 / 已知上游 Bug: Hermes 3.7：`mapThinkLevelToGoogleThinkingLevel("off")` 返回 `undefined`，thinking 内容仍被输出——等待上游修复
§
2026-02-13 > Tasks & Automation: **Cron Jobs Refined**:
§
2026-02-13 > Tasks & Automation: **Daily MacOS Maintenance**: Modified prompt to clarify that Casks are _checked_ but not _auto-upgraded_ (to avoid "fake news" reports). Disabled auto-delivery.
§
2026-02-13 > Tasks & Automation: **Hourly Network Optimization**: Removed obsolete references to sudo/permissions in the prompt. Disabled auto-delivery.
§
2026-02-13 > Tasks & Automation: **Reporting Policy**: User requested a **single source of truth**. Direct cron delivery is disabled. I (Main Agent) will receive the cron result and **always** send a summary report to the user, even if there are no changes ("Everything is up-to-date").
§
2026-02-13 > Repository: **`~/.Hermes` Config Repo**:
§
2026-02-13 > Repository: Updated `cron/jobs.json` with the new prompts and delivery settings.
§
2026-02-13 > Repository: Pushed changes to GitHub `OpenClawWorkspace`.
§
Cron job "Hourly Network Optimization & Update Check" output: ✅ App & Core are up-to-date. ⚡ **Network Optimization:** 🇭🇰 HK: v.3 联通 | 上海 › 香港 4 (36ms) <- v.3 CT | SH › Hong Kong 01 (36ms), 🇯🇵 JP: v.3 联通 | 上海 › 東京 3 (85ms) <- v.3 JP 5.0 • 1x (92ms), 🇸🇬 SG: v.3 联通 | 上海 › 新加坡 1 (68ms) <- v.3 SG 5.0 • 1x (76ms), 🇹🇼 TW: v.3 TW 1.2 (73ms) <- v.3 TW 5.0 • 1x (87ms), 🇺🇸 US: v.3 US 5.1 • 1x (183ms) <- v.3 专线 | 广 › 美国 1 • 1x (214ms)
§
2026-02-22 > Automation & Maintenance: **Stop Request**: User requested to stop both `Daily MacOS Maintenance` and `Hourly Network Optimization` cron jobs.
