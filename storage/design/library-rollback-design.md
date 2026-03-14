# Technical Design: library-rollback

## Overview

`library-rollback` は、永続化済み `execution_run` を入力にして、`apply` によるファイル変更を安全に逆方向へ戻すための設計である。主眼は、successful apply item のみを対象にすること、逆順で処理すること、same-volume / cross-volume の rollback 戦略を分離すること、そして rollback 自体の監査ログを専用テーブルに保存することにある。

本設計は `storage/specs/library-rollback-requirements.md` の全要件を対象とし、rollback に必要な DB、service、filesystem adapter、CLI 契約を定義する。

---

## Design Goals

- `rollback` は `execution_run_id` を唯一の入力にする
- rollback は apply の成功ログだけを対象にする
- item は `sequence_no` の逆順で処理する
- same-volume は reverse move、cross-volume は reverse copy/verify/delete を使う
- rollback の履歴は apply とは別テーブルで保存する

---

## Architecture Design

### C4 Model: Context Diagram

```text
+-----------------------+        +----------------------------------+
| Individual User       |        | PowerShell / Batch Automation    |
| - reviews dry-run     |        | - executes rollback              |
| - approves rollback   |        | - checks exit codes and logs     |
+-----------+-----------+        +----------------+-----------------+
            |                                      |
            v                                      v
      +------------------------------------------------------+
      | music_folder_builder CLI                             |
      | - rollback                                           |
      +-----------------------+------------------------------+
                              |
                              v
      +------------------------------------------------------+
      | Core Rollback Library                                |
      | - rollback service                                   |
      | - reverse execution policy                           |
      +-----------------------+------------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
      +----------------------+     +--------------------------+
      | SQLite State DB      |     | Filesystem Adapter       |
      | - execution_runs     |     | - move / copy / delete   |
      | - operation_logs     |     | - existence checks       |
      | - rollback_runs      |     | - volume checks          |
      | - rollback_logs      |     | - size verification      |
      +----------------------+     +--------------------------+
```

### C4 Model: Container Diagram

```text
+--------------------------------------------------------------+
| music_folder_builder                                         |
|                                                              |
|  +------------------+     +-------------------------------+  |
|  | CLI Container    | --> | Rollback Core Library        |  |
|  | argparse / main  |     | application + domain         |  |
|  +------------------+     +---------------+--------------+  |
|                                              |               |
|                     +------------------------+-------------+ |
|                     |                                      | |
|                     v                                      v |
|          +-------------------------+       +-----------------+
|          | SQLite Adapter          |       | Filesystem I/O  |
|          | rollback repositories   |       | mover/verifier  |
|          +-------------------------+       +-----------------+
+--------------------------------------------------------------+
```

### C4 Model: Component Diagram

```text
RollbackCommand
  -> RollbackService
     -> ApplyHistoryRepository
     -> RollbackRunRepository
     -> RollbackLogRepository
     -> RollbackStrategyResolver
     -> FileMutationGateway
     -> ExitCodeMapper

RollbackStrategyResolver
  -> RollbackDryRunStrategy
  -> ReverseMoveStrategy
  -> ReverseCopyStrategy
  -> SkipRollbackStrategy
```

---

## Directory and Module Design

```text
src/music_folder_builder/
├── cli/
│   └── commands/
│       └── rollback.py
├── application/
│   ├── dto/
│   │   ├── rollback_request.py
│   │   └── rollback_result.py
│   └── services/
│       └── rollback_service.py
├── domain/
│   └── policies/
│       └── rollback_strategy.py
└── infrastructure/
    ├── db/
    │   ├── apply_history_repository.py
    │   ├── rollback_run_repository.py
    │   └── rollback_log_repository.py
    └── fs/
        └── mutation_gateway.py
```

---

## Command Design

### `rollback`

**Purpose**: `execution_run` を入力にして rollback を dry-run または本実行する  
**Primary Inputs**:

- `--execution-run-id`
- `--db`
- `--dry-run`
- `--config`

**Primary Outputs**:

- `rollback_run_id`
- success / skipped / failed / risky counts
- exit code

---

## Application Flow

### Dry-Run Flow

1. CLI が `execution_run_id` を解決する
2. `RollbackService` が `rollback_run` を `dry_run` モードで開始する
3. `ApplyHistoryRepository` が rollback 対象 item を `sequence_no DESC` で取得する
4. item ごとに rollback eligibility を判定する
5. 実ファイル変更は行わず、予測結果を `rollback_logs` に記録する
6. `rollback_run` に summary を保存する
7. exit code を返す

### Real Rollback Flow

1. CLI が `execution_run_id` を解決する
2. `RollbackService` が `rollback_run` を開始する
3. `ApplyHistoryRepository` が apply success item を逆順で取得する
4. 既に rollback 済み item は skip として記録する
5. same-volume item は `target -> source` の reverse move を試行する
6. cross-volume item は `target -> source` の copy -> verify -> delete を試行する
7. unsafe 状態では surviving copy を消さず `failed` または `skipped` にする
8. item ごとに `rollback_logs` を保存する
9. `rollback_run` に summary と status を保存する
10. exit code を返す

---

## Strategy Design

### Rollback Eligibility

rollback 対象は次を満たす item に限定する。

- 元 `operation_logs.result = success`
- 元 `execution_runs.mode = apply`
- 元 `operation_logs.performed_action` が mutation を伴う
- 同一 item に成功済み rollback が無い

対象外 item は `skip` として `rollback_logs` に残す。

### Strategy Selection

| Condition | Strategy | Notes |
| --- | --- | --- |
| `--dry-run` | `RollbackDryRunStrategy` | ファイル変更なし |
| already rolled back | `SkipRollbackStrategy` | 二重 rollback 防止 |
| original action = `move` | `ReverseMoveStrategy` | `target -> source` |
| original action = `copy_delete` | `ReverseCopyStrategy` | copy / verify / delete |
| original action = `dry_run`, `skip`, `copy` failed | `SkipRollbackStrategy` | rollback 対象外 |

### ReverseMoveStrategy

- target exists を確認
- source exists なら skip
- move 実行
- 成功時に `target_deleted = true` 相当の意味で rollback log を保存

### ReverseCopyStrategy

- target exists を確認
- source exists なら skip
- copy 実行
- source/target の size verify を実行
- verify 成功時のみ target delete
- 失敗時は source と target の surviving copy を保持する

---

## Database Design

`library-rollback` では既存 `execution_runs` / `operation_logs` を参照しつつ、rollback 専用の `rollback_runs` と `rollback_logs` を新設する。

### Entity Relationship

```text
execution_runs 1 --- N operation_logs
execution_runs 1 --- N rollback_runs
rollback_runs 1 --- N rollback_logs
operation_logs 1 --- N rollback_logs
```

### Tables

#### `rollback_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | rollback run ID |
| execution_run_id | TEXT FK | 対象 apply 実行 |
| mode | TEXT | `dry_run` or `rollback` |
| started_at | TEXT | ISO-8601 |
| finished_at | TEXT NULL | ISO-8601 |
| status | TEXT | `running`, `completed`, `partial`, `failed` |
| success_count | INTEGER | |
| skipped_count | INTEGER | |
| failed_count | INTEGER | |
| risky_count | INTEGER | |

#### `rollback_logs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | rollback log ID |
| rollback_run_id | TEXT FK | `rollback_runs.id` |
| operation_log_id | TEXT FK | 元 apply operation |
| sequence_no | INTEGER | reverse deterministic ordering |
| source_path | TEXT | apply 時の source |
| target_path | TEXT | apply 時の target |
| performed_action | TEXT | `rollback_dry_run`, `reverse_move`, `reverse_copy`, `skip` |
| result | TEXT | `success`, `skipped`, `failed` |
| error_message | TEXT NULL | |
| target_deleted | INTEGER | 0/1 |
| created_at | TEXT | ISO-8601 |

### DDL Sketch

```sql
CREATE TABLE rollback_runs (
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
);

CREATE TABLE rollback_logs (
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
);
```

---

## Repository Design

### `ApplyHistoryRepository`

Responsibilities:

- `execution_run_id` に紐づく apply success log を逆順で取得する
- rollback 対象外 action を識別する
- 同一 operation log に対する成功 rollback の有無を確認する

Primary query contract:

```text
fetch_rollback_items(execution_run_id) -> list[RollbackItemRecord]
```

### `RollbackRunRepository`

Responsibilities:

- rollback run の開始・完了を保存する

### `RollbackLogRepository`

Responsibilities:

- item ごとの rollback 結果を保存する
- duplicate rollback 判定用の成功履歴を返す

---

## Error Handling Design

| Condition | Handling | Result |
| --- | --- | --- |
| execution run missing | command error | failed |
| target missing | skip or failed | source side untouched |
| source exists already | skip | target untouched |
| reverse verify failed | failed | surviving copies kept |
| duplicate rollback detected | skip | no mutation |

---

## Test Design

### Unit Tests

- apply history query が success apply item のみ返す
- reverse ordering が `sequence_no DESC` になる
- duplicate rollback 判定ができる
- same-volume reverse move が成功する
- cross-volume reverse copy/verify/delete が成功する
- verify failure で surviving copy を保持する

### CLI Tests

- `rollback` が `execution_run_id` と `db` を受け取れる
- `--dry-run` を受け取れる
- partial failure 時に deterministic exit code を返す

---

## Requirement Mapping

| Design Element | Requirements | Rationale |
| --- | --- | --- |
| `rollback_runs` | REQ-LRB-001, REQ-LRB-009 | rollback 実行の独立追跡 |
| `rollback_logs` | REQ-LRB-008, REQ-OBS-RB-001 | apply と rollback の監査分離 |
| reverse ordering | REQ-LRB-004 | deterministic rollback |
| success-only eligibility | REQ-LRB-003, REQ-LRB-010 | unsafe item の除外と二重 rollback 防止 |
| reverse move / reverse copy | REQ-LRB-005, REQ-LRB-006, REQ-LRB-007 | same/cross volume の安全な逆操作 |

---

## ADR Notes

### ADR-RB-001: Rollback Tables Are Separated From Apply Tables

**Decision**: rollback は `rollback_runs` / `rollback_logs` を新設する。  
**Rationale**: apply と rollback の監査軸を混ぜると、どの操作が元実行でどの操作が巻き戻しなのか曖昧になる。専用テーブルに分けることで、元 execution と rollback execution の対応関係、二重 rollback 判定、監査検索が単純になる。  
**Tradeoff**: schema と repository が増える。ただし追跡性と将来の verify / audit の明確さを優先する。
