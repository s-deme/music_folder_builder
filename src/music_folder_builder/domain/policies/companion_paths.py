from pathlib import PureWindowsPath

COMPANION_IMAGE_EXTENSIONS = (".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp")


def register_source_dir_targets(
    *,
    source_dir_targets: dict[str, set[str]],
    source_path: PureWindowsPath,
    source_root: PureWindowsPath,
    target_path: PureWindowsPath,
) -> None:
    current_source = source_path.parent
    current_target = target_path.parent
    while True:
        source_dir_targets.setdefault(str(current_source), set()).add(str(current_target))
        if current_source == source_root:
            return
        parent_source = current_source.parent
        parent_target = current_target.parent
        if parent_source == current_source or parent_target == current_target:
            return
        current_source = parent_source
        current_target = parent_target
