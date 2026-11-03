"""Experimental Windows NtCreateFile relative-open and handle disposition.

Only for disposable test files. No journal binding, no production integration.
"""
import os
import re


def delete_relative_test_file(parent_path, child_name, *,
                              expected_parent_volume_serial=None,
                              expected_parent_file_index=None,
                              expected_file_volume_serial=None,
                              expected_file_index=None, _test_before_disposition=None):
    def denied(reason):
        return {"state": "blocked", "reason": reason,
                "deletion_performed": False, "cleanup_allowed": False}
    if os.name != "nt":
        return denied("windows_only")
    if (not isinstance(child_name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", child_name)
            or child_name in (".", "..") or child_name.endswith((".", " "))):
        return denied("invalid_child_name")
    if not isinstance(parent_path, (str, os.PathLike)) or not os.fspath(parent_path):
        return denied("invalid_parent_path")
    identities = (expected_parent_volume_serial, expected_parent_file_index,
                  expected_file_volume_serial, expected_file_index)
    if any(type(value) is not int or value < 0 for value in identities):
        return denied("expected_native_identities_required")
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

    class Disposition(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]

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
    set_info = kernel.SetFileInformationByHandle
    set_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    set_info.restype = wintypes.BOOL

    def identity(info):
        return int(info.volume), (int(info.index_high) << 32) | int(info.index_low)

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
        if identity(parent_info) != identities[:2]:
            return denied("native_parent_identity_mismatch")
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
        # DELETE | FILE_READ_ATTRIBUTES | SYNCHRONIZE.
        # FILE_NON_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT.
        status = nt_create(ctypes.byref(child), 0x10000 | 0x80 | 0x100000,
                           ctypes.byref(attrs), ctypes.byref(io), None, 0,
                           0x1 | 0x2, 1, 0x40 | 0x00200000 | 0x20, None, 0)
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
            if identity(info) != identities[2:]:
                return denied("native_file_identity_mismatch")
            # Test-only deterministic scheduling point; never wired into runtime.
            if _test_before_disposition is not None:
                _test_before_disposition()
            # Verify held handles remain the expected objects after the test hook.
            if not get_info(parent, ctypes.byref(parent_info)):
                return denied("native_parent_info_failed")
            if identity(parent_info) != identities[:2] or parent_info.attributes & 0x400:
                return denied("native_parent_identity_mismatch")
            if not get_info(child, ctypes.byref(info)):
                return denied("native_child_info_failed")
            if (identity(info) != identities[2:] or info.attributes & 0x400
                    or info.attributes & 0x10 or info.links != 1):
                return denied("native_file_identity_changed")
            disposition = Disposition(True)
            if not set_info(child, 4, ctypes.byref(disposition),
                            ctypes.sizeof(disposition)):
                return denied("native_file_disposition_failed")
            return {"state": "removed", "reason": "relative_handle_disposition_set",
                    "deletion_performed": True, "cleanup_allowed": False}
        finally:
            close(child)
    finally:
        close(parent)
