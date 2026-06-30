import csv
import re
import sys

from .config import get_settings

# PostgreSQL reserved words that cannot be used as plain column names.
RESERVED = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "authorization", "between", "binary", "both", "case", "cast", "check", "collate",
    "column", "concurrently", "constraint", "create", "cross", "current_catalog",
    "current_date", "current_role", "current_schema", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "desc", "distinct",
    "do", "else", "end", "except", "false", "fetch", "for", "foreign", "freeze",
    "from", "full", "grant", "group", "having", "ilike", "in", "initially", "inner",
    "intersect", "into", "is", "isnull", "join", "lateral", "leading", "left", "like",
    "limit", "localtime", "localtimestamp", "natural", "not", "notnull", "null",
    "offset", "on", "only", "or", "order", "outer", "overlaps", "placing", "primary",
    "references", "returning", "right", "select", "session_user", "similar", "some",
    "symmetric", "table", "tablesample", "then", "to", "trailing", "true", "union",
    "unique", "user", "using", "variadic", "verbose", "when", "where", "window", "with",
}


def sanitize(name: str) -> str:
    """Turn a messy header/filename into a safe SQL identifier."""
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower()).strip("_")
    if not name:
        name = "col"
    if name[0].isdigit():
        name = "c_" + name
    return name


def make_safe_unique(names: list[str]) -> list[str]:
    """Rename reserved-word columns and de-duplicate repeated names."""
    out: list[str] = []
    counts: dict[str, int] = {}
    for n in names:
        if n in RESERVED:
            n = n + "_"
        if n in counts:
            counts[n] += 1
            n = f"{n}_{counts[n]}"
        else:
            counts[n] = 1
        out.append(n)
    return out


def _is_int(v: str) -> bool:
    try:
        int(v)
        return True
    except ValueError:
        return False


def _is_float(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def infer_type(values: list[str]) -> str:
    """Look at a column's values and decide INTEGER / NUMERIC / TEXT."""
    seen = [v.strip() for v in values if v.strip() != ""]
    if not seen:
        return "TEXT"
    if all(_is_int(v) for v in seen):
        return "INTEGER"
    if all(_is_float(v) for v in seen):
        return "NUMERIC"
    return "TEXT"


def coerce(value: str, sql_type: str):
    """Convert a CSV string into the right Python type for its column."""
    if value is None or value.strip() == "":
        return None
    if sql_type == "INTEGER":
        return int(value)
    if sql_type == "NUMERIC":
        return float(value)
    return value


def load_csv(path: str, table: str | None = None) -> int:
    import psycopg

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = make_safe_unique([sanitize(h) for h in next(reader)])
        data = list(reader)

    if table is None:
        table = sanitize(path.split("/")[-1].rsplit(".", 1)[0])

    # infer a type per column from the loaded rows
    types = []
    for i in range(len(header)):
        col_values = [row[i] for row in data if i < len(row)]
        types.append(infer_type(col_values))

    # quote every identifier so reserved words / odd names are always safe
    col_defs = ", ".join(f'"{h}" {t}' for h, t in zip(header, types))
    col_list = ", ".join(f'"{h}"' for h in header)
    tbl = f'"{table}"'

    dsn = get_settings().database_url
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
        cur.execute(f"CREATE TABLE {tbl} ({col_defs})")
        with cur.copy(f"COPY {tbl} ({col_list}) FROM STDIN") as copy:
            for row in data:
                row = row + [""] * (len(header) - len(row))      # pad short rows
                copy.write_row([coerce(row[i], types[i]) for i in range(len(header))])

    print(f"Loaded {len(data)} rows into table '{table}'.")
    print(f"Columns: {col_defs}")
    return len(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.load_data <path-to-csv> [table_name]")
        sys.exit(1)
    load_csv(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
