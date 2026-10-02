"""Tiny login handler for the fix-bug eval. The bug is real: the surname is
interpolated into SQL, so an apostrophe breaks the query and login returns 500."""

import sqlite3


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, surname TEXT)")
    db.executemany("INSERT INTO users (surname) VALUES (?)", [("Smith",), ("O'Brien",)])
    return db


def login(surname: str) -> int:
    """HTTP-style status: 200 found, 404 unknown, 500 on error."""
    try:
        row = _db().execute(f"SELECT id FROM users WHERE surname = '{surname}'").fetchone()
    except sqlite3.Error:
        return 500
    return 200 if row else 404


if __name__ == "__main__":
    import sys
    print(login(sys.argv[1] if len(sys.argv) > 1 else "Smith"))
