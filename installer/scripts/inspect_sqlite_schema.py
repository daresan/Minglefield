"""Read-only SQLite integrity and schema inventory for installer diagnostics.

This module never executes schema SQL or changes the source database.
The SQLite backup API creates a consistent in-memory snapshot, including WAL.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def inspect_sqlite(path: str | Path) -> dict:
    source = Path(path)
    result = {
        "status": "inspection_failed",
        "integrityOk": False,
        "applicationId": None,
        "userVersion": None,
        "tables": [],
    }
    if not source.is_file() or source.is_symlink():
        result["error"] = "not_a_regular_file"
        return result
    try:
        if source.stat().st_size > 1024 * 1024 * 1024:
            result["error"] = "file_too_large"
            return result
        # Reject URI injection by using an absolute Path and URI encoding.
        uri = source.resolve(strict=True).as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=3) as db:
            with sqlite3.connect(":memory:") as snapshot:
                db.backup(snapshot, pages=128, sleep=0.05)
                check = snapshot.execute("PRAGMA quick_check").fetchall()
                if check != [("ok",)]:
                    result["status"] = "integrity_failed"
                    return result
                result["integrityOk"] = True
                result["applicationId"] = snapshot.execute(
                    "PRAGMA application_id"
                ).fetchone()[0]
                result["userVersion"] = snapshot.execute(
                    "PRAGMA user_version"
                ).fetchone()[0]
                rows = snapshot.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
                if len(rows) > 4096:
                    result["status"] = "too_many_tables"
                    return result
                for (name,) in rows:
                    # table_xinfo accepts a bound table name on supported SQLite.
                    columns = snapshot.execute(
                        "SELECT name FROM pragma_table_xinfo(?) ORDER BY cid",
                        (name,),
                    ).fetchall()
                    result["tables"].append({
                        "name": name,
                        "columns": [col[0] for col in columns],
                    })
                result["status"] = "sqlite_integrity_verified_schema_unclassified"
    except (sqlite3.Error, OSError, ValueError) as exc:
        # Never expose raw exception strings: they may contain private paths.
        result["error"] = type(exc).__name__
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    args = parser.parse_args()
    print(json.dumps(inspect_sqlite(args.database), indent=2))
