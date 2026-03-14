import tempfile
import unittest
from pathlib import Path

from music_folder_builder.infrastructure.fs.walker import FileWalker


class FileWalkerTests(unittest.TestCase):
    def test_walk_yields_supported_music_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "album").mkdir()
            music_path = root / "album" / "track01.flac"
            other_path = root / "album" / "cover.jpg"
            music_path.write_bytes(b"music")
            other_path.write_bytes(b"image")

            walker = FileWalker(supported_extensions={".flac", ".mp3"})
            results = list(walker.walk(root))

            self.assertEqual(2, len(results))
            results_by_path = {result.path: result for result in results}
            self.assertEqual("music", results_by_path[music_path].file_type)
            self.assertEqual("unsupported", results_by_path[other_path].file_type)

    def test_walk_does_not_follow_symlinks_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target_dir = root / "target"
            linked_dir = root / "linked"
            target_dir.mkdir()
            (target_dir / "track01.flac").write_bytes(b"music")

            try:
                linked_dir.symlink_to(target_dir, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink unavailable in this environment: {error}")

            walker = FileWalker(supported_extensions={".flac"})
            results = list(walker.walk(root))

            music_paths = {result.path for result in results if result.file_type == "music"}
            self.assertEqual({target_dir / "track01.flac"}, music_paths)

    def test_walk_marks_symlink_entry_as_reparse_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target_dir = root / "target"
            linked_dir = root / "linked"
            target_dir.mkdir()
            (target_dir / "track01.flac").write_bytes(b"music")

            try:
                linked_dir.symlink_to(target_dir, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink unavailable in this environment: {error}")

            walker = FileWalker(supported_extensions={".flac"})
            results = list(walker.walk(root))

            skipped_entries = [result for result in results if result.link_state == "reparse_skipped"]
            self.assertEqual(1, len(skipped_entries))
            self.assertEqual(linked_dir, skipped_entries[0].path)
            self.assertEqual("ignored", skipped_entries[0].file_type)


if __name__ == "__main__":
    unittest.main()
