"""Experimental Windows handle-bound deletion of a single isolated regular file.

Not connected to journal, HTTP, staging cleanup or production execution.
Only call with a disposable test file under a trusted private directory.
"""
import os


def delete_isolated_regular_file_by_handle(path, *, expected_volume_serial=None,
                                           expected_file_index=None,
                                           expected_parent_volume_serial=None,
                                           expected_parent_file_index=None):
    """Delete the opened file object, never a later replacement at its pathname.

    The caller must supply expected native file and parent identities.
    A replaced file is rejected after opening, before disposition.
    This low-level primitive is intentionally not an authorization boundary.
    Callers must independently establish owner, journal, root, plan and
    directory binding; until then production cleanup remains disabled.
    """
    def result(state, reason):
        return {"state": state, "reason": reason,
                "deletion_performed": state == "removed",
                "cleanup_allowed": False}
    if os.name != "nt":
        return result("blocked", "windows_only")
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
        return result("blocked", "invalid_file_path")
    if (not isinstance(expected_volume_serial, int) or isinstance(expected_volume_serial, bool)
            or not isinstance(expected_file_index, int) or isinstance(expected_file_index, bool)
            or expected_volume_serial < 0 or expected_file_index < 0):
        return result("blocked", "expected_file_identity_required")
    if (not isinstance(expected_parent_volume_serial, int)
            or isinstance(expected_parent_volume_serial, bool)
            or not isinstance(expected_parent_file_index, int)
            or isinstance(expected_parent_file_index, bool)
            or expected_parent_volume_serial < 0 or expected_parent_file_index < 0):
        return result("blocked", "expected_parent_identity_required")
    from game_integration_install_cleanup_windows import inspect_windows_directory_handle

    def parent_matches():
        parent = inspect_windows_directory_handle(os.path.dirname(os.path.abspath(path)))
        return (parent["state"] == "inspected"
                and parent["volume_serial"] == expected_parent_volume_serial
                and parent["file_index"] == expected_parent_file_index)

    if not parent_matches():
        return result("blocked", "native_parent_identity_mismatch")
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    get_info = kernel.GetFileInformationByHandle
    class Info(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD),
                    ("created", wintypes.FILETIME), ("accessed", wintypes.FILETIME),
                    ("modified", wintypes.FILETIME), ("volume", wintypes.DWORD),
                    ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
                    ("links", wintypes.DWORD), ("index_high", wintypes.DWORD),
                    ("index_low", wintypes.DWORD)]
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    get_info.restype = wintypes.BOOL
    class Disposition(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]
    set_info = kernel.SetFileInformationByHandle
    set_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                         wintypes.DWORD]
    set_info.restype = wintypes.BOOL

    # DELETE | FILE_READ_ATTRIBUTES; share reads/writes, not deletion.
    handle = create(os.path.abspath(path), 0x00010000 | 0x80,
                    0x1 | 0x2, None, 3, 0x00200000, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        return result("blocked", "native_file_open_failed")
    try:
        info = Info()
        if not get_info(handle, ctypes.byref(info)):
            return result("blocked", "native_file_info_failed")
        if info.attributes & 0x400:
            return result("blocked", "windows_reparse_point")
        if info.attributes & 0x10:
            return result("blocked", "not_regular_file")
        if info.links != 1:
            return result("blocked", "unsafe_staging_hardlink")
        observed_index = (int(info.index_high) << 32) | int(info.index_low)
        if (int(info.volume) != expected_volume_serial
                or observed_index != expected_file_index):
            return result("blocked", "native_file_identity_mismatch")
        # Defense in depth only: this path-based parent observation is not
        # atomic with file open/disposition. A future executor must use
        # handle-relative child opens and bind the journal transaction.
        if not parent_matches():
            return result("blocked", "native_parent_identity_mismatch")
        disposition = Disposition(True)
        # FILE_INFO_BY_HANDLE_CLASS FileDispositionInfo = 4
        if not set_info(handle, 4, ctypes.byref(disposition),
                        ctypes.sizeof(disposition)):
            return result("blocked", "native_file_disposition_failed")
        return result("removed", "handle_bound_file_disposition_set")
    finally:
        close(handle)
