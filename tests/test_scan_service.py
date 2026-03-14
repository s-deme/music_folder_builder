import tempfile
import unittest
from pathlib import Path

from music_folder_builder.application.dto.scan_request import ScanRequest
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


class FakeMetadataReader:
    def read(self, path: Path) -> MetadataReadResult:
        if path.stem == "broken":
            raise ValueError("metadata decode failed")
        return MetadataReadResult(title=path.stem, metadata_status="ok")


class ScanServiceTests(unittest.TestCase):
    def test_scan_persists_run_files_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            good_file = root / "song.flac"
            other_file = root / "cover.jpg"
            good_file.write_bytes(b"music")
            other_file.write_bytes(b"image")
            db_path = Path(tmp_dir) / "state.db"

            service = ScanService(metadata_reader=FakeMetadataReader())
            result = service.execute(ScanRequest(source_root=root, db_path=db_path))

            self.assertEqual(2, result.file_count)
            self.assertEqual(0, result.warning_count)

            with connect_sqlite(db_path) as connection:
                run_row = connection.execute(
                    "SELECT status, source_root, file_count, warning_count, finished_at FROM scan_runs WHERE id = ?",
                    (result.scan_run_id,),
                ).fetchone()
                self.assertIsNotNone(run_row)
                self.assertEqual("completed", run_row["status"])
                self.assertEqual(str(root), run_row["source_root"])
                self.assertEqual(2, run_row["file_count"])
                self.assertEqual(0, run_row["warning_count"])
                self.assertIsNotNone(run_row["finished_at"])

                file_rows = connection.execute(
                    "SELECT source_path, file_type, link_state FROM scanned_files ORDER BY source_path"
                ).fetchall()
                self.assertEqual(2, len(file_rows))
                self.assertEqual(str(other_file), file_rows[0]["source_path"])
                self.assertEqual("unsupported", file_rows[0]["file_type"])
                self.assertEqual(str(good_file), file_rows[1]["source_path"])
                self.assertEqual("music", file_rows[1]["file_type"])

                metadata_rows = connection.execute(
                    "SELECT title, metadata_status, metadata_error FROM scanned_metadata"
                ).fetchall()
                self.assertEqual(1, len(metadata_rows))
                self.assertEqual("song", metadata_rows[0]["title"])
                self.assertEqual("ok", metadata_rows[0]["metadata_status"])
                self.assertIsNone(metadata_rows[0]["metadata_error"])

    def test_scan_continues_when_metadata_reader_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            broken_file = root / "broken.flac"
            broken_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            service = ScanService(metadata_reader=FakeMetadataReader())
            result = service.execute(ScanRequest(source_root=root, db_path=db_path))

            self.assertEqual(1, result.file_count)
            self.assertEqual(1, result.warning_count)

            with connect_sqlite(db_path) as connection:
                run_row = connection.execute(
                    "SELECT status, warning_count FROM scan_runs WHERE id = ?",
                    (result.scan_run_id,),
                ).fetchone()
                self.assertEqual("completed", run_row["status"])
                self.assertEqual(1, run_row["warning_count"])

                metadata_row = connection.execute(
                    "SELECT title, metadata_status, metadata_error FROM scanned_metadata"
                ).fetchone()
                self.assertIsNone(metadata_row["title"])
                self.assertEqual("error", metadata_row["metadata_status"])
                self.assertEqual("metadata decode failed", metadata_row["metadata_error"])


if __name__ == "__main__":
    unittest.main()
