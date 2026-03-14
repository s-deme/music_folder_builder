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
    def __init__(
        self,
        *,
        organization_rules: OrganizationRules | None = None,
        sanitizer: PathSanitizer | None = None,
        max_component_length: int = 80,
        max_path_length: int = 240,
    ) -> None:
        self._organization_rules = organization_rules or OrganizationRules()
        self._sanitizer = sanitizer or PathSanitizer()
        self._path_policy = PathPolicy(
            max_component_length=max_component_length,
            max_path_length=max_path_length,
        )

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

            for record in scan_repository.fetch_plan_records(scan_run_id=request.scan_run_id):
                item_count += 1
                target_path = self._organization_rules.build_target_path(
                    library_root=str(request.library_root),
                    record=record,
                )
                sanitized_path = self._sanitizer.sanitize_path(target_path)
                risk = self._path_policy.assess(sanitized_path)

                action = "move"
                conflict_status = "none"
                risk_status = risk.status
                reason = risk.reason

                sanitized_text = str(sanitized_path)
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

                plan_repository.insert_plan_item(
                    plan_item_id=str(uuid4()),
                    plan_run_id=plan_run_id,
                    file_id=record.file_id,
                    action=action,
                    target_path=str(target_path),
                    target_path_sanitized=sanitized_text,
                    conflict_status=conflict_status,
                    risk_status=risk_status,
                    reason=reason,
                )

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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
