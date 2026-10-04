from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from music_folder_builder.infrastructure.fs.path_safety import is_reparse_point, validate_path


class FileMutationGateway:
    def __init__(self) -> None:
        self._handles: dict[Path, int] = {}
        self._directories: dict[Path, int] = {}

    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    @contextmanager
    def guarded_paths(
        self, source: Path, target: Path, source_root: Path, target_root: Path
    ) -> Iterator[None]:
        validate_path(source, source_root)
        validate_path(target, target_root)
        handles: list[int] = []
        try:
            if os.name == "nt":
                for parent in dict.fromkeys((*reversed(source.parent.parents), source.parent,
                                             *reversed(target.parent.parents), target.parent)):
                    if not parent.exists():
                        parent.mkdir()
                    handle = _open_handle(parent, directory=True)
                    handles.append(handle)
                    self._directories[parent.absolute()] = handle
                    if is_reparse_point(parent):
                        raise ValueError("reparse_point_rejected")
                handle = _open_handle(source)
                handles.append(handle)
                self._handles[source.absolute()] = handle
                if is_reparse_point(source):
                    raise ValueError("reparse_point_rejected")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
            validate_path(source, source_root)
            validate_path(target, target_root)
            yield
        finally:
            for handle in self._handles.values():
                if handle not in handles:
                    _close_handle(handle)
            self._handles.clear()
            self._directories.clear()
            for handle in reversed(handles):
                _close_handle(handle)

    def move(self, source: str | Path, target: str | Path) -> None:
        source, target = Path(source), Path(target)
        if os.name == "nt":
            _rename_handle(self._handles[source.absolute()], target,
                           self._directories[target.parent.absolute()])
        else:
            # Link publishes without replacing a competing destination, then removes the source.
            os.link(source, target, follow_symlinks=False)
            source.unlink()

    def copy(self, source: str | Path, target: str | Path) -> None:
        source, target = Path(source), Path(target)
        if os.name == "nt":
            handle = _create_relative_handle(target.name, self._directories[target.parent.absolute()])
            self._handles[target.absolute()] = handle
            try:
                with _handle_file(self._handles[source.absolute()], "rb") as input_file:
                    with _handle_file(handle, "wb") as output_file:
                        shutil.copyfileobj(input_file, output_file)
                        output_file.flush()
                        os.fsync(output_file.fileno())
                _copy_times(self._handles[source.absolute()], handle)
            except BaseException:
                _delete_handle(handle)
                raise
        else:
            with source.open("rb") as input_file, target.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file)
                output_file.flush()
                os.fsync(output_file.fileno())

    def delete(self, path: str | Path) -> None:
        path = Path(path)
        if os.name == "nt":
            _delete_handle(self._handles[path.absolute()])
        else:
            path.unlink()

    def size(self, path: str | Path) -> int:
        return Path(path).stat().st_size

    def same_volume(self, source: str | Path, target: str | Path) -> bool:
        source_path, target_path = Path(source), Path(target)
        source_anchor = source_path.anchor or source_path.parts[0]
        target_anchor = target_path.anchor or target_path.parts[0]
        return source_anchor.casefold() == target_anchor.casefold()


# Pin Windows directory/file identities without FILE_SHARE_DELETE or FILE_SHARE_WRITE
# for files, so reparse retargeting, file substitution and concurrent writers fail.
if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _kernel.CreateFileW.restype = wintypes.HANDLE
    _kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel.CloseHandle.restype = wintypes.BOOL
    _kernel.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    _kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    _kernel.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel.DuplicateHandle.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
    ]
    _kernel.DuplicateHandle.restype = wintypes.BOOL

    def _open_handle(path: Path, *, directory: bool = False, create: bool = False) -> int:
        access = 0x81 if directory else 0x80000000 | 0x10000
        if create:
            access |= 0x40000000
        flags = 0x00200000 | (0x02000000 if directory else 0x80)
        handle = _kernel.CreateFileW(str(path.absolute()), access, 3 if directory else 1,
                                    None, 1 if create else 3, flags, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    def _create_relative_handle(name: str, directory_handle: int) -> int:
        # Resolve against the pinned directory object, never a path that can be retargeted.
        class UnicodeString(ctypes.Structure):
            _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT),
                        ("Buffer", wintypes.LPWSTR)]
        class ObjectAttributes(ctypes.Structure):
            _fields_ = [("Length", wintypes.ULONG), ("RootDirectory", wintypes.HANDLE),
                        ("ObjectName", ctypes.POINTER(UnicodeString)), ("Attributes", wintypes.ULONG),
                        ("SecurityDescriptor", ctypes.c_void_p), ("SecurityQualityOfService", ctypes.c_void_p)]
        class IoStatus(ctypes.Structure):
            _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]
        buffer = ctypes.create_unicode_buffer(name)
        length = len(name.encode("utf-16-le"))
        string = UnicodeString(length, length + 2, ctypes.cast(buffer, wintypes.LPWSTR))
        attributes = ObjectAttributes(ctypes.sizeof(ObjectAttributes), directory_handle,
                                      ctypes.pointer(string), 0x40, None, None)
        native = ctypes.WinDLL("ntdll")
        native.NtCreateFile.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
            ctypes.POINTER(ObjectAttributes), ctypes.POINTER(IoStatus), ctypes.c_void_p,
            wintypes.ULONG, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
            ctypes.c_void_p, wintypes.ULONG]
        native.NtCreateFile.restype = ctypes.c_long
        native.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        native.RtlNtStatusToDosError.restype = wintypes.ULONG
        handle, status_block = wintypes.HANDLE(), IoStatus()
        status = native.NtCreateFile(ctypes.byref(handle), 0xC0110080, ctypes.byref(attributes),
            ctypes.byref(status_block), None, 0x80, 1, 2, 0x200000 | 0x40 | 0x20, None, 0)
        if status < 0:
            raise ctypes.WinError(native.RtlNtStatusToDosError(status))
        return int(handle.value)

    def _close_handle(handle: int) -> None:
        _kernel.CloseHandle(handle)

    def _handle_file(handle: int, mode: str):
        duplicate = wintypes.HANDLE()
        process = _kernel.GetCurrentProcess()
        if not _kernel.DuplicateHandle(process, handle, process, ctypes.byref(duplicate), 0, False, 2):
            raise ctypes.WinError(ctypes.get_last_error())
        flags = os.O_BINARY | (os.O_RDONLY if mode == "rb" else os.O_WRONLY)
        return os.fdopen(msvcrt.open_osfhandle(duplicate.value, flags), mode)

    def _rename_handle(handle: int, target: Path, directory_handle: int) -> None:
        filename = target.name.encode("utf-16-le")
        class RenameInfo(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                        ("FileNameLength", wintypes.DWORD),
                        ("FileName", ctypes.c_ubyte * (len(filename) + 2))]
        info = RenameInfo()
        info.RootDirectory = directory_handle
        info.FileNameLength = len(filename)
        ctypes.memmove(ctypes.addressof(info) + RenameInfo.FileName.offset,
                       filename, len(filename))
        class IoStatus(ctypes.Structure):
            _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]
        native = ctypes.WinDLL("ntdll")
        native.NtSetInformationFile.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(IoStatus), ctypes.c_void_p,
            wintypes.ULONG, ctypes.c_int,
        ]
        native.NtSetInformationFile.restype = ctypes.c_long
        native.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        native.RtlNtStatusToDosError.restype = wintypes.ULONG
        status_block = IoStatus()
        status = native.NtSetInformationFile(
            handle, ctypes.byref(status_block), ctypes.byref(info), ctypes.sizeof(info), 10
        )
        if status < 0:
            raise ctypes.WinError(native.RtlNtStatusToDosError(status))

    def _delete_handle(handle: int) -> None:
        delete = wintypes.BOOLEAN(True)
        if not _kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(delete), ctypes.sizeof(delete)):
            raise ctypes.WinError(ctypes.get_last_error())

    def _copy_times(source: int, target: int) -> None:
        _kernel.GetFileTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME)]
        _kernel.SetFileTime.argtypes = _kernel.GetFileTime.argtypes
        created, accessed, modified = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not _kernel.GetFileTime(source, ctypes.byref(created), ctypes.byref(accessed),
                                   ctypes.byref(modified)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not _kernel.SetFileTime(target, ctypes.byref(created), ctypes.byref(accessed),
                                   ctypes.byref(modified)):
            raise ctypes.WinError(ctypes.get_last_error())
