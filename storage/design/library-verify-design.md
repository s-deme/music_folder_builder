# Technical Design: library-verify

## Overview

`library-verify` は、`apply` または `rollback` 実行後の実ファイル状態を read-only に確認するための設計である。主眼は、成功 item に対する expected state を DB から再構築すること、existence と size による軽量検証を行うこと、そして verify 自体の監査ログを専用テーブルに保存することにある。

本設計は `storage/specs/library-verify-requirements.md` の全要件を対象とし、verify に必要な DB、service、filesystem reader、CLI 契約を定義する。

---

## Design Goals

- `verify` は `execution_run_id` または `rollback_run_id` を唯一の入力にする
- verify は完全 read-only とする
- apply 用 / rollback 用の expected state を別 query で扱う
- existence を P0、size comparison を P1 の軽量検証とする
- verify の履歴は apply / rollback と別テーブルで保存する

---

## Architecture Design

### C4 Model: Context Diagram

```text
+-----------------------+        +----------------------------------+
| Individual User       |        | PowerShell / Batch Automation    |
| - checks result       |        | - executes verify                |
| - decides next action |        | - checks exit codes and logs     |
+-----------+-----------+        +----------------+-----------------+
            |                                      |
            v                                      v
      +------------------------------------------------------+
      | music_folder_builder CLI                             |
      | - verify                                             |
      +-----------------------+------------------------------+
                              |
                              v
      +------------------------------------------------------+
      | Core Verify Library                                  |
      | - verify service                                     |
      | - expectation resolver                               |
      +-----------------------+------------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
      +----------------------+     +--------------------------+
      | SQLite State DB      |     | Filesystem Reader        |
      | - execution_runs     |     | - exists                 |
      | - rollback_runs      |     | - size                   |
      | - verify_runs        |     +--------------------------+
      | - verify_logs        |
      +----------------------+
```

### C4 Model: Container Diagram

```text
+--------------------------------------------------------------+
| music_folder_builder                                         |
|                                                              |
|  +------------------+     +-------------------------------+  |
|  | CLI Container    | --> | Verify Core Library          |  |
|  | argparse / main  |     | application + domain         |  |
|  +------------------+     +---------------+--------------+  |
|                                              |               |
|                     +------------------------+-------------+ |
|                     |                                      | |
|                     v                                      v |
|          +-------------------------+       +-----------------+
|          | SQLite Adapter          |       | Filesystem Read |
|          | verify repositories     |       | exists / size   |
|          +-------------------------+       +-----------------+
+--------------------------------------------------------------+
```

### C4 Model: Component Diagram

```text
VerifyCommand
  -> VerifyService
     -> ApplyVerifyRepository
     -> RollbackVerifyRepository
     -> VerifyRunRepository
     -> VerifyLogRepository
     -> FileStateGateway
     -> ExitCodeMapper
```

---

## Directory and Module Design

```text
src/music_folder_builder/
├── cli/
│   └── commands/
│       └── verify.py
├── application/
│   ├── dto/
│   │   ├── verify_request.py
│   │   └── verify_result.py
│   └── services/
│       └── verify_service.py
└── infrastructure/
    ├── db/
    │   ├── apply_verify_repository.py
    │   ├── rollback_verify_repository.py
    │   ├── verify_run_repository.py
    │   └── verify_log_repository.py
    └── fs/
        └── state_gateway.py
```

---

## Command Design

### `verify`

**Purpose**: `apply` または `rollback` 実行後の状態を read-only に検証する  
**Primary Inputs**:

- `--db`
- `--execution-run-id`
- `--rollback-run-id`
- `--config`

**Primary Outputs**:

- `verify_run_id`
- success / skipped / failed / risky counts
- exit code

ルール:

- `execution-run-id` と `rollback-run-id` は同時指定不可
- どちらも無い場合は引数エラー

---

## Application Flow

### Verify Apply Run Flow

1. CLI が `execution_run_id` を解決する
2. `VerifyService` が `verify_run` を開始する
3. `ApplyVerifyRepository` が対象 item を順序付きで取得する
4. success item について expected source/target state を構築する
5. `FileStateGateway` が exists / size を読む
6. item ごとに `verify_logs` を保存する
7. `verify_run` に summary を保存する

### Verify Rollback Run Flow

1. CLI が `rollback_run_id` を解決する
2. `VerifyService` が `verify_run` を開始する
3. `RollbackVerifyRepository` が対象 item を順序付きで取得する
4. success rollback item について expected source/target state を構築する
5. `FileStateGateway` が exists / size を読む
6. item ごとに `verify_logs` を保存する
7. `verify_run` に summary を保存する

---

## Expectation Design

### Apply Success Expectations

| Original action | Expected source | Expected target |
| --- | --- | --- |
| `move` success | absent if `source_deleted=1` | present |
| `copy_delete` success | absent if `source_deleted=1` | present |
| `skip` / `failed` | not enforced | not enforced |

### Rollback Success Expectations

| Rollback action | Expected source | Expected target |
| --- | --- | --- |
| `reverse_move` success | present | absent if `target_deleted=1` |
| `reverse_copy` success | present | absent if `target_deleted=1` |
| `skip` / `failed` | not enforced | not enforced |

### Result Rules

- expected state を満たす: `success`
- 対象外 item: `skipped`
- expected state を満たさない: `failed`
- size mismatch: `failed` with `size_mismatch`

---

## Database Design

verify 専用の `verify_runs` と `verify_logs` を新設し、対象 run が apply か rollback かを外部キーで区別する。

### Entity Relationship

```text
execution_runs 1 --- N verify_runs
rollback_runs 1 --- N verify_runs
verify_runs 1 --- N verify_logs
operation_logs 1 --- N verify_logs
rollback_logs 1 --- N verify_logs
```

### Tables

#### `verify_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | verify run ID |
| execution_run_id | TEXT FK NULL | apply verify の対象 |
| rollback_run_id | TEXT FK NULL | rollback verify の対象 |
| started_at | TEXT | ISO-8601 |
| finished_at | TEXT NULL | ISO-8601 |
| status | TEXT | `running`, `completed`, `partial`, `failed` |
| success_count | INTEGER | |
| skipped_count | INTEGER | |
| failed_count | INTEGER | |
| risky_count | INTEGER | |

Constraint:

- `execution_run_id` と `rollback_run_id` はどちらか一方のみ非 NULL

#### `verify_logs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | verify log ID |
| verify_run_id | TEXT FK | `verify_runs.id` |
| operation_log_id | TEXT FK NULL | apply verify の元 log |
| rollback_log_id | TEXT FK NULL | rollback verify の元 log |
| sequence_no | INTEGER | deterministic ordering |
| subject_path | TEXT | 主検証対象パス |
| counterpart_path | TEXT NULL | 比較対象パス |
| expected_state | TEXT | `target_present_source_absent` など |
| actual_state | TEXT | 実測結果の要約 |
| result | TEXT | `success`, `skipped`, `failed` |
| error_message | TEXT NULL | |
| created_at | TEXT | ISO-8601 |

### DDL Sketch

```sql
CREATE TABLE verify_runs (
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
);

CREATE TABLE verify_logs (
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
);
```

---

## Repository Design

### `ApplyVerifyRepository`

Responsibilities:

- apply success item を deterministic order で取得する
- expected source/target state を構築する

Primary query contract:

```text
fetch_apply_verify_items(execution_run_id) -> list[ApplyVerifyItemRecord]
```

### `RollbackVerifyRepository`

Responsibilities:

- rollback success item を deterministic order で取得する
- expected source/target state を構築する

### `VerifyRunRepository`

Responsibilities:

- verify run の開始・完了を保存する

### `VerifyLogRepository`

Responsibilities:

- item ごとの verify 結果を保存する

---

## Error Handling Design

| Condition | Handling | Result |
| --- | --- | --- |
| run missing | command error | failed |
| both ids specified | argument error | failed |
| target expected but missing | verify failure | failed |
| source expected absent but present | verify failure | failed |
| size mismatch | verify failure | failed |
| skip / failed source item | no expectation enforcement | skipped |

---

## Test Design

### Unit Tests

- apply verify query が success mutation item を返す
- rollback verify query が success rollback item を返す
- apply verify で target present / source absent を判定できる
- rollback verify で source present / target absent を判定できる
- size mismatch を failure にできる

### CLI Tests

- `verify` が `execution-run-id` を受け取れる
- `verify` が `rollback-run-id` を受け取れる
- 両方指定時に argument error を返す
- mismatch 時に deterministic exit code を返す

---

## Requirement Mapping

| Design Element | Requirements | Rationale |
| --- | --- | --- |
| `verify_runs` | REQ-LVF-001, REQ-LVF-007 | verify 実行の独立追跡 |
| `verify_logs` | REQ-LVF-006, REQ-OBS-VF-001 | 期待値と実測値の監査 |
| apply verify repository | REQ-LVF-003, REQ-LVF-008 | apply 後の deterministic verify |
| rollback verify repository | REQ-LVF-004, REQ-LVF-008 | rollback 後の deterministic verify |
| file state gateway | REQ-LVF-002, REQ-LVF-005, REQ-TEST-VF-001 | read-only 検証と testability |

---

## ADR Notes

### ADR-VF-001: Verify Uses Dedicated Run/Log Tables

**Decision**: verify は `verify_runs` / `verify_logs` を新設する。  
**Rationale**: apply / rollback の結果と verify の観測結果は役割が異なる。別テーブルに分けることで、予想された状態と観測された状態の差分を明確に保存できる。  
**Tradeoff**: schema と repository は増えるが、監査と後続の運用判断が単純になる。
