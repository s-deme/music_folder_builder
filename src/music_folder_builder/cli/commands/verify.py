from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TextIO

from music_folder_builder.application.dto.verify_request import VerifyRequest
from music_folder_builder.application.services.verify_service import VerifyService
from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.output import write_output


def run_verify_command(args: Namespace, stdout: TextIO) -> int:
    if not args.db:
        stdout.write("error: verify requires db\n")
        return exit_codes.ARGUMENT_ERROR
    if bool(args.execution_run_id) == bool(args.rollback_run_id):
        stdout.write("error: verify requires exactly one of execution-run-id or rollback-run-id\n")
        return exit_codes.ARGUMENT_ERROR

    service = VerifyService()
    result = service.execute(
        VerifyRequest(
            db_path=Path(args.db),
            execution_run_id=args.execution_run_id,
            rollback_run_id=args.rollback_run_id,
        )
    )
    mode = "execution" if args.execution_run_id else "rollback"
    write_output(
        stdout,
        {
            "verify_run_id": result.verify_run_id,
            "successes": result.success_count,
            "skips": result.skipped_count,
            "failures": result.failed_count,
            "risks": result.risky_count,
            "mode": mode,
        },
        as_json=bool(args.json),
    )
    if result.failed_count or result.risky_count:
        return exit_codes.RISK_DETECTED
    return exit_codes.SUCCESS
