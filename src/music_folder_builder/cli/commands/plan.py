from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TextIO

from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.services.plan_service import PlanService
from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.output import write_output


def run_plan_command(args: Namespace, stdout: TextIO) -> int:
    if not args.db or not args.scan_run_id or not args.library_root:
        stdout.write("error: plan requires db, scan-run-id, and library-root\n")
        return exit_codes.ARGUMENT_ERROR

    service = PlanService(
        max_component_length=args.max_component_length,
        max_path_length=args.max_path_length,
    )
    result = service.execute(
        PlanRequest(
            db_path=Path(args.db),
            scan_run_id=args.scan_run_id,
            library_root=Path(args.library_root),
        )
    )
    write_output(
        stdout,
        {
            "plan_run_id": result.plan_run_id,
            "items": result.item_count,
            "conflicts": result.conflict_count,
            "risks": result.risk_count,
        },
        as_json=bool(args.json),
    )
    if result.conflict_count or result.risk_count:
        return exit_codes.RISK_DETECTED
    return exit_codes.SUCCESS
