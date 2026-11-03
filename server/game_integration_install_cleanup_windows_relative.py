"""Experimental read-only NtCreateFile child open relative to held parent handle.

No deletion, journal authority, or production cleanup integration.
"""
import os
import re


def inspect_windows_relative_child(parent_path, child_name):
    def denied(reason):
        return {"state": "blocked", "reason": reason,
                "cleanup_allowed": False, "deletion_performed": False}
    if os.name != "nt":
        return denied("windows_only")
    if (not isinstance(child_name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", child_name)
            or child_name in (".", "..") or child_name.endswith((".", " "))):
        return denied("invalid_child_name")
    if not isinstance(parent_path, (str, os.PathLike)) or not os.fspath(parent_path):
        return denied("invalid_parent_path")
    from game_integration_install_path_safety import has_redirecting_component
    if has_redirecting_component(parent_path):
        return denied("unsafe_parent_path")
    import ctypes
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = [("length", wintypes.USHORT), ("maximum", wintypes.USHORT),
                    ("buffer", ctypes.c_void_p)]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.ULONG), ("root", wintypes.HANDLE),
                    ("name", ctypes.POINTER(UnicodeString)),
                    ("attributes", wintypes.ULONG), ("security", ctypes.c_void_p),
                    ("quality", ctypes.c_void_p)]

    class IoStatusBlock(ctypes.Structure):
        _fields_ = [("status", ctypes.c_void_p), ("information", ctypes.c_size_t)]

    class Info(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD),
                    ("created", wintypes.FILETIME), ("accessed", wintypes.FILETIME),
                    ("modified", wintypes.FILETIME), ("volume", wintypes.DWORD),
                    ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
                    ("links", wintypes.DWORD), ("index_high", wintypes.DWORD),
                    ("index_low", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    get_info = kernel.GetFileInformationByHandle
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    get_info.restype = wintypes.BOOL

    # FILE_READ_ATTRIBUTES | FILE_TRAVERSE, no delete sharing.
    parent = create(os.path.abspath(parent_path), 0x80 | 0x20, 0x1 | 0x2,
                    None, 3, 0x02000000 | 0x00200000, None)
    if parent in (None, ctypes.c_void_p(-1).value):
        return denied("native_parent_open_failed")
    try:
        parent_info = Info()
        if not get_info(parent, ctypes.byref(parent_info)):
            return denied("native_parent_info_failed")
        if parent_info.attributes & 0x400 or not parent_info.attributes & 0x10:
            return denied("unsafe_native_parent")
        nt_create = ctypes.WinDLL("ntdll").NtCreateFile
        nt_create.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG,
                              ctypes.POINTER(ObjectAttributes),
                              ctypes.POINTER(IoStatusBlock), ctypes.c_void_p,
                              wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
                              wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
        nt_create.restype = ctypes.c_long
        buffer = ctypes.create_unicode_buffer(child_name)
        name = UnicodeString(len(child_name) * 2, (len(child_name) + 1) * 2,
                             ctypes.cast(buffer, ctypes.c_void_p).value)
        attrs = ObjectAttributes(ctypes.sizeof(ObjectAttributes), parent,
                                 ctypes.pointer(name), 0x40, None, None)
        io = IoStatusBlock()
        child = wintypes.HANDLE()
        # Relative RootDirectory open; no path reconstruction.
        # FILE_READ_ATTRIBUTES | SYNCHRONIZE; FILE_OPEN; OPEN_REPARSE_POINT.
        status = nt_create(ctypes.byref(child), 0x80 | 0x100000,
                           ctypes.byref(attrs), ctypes.byref(io), None, 0,
                           0x1 | 0x2, 1, 0x00200000 | 0x20, None, 0)
        if status < 0:
            return denied("native_relative_open_failed")
        try:
            info = Info()
            if not get_info(child, ctypes.byref(info)):
                return denied("native_child_info_failed")
            if info.attributes & 0x400:
                return denied("windows_reparse_point")
            if info.attributes & 0x10:
                return denied("not_regular_file")
            if info.links != 1:
                return denied("unsafe_staging_hardlink")
            return {"state": "inspected", "reason": "native_relative_child_observed",
                    "volume_serial": int(info.volume),
                    "file_index": (int(info.index_high) << 32) | int(info.index_low),
                    "cleanup_allowed": False, "deletion_performed": False}
        finally:
            close(child)
    finally:
        close(parent)
