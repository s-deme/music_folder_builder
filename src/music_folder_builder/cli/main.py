from __future__ import annotations

import argparse
import sys
from typing import Sequence, TextIO

from music_folder_builder.cli import exit_codes
from music_folder_builder.cli.config import get_command_config, load_config
from music_folder_builder.cli.commands.apply import run_apply_command
from music_folder_builder.cli.commands.plan import run_plan_command
from music_folder_builder.cli.commands.rollback import run_rollback_command
from music_folder_builder.cli.commands.scan import run_scan_command
from music_folder_builder.cli.commands.verify import run_verify_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="music-folder-builder")
    parser.add_argument("--config", default="config/local.toml")
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--source")
    scan_parser.add_argument("--db")
    scan_parser.set_defaults(handler=run_scan_command)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--db")
    plan_parser.add_argument("--scan-run-id")
    plan_parser.add_argument("--library-root")
    plan_parser.add_argument("--max-component-length", type=int, default=80)
    plan_parser.add_argument("--max-path-length", type=int, default=240)
    plan_parser.add_argument("--use-source-image-filename", action="store_true", default=None)
    plan_parser.set_defaults(handler=run_plan_command)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--db")
    apply_parser.add_argument("--plan-run-id")
    apply_parser.add_argument("--dry-run", action="store_true", default=None)
    apply_parser.set_defaults(handler=run_apply_command)

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--db")
    rollback_parser.add_argument("--execution-run-id")
    rollback_parser.add_argument("--dry-run", action="store_true", default=None)
    rollback_parser.set_defaults(handler=run_rollback_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--db")
    verify_parser.add_argument("--execution-run-id")
    verify_parser.add_argument("--rollback-run-id")
    verify_parser.set_defaults(handler=run_verify_command)

    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None) -> int:
    parser = build_parser()
    output = stdout or sys.stdout

    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as error:
        return int(error.code)

    if not hasattr(args, "handler"):
        parser.print_help(file=output)
        return exit_codes.ARGUMENT_ERROR

    config = load_config(args.config)
    command_config = get_command_config(config, args.command)
    _apply_config_defaults(args, command_config)

    try:
        return args.handler(args, output)
    except Exception as error:
        output.write(f"error: {error}\n")
        return exit_codes.GENERAL_ERROR


def _apply_config_defaults(args: argparse.Namespace, command_config: dict[str, object]) -> None:
    for key, value in command_config.items():
        if not hasattr(args, key):
            continue
        if getattr(args, key) in (None, ""):
            setattr(args, key, value)


if __name__ == "__main__":
    raise SystemExit(main())
