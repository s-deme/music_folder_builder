from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PureWindowsPath
from uuid import uuid4

from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.dto.plan_result import PlanResult
from music_folder_builder.domain.policies.organization_rules import OrganizationRules
from music_folder_builder.domain.policies.path_policy import PathPolicy
from music_folder_builder.domain.policies.path_sanitization import PathSanitizer
from music_folder_builder.infrastructure.db.connection import connect_sqlite
from music_folder_builder.infrastructure.db.plan_repository import PlanRepository
from music_folder_builder.infrastructure.db.run_repository import RunRepository
from music_folder_builder.infrastructure.db.scan_repository import PlannedScanRecord, ScanRepository
from music_folder_builder.infrastructure.db.schema import initialize_schema


class PlanService:
    _DEFAULT_BATCH_SIZE = 500
    _COMPANION_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

    def __init__(
        self,
        *,
        organization_rules: OrganizationRules | None = None,
        sanitizer: PathSanitizer | None = None,
        max_component_length: int = 80,
        max_path_length: int = 240,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._organization_rules = organization_rules or OrganizationRules()
        self._sanitizer = sanitizer or PathSanitizer()
        self._path_policy = PathPolicy(
            max_component_length=max_component_length,
            max_path_length=max_path_length,
        )
        self._batch_size = batch_size

    def execute(self, request: PlanRequest) -> PlanResult:
        plan_run_id = str(uuid4())
        item_count = 0
        conflict_count = 0
        risk_count = 0
        seen_targets: set[str] = set()

        with connect_sqlite(request.db_path) as connection:
            initialize_schema(connection)
            run_repository = RunRepository(connection)
            scan_repository = ScanRepository(connection)
            plan_repository = PlanRepository(connection)

            run_repository.create_plan_run(
                plan_run_id=plan_run_id,
                scan_run_id=request.scan_run_id,
                started_at=_utc_now(),
            )

            plan_item_rows: list[tuple[object, ...]] = []
            music_records = scan_repository.fetch_plan_records(scan_run_id=request.scan_run_id)
            source_dir_targets: dict[str, set[str]] = {}
            music_target_groups: dict[str, list[tuple[PlannedScanRecord, PureWindowsPath, str]]] = {}
            for record in music_records:
                target_path = self._organization_rules.build_target_path(
                    library_root=str(request.library_root),
                    record=record,
                )
                sanitized_text = str(self._sanitizer.sanitize_path(target_path))
                music_target_groups.setdefault(sanitized_text, []).append((record, target_path, sanitized_text))

            for group in music_target_groups.values():
                use_duplicate_suffix = len(group) > 1 and bool(request.duplicate_suffix_template.strip())
                for record, target_path, sanitized_text in group:
                    if use_duplicate_suffix:
                        target_path = self._organization_rules.build_duplicate_target_path(
                            library_root=str(request.library_root),
                            record=record,
                            duplicate_suffix_template=request.duplicate_suffix_template,
                        )
                        sanitized_text = str(self._sanitizer.sanitize_path(target_path))

                    item_count += 1
                    risk = self._path_policy.assess(PureWindowsPath(sanitized_text))

                    action = "move"
                    conflict_status = "none"
                    risk_status = risk.status
                    reason = risk.reason

                    if sanitized_text in seen_targets:
                        action = "skip"
                        conflict_status = "duplicate_target"
                        reason = "duplicate_target_path"
                        conflict_count += 1
                    elif risk.status != "none":
                        action = "skip"
                        risk_count += 1
                    else:
                        seen_targets.add(sanitized_text)
                        self._register_source_dir_targets(
                            source_dir_targets=source_dir_targets,
                            source_path=PureWindowsPath(record.source_path),
                            source_root=PureWindowsPath(record.source_root),
                            target_path=PureWindowsPath(sanitized_text),
                        )

                    plan_item_rows.append(
                        (
                            str(uuid4()),
                            plan_run_id,
                            record.file_id,
                            action,
                            str(target_path),
                            sanitized_text,
                            conflict_status,
                            risk_status,
                            reason,
                        )
                    )
                    if len(plan_item_rows) >= self._batch_size:
                        plan_repository.insert_plan_items_batch(rows=plan_item_rows)
                        connection.commit()
                        plan_item_rows.clear()

            companion_assets = scan_repository.fetch_companion_asset_records(
                scan_run_id=request.scan_run_id,
                extensions=self._COMPANION_IMAGE_EXTENSIONS,
            )
            for asset in companion_assets:
                item_count += 1
                anchor = self._resolve_companion_anchor(
                    asset_path=PureWindowsPath(asset.source_path),
                    source_dir_targets=source_dir_targets,
                )
                candidate_target_dirs = set() if anchor is None else source_dir_targets.get(str(anchor), set())

                action = "move"
                conflict_status = "none"
                risk_status = "none"
                reason = None
                if not candidate_target_dirs:
                    action = "skip"
                    risk_status = "companion_without_music"
                    reason = "companion_without_music"
                    risk_count += 1
                    target_path = None
                    sanitized_text = None
                elif len(candidate_target_dirs) > 1:
                    target_dir = (
                        self._resolve_common_companion_target_dir(
                            candidate_target_dirs=candidate_target_dirs,
                            library_root=PureWindowsPath(request.library_root),
                        )
                        if request.use_source_image_filename
                        else None
                    )
                    if target_dir is None:
                        action = "skip"
                        risk_status = "companion_target_ambiguous"
                        reason = "companion_target_ambiguous"
                        risk_count += 1
                        target_path = None
                        sanitized_text = None
                    else:
                        relative_path = PureWindowsPath(asset.source_path).relative_to(anchor)
                        target_path = str(target_dir / relative_path)
                        target_path, sanitized_text = self._build_unique_companion_target_path(
                            target_path=PureWindowsPath(target_path),
                            seen_targets=seen_targets,
                        )
                        risk = self._path_policy.assess(PureWindowsPath(sanitized_text))
                        risk_status = risk.status
                        reason = risk.reason
                        if risk.status != "none":
                            action = "skip"
                            risk_count += 1
                        else:
                            seen_targets.add(sanitized_text)
                else:
                    target_dir = PureWindowsPath(next(iter(candidate_target_dirs)))
                    relative_path = PureWindowsPath(asset.source_path).relative_to(anchor)
                    target_path = str(target_dir / relative_path)
                    if request.use_source_image_filename:
                        target_path, sanitized_text = self._build_unique_companion_target_path(
                            target_path=PureWindowsPath(target_path),
                            seen_targets=seen_targets,
                        )
                    else:
                        sanitized_text = str(self._sanitizer.sanitize_path(PureWindowsPath(target_path)))
                    risk = self._path_policy.assess(PureWindowsPath(sanitized_text))
                    risk_status = risk.status
                    reason = risk.reason
                    if sanitized_text in seen_targets:
                        action = "skip"
                        conflict_status = "duplicate_target"
                        reason = "duplicate_target_path"
                        conflict_count += 1
                    elif risk.status != "none":
                        action = "skip"
                        risk_count += 1
                    else:
                        seen_targets.add(sanitized_text)

                plan_item_rows.append(
                    (
                        str(uuid4()),
                        plan_run_id,
                        asset.file_id,
                        action,
                        target_path,
                        sanitized_text,
                        conflict_status,
                        risk_status,
                        reason,
                    )
                )
                if len(plan_item_rows) >= self._batch_size:
                    plan_repository.insert_plan_items_batch(rows=plan_item_rows)
                    connection.commit()
                    plan_item_rows.clear()

            if plan_item_rows:
                plan_repository.insert_plan_items_batch(rows=plan_item_rows)
                connection.commit()

            run_repository.complete_plan_run(
                plan_run_id=plan_run_id,
                finished_at=_utc_now(),
                conflict_count=conflict_count,
                risk_count=risk_count,
            )

        return PlanResult(
            plan_run_id=plan_run_id,
            item_count=item_count,
            conflict_count=conflict_count,
            risk_count=risk_count,
        )

    def _register_source_dir_targets(
        self,
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

    def _resolve_companion_anchor(
        self,
        *,
        asset_path: PureWindowsPath,
        source_dir_targets: dict[str, set[str]],
    ) -> PureWindowsPath | None:
        current = asset_path.parent
        while True:
            if str(current) in source_dir_targets:
                return current
            parent = current.parent
            if parent == current:
                return None
            current = parent

    def _resolve_common_companion_target_dir(
        self,
        *,
        candidate_target_dirs: set[str],
        library_root: PureWindowsPath,
    ) -> PureWindowsPath | None:
        candidate_parts = [PureWindowsPath(target_dir).parts for target_dir in candidate_target_dirs]
        if not candidate_parts:
            return None

        common_parts: list[str] = []
        for parts_group in zip(*candidate_parts, strict=False):
            first_part = parts_group[0]
            if all(part == first_part for part in parts_group):
                common_parts.append(first_part)
                continue
            break

        if len(common_parts) <= len(library_root.parts):
            return None
        return PureWindowsPath(*common_parts)

    def _build_unique_companion_target_path(
        self,
        *,
        target_path: PureWindowsPath,
        seen_targets: set[str],
    ) -> tuple[str, str]:
        candidate = target_path
        counter = 2
        while True:
            sanitized_text = str(self._sanitizer.sanitize_path(candidate))
            if sanitized_text not in seen_targets:
                return str(candidate), sanitized_text
            candidate = target_path.with_name(f"{target_path.stem}_{counter}{target_path.suffix}")
            counter += 1


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
