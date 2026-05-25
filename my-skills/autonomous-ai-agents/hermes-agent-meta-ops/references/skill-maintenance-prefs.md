# Custom Skill Maintenance Preferences

When maintaining or refactoring the user's custom skills (`~/.hermes/my-skills/`), strictly adhere to the following architectural preferences gathered from the user's workflows:

1. **Token Efficiency (Script Extraction)**: Keep `SKILL.md` bodies concise to reduce context overhead. Always extract inline scripts (Python, Bash) into separate files under the skill's `scripts/` directory, and reference their absolute paths in the markdown.
2. **Generic Naming Convention**: Prefer broad, scalable directory names over narrow, tool-specific ones. This provides generic containers for future tools (e.g., use `editor-configs` instead of `macvim-ops`, use `mobile-dev-workflows` instead of `flutter-development`).
3. **Atomic Operations**: When authoring new scripts (especially API wrappers like Feishu), ensure operations are atomic. Snapshot existing state before destructive writes, and implement safe rollbacks on connection drops (e.g., `RemoteDisconnected`) to prevent corrupted states.
