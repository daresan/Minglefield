"""Fail-closed SQLCipher connection boundary for the existing local Alpha store.

This module deliberately does not create encrypted databases or persist keys.
The installer creates/verifies a separate destination; a future authenticated
first-run flow supplies an in-memory key provider to AlphaAuthStore. Legacy
plaintext operation is retained *only* for the existing local Alpha prototype.
"""
from __future__ import annotations

import importlib
import sqlite3
import stat
from pathlib import Path


SQLITE_HEADER = b"SQLite format 3\x00"


class AlphaDatabaseOpenError(RuntimeError):
    """Stable, non-secret-bearing reason for a rejected database connection."""


def sqlcipher_driver():
    """Load only the reviewed SQLCipher DB-API package; no plaintext fallback."""
    try:
        driver = importlib.import_module("sqlcipher3.dbapi2")
        if not callable(getattr(driver, "connect", None)):
            raise ImportError("invalid SQLCipher DB-API")
        if not isinstance(getattr(driver, "IntegrityError", None), type):
            raise ImportError("invalid SQLCipher DB-API error type")
        return driver
    except (ImportError, AttributeError, OSError) as exc:
        raise AlphaDatabaseOpenError("sqlcipher_runtime_unavailable") from None


def integrity_error_type(*, encrypted=False):
    """Return the DB-API-specific exception caught at the existing Host boundary."""
    return sqlcipher_driver().IntegrityError if encrypted else sqlite3.IntegrityError


def _source_header(path):
    """Read an existing database; no automatic creation or symlink traversal."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise AlphaDatabaseOpenError("database_source_unavailable") from None
    if not stat.S_ISREG(metadata.st_mode):
        raise AlphaDatabaseOpenError("database_source_not_regular")
    try:
        with path.open("rb") as source:
            header = source.read(16)
    except OSError:
        raise AlphaDatabaseOpenError("database_source_unavailable") from None
    if len(header) != 16:
        raise AlphaDatabaseOpenError("database_header_invalid")
    return header


def open_alpha_database(database, *, key_provider=None, driver=None):
    """Open existing encrypted DB using SQLCipher or legacy plaintext with sqlite3.

    A key provider must be an explicit callable returning a password in memory,
    never an environment variable, command line, database field or config file.
    An encrypted file never falls back to sqlite3. The encrypted mode refuses
    plaintext and nonexistent paths; it cannot be used to create a database.
    """
    path = Path(database)
    encrypted = key_provider is not None
    header = _source_header(path)
    if encrypted:
        if header is None:
            raise AlphaDatabaseOpenError("encrypted_database_not_found")
        if header == SQLITE_HEADER:
            raise AlphaDatabaseOpenError("encrypted_database_required")
        if not callable(key_provider):
            raise AlphaDatabaseOpenError("invalid_key_provider")
        try:
            key = key_provider()
        except BaseException:
            raise AlphaDatabaseOpenError("database_key_unavailable") from None
        if type(key) is not str or not 1 <= len(key) <= 4096 or "\x00" in key:
            raise AlphaDatabaseOpenError("database_key_unavailable")
        api = driver if driver is not None else sqlcipher_driver()
        connection = None
        try:
            # URI mode=rw prevents silent recreation if the file disappears.
            # Driver and data paths are external to the source repository.
            uri = path.resolve(strict=True).as_uri() + "?mode=rw"
            connection = api.connect(uri, timeout=10, isolation_level=None, uri=True)
            # PRAGMA values cannot be bound by SQLite. Quote the passphrase as
            # a SQL string literal with doubled apostrophes. Do not log SQL.
            connection.execute("PRAGMA key = '" + key.replace("'", "''") + "'")
            version = connection.execute("PRAGMA cipher_version").fetchone()
            if not version or not version[0]:
                raise AlphaDatabaseOpenError("sqlcipher_engine_unverified")
            connection.execute("SELECT count(*) FROM sqlite_schema").fetchone()
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except Exception:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            raise AlphaDatabaseOpenError("sqlcipher_unlock_or_open_failed") from None
    if header is not None and header != SQLITE_HEADER:
        raise AlphaDatabaseOpenError("encrypted_database_key_required")
    # The preexisting local Alpha developer mode is retained. This is NOT the
    # installed Minglefield runtime and does not authorize plaintext installs.
    try:
        return sqlite3.connect(str(path), timeout=10, isolation_level=None)
    except sqlite3.Error:
        raise AlphaDatabaseOpenError("legacy_sqlite_open_failed") from None
