from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TextIO

from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.services.rollback_service import RollbackService
from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.output import write_output


def run_rollback_command(args: Namespace, stdout: TextIO) -> int:
    if not args.db or not args.execution_run_id:
        stdout.write("error: rollback requires db and execution-run-id\n")
        return exit_codes.ARGUMENT_ERROR

    service = RollbackService()
    result = service.execute(
        RollbackRequest(
            db_path=Path(args.db),
            execution_run_id=args.execution_run_id,
            dry_run=bool(args.dry_run),
        )
    )
    write_output(
        stdout,
        {
            "rollback_run_id": result.rollback_run_id,
            "successes": result.success_count,
            "skips": result.skipped_count,
            "failures": result.failed_count,
            "risks": result.risky_count,
            "mode": "dry_run" if args.dry_run else "rollback",
        },
        as_json=bool(args.json),
    )
    if result.failed_count or result.risky_count:
        return exit_codes.RISK_DETECTED
    return exit_codes.SUCCESS
