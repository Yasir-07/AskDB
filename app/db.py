import re

_ALLOWED_START = ("select", "with")
_FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create",
              "attach", "pragma", "replace", "truncate", "vacuum", "grant",
              "revoke", "copy", "merge")


def is_safe(sql: str) -> bool:
    """True only for a single read-only SELECT/WITH statement."""
    s = sql.strip().rstrip(";").lower()
    if ";" in s:                       # block multiple statements
        return False
    if not s.startswith(_ALLOWED_START):
        return False
    return not any(re.search(rf"\b{kw}\b", s) for kw in _FORBIDDEN)


class PostgresDatabase:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        import psycopg
        # `-c default_transaction_read_only=on` makes the WHOLE session read-only
        return psycopg.connect(
            self.dsn, autocommit=True,
            options="-c default_transaction_read_only=on",
        )

    def schema_text(self) -> str:
        """A compact description of every table the AI is allowed to use."""
        query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            tables: dict[str, list[str]] = {}
            for table, column, dtype in cur.fetchall():
                tables.setdefault(table, []).append(f"{column} {dtype}")
        return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())

    def run_select(self, sql: str, limit: int = 50):
        """Returns (ok, payload).
        ok=True  -> payload = {"columns": [...], "rows": [[...], ...]}
        ok=False -> payload = error message string
        """
        if not is_safe(sql):
            return False, "Rejected: only single read-only SELECT queries are allowed."
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchmany(limit)
                columns = [d.name for d in cur.description] if cur.description else []
                return True, {"columns": columns, "rows": [list(r) for r in rows]}
        except Exception as e:  # psycopg raises subclasses of Exception
            return False, f"SQL error: {e}"
