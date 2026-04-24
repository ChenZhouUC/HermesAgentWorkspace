---
name: postgres-manager
description: 自动管理 PostgreSQL 连接配置、持久化存储表结构（元数据），并基于准确的元数据辅助执行 SQL 任务。
---

# Postgres Manager

This skill automates the management of PostgreSQL connections, locally caches database schemas (tables, columns, types) to provide accurate context for LLM, and handles query execution.

## Environment & File Locations

- **Workspace Dir**: `~/.hermes/db_workspace/`
- **Connections Config**: `~/.hermes/db_workspace/connections.json`
  - Format: `{"alias_name": {"uri": "postgresql://user:pass@host:port/dbname", "created_at": "..."}}`
- **Metadata Cache**: `~/.hermes/db_workspace/metadata/<alias_name>_schema.json`
  - Contains grouped tables, column names, and data types.

## Dependencies

Since Python `psycopg2` or `psql` CLI might not be pre-installed, tasks involving new connections might require setting up the environment first (e.g., `pip install psycopg2-binary` or `pip install pg8000`).

## Workflow 1: Add Connection & Refresh Metadata

When the user provides a DB connection string:

1. Parse the connection and determine an easy-to-use `alias` (e.g., `prod_db`, `test_db`).
2. Verify the connection works via `execute_code` (installing `psycopg2-binary` if needed).
3. If successful, save the connection URI to `connections.json`.
4. Run a schema extraction query to fetch metadata:
   ```sql
   SELECT table_schema, table_name, column_name, data_type
   FROM information_schema.columns
   WHERE table_schema NOT IN ('pg_catalog', 'information_schema');
   ```
5. Group the results by table and save them as formatted JSON to `metadata/<alias_name>_schema.json`.

## Workflow 2: Execute SQL Tasks

When the user asks to write/run SQL or do database data processing:

1. Check which `alias` is intended. Read the connection string from `connections.json`.
2. Read the schema from the corresponding `metadata/<alias_name>_schema.json` to understand the table structures strictly.
3. Write the exact SQL query based on the cached schema.
4. Execute the query using `execute_code` (Python script). Format the output cleanly (e.g., using `pandas` to print tabular data or exporting to CSV if requested).
5. **Continuous Update**: If a query includes DDL (CREATE, ALTER, DROP), automatically re-run **Workflow 1**'s Step 4 & 5 to keep the local metadata cache up to date.
