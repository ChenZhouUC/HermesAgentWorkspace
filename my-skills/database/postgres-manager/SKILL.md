---
name: postgres-manager
description: 自动管理 PostgreSQL 连接配置、持久化存储表结构（元数据），并基于准确的元数据辅助执行 SQL 任务。
category: database
version: 2026.06.03
author: Chen Zhou <chenzhou@uchicago.edu>
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
