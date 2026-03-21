from __future__ import annotations

from pathlib import Path

from music_folder_builder.gui.app import MusicFolderBuilderApp


def main() -> int:
    app = MusicFolderBuilderApp(default_config_path=Path("config/local.toml"))
    app.run()
    return 0
