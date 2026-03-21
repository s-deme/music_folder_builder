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


if __name__ == "__main__":
    unittest.main()
