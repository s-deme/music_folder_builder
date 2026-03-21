import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.dto.scan_request import ScanRequest
from music_folder_builder.application.services.apply_service import ApplyService
from music_folder_builder.application.services.plan_service import PlanService
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.gui.query_service import GuiQueryService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


class GuiTestMetadataReader:
    def __init__(self, mapping: dict[str, dict[str, object]]) -> None:
        self._mapping = mapping

    def read(self, path: Path) -> MetadataReadResult:
        values = self._mapping[path.name]
        return MetadataReadResult(
            artist=values.get("artist", "Artist"),
            album_artist=values.get("album_artist", "Album Artist"),
            album=values.get("album"),
            title=values.get("title", path.stem),
            track_no=values.get("track_no", 1),
            disc_no=values.get("disc_no"),
            metadata_status="ok",
        )


class GuiQueryServiceTests(unittest.TestCase):
    def test_lists_plan_runs_and_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_result = ScanService().execute(ScanRequest(source_root=root, db_path=db_path))
            plan_result = PlanService().execute(
                PlanRequest(
                    db_path=db_path,
                    scan_run_id=scan_result.scan_run_id,
                    library_root=Path("D:/Music"),
                )
            )

            query_service = GuiQueryService(db_path)
            plan_runs = query_service.list_plan_runs()
            self.assertEqual(plan_result.plan_run_id, plan_runs[0].run_id)

            plan_items = query_service.list_plan_items(plan_run_id=plan_result.plan_run_id)
            self.assertEqual(1, len(plan_items))
            self.assertIn("song.flac", plan_items[0].source_path)

    def test_delete_plan_run_removes_downstream_execution_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_result = ScanService().execute(ScanRequest(source_root=root, db_path=db_path))
            plan_result = PlanService().execute(
                PlanRequest(
                    db_path=db_path,
                    scan_run_id=scan_result.scan_run_id,
                    library_root=Path(tmp_dir) / "organized",
                )
            )
            ApplyService().execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=True,
                )
            )

            query_service = GuiQueryService(db_path)
            self.assertEqual(1, len(query_service.list_execution_runs()))

            query_service.delete_plan_run(plan_run_id=plan_result.plan_run_id)

            self.assertEqual(0, len(query_service.list_plan_runs()))
            self.assertEqual(0, len(query_service.list_execution_runs()))

    def test_find_active_plan_progress_counts_companion_images_in_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "song.flac").write_bytes(b"music")
            (root / "cover.jpg").write_bytes(b"image")
            db_path = Path(tmp_dir) / "state.db"

            scan_result = ScanService().execute(ScanRequest(source_root=root, db_path=db_path))
            query_service = GuiQueryService(db_path)

            with patch.object(
                GuiQueryService,
                "_fetchone",
                side_effect=[
                    {"id": "plan-1", "scan_run_id": scan_result.scan_run_id},
                    {"count": 1},
                    {"count": 2},
                ],
            ):
                progress = query_service._find_active_plan_progress()

            self.assertIsNotNone(progress)
            assert progress is not None
            self.assertEqual("plan", progress.stage)
            self.assertEqual(1, progress.processed)
            self.assertEqual(2, progress.total)

    def test_assign_plan_item_target_resolves_ambiguous_companion_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            (root / "album1").mkdir(parents=True)
            (root / "album2").mkdir(parents=True)
            (root / "album1" / "song1.flac").write_bytes(b"music")
            (root / "album2" / "song2.flac").write_bytes(b"music")
            (root / "artist-poster.jpg").write_bytes(b"image")
            db_path = Path(tmp_dir) / "state.db"

            scan_service = ScanService(
                metadata_reader=GuiTestMetadataReader(
                    {
                        "song1.flac": {
                            "album_artist": "Artist One",
                            "album": "Album One",
                            "title": "Song One",
                        },
                        "song2.flac": {
                            "album_artist": "Artist Two",
                            "album": "Album Two",
                            "title": "Song Two",
                        },
                    }
                )
            )
            scan_result = scan_service.execute(ScanRequest(source_root=root, db_path=db_path))
            plan_result = PlanService().execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_result.scan_run_id, library_root=Path("D:/Music"))
            )

            query_service = GuiQueryService(db_path)
            item = next(
                row
                for row in query_service.list_plan_items(plan_run_id=plan_result.plan_run_id)
                if row.source_path.endswith("artist-poster.jpg")
            )
            self.assertEqual("companion_target_ambiguous", item.reason)

            candidates = query_service.list_plan_item_target_candidates(plan_item_id=item.plan_item_id)
            self.assertEqual(2, len(candidates))
            self.assertTrue(any("Artist One" in candidate.target_path for candidate in candidates))
            self.assertTrue(any("Artist Two" in candidate.target_path for candidate in candidates))

            selected_target = candidates[0].target_path
            query_service.assign_plan_item_target(plan_item_id=item.plan_item_id, target_path=selected_target)

            with connect_sqlite(db_path) as connection:
                updated_row = connection.execute(
                    """
                    SELECT action, target_path_sanitized, conflict_status, risk_status, reason
                    FROM plan_items
                    WHERE id = ?
                    """,
                    (item.plan_item_id,),
                ).fetchone()
                self.assertEqual("move", updated_row["action"])
                self.assertEqual(selected_target, updated_row["target_path_sanitized"])
                self.assertEqual("none", updated_row["conflict_status"])
                self.assertEqual("none", updated_row["risk_status"])
                self.assertIsNone(updated_row["reason"])

                plan_run_row = connection.execute(
                    "SELECT risk_count FROM plan_runs WHERE id = ?",
                    (plan_result.plan_run_id,),
                ).fetchone()
                self.assertEqual(0, plan_run_row["risk_count"])


if __name__ == "__main__":
    unittest.main()
