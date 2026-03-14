# Technical Design: library-scan-and-plan

## Overview

`library-scan-and-plan` は、Windows 向け音楽整理 CLI の最初の実装対象である。目的は、対象フォルダの状態を安全に走査して永続化し、その結果から移動計画を生成することで、後続の `apply`, `verify`, `rollback` に耐える基盤を作ることにある。

本設計は `storage/specs/library-scan-and-plan-requirements.md` の全要件を対象とし、`scan` と `plan` に限定した構造とデータ契約を定義する。

---

## Architecture Design

### Design Goals

- `scan` と `plan` を非破壊操作として分離する
- CLI から直接ファイル移動ロジックを呼ばない
- SQLite を業務状態の単一保存先として使う
- Windows 固有のパス制約を `plan` 生成時に吸収する
- 後続機能で再利用できる plan データ構造を先に固める

### C4 Model: Context Diagram

```text
+-----------------------+         +----------------------------------+
| Individual User       |         | PowerShell / Batch Automation    |
| - reviews plan        |         | - runs scan / plan               |
| - configures rules    |         | - consumes exit codes / logs     |
+-----------+-----------+         +----------------+-----------------+
            |                                       |
            v                                       v
       +----------------------------------------------------+
       | music_folder_builder CLI                           |
       | - scan                                             |
       | - plan                                             |
       +----------------------+-----------------------------+
                              |
                              v
       +----------------------------------------------------+
       | Local Music Library + SQLite State DB              |
       | - source files                                     |
       | - scan results                                     |
       | - plan results                                     |
       +----------------------------------------------------+
```

### C4 Model: Container Diagram

```text
+--------------------------------------------------------------+
| music_folder_builder                                         |
|                                                              |
|  +------------------+     +-------------------------------+  |
|  | CLI Container    | --> | Core Library                 |  |
|  | argparse / main  |     | application + domain         |  |
|  +------------------+     +---------------+--------------+  |
|                                              |               |
|                     +------------------------+------------+  |
|                     |                                     |  |
|                     v                                     v  |
|          +-------------------------+       +------------------+
|          | SQLite Adapter          |       | File/Metadata    |
|          | sqlite3 repositories    |       | FS + tag reader  |
|          +-------------------------+       +------------------+
+--------------------------------------------------------------+
```

### C4 Model: Component Diagram

```text
CLI Commands
  -> ScanCommand
  -> PlanCommand

ScanCommand
  -> ScanService
     -> FileWalker
     -> MetadataReader
     -> ScanRepository
     -> RunLogRepository

PlanCommand
  -> PlanService
     -> ScanQueryRepository
     -> PathTemplateEngine
     -> PathSanitizer
     -> PathPolicy
     -> ConflictDetector
     -> PlanRepository

Shared
  -> ConfigLoader
  -> ExitCodeMapper
  -> Logger
```

---

## Directory and Module Design

```text
src/music_folder_builder/
├── cli/
│   ├── main.py
│   └── commands/
│       ├── scan.py
│       └── plan.py
├── application/
│   ├── dto/
│   │   ├── scan_request.py
│   │   ├── scan_result.py
│   │   ├── plan_request.py
│   │   └── plan_result.py
│   └── services/
│       ├── scan_service.py
│       └── plan_service.py
├── domain/
│   ├── models/
│   │   ├── file_record.py
│   │   ├── metadata_record.py
│   │   ├── scan_run.py
│   │   ├── plan_item.py
│   │   └── plan_run.py
│   ├── policies/
│   │   ├── path_sanitization.py
│   │   ├── path_policy.py
│   │   ├── conflict_policy.py
│   │   └── organization_rules.py
│   └── errors/
│       ├── input_errors.py
│       └── planning_errors.py
└── infrastructure/
    ├── db/
    │   ├── connection.py
    │   ├── schema.py
    │   ├── scan_repository.py
    │   ├── plan_repository.py
    │   └── run_repository.py
    ├── fs/
    │   ├── walker.py
    │   └── file_info.py
    ├── metadata/
    │   └── reader.py
    └── logging/
        └── logger.py
```

---

## Command Design

### `scan`

**Purpose**: source root を走査して scan result を保存する  
**Primary Inputs**:

- `--source`
- `--db`
- `--config`
- `--follow-links` は将来拡張候補だが既定では false

**Primary Outputs**:

- `scan_run_id`
- 保存済み file / metadata 件数
- 警告件数
- 終了コード

### `plan`

**Purpose**: 保存済み scan 結果から target path 候補を生成する  
**Primary Inputs**:

- `--scan-run-id` または最新 scan の参照
- `--db`
- `--config`
- `--json`

**Primary Outputs**:

- `plan_run_id`
- `plan_item` 一覧
- 衝突件数
- 危険件数
- 終了コード

---

## Application Flow

### Scan Flow

1. CLI が引数を検証する
2. `ScanService` が `scan_run` を開始する
3. `FileWalker` が対象ディレクトリを再帰走査する
4. reparse point は既定値で除外する
5. 対象拡張子ファイルを `MetadataReader` に渡す
6. `ScanRepository` が file 情報と metadata を逐次保存する
7. `RunRepository` が完了状態と統計を保存する
8. `ExitCodeMapper` が終了コードを決定する

### Plan Flow

1. CLI が対象 scan を解決する
2. `PlanService` が `plan_run` を開始する
3. `ScanQueryRepository` が scan 結果をストリームまたはページ単位で取得する
4. `OrganizationRules` が target path 素材を組み立てる
5. `PathSanitizer` が Windows 禁止文字・予約名・末尾不正を正規化する
6. `PathPolicy` が長パス危険を判定する
7. `ConflictDetector` が target path 衝突を判定する
8. `PlanRepository` が action, target path, reason, risk を保存する
9. `ExitCodeMapper` が危険状態に応じて終了コードを返す

---

## Database Design

SQLite を内部状態保存に使う。初期版では migration ツールを前提にせず、起動時に schema 初期化を行う。

### Entity Relationship

```text
scan_runs 1 --- N scanned_files 1 --- 1 scanned_metadata
scan_runs 1 --- N plan_runs
plan_runs 1 --- N plan_items
```

### Tables

#### `scan_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | UUID or timestamp-based ID |
| source_root | TEXT | scan 対象 root |
| started_at | TEXT | ISO-8601 |
| finished_at | TEXT NULL | ISO-8601 |
| status | TEXT | `running`, `completed`, `failed`, `partial` |
| file_count | INTEGER | 集計 |
| warning_count | INTEGER | 集計 |

#### `scanned_files`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | file record ID |
| scan_run_id | TEXT FK | `scan_runs.id` |
| source_path | TEXT | 元ファイルの絶対パス |
| source_root | TEXT | 再利用しやすさのため冗長保持可 |
| extension | TEXT | lowercase |
| size_bytes | INTEGER | |
| mtime_utc | TEXT | |
| file_type | TEXT | `music`, `ignored`, `unsupported` |
| exclusion_reason | TEXT NULL | 除外理由 |
| link_state | TEXT | `normal`, `reparse_skipped` |

#### `scanned_metadata`

| Column | Type | Notes |
| --- | --- | --- |
| file_id | TEXT PK/FK | `scanned_files.id` |
| artist | TEXT NULL | |
| album_artist | TEXT NULL | |
| album | TEXT NULL | |
| title | TEXT NULL | |
| track_no | INTEGER NULL | |
| disc_no | INTEGER NULL | |
| year | INTEGER NULL | |
| metadata_status | TEXT | `ok`, `partial`, `missing`, `error` |
| metadata_error | TEXT NULL | |

#### `plan_runs`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | plan run ID |
| scan_run_id | TEXT FK | 対象 scan |
| started_at | TEXT | |
| finished_at | TEXT NULL | |
| status | TEXT | `running`, `completed`, `failed`, `partial` |
| rule_profile | TEXT | 将来拡張向け |
| conflict_count | INTEGER | |
| risk_count | INTEGER | |

#### `plan_items`

| Column | Type | Notes |
| --- | --- | --- |
| id | TEXT PK | plan item ID |
| plan_run_id | TEXT FK | |
| file_id | TEXT FK | `scanned_files.id` |
| action | TEXT | `move`, `skip` |
| target_path | TEXT NULL | |
| target_path_sanitized | TEXT NULL | |
| conflict_status | TEXT | `none`, `duplicate_target`, `existing_target` |
| risk_status | TEXT | `none`, `path_too_long`, `invalid_target` |
| reason | TEXT NULL | 説明用 |

### DDL Sketch

```sql
CREATE TABLE scan_runs (
  id TEXT PRIMARY KEY,
  source_root TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  file_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE scanned_files (
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
);

CREATE TABLE scanned_metadata (
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
);

CREATE TABLE plan_runs (
  id TEXT PRIMARY KEY,
  scan_run_id TEXT NOT NULL REFERENCES scan_runs(id),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  rule_profile TEXT NOT NULL,
  conflict_count INTEGER NOT NULL DEFAULT 0,
  risk_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE plan_items (
  id TEXT PRIMARY KEY,
  plan_run_id TEXT NOT NULL REFERENCES plan_runs(id),
  file_id TEXT NOT NULL REFERENCES scanned_files(id),
  action TEXT NOT NULL,
  target_path TEXT,
  target_path_sanitized TEXT,
  conflict_status TEXT NOT NULL,
  risk_status TEXT NOT NULL,
  reason TEXT
);
```

---

## Domain Design

### `FileRecord`

- source path
- size / mtime / extension
- file classification
- scan run association

### `MetadataRecord`

- normalized metadata fields
- extraction status
- extraction error summary

### `PlanItem`

- source file reference
- target path candidate
- action
- conflict / risk state
- human-readable reason

### `OrganizationRules`

- path template evaluation
- metadata fallback decision
- compilation / unknown artist rules は将来拡張

### `PathSanitizer`

- invalid char replacement
- reserved name escaping
- trailing space / trailing period cleanup

### `PathPolicy`

- component length check
- full path length check
- Windows-specific risk classification

### `ConflictDetector`

- duplicate target path detection within the current plan
- existing destination path detection against filesystem

---

## Logging and Exit Codes

### Logging

- CLI summary: 人間向けの件数表示
- Structured log: 進捗、警告、失敗、risk 検出の記録
- DB state: scan / plan 実行の正式記録

### Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | 成功 |
| 2 | 引数エラー |
| 3 | 衝突または危険状態あり |
| 4 | 一部失敗 |
| 5 | 危険な事前条件検出 |

`scan` と `plan` は、warning のみなら 0、衝突や危険な target が含まれる場合は 3 を返す方針とする。

---

## Error Handling

- source root 不正: 即時に引数エラー
- DB 接続不能: 実行失敗として終了
- metadata 読み取り失敗: file 単位で `metadata_status=error` を保存し、全体継続
- target path 生成不能: `plan_item.action=skip` と `reason` を保存
- 長パス: `risk_status=path_too_long`
- 既存ファイル衝突: `conflict_status=existing_target`

---

## Requirements Mapping

| Component / Decision | Requirements | Design Rationale |
| --- | --- | --- |
| `ScanCommand` | REQ-LSP-001, REQ-LSP-013 | CLI entry point と終了コード制御 |
| `FileWalker` | REQ-LSP-002, REQ-LSP-005, REQ-WIN-001 | 対象拡張子判定と reparse point 非追跡 |
| `MetadataReader` | REQ-LSP-003, REQ-TEST-001 | metadata 抽出を独立コンポーネント化 |
| SQLite repositories | REQ-LSP-004, REQ-LSP-006, REQ-REL-001, REQ-LSP-014 | 再実行性と監査可能性 |
| `PlanService` | REQ-LSP-007, REQ-LSP-012 | 保存済み scan を元に計画生成 |
| `OrganizationRules` | REQ-LSP-008 | ルールベースの path 構築 |
| `PathSanitizer` | REQ-LSP-009, REQ-WIN-001 | Windows 禁止文字と予約名への対応 |
| `PathPolicy` | REQ-LSP-010 | 長パスを risk として扱う |
| `ConflictDetector` | REQ-LSP-011 | apply 前に衝突を顕在化する |
| log separation | REQ-OBS-001, REQ-LSP-012 | 人間向け表示と内部ログの分離 |
| incremental persistence | REQ-PERF-001, REQ-REL-001 | 全件メモリ保持を避ける |
| library-first module split | REQ-TEST-001 | CLI と業務ロジックの分離 |

Coverage validation:

- All functional requirements mapped: Yes
- All non-functional requirements addressed: Yes
- 100% requirements coverage: Yes

---

## Test Design

### Unit Tests

- extension filter
- path sanitization
- reserved name normalization
- path length policy
- conflict detection
- metadata fallback rule

### Integration Tests

- `scan` が DB に file / metadata を保存する
- `plan` が scan 結果から `plan_items` を生成する
- reparse point 非追跡
- metadata 欠損ファイルの skip / fallback
- path too long の risk 保存

### Windows-Focused Tests

- 日本語 path
- 予約名 `CON`, `NUL`
- 禁止文字を含む title
- 長パス近傍の target
- 既存 destination との衝突

---

## ADR Summary

### ADR-001: SQLite を内部状態ストアとする

**Decision**: `scan` と `plan` の結果を SQLite に保存する。  
**Rationale**: 再実行性、追跡性、中断耐性を満たしやすい。

### ADR-002: `scan` と `plan` を非破壊コマンドとして分離する

**Decision**: `plan` は保存済み scan のみを入力とし、直接変更しない。  
**Rationale**: apply 前のレビュー可能性を最大化する。

### ADR-003: Windows 固有制約は Domain/Application で明示的に扱う

**Decision**: 禁止文字、予約名、長パス、reparse point を暗黙にせず専用ポリシーに分離する。  
**Rationale**: バグを局所化し、単体テスト可能にする。

---

## Open Questions

- metadata reader にどのライブラリを使うか
- `plan` 実行時の既存 destination チェックをどの粒度で行うか
- path shortening の具体ルールをどうするか
- config フォーマットを YAML にするか TOML にするか
