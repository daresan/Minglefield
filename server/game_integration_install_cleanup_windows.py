"""Read-only native Windows directory-handle inspection for installer staging.

No deletion or authorization. Open directory handles without FILE_SHARE_DELETE,
so cooperative Windows rename/delete requests are denied while handles live.
The native deletion backend is not implemented.
"""
import os


def inspect_windows_directory_handle(path):
    def result(state, reason, **extra):
        return {"state": state, "reason": reason,
                "cleanup_allowed": False, "deletion_performed": False, **extra}
    if os.name != "nt":
        return result("unavailable", "windows_only")
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
        return result("blocked", "invalid_directory_path")
    import ctypes
    from ctypes import wintypes

    FILE_READ_ATTRIBUTES = 0x80
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_ATTRIBUTE_DIRECTORY = 0x10
    FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_handle = kernel32.CreateFileW
    open_handle.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                            wintypes.HANDLE]
    open_handle.restype = wintypes.HANDLE
    get_info = kernel32.GetFileInformationByHandle
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
    get_info.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_handle(os.path.abspath(path), FILE_READ_ATTRIBUTES,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                         OPEN_EXISTING,
                         FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
                         None)
    if handle in (None, INVALID_HANDLE_VALUE):
        return result("blocked", "windows_directory_open_failed")
    try:
        info = BY_HANDLE_FILE_INFORMATION()
        if not get_info(handle, ctypes.byref(info)):
            return result("blocked", "windows_directory_info_failed")
        if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
            return result("blocked", "windows_reparse_point")
        if not info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY:
            return result("blocked", "not_directory")
        return result("inspected", "native_directory_identity_observed",
                      volume_serial=int(info.dwVolumeSerialNumber),
                      file_index=(int(info.nFileIndexHigh) << 32)
                      | int(info.nFileIndexLow))
    finally:
        close_handle(handle)


def inspect_windows_staging_binding(root, operation_id):
    """Inspect root and operation while both no-delete-share handles are held.

    Read-only diagnostic, not a cleanup authorization. The parent-to-child
    open is still path-based; a future executor must use native relative
    opens and handle-based disposition before permitting deletion.
    """
    import re
    def denied(reason):
        return {"state": "blocked", "reason": reason,
                "cleanup_allowed": False, "deletion_performed": False}
    if os.name != "nt":
        return denied("windows_only")
    if (not isinstance(operation_id, str) or not operation_id
            or operation_id in (".", "..")
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", operation_id)
            or operation_id.endswith((".", " "))):
        return denied("invalid_install_operation")
    from game_integration_install_path_safety import has_redirecting_component
    if has_redirecting_component(root):
        return denied("unsafe_installation_staging_root")
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_file = kernel32.CreateFileW
    open_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                          wintypes.HANDLE]
    open_file.restype = wintypes.HANDLE
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    get_info = kernel32.GetFileInformationByHandle
    class Info(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD),
                    ("created", wintypes.FILETIME),
                    ("accessed", wintypes.FILETIME),
                    ("modified", wintypes.FILETIME),
                    ("volume", wintypes.DWORD),
                    ("size_high", wintypes.DWORD),
                    ("size_low", wintypes.DWORD),
                    ("links", wintypes.DWORD),
                    ("index_high", wintypes.DWORD),
                    ("index_low", wintypes.DWORD)]
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    get_info.restype = wintypes.BOOL
    invalid = ctypes.c_void_p(-1).value
    handles = []
    try:
        for path in (root, os.path.join(root, operation_id)):
            handle = open_file(os.path.abspath(path), 0x80, 0x1 | 0x2,
                               None, 3, 0x02000000 | 0x00200000, None)
            if handle in (None, invalid):
                return denied("windows_directory_open_failed")
            handles.append(handle)
            info = Info()
            if not get_info(handle, ctypes.byref(info)):
                return denied("windows_directory_info_failed")
            if info.attributes & 0x400:
                return denied("windows_reparse_point")
            if not info.attributes & 0x10:
                return denied("not_directory")
        # A second, path-based observation detects a changed binding while
        # the native handles are still held. This remains a diagnostic, not
        # a substitute for native handle-relative opens in a writer.
        for path, handle in zip((root, os.path.join(root, operation_id)), handles):
            observed = inspect_windows_directory_handle(path)
            if observed["state"] != "inspected":
                return denied("windows_staging_binding_changed")
            held = Info()
            if not get_info(handle, ctypes.byref(held)):
                return denied("windows_directory_info_failed")
            if (observed["volume_serial"] != int(held.volume)
                    or observed["file_index"] !=
                    ((int(held.index_high) << 32) | int(held.index_low))):
                return denied("windows_staging_binding_changed")
        return {"state": "inspected", "reason": "native_staging_handles_observed",
                "cleanup_allowed": False, "deletion_performed": False}
    finally:
        for handle in reversed(handles):
            close(handle)


def inspect_windows_staged_file(path):
    """Read-only native handle probe for a single staged regular file.

    Reject reparse points, directories and hardlinks before a future cleanup
    executor may consider a file. This does not grant deletion authority and
    does not protect against a subsequent path swap.
    """
    def denied(reason):
        return {"state": "blocked", "reason": reason,
                "cleanup_allowed": False, "deletion_performed": False}
    if os.name != "nt":
        return denied("windows_only")
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
        return denied("invalid_staged_file_path")
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_file = kernel32.CreateFileW
    open_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                          wintypes.HANDLE]
    open_file.restype = wintypes.HANDLE
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    class Info(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD),
                    ("created", wintypes.FILETIME),
                    ("accessed", wintypes.FILETIME),
                    ("modified", wintypes.FILETIME),
                    ("volume", wintypes.DWORD),
                    ("size_high", wintypes.DWORD),
                    ("size_low", wintypes.DWORD),
                    ("links", wintypes.DWORD),
                    ("index_high", wintypes.DWORD),
                    ("index_low", wintypes.DWORD)]

    get_info = kernel32.GetFileInformationByHandle
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    get_info.restype = wintypes.BOOL
    invalid = ctypes.c_void_p(-1).value
    handle = open_file(os.path.abspath(path), 0x80, 0x1 | 0x2, None, 3,
                       0x00200000, None)  # OPEN_REPARSE_POINT
    if handle in (None, invalid):
        return denied("windows_staged_file_open_failed")
    try:
        info = Info()
        if not get_info(handle, ctypes.byref(info)):
            return denied("windows_staged_file_info_failed")
        if info.attributes & 0x400:
            return denied("windows_reparse_point")
        if info.attributes & 0x10:
            return denied("not_regular_file")
        if info.links != 1:
            return denied("unsafe_staging_hardlink")
        return {"state": "inspected", "reason": "native_staged_file_observed",
                "volume_serial": int(info.volume),
                "file_index": (int(info.index_high) << 32) | int(info.index_low),
                "cleanup_allowed": False, "deletion_performed": False}
    finally:
        close(handle)
