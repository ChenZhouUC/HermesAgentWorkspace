---
name: postgres-manager
description: Safely inspect and manage PostgreSQL connection profiles.
---

# Postgres Manager

This skill automates the management of PostgreSQL connections, locally caches database schemas (tables, columns, types) to provide accurate context for LLM, and handles query execution.

## When to Use

Use for connection-profile maintenance, schema refresh, read-only database
inspection, or explicitly approved SQL execution through the local manager.

## Environment & File Locations

- **Workspace Dir**: `~/.hermes/db_workspace/`
- **Connections Config**: `~/.hermes/db_workspace/connections.json`
  - Format: `{"alias_name": {"uri": "postgresql://user:pass@host:port/dbname", "created_at": "..."}}`
  - **🔒 Contains plaintext DB passwords.** After `pg_manager.py add` creates or modifies this file, ensure it's `chmod 600`. If the user reports a leaked credential or rotates a password, update via `pg_manager.py add <alias> <new_uri>` (overwrites) and confirm the old URI is gone.
- **Metadata Cache**: `~/.hermes/db_workspace/metadata/<alias_name>_schema.json`
  - Contains grouped tables, column names, and data types.

## Dependencies

Since Python `psycopg2` or `psql` CLI might not be pre-installed, tasks involving new connections might require setting up the environment first (e.g., `pip install psycopg2-binary` or `pip install pg8000`).

## Safety Rules

1. **Do not echo connection URIs.** When reporting status, refer to the alias only. Do not print passwords, full DSNs, tokens, or host/user combinations unless the user explicitly needs to verify a non-secret fragment.
2. **Default to read-only.** For exploration, use `SELECT`, schema metadata, and small `LIMIT` samples first.
3. **Confirm write or destructive work.** Before `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `ALTER`, `DROP`, bulk export, or any query that may expose sensitive rows, state the target alias/table and intended effect, then wait for explicit user approval unless the user already gave a concrete command for that exact operation.
4. **Keep metadata fresh after DDL.** If approved DDL changes the schema, refresh the local metadata cache before answering follow-up SQL questions.

## Workflow 1: Add Connection & Refresh Metadata

When the user provides a DB connection string:

1. Use the Postgres Manager CLI script to add the connection and extract the schema.
   ```bash
   uv run --with psycopg2-binary python ~/.hermes/my-skills/database/postgres-manager/scripts/pg_manager.py add <alias> "<connection_uri>"
   ```
2. The script will automatically verify the connection, save the URI to `connections.json`, extract the table schema, and save it to `metadata/<alias>_schema.json`.

## Workflow 2: Execute SQL Tasks

When the user asks to write/run SQL or do database data processing:

1. Read the schema from `~/.hermes/db_workspace/metadata/<alias>_schema.json` to understand the table structures.
2. Write the exact SQL query based on the cached schema.
3. Execute the query using the CLI:
   ```bash
   uv run --with psycopg2-binary python ~/.hermes/my-skills/database/postgres-manager/scripts/pg_manager.py query <alias> "<sql_query>"
   ```
4. **Continuous Update**: If a query includes DDL (CREATE, ALTER, DROP), automatically re-run `pg_manager.py refresh <alias>` to keep the local metadata cache up to date.
