from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TextIO

from music_folder_builder.application.dto.scan_request import ScanRequest
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.output import write_output


def run_scan_command(args: Namespace, stdout: TextIO) -> int:
    if not args.source or not args.db:
        stdout.write("error: scan requires source and db\n")
        return exit_codes.ARGUMENT_ERROR

    service = ScanService()
    result = service.execute(
        ScanRequest(
            source_root=Path(args.source),
            db_path=Path(args.db),
        )
    )
    write_output(
        stdout,
        {
            "scan_run_id": result.scan_run_id,
            "files": result.file_count,
            "warnings": result.warning_count,
        },
        as_json=bool(args.json),
    )
    return exit_codes.SUCCESS
