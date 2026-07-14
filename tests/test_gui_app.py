import unittest
from types import ModuleType
from unittest.mock import patch

from music_folder_builder.gui.query_service import PlanItemRow


def _fake_tkinter_modules() -> dict[str, ModuleType]:
    tkinter = ModuleType("tkinter")
    tkinter.Widget = object
    tkinter.Tk = object
    tkinter.Toplevel = object
    tkinter.Label = object
    tkinter.StringVar = object
    tkinter.BooleanVar = object

    filedialog = ModuleType("tkinter.filedialog")
    messagebox = ModuleType("tkinter.messagebox")
    ttk = ModuleType("tkinter.ttk")
    tkfont = ModuleType("tkinter.font")

    tkinter.filedialog = filedialog
    tkinter.messagebox = messagebox
    tkinter.ttk = ttk
    tkinter.font = tkfont
    return {
        "tkinter": tkinter,
        "tkinter.filedialog": filedialog,
        "tkinter.messagebox": messagebox,
        "tkinter.ttk": ttk,
        "tkinter.font": tkfont,
    }


class MusicFolderBuilderAppTests(unittest.TestCase):
    def test_render_plan_reason_counts_windows_path_components(self) -> None:
        with patch.dict("sys.modules", _fake_tkinter_modules()):
            from music_folder_builder.gui.app import MusicFolderBuilderApp

        app = object.__new__(MusicFolderBuilderApp)
        row = PlanItemRow(
            plan_item_id="plan-item-1",
            source_path="E:/source/song.flac",
            target_path=r"D:\Music\ArtistName\AlbumTitle\1234567890.flac",
            action="skip",
            conflict_status="none",
            risk_status="invalid_target",
            reason="component_too_long",
            artist="ArtistName",
            album="AlbumTitle",
            title="1234567890",
        )

        reason = app._render_plan_reason(row)

        self.assertEqual("フォルダ名またはファイル名が長すぎる (最長 15文字 / 全体 46文字)", reason)


if __name__ == "__main__":
    unittest.main()
