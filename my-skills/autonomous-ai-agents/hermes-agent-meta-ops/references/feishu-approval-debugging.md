# Debugging Feishu Terminal Approval Unresponsive Cards

## Symptom

The user clicks "Approve" or "Deny" on a terminal approval card in Feishu, but nothing happens and the agent's workflow remains blocked.

## Root Cause

The Hermes Gateway silently drops the interaction due to insufficient permissions. High-risk interactive cards (like terminal execution approval) require the acting user's Feishu `open_id` to be explicitly allowlisted in the environment config if the agent is operating under strict access policies.

## Diagnostic Workflow

1. Read the gateway log: `tail -n 50 ~/.hermes/logs/gateway.log`
2. Look for permission drop warnings: `WARNING [Feishu] Unauthorized approval click by ou_...`
3. The logged ID is the user's actual Feishu `open_id` for this bot application.

## Resolution Steps

1. Inform the user of their exact `open_id` found in the logs.
2. Instruct them to manually open `~/.hermes/.env` in their editor.
3. Tell them to uncomment or add the line: `FEISHU_ALLOWED_USERS=<their_open_id>`
4. Instruct them to restart the agent: `hermes restart`

## ⚠️ Critical Pitfall: Protected Files

Do **NOT** attempt to use the `patch` or `write_file` tools to fix `~/.hermes/.env` for the user. It is a system-protected credential file. Tool writes to it will be rejected at the system level (`Write denied: '.../.env' is a protected system/credential file`). You must guide the user to make the edit manually.
