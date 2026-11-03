"""Portable fail-closed detection of filesystem redirection components.

On Windows, junctions and other reparse points are not reliably covered by
Path.is_symlink(), especially with Python 3.11.
"""
import os
import stat
from pathlib import Path

_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def is_redirecting_path(path):
    """True for symlinks and Windows reparse points; never follow the entry."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError:
        return True  # Uninspectable paths are unsafe.
    return (stat.S_ISLNK(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT))


def has_redirecting_component(path):
    """Inspect every existing ancestor including the supplied path."""
    current = Path(os.path.abspath(path))
    while True:
        if is_redirecting_path(current):
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent
