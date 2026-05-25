#!/usr/bin/env python3
"""
Postgres Manager CLI
Handles database connection testing, schema extraction, and query execution.
Designed to run via `uv run --with psycopg2-binary python pg_manager.py ...`
"""

import argparse
import json
import os
import sys

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print(
        "Error: psycopg2 is not installed. Please run this script using `uv run --with psycopg2-binary python pg_manager.py`",
        file=sys.stderr,
    )
    sys.exit(1)

WORKSPACE_DIR = os.path.expanduser("~/.hermes/db_workspace")
CONNECTIONS_FILE = os.path.join(WORKSPACE_DIR, "connections.json")
METADATA_DIR = os.path.join(WORKSPACE_DIR, "metadata")


def init_workspace():
    os.makedirs(METADATA_DIR, exist_ok=True)
    if not os.path.exists(CONNECTIONS_FILE):
        with open(CONNECTIONS_FILE, "w") as f:
            json.dump({}, f)


def get_connection_uri(alias):
    init_workspace()
    with open(CONNECTIONS_FILE, "r") as f:
        connections = json.load(f)
    if alias not in connections:
        print(f"Error: Connection alias '{alias}' not found.", file=sys.stderr)
        sys.exit(1)
    return connections[alias]["uri"]


def extract_schema(uri, alias):
    print(f"Extracting schema for '{alias}'...")
    try:
        conn = psycopg2.connect(uri)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Query to get tables and columns
        query = """
        SELECT table_schema, table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position;
        """
        cur.execute(query)
        rows = cur.fetchall()

        schema_dict = {}
        for row in rows:
            schema = row["table_schema"]
            table = row["table_name"]
            col = row["column_name"]
            dtype = row["data_type"]

            if schema not in schema_dict:
                schema_dict[schema] = {}
            if table not in schema_dict[schema]:
                schema_dict[schema][table] = []

            schema_dict[schema][table].append({"column": col, "type": dtype})

        cur.close()
        conn.close()

        output_file = os.path.join(METADATA_DIR, f"{alias}_schema.json")
        with open(output_file, "w") as f:
            json.dump(schema_dict, f, indent=2)

        print(f"Schema saved to {output_file}")
        return True
    except Exception as e:
        print(f"Error extracting schema: {e}", file=sys.stderr)
        return False


def cmd_add(args):
    init_workspace()
    print(f"Testing connection for '{args.alias}'...")
    try:
        conn = psycopg2.connect(args.uri)
        conn.close()
        print("Connection successful.")

        with open(CONNECTIONS_FILE, "r") as f:
            connections = json.load(f)

        import datetime

        connections[args.alias] = {"uri": args.uri, "created_at": datetime.datetime.now().isoformat()}

        with open(CONNECTIONS_FILE, "w") as f:
            json.dump(connections, f, indent=2)

        extract_schema(args.uri, args.alias)

    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_refresh(args):
    uri = get_connection_uri(args.alias)
    extract_schema(uri, args.alias)


def cmd_query(args):
    uri = get_connection_uri(args.alias)
    try:
        conn = psycopg2.connect(uri)
        # Use RealDictCursor to get column names in output
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(args.sql)

        if cur.description:
            rows = cur.fetchall()
            print(json.dumps(rows, indent=2, default=str))
        else:
            conn.commit()
            print(f"Query executed successfully. Rows affected: {cur.rowcount}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Query execution failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermes Postgres Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'add' command
    parser_add = subparsers.add_parser("add", help="Add a new database connection")
    parser_add.add_argument("alias", help="Alias for the connection (e.g., prod_db)")
    parser_add.add_argument("uri", help="PostgreSQL connection URI")

    # 'refresh' command
    parser_refresh = subparsers.add_parser("refresh", help="Refresh schema metadata for an alias")
    parser_refresh.add_argument("alias", help="Alias for the connection")

    # 'query' command
    parser_query = subparsers.add_parser("query", help="Execute a SQL query")
    parser_query.add_argument("alias", help="Alias for the connection")
    parser_query.add_argument("sql", help="SQL query string to execute")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "query":
        cmd_query(args)
