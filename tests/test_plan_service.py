import tempfile
import unittest
from pathlib import Path

from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.services.plan_service import PlanService
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


class PlanMetadataReader:
    def __init__(self, metadata_by_file: dict[str, dict[str, object]]) -> None:
        self._metadata_by_file = metadata_by_file

    def read(self, path: Path) -> MetadataReadResult:
        metadata = self._metadata_by_file[path.name]
        return MetadataReadResult(
            artist=str(metadata.get("artist", "Artist")),
            album_artist=str(metadata.get("album_artist", "Album Artist")),
            album=str(metadata.get("album", "Album")),
            title=str(metadata["title"]),
            track_no=None if metadata.get("track_no") is None else int(metadata.get("track_no", 1)),
            disc_no=None if metadata.get("disc_no") is None else int(metadata.get("disc_no", 1)),
            metadata_status="ok",
        )


class PlanServiceTests(unittest.TestCase):
    def test_plan_persists_target_path_for_music_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_service = ScanService(
                metadata_reader=PlanMetadataReader(
                    {"track01.flac": {"title": "Song:One", "track_no": 1, "disc_no": 1}}
                )
            )
            scan_result = scan_service.execute(request=self._scan_request(root, db_path))

            service = PlanService()
            result = service.execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            self.assertEqual(1, result.item_count)
            self.assertEqual(0, result.conflict_count)
            self.assertEqual(0, result.risk_count)

            with connect_sqlite(db_path) as connection:
                plan_row = connection.execute(
                    "SELECT status, scan_run_id, conflict_count, risk_count FROM plan_runs WHERE id = ?",
                    (result.plan_run_id,),
                ).fetchone()
                self.assertEqual("completed", plan_row["status"])
                self.assertEqual(scan_result.scan_run_id, plan_row["scan_run_id"])
                self.assertEqual(0, plan_row["conflict_count"])
                self.assertEqual(0, plan_row["risk_count"])

                item_row = connection.execute(
                    """
                    SELECT action, target_path, target_path_sanitized, conflict_status, risk_status, reason
                    FROM plan_items
                    """
                ).fetchone()
                self.assertEqual("move", item_row["action"])
                self.assertEqual(r"D:\Music\Album Artist\Album\01\01_Song:One.flac", item_row["target_path"])
                self.assertEqual(
                    r"D:\Music\Album Artist\Album\01\01_Song_One.flac",
                    item_row["target_path_sanitized"],
                )
                self.assertEqual("none", item_row["conflict_status"])
                self.assertEqual("none", item_row["risk_status"])
                self.assertIsNone(item_row["reason"])

    def test_plan_marks_duplicate_target_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            (root / "track02.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_service = ScanService(
                metadata_reader=PlanMetadataReader(
                    {
                        "track01.flac": {"title": "Same Song", "track_no": 1, "disc_no": 1},
                        "track02.flac": {"title": "Same Song", "track_no": 1, "disc_no": 1},
                    }
                )
            )
            scan_result = scan_service.execute(request=self._scan_request(root, db_path))

            service = PlanService()
            result = service.execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            self.assertEqual(2, result.item_count)
            self.assertEqual(1, result.conflict_count)

            with connect_sqlite(db_path) as connection:
                conflict_rows = connection.execute(
                    """
                    SELECT action, conflict_status, reason
                    FROM plan_items
                    WHERE conflict_status != 'none'
                    """
                ).fetchall()
                self.assertEqual(1, len(conflict_rows))
                self.assertEqual("skip", conflict_rows[0]["action"])
                self.assertEqual("duplicate_target", conflict_rows[0]["conflict_status"])
                self.assertEqual("duplicate_target_path", conflict_rows[0]["reason"])

    def test_plan_marks_long_path_as_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            long_title = "VeryLongSongTitleForRisk"
            scan_service = ScanService(
                metadata_reader=PlanMetadataReader(
                    {"track01.flac": {"title": long_title, "track_no": 1, "disc_no": 1}}
                )
            )
            scan_result = scan_service.execute(request=self._scan_request(root, db_path))

            service = PlanService(max_path_length=20, max_component_length=64)
            result = service.execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            self.assertEqual(1, result.risk_count)

            with connect_sqlite(db_path) as connection:
                risk_row = connection.execute(
                    """
                    SELECT action, risk_status, reason
                    FROM plan_items
                    WHERE risk_status != 'none'
                    """
                ).fetchone()
                self.assertEqual("skip", risk_row["action"])
                self.assertEqual("path_too_long", risk_row["risk_status"])
                self.assertEqual("path_length_exceeded", risk_row["reason"])

    def test_plan_omits_disc_directory_when_disc_number_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_service = ScanService(
                metadata_reader=PlanMetadataReader(
                    {"track01.flac": {"title": "Song", "track_no": 1, "disc_no": None}}
                )
            )
            scan_result = scan_service.execute(request=self._scan_request(root, db_path))

            service = PlanService()
            result = service.execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            with connect_sqlite(db_path) as connection:
                item_row = connection.execute(
                    "SELECT target_path_sanitized FROM plan_items WHERE plan_run_id = ?",
                    (result.plan_run_id,),
                ).fetchone()
                self.assertEqual(r"D:\Music\Album Artist\Album\01_Song.flac", item_row["target_path_sanitized"])

    def test_plan_omits_track_prefix_when_track_number_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_service = ScanService(
                metadata_reader=PlanMetadataReader(
                    {"track01.flac": {"title": "Song", "track_no": None, "disc_no": 1}}
                )
            )
            scan_result = scan_service.execute(request=self._scan_request(root, db_path))

            service = PlanService()
            result = service.execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            with connect_sqlite(db_path) as connection:
                item_row = connection.execute(
                    "SELECT target_path_sanitized FROM plan_items WHERE plan_run_id = ?",
                    (result.plan_run_id,),
                ).fetchone()
                self.assertEqual(r"D:\Music\Album Artist\Album\01\Song.flac", item_row["target_path_sanitized"])

    @staticmethod
    def _scan_request(source_root: Path, db_path: Path):
        from music_folder_builder.application.dto.scan_request import ScanRequest

        return ScanRequest(source_root=source_root, db_path=db_path)


if __name__ == "__main__":
    unittest.main()
