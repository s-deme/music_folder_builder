import tempfile
import unittest
from pathlib import Path

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.services.apply_service import ApplyService
from music_folder_builder.application.services.plan_service import PlanService
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.fs.mutation_gateway import FileMutationGateway
from music_folder_builder.infrastructure.metadata.reader import MetadataReadResult


class ApplyMetadataReader:
    def read(self, path: Path) -> MetadataReadResult:
        return MetadataReadResult(
            artist="Artist",
            album_artist="Album Artist",
            album="Album",
            title=path.stem,
            track_no=1,
            disc_no=None,
            metadata_status="ok",
        )


class ApplyServiceTests(unittest.TestCase):
    def test_dry_run_persists_execution_and_operation_logs_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_result, plan_result = self._prepare_plan(root, db_path)

            service = ApplyService()
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=True,
                )
            )

            self.assertEqual(1, result.success_count)
            self.assertEqual(0, result.failed_count)
            self.assertEqual(0, result.skipped_count)
            self.assertTrue(source_file.exists())

            with connect_sqlite(db_path) as connection:
                execution_row = connection.execute(
                    """
                    SELECT plan_run_id, mode, status, success_count, skipped_count, failed_count
                    FROM execution_runs
                    WHERE id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual(plan_result.plan_run_id, execution_row["plan_run_id"])
                self.assertEqual("dry_run", execution_row["mode"])
                self.assertEqual("completed", execution_row["status"])
                self.assertEqual(1, execution_row["success_count"])

                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, source_path, target_path, source_deleted
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("dry_run", operation_row["performed_action"])
                self.assertEqual("success", operation_row["result"])
                self.assertEqual(str(source_file), operation_row["source_path"])
                self.assertEqual(0, operation_row["source_deleted"])

    def test_dry_run_respects_skip_plan_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            scan_result, plan_result = self._prepare_plan(root, db_path, max_path_length=20)

            service = ApplyService()
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=True,
                )
            )

            self.assertEqual(0, result.success_count)
            self.assertEqual(1, result.skipped_count)

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("skip", operation_row["performed_action"])
                self.assertEqual("skipped", operation_row["result"])
                self.assertEqual("path_length_exceeded", operation_row["error_message"])

    def test_dry_run_persists_skip_items_without_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            (root / "track01.flac").write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            _, plan_result = self._prepare_plan(root, db_path)
            with connect_sqlite(db_path) as connection:
                connection.execute(
                    """
                    UPDATE plan_items
                    SET action = 'skip',
                        target_path = NULL,
                        target_path_sanitized = NULL,
                        risk_status = 'companion_without_music',
                        reason = 'companion_without_music'
                    WHERE plan_run_id = ?
                    """,
                    (plan_result.plan_run_id,),
                )
                connection.commit()

            service = ApplyService()
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=True,
                )
            )

            self.assertEqual(0, result.success_count)
            self.assertEqual(1, result.skipped_count)
            self.assertEqual(0, result.failed_count)

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, target_path, error_message
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("skip", operation_row["performed_action"])
                self.assertEqual("skipped", operation_row["result"])
                self.assertEqual("", operation_row["target_path"])
                self.assertEqual("companion_without_music", operation_row["error_message"])

    def test_apply_moves_file_on_same_volume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.success_count)
            self.assertFalse(source_file.exists())

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, target_path, source_deleted
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("move", operation_row["performed_action"])
                self.assertEqual("success", operation_row["result"])
                self.assertEqual(1, operation_row["source_deleted"])

    def test_apply_moves_companion_images_with_music(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            cover_file = root / "cover.jpg"
            source_file.write_bytes(b"music")
            cover_file.write_bytes(b"image")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            target_music = library_root / "Album Artist" / "Album" / "01_track01.flac"
            target_cover = library_root / "Album Artist" / "Album" / "cover.jpg"
            self.assertEqual(2, result.success_count)
            self.assertFalse(source_file.exists())
            self.assertFalse(cover_file.exists())
            self.assertTrue(target_music.exists())
            self.assertTrue(target_cover.exists())
            self.assertEqual(b"image", target_cover.read_bytes())

    def test_apply_moves_companion_images_in_subfolder_with_music(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            scans_dir = root / "Scans"
            scans_dir.mkdir(parents=True)
            source_file = root / "track01.flac"
            cover_file = scans_dir / "cover.jpg"
            source_file.write_bytes(b"music")
            cover_file.write_bytes(b"image")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            target_music = library_root / "Album Artist" / "Album" / "01_track01.flac"
            target_cover = library_root / "Album Artist" / "Album" / "Scans" / "cover.jpg"
            self.assertEqual(2, result.success_count)
            self.assertFalse(source_file.exists())
            self.assertFalse(cover_file.exists())
            self.assertTrue(target_music.exists())
            self.assertTrue(target_cover.exists())
            self.assertEqual(b"image", target_cover.read_bytes())

    def test_apply_skips_when_target_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            _, plan_result = self._prepare_plan(root, db_path)
            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)
            target_file = library_root / "Album Artist" / "Album" / "01_track01.flac"
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(b"existing")

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.skipped_count)
            self.assertTrue(source_file.exists())

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("skip", operation_row["performed_action"])
                self.assertEqual("skipped", operation_row["result"])
                self.assertEqual("target_already_exists", operation_row["error_message"])

    def test_apply_fails_when_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)
            source_file.unlink()

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            self.assertEqual(1, result.failed_count)

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("move", operation_row["performed_action"])
                self.assertEqual("failed", operation_row["result"])
                self.assertEqual("source_missing", operation_row["error_message"])

    def test_apply_copies_verifies_and_deletes_source_on_cross_volume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=CrossVolumeGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            target_file = library_root / "Album Artist" / "Album" / "01_track01.flac"
            self.assertEqual(1, result.success_count)
            self.assertFalse(source_file.exists())
            self.assertTrue(target_file.exists())
            self.assertEqual(b"music", target_file.read_bytes())

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, source_deleted
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("copy_delete", operation_row["performed_action"])
                self.assertEqual("success", operation_row["result"])
                self.assertIsNone(operation_row["error_message"])
                self.assertEqual(1, operation_row["source_deleted"])

    def test_apply_keeps_source_when_cross_volume_verify_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=CorruptingCrossVolumeGateway())
            result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            target_file = library_root / "Album Artist" / "Album" / "01_track01.flac"
            self.assertEqual(1, result.failed_count)
            self.assertTrue(source_file.exists())
            self.assertTrue(target_file.exists())
            self.assertEqual(b"corrupt", target_file.read_bytes())

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message, source_deleted
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (result.execution_run_id,),
                ).fetchone()
                self.assertEqual("copy", operation_row["performed_action"])
                self.assertEqual("failed", operation_row["result"])
                self.assertEqual("cross_volume_verify_failed", operation_row["error_message"])
                self.assertEqual(0, operation_row["source_deleted"])

    def test_apply_skips_when_plan_item_was_already_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "library"
            root.mkdir()
            source_file = root / "track01.flac"
            source_file.write_bytes(b"music")
            db_path = Path(tmp_dir) / "state.db"

            library_root = Path(tmp_dir) / "organized"
            _, plan_result = self._prepare_plan(root, db_path, library_root=library_root)

            service = ApplyService(file_mutation_gateway=FileMutationGateway())
            first_result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )
            self.assertEqual(1, first_result.success_count)

            second_result = service.execute(
                ApplyRequest(
                    db_path=db_path,
                    plan_run_id=plan_result.plan_run_id,
                    dry_run=False,
                )
            )

            self.assertEqual(1, second_result.skipped_count)
            self.assertEqual(0, second_result.failed_count)
            self.assertFalse(source_file.exists())

            with connect_sqlite(db_path) as connection:
                operation_row = connection.execute(
                    """
                    SELECT performed_action, result, error_message
                    FROM operation_logs
                    WHERE execution_run_id = ?
                    """,
                    (second_result.execution_run_id,),
                ).fetchone()
                self.assertEqual("skip", operation_row["performed_action"])
                self.assertEqual("skipped", operation_row["result"])
                self.assertEqual("already_applied", operation_row["error_message"])

    def _prepare_plan(
        self,
        root: Path,
        db_path: Path,
        *,
        max_path_length: int = 240,
        library_root: Path | None = None,
    ):
        scan_service = ScanService(metadata_reader=ApplyMetadataReader())
        scan_result = scan_service.execute(request=self._scan_request(root, db_path))

        plan_service = PlanService(max_path_length=max_path_length)
        plan_result = plan_service.execute(
            PlanRequest(
                db_path=db_path,
                scan_run_id=scan_result.scan_run_id,
                library_root=library_root or Path("D:/Music"),
            )
        )
        if library_root is not None:
            self._rewrite_plan_targets_for_posix(db_path, plan_result.plan_run_id, library_root)
        return scan_result, plan_result

    @staticmethod
    def _scan_request(source_root: Path, db_path: Path):
        from music_folder_builder.application.dto.scan_request import ScanRequest

        return ScanRequest(source_root=source_root, db_path=db_path)

    @staticmethod
    def _rewrite_plan_targets_for_posix(db_path: Path, plan_run_id: str, library_root: Path) -> None:
        with connect_sqlite(db_path) as connection:
            rows = connection.execute(
                "SELECT id, target_path, target_path_sanitized FROM plan_items WHERE plan_run_id = ?",
                (plan_run_id,),
            ).fetchall()

            for row in rows:
                target_path = row["target_path"].replace("D:\\Music\\", "").replace("\\", "/")
                sanitized_path = row["target_path_sanitized"].replace("D:\\Music\\", "").replace("\\", "/")
                connection.execute(
                    """
                    UPDATE plan_items
                    SET target_path = ?, target_path_sanitized = ?
                    WHERE id = ?
                    """,
                    (
                        str(library_root / target_path),
                        str(library_root / sanitized_path),
                        row["id"],
                    ),
                )
            connection.commit()


if __name__ == "__main__":
    unittest.main()


class CrossVolumeGateway(FileMutationGateway):
    def same_volume(self, source: str | Path, target: str | Path) -> bool:
        return False


class CorruptingCrossVolumeGateway(CrossVolumeGateway):
    def copy(self, source: str | Path, target: str | Path) -> None:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"corrupt")
