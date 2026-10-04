from __future__ import annotations

import os
import stat
from pathlib import Path


def is_reparse_point(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def validate_path(path: Path, root: Path) -> None:
    path = Path(os.path.abspath(path))
    root = Path(os.path.abspath(root))
    for candidate in dict.fromkeys((path, *path.parents, root, *root.parents)):
        try:
            if is_reparse_point(candidate):
                raise ValueError("reparse_point_rejected")
        except FileNotFoundError:
            continue
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("path_outside_root")
