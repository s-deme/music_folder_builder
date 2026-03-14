# Technical Design: library-apply

## Overview

`library-apply` は、永続化済み `plan_run` を入力にして、実ファイルへ安全に変更を適用するための設計である。主眼は、dry-run と本実行の分離、same-volume / cross-volume の適用戦略、operation log の完全保存、将来の rollback を可能にする履歴の保持にある。

本設計は `storage/specs/library-apply-requirements.md` の全要件を対象とし、`apply` に必要な DB、service、filesystem adapter、CLI 契約を定義する。

---

## Design Goals

- `apply` は `plan_run` を唯一の入力にする
- dry-run と本実行を同じ service 契約で扱う
- same-volume は move、cross-volume は copy/verify/delete を基本戦略にする
- unsafe 状態では source を消さない
- 実行ログから rollback に必要な履歴を再構築できる

---

## Architecture Design

### C4 Model: Context Diagram

```text
+-----------------------+        +----------------------------------+
| Individual User       |        | PowerShell / Batch Automation    |
| - reviews dry-run     |        | - executes apply                 |
| - approves execution  |        | - checks exit codes and logs     |
+-----------+-----------+        +----------------+-----------------+
            |                                      |
            v                                      v
      +------------------------------------------------------+
      | music_folder_builder CLI                             |
      | - apply                                              |
      +-----------------------+------------------------------+
                              |
                              v
      +------------------------------------------------------+
      | Core Apply Library                                   |
      | - apply service                                      |
      | - execution policy                                   |
      +-----------------------+------------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
      +----------------------+     +--------------------------+
      | SQLite State DB      |     | Filesystem Adapter       |
      | - plan_runs          |     | - move / copy / delete   |
      | - execution_runs     |     | - existence checks       |
      | - operation_logs     |     | - volume checks          |
      +----------------------+     +--------------------------+
```

### C4 Model: Container Diagram

```text
+--------------------------------------------------------------+
| music_folder_builder                                         |
|                                                              |
|  +------------------+     +-------------------------------+  |
|  | CLI Container    | --> | Apply Core Library           |  |
|  | argparse / main  |     | application + domain         |  |
|  +------------------+     +---------------+--------------+  |
|                                              |               |
|                     +------------------------+-------------+ |
|                     |                                      | |
|                     v                                      v |
|          +-------------------------+       +-----------------+
|          | SQLite Adapter          |       | Filesystem I/O  |
|          | execution repositories  |       | mover/verifier  |
|          +-------------------------+       +-----------------+
+--------------------------------------------------------------+
```

### C4 Model: Component Diagram

```text
ApplyCommand
  -> ApplyService
     -> PlanQueryRepository
     -> ExecutionRepository
     -> OperationLogRepository
     -> ApplyStrategyResolver
     -> FileMutationGateway
     -> FileVerificationGateway
     -> ExitCodeMapper

ApplyStrategyResolver
  -> SameVolumeMoveStrategy
  -> CrossVolumeCopyStrategy
  -> DryRunStrategy
```

---

## Directory and Module Design

```text
src/music_folder_builder/
├── cli/
│   └── commands/
│       └── apply.py
├── application/
│   ├── dto/
│   │   ├── apply_request.py
│   │   └── apply_result.py
│   └── services/
│       └── apply_service.py
├── domain/
│   ├── models/
│   │   ├── execution_run.py
│   │   └── operation_log.py
│   └── policies/
│       ├── apply_strategy.py
│       └── volume_policy.py
└── infrastructure/
    ├── db/
    │   ├── execution_repository.py
    │   ├── operation_log_repository.py
    │   └── plan_query_repository.py
    └── fs/
        ├── mutation_gateway.py
        └── verification_gateway.py
```

---

## Command Design

### `apply`

**Purpose**: `plan_run` を入力にして計画を dry-run または本実行する  
**Primary Inputs**:

- `--plan-run-id`
- `--db`
- `--dry-run`
- `--config`

**Primary Outputs**:

- `execution_run_id`
- success / skipped / failed / risky counts
- exit code

---

## Application Flow

### Dry-Run Flow

1. CLI が `plan_run_id` を解決する
2. `ApplyService` が `execution_run` を `dry_run` モードで開始する
3. `PlanQueryRepository` が plan items を安定順序で取得する
4. 各 item について strategy を解決する
5. 実ファイル変更は行わず、予測結果を `operation_logs` に記録する
6. `execution_run` に summary を保存する
7. exit code を返す

### Real Apply Flow

1. CLI が `plan_run_id` を解決する
2. `ApplyService` が `execution_run` を開始する
3. `PlanQueryRepository` が `plan_items` を取得する
4. `skip` item は source を変更せず log に記録する
5. `move` item は volume 判定で strategy を選ぶ
6. same-volume は rename/move を試行する
7. cross-volume は copy -> verify -> delete の順で処理する
8. item ごとに `operation_logs` を保存する
9. `execution_run` に summary と status を保存する
10. exit code を返す

---

## Strategy Design

### Strategy Selection

| Condition | Strategy | Notes |
| --- | --- | --- |
| `--dry-run` | `DryRunStrategy` | ファイル変更なし |
| `plan_item.action = skip` | `SkipStrategy` | plan 決定を尊重 |
| same volume | `SameVolumeMoveStrategy` | rename / move |
| cross volume | `CrossVolumeCopyStrategy` | copy / verify / delete |

### SameVolumeMoveStrategy

- source exists を確認
- target exists なら skip
- move 実行
- 成功時に operation log を保存

### CrossVolumeCopyStrategy

- source exists を確認
- target exists なら skip
- copy 実行
- size or hash-based verification を実行
- verify 成功時のみ source delete
- 失敗時は source を保持

---

## Database Design

`library-apply` では既存 `plan_runs` / `plan_items` に加え、`execution_runs` と `operation_logs` を追加する。

### Entity Relationship

```text
plan_runs 1 --- N plan_items
plan_runs 1 --- N execution_runs
execution_runs 1 --- N operation_logs
plan_items 1 --- N operation_logs
```

### Tables

#### `execution_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | execution run ID |
| plan_run_id | TEXT FK | 対象 plan |
| mode | TEXT | `dry_run` or `apply` |
| started_at | TEXT | ISO-8601 |
| finished_at | TEXT NULL | ISO-8601 |
| status | TEXT | `running`, `completed`, `partial`, `failed` |
| success_count | INTEGER | |
| skipped_count | INTEGER | |
| failed_count | INTEGER | |
| risky_count | INTEGER | |

#### `operation_logs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | operation log ID |
| execution_run_id | TEXT FK | `execution_runs.id` |
| plan_item_id | TEXT FK | `plan_items.id` |
| sequence_no | INTEGER | deterministic ordering |
| source_path | TEXT | source |
| target_path | TEXT | planned target |
| performed_action | TEXT | `dry_run`, `move`, `copy`, `verify`, `delete`, `skip` |
| result | TEXT | `success`, `skipped`, `failed` |
| error_message | TEXT NULL | |
| source_deleted | INTEGER | 0/1 |
| created_at | TEXT | ISO-8601 |

### DDL Sketch

```sql
CREATE TABLE execution_runs (
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
);

CREATE TABLE operation_logs (
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
);
```

---

## Filesystem Gateway Design

### `FileMutationGateway`

- `move(source, target)`
- `copy(source, target)`
- `delete(source)`
- `exists(path)`
- `same_volume(source, target)`

### `FileVerificationGateway`

- `verify_copy(source, target)`
- 初期版は size 一致を最低ラインにする
- 将来 hash-based verification を差し替え可能にする

---

## Error Handling

- missing plan_run: argument/state error
- missing source file: item failure
- target already exists: item skip
- move failure: item failure
- copy failure: item failure
- verify failure: item failure, source retained
- delete failure after successful copy: partial failure, source retained if possible

---

## Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | 全成功 |
| 2 | 引数エラー |
| 3 | blocked / risky / skipped due to unsafe state |
| 4 | 一部失敗 |

`apply` は unsafe item が含まれる dry-run では 3、本実行で item failure があれば 4 を返す方針とする。

---

## Requirements Mapping

| Component / Decision | Requirements | Design Rationale |
| --- | --- | --- |
| `ApplyService` input contract | REQ-LAP-001 | plan_run を唯一入力に限定 |
| `DryRunStrategy` | REQ-LAP-002, REQ-TEST-AP-001 | 非破壊 apply の保証 |
| `SameVolumeMoveStrategy` | REQ-LAP-003 | 同一ボリューム最適化 |
| `CrossVolumeCopyStrategy` | REQ-LAP-004, REQ-LAP-005 | copy/verify/delete と source 保護 |
| `operation_logs` | REQ-LAP-006, REQ-LAP-011, REQ-OBS-AP-001 | rollback-ready かつ監査可能 |
| `execution_runs` | REQ-LAP-007, REQ-REL-AP-001 | apply run の状態保存 |
| skip handling | REQ-LAP-008 | plan 決定を尊重 |
| target protection | REQ-LAP-009 | overwrite 防止 |
| re-run guard | REQ-LAP-010 | duplicate mutation 防止 |
| ordered retrieval | REQ-LAP-014 | deterministic ordering |
| sanitized target reuse | REQ-WIN-AP-001 | Windows path 契約を再利用 |
| summary + exit codes | REQ-LAP-012, REQ-LAP-013 | CLI 自動化と報告 |

Coverage validation:

- All functional requirements mapped: Yes
- All non-functional requirements addressed: Yes
- 100% requirements coverage: Yes

---

## Test Design

### Unit Tests

- dry-run does not mutate files
- same-volume move path
- cross-volume copy/verify/delete path
- verify failure keeps source
- skip item preserves source
- re-run guard blocks duplicate mutation

### Integration Tests

- `plan -> apply(dry-run)` persists execution logs
- `plan -> apply` on same volume
- `plan -> apply` on cross volume
- operation log and execution summary persistence

### Windows-Focused Tests

- sanitized target path is reused as-is
- existing target causes skip
- delete failure leaves recoverable state

---

## ADR Summary

### ADR-AP-001: `apply` は `plan_run` のみを入力にする

**Decision**: 実行時に target path を再計算しない。  
**Rationale**: plan 時点の判断と path sanitization 契約を固定するため。

### ADR-AP-002: cross-volume は copy/verify/delete を標準戦略にする

**Decision**: 異ボリュームでは move 相当の一発処理に依存しない。  
**Rationale**: source 保護と failure isolation を優先するため。

### ADR-AP-003: dry-run も execution log を残す

**Decision**: dry-run でも `execution_runs` / `operation_logs` に記録する。  
**Rationale**: 事前確認結果を監査できるようにするため。

---

## Open Questions

- verify を size だけにするか hash も含めるか
- same-volume 判定を Windows ドライブレターだけで扱うか inode/device 情報も使うか
- delete failure 後の cleanup 再試行をどこまで組み込むか
