"""Resolve per-user Minglefield paths without hardcoded Windows user profiles.

This module is intentionally independent of the current working directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath


class PlatformPathError(ValueError):
    pass


def user_paths(*, platform: str | None = None, environ=None, home: str | Path | None = None) -> dict[str, PurePosixPath | PureWindowsPath]:
    platform = sys.platform if platform is None else platform
    env = os.environ if environ is None else environ
    home_value = str(Path.home()) if home is None else str(home)
    home_path = PureWindowsPath(home_value) if platform == "win32" else PurePosixPath(home_value)
    if platform == "win32":
        local = env.get("LOCALAPPDATA")
        if not local or not PureWindowsPath(local).is_absolute():
            raise PlatformPathError("LOCALAPPDATA must be an absolute directory on Windows")
        base = PureWindowsPath(local)
        return {"install": base / "Programs" / "Minglefield",
                "data": base / "Minglefield"}
    if platform == "darwin":
        base = home_path / "Library" / "Application Support"
        return {"install": home_path / "Applications" / "Minglefield.app",
                "data": base / "Minglefield"}
    if platform.startswith("linux"):
        data = env.get("XDG_DATA_HOME")
        data_root = PurePosixPath(data) if data else home_path / ".local" / "share"
        if not data_root.is_absolute():
            raise PlatformPathError("XDG_DATA_HOME must be absolute")
        return {"install": home_path / ".local" / "opt" / "minglefield",
                "data": data_root / "minglefield"}
    raise PlatformPathError("unsupported operating system")
