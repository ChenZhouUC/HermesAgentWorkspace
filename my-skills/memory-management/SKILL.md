---
name: memory-management
description: A guide for robustly handling memory tool errors, especially when content exceeds size limits or the memory state is unexpected.
---

## Trigger

This skill should be used whenever a `memory(action='add')` or `memory(action='replace')` tool call fails, particularly with an error related to size limits or unexpected existing data.

## Steps

1.  **Diagnose the Failure:** Carefully analyze the error message returned by the `memory` tool.
    - Does it indicate the content is too large for the memory store?
    - Does it reveal that the memory store contains unexpected entries, contradicting a user's instruction (e.g., user says memory is clear, but it's not)?

2.  **Inspect Content for Pruning:** Before retrying, critically evaluate the content you are attempting to save. Differentiate between high-value, durable facts and low-value, transient information.
    - **Prioritize Keeping:**
      - User preferences, corrections, and direct instructions (e.g., "don't do X again").
      - Stable environment facts (OS, key file paths, tool quirks).
      - Core configurations, policies, and principles.
      - Warnings about buggy tools or specific parameters to avoid.
    - **Prioritize Removing/Pruning:**
      - Temporary state information (e.g., the output of a single command).
      - Verbose logs or data dumps.
      - Information that is easily re-discoverable with other tools.
      - Content that belongs in a different tool (e.g., a complex procedure should be a `skill`, not a `memory` entry).

3.  **Formulate and Execute a Recovery Plan:**
    - **Step 3a (If necessary): Clear Stale Data.** If the diagnosis revealed unexpected existing entries, use `memory(action='remove', old_text='...')` to remove them first.
    - **Step 3b: Add Pruned Content.** Use `memory(action='add', ...)` with the newly pruned and compacted content from Step 2.

4.  **Verify:** After a successful call, you can confirm with the user by summarizing the newly added memories, ensuring the correct information was retained.

## Pitfalls

- **Do not blindly delete all existing memory.** If existing data seems valuable but is in the way, use the `clarify` tool to ask the user whether to merge, replace, or abort the operation. Only delete autonomously if you are confident the data is stale or irrelevant.
- **Avoid over-pruning.** If you are unsure whether a piece of information is valuable, it's safer to ask the user for guidance rather than potentially losing important context.
- **Distinguish between Memory and Skills.** Do not save complex, multi-step procedures to memory. That is the primary function of the `skill_manage` tool. Memory is for durable _facts_, skills are for reusable _processes_.
