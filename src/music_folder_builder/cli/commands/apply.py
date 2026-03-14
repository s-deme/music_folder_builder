from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TextIO

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.services.apply_service import ApplyService
from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.output import write_output


def run_apply_command(args: Namespace, stdout: TextIO) -> int:
    if not args.db or not args.plan_run_id:
        stdout.write("error: apply requires db and plan-run-id\n")
        return exit_codes.ARGUMENT_ERROR

    service = ApplyService()
    result = service.execute(
        ApplyRequest(
            db_path=Path(args.db),
            plan_run_id=args.plan_run_id,
            dry_run=bool(args.dry_run),
        )
    )
    write_output(
        stdout,
        {
            "execution_run_id": result.execution_run_id,
            "successes": result.success_count,
            "skips": result.skipped_count,
            "failures": result.failed_count,
            "risks": result.risky_count,
            "mode": "dry_run" if args.dry_run else "apply",
        },
        as_json=bool(args.json),
    )
    if result.failed_count or result.risky_count:
        return exit_codes.RISK_DETECTED
    return exit_codes.SUCCESS
