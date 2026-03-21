from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
      id TEXT PRIMARY KEY,
      source_root TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      file_count INTEGER NOT NULL DEFAULT 0,
      warning_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scanned_files (
      id TEXT PRIMARY KEY,
      scan_run_id TEXT NOT NULL REFERENCES scan_runs(id),
      source_path TEXT NOT NULL,
      source_root TEXT NOT NULL,
      extension TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      mtime_utc TEXT NOT NULL,
      file_type TEXT NOT NULL,
      exclusion_reason TEXT,
      link_state TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scanned_metadata (
      file_id TEXT PRIMARY KEY REFERENCES scanned_files(id),
      artist TEXT,
      album_artist TEXT,
      album TEXT,
      title TEXT,
      track_no INTEGER,
      disc_no INTEGER,
      year INTEGER,
      metadata_status TEXT NOT NULL,
      metadata_error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_runs (
      id TEXT PRIMARY KEY,
      scan_run_id TEXT NOT NULL REFERENCES scan_runs(id),
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      rule_profile TEXT NOT NULL,
      conflict_count INTEGER NOT NULL DEFAULT 0,
      risk_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_items (
      id TEXT PRIMARY KEY,
      plan_run_id TEXT NOT NULL REFERENCES plan_runs(id),
      file_id TEXT NOT NULL REFERENCES scanned_files(id),
      action TEXT NOT NULL,
      target_path TEXT,
      target_path_sanitized TEXT,
      conflict_status TEXT NOT NULL,
      risk_status TEXT NOT NULL,
      reason TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS execution_runs (
      id TEXT PRIMARY KEY,
      plan_run_id TEXT NOT NULL REFERENCES plan_runs(id),
      mode TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      success_count INTEGER NOT NULL DEFAULT 0,
      skipped_count INTEGER NOT NULL DEFAULT 0,
      failed_count INTEGER NOT NULL DEFAULT 0,
      risky_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operation_logs (
      id TEXT PRIMARY KEY,
      execution_run_id TEXT NOT NULL REFERENCES execution_runs(id),
      plan_item_id TEXT NOT NULL REFERENCES plan_items(id),
      sequence_no INTEGER NOT NULL,
      source_path TEXT NOT NULL,
      target_path TEXT NOT NULL,
      performed_action TEXT NOT NULL,
      result TEXT NOT NULL,
      error_message TEXT,
      source_deleted INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rollback_runs (
      id TEXT PRIMARY KEY,
      execution_run_id TEXT NOT NULL REFERENCES execution_runs(id),
      mode TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      success_count INTEGER NOT NULL DEFAULT 0,
      skipped_count INTEGER NOT NULL DEFAULT 0,
      failed_count INTEGER NOT NULL DEFAULT 0,
      risky_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rollback_logs (
      id TEXT PRIMARY KEY,
      rollback_run_id TEXT NOT NULL REFERENCES rollback_runs(id),
      operation_log_id TEXT NOT NULL REFERENCES operation_logs(id),
      sequence_no INTEGER NOT NULL,
      source_path TEXT NOT NULL,
      target_path TEXT NOT NULL,
      performed_action TEXT NOT NULL,
      result TEXT NOT NULL,
      error_message TEXT,
      target_deleted INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verify_runs (
      id TEXT PRIMARY KEY,
      execution_run_id TEXT REFERENCES execution_runs(id),
      rollback_run_id TEXT REFERENCES rollback_runs(id),
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      success_count INTEGER NOT NULL DEFAULT 0,
      skipped_count INTEGER NOT NULL DEFAULT 0,
      failed_count INTEGER NOT NULL DEFAULT 0,
      risky_count INTEGER NOT NULL DEFAULT 0,
      CHECK (
        (execution_run_id IS NOT NULL AND rollback_run_id IS NULL) OR
        (execution_run_id IS NULL AND rollback_run_id IS NOT NULL)
      )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verify_logs (
      id TEXT PRIMARY KEY,
      verify_run_id TEXT NOT NULL REFERENCES verify_runs(id),
      operation_log_id TEXT REFERENCES operation_logs(id),
      rollback_log_id TEXT REFERENCES rollback_logs(id),
      sequence_no INTEGER NOT NULL,
      subject_path TEXT NOT NULL,
      counterpart_path TEXT,
      expected_state TEXT NOT NULL,
      actual_state TEXT NOT NULL,
      result TEXT NOT NULL,
      error_message TEXT,
      created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scanned_files_scan_run_id ON scanned_files(scan_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_scanned_metadata_file_id ON scanned_metadata(file_id)",
    "CREATE INDEX IF NOT EXISTS idx_plan_runs_scan_run_id ON plan_runs(scan_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_plan_items_plan_run_id ON plan_items(plan_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_plan_items_file_id ON plan_items(file_id)",
    "CREATE INDEX IF NOT EXISTS idx_execution_runs_plan_run_id ON execution_runs(plan_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_operation_logs_execution_run_id ON operation_logs(execution_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_operation_logs_plan_item_id ON operation_logs(plan_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_rollback_runs_execution_run_id ON rollback_runs(execution_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_rollback_logs_rollback_run_id ON rollback_logs(rollback_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_rollback_logs_operation_log_id ON rollback_logs(operation_log_id)",
    "CREATE INDEX IF NOT EXISTS idx_verify_runs_execution_run_id ON verify_runs(execution_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_verify_runs_rollback_run_id ON verify_runs(rollback_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_verify_logs_verify_run_id ON verify_logs(verify_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_verify_logs_operation_log_id ON verify_logs(operation_log_id)",
    "CREATE INDEX IF NOT EXISTS idx_verify_logs_rollback_log_id ON verify_logs(rollback_log_id)",
)


def initialize_schema(connection: sqlite3.Connection) -> None:
    with connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
