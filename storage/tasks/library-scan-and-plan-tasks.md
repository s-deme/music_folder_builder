# Task Breakdown: library-scan-and-plan

## Overview

このタスク分解は `storage/design/library-scan-and-plan-design.md` を実装可能な単位に分けたものである。最優先は、`scan` と `plan` を安全な非破壊コマンドとして成立させること、そのために必要な SQLite、Windows path policy、CLI 契約、テスト基盤を先に整えることにある。

---

## Execution Strategy

1. まずプロジェクト名と Python パッケージ構成を整える
2. DB 初期化と共通モデルを先に作る
3. `scan` を Red-Green-Blue で成立させる
4. `plan` の path rule / sanitizer / conflict detection を Red-Green-Blue で成立させる
5. 最後に CLI の統合テストと Windows ケースを足す

---

## P0 Tasks

### TASK-001: Align Package Structure and Project Identity

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 2  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`workspace` の仮名を `music_folder_builder` にそろえ、設計書どおりの Python パッケージ構成を作る。

**Requirements Coverage**:

- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] `pyproject.toml` の project name と package path がプロジェクト名に一致する
- [ ] `src/music_folder_builder/` の基本ディレクトリが作成される
- [ ] 既存の仮 package 名が後続実装の障害にならない

**Dependencies**:

- None

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

**Implementation Notes**:

- `pyproject.toml`
- `src/music_folder_builder/`
- 既存 `src/workspace/` の扱いを整理する

---

### TASK-002: Write Failing Tests for SQLite Schema Initialization

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
SQLite schema の初期化に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-004: SQLite Persistence
- REQ-REL-001: Crash Resilience
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] schema 初期化テストが追加される
- [ ] `scan_runs`, `scanned_files`, `scanned_metadata`, `plan_runs`, `plan_items` を検証する
- [ ] テストは初期実装前には失敗する

**Dependencies**:

- TASK-001: package path 整備

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-003: Implement SQLite Connection and Schema Bootstrap

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`sqlite3` 接続と schema bootstrap を実装し、DB 初期化可能な状態にする。

**Requirements Coverage**:

- REQ-LSP-004: SQLite Persistence
- REQ-REL-001: Crash Resilience

**Acceptance Criteria**:

- [ ] DB 接続ヘルパが実装される
- [ ] schema 初期化関数が実装される
- [ ] TASK-002 のテストが通る

**Dependencies**:

- TASK-002: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-004: Refactor Database Layer for Repository Reuse

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 2  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
DB 初期化コードを repository から再利用しやすい構造へ整理する。

**Requirements Coverage**:

- REQ-LSP-004: SQLite Persistence
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] DB 接続責務と schema 責務が分離される
- [ ] repository が共通接続ヘルパを再利用できる
- [ ] テストが維持される

**Dependencies**:

- TASK-003: SQLite bootstrap 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-005: Write Failing Tests for File Classification and Reparse Handling

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
対象拡張子判定、非対象ファイル扱い、reparse point 非追跡の failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-001: Scan Command Entry Point
- REQ-LSP-002: Music File Detection
- REQ-LSP-005: Reparse Point Handling
- REQ-WIN-001: Windows Compatibility

**Acceptance Criteria**:

- [ ] 対象拡張子の判定テストがある
- [ ] 非対象ファイル除外のテストがある
- [ ] reparse point 非追跡方針のテストがある
- [ ] テストは実装前に失敗する

**Dependencies**:

- TASK-001: package path 整備

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-006: Implement FileWalker and File Classification

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`scan` 用の walker を実装し、対象ファイル分類と reparse point 非追跡を成立させる。

**Requirements Coverage**:

- REQ-LSP-001: Scan Command Entry Point
- REQ-LSP-002: Music File Detection
- REQ-LSP-005: Reparse Point Handling
- REQ-PERF-001: Scan Throughput

**Acceptance Criteria**:

- [ ] walker が逐次的に file record を返す
- [ ] 対象拡張子だけを音楽ファイル候補として扱う
- [ ] reparse point を既定で辿らない
- [ ] TASK-005 のテストが通る

**Dependencies**:

- TASK-005: failing tests
- TASK-003: DB bootstrap

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-007: Write Failing Tests for Metadata Persistence and Scan Run Tracking

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
metadata 保存、scan run 記録、部分失敗継続の failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-003: Metadata Extraction
- REQ-LSP-004: SQLite Persistence
- REQ-LSP-006: Scan Reproducibility
- REQ-LSP-014: Auditability
- REQ-REL-001: Crash Resilience

**Acceptance Criteria**:

- [ ] metadata fields の保存を検証するテストがある
- [ ] `scan_run` の開始・完了記録を検証するテストがある
- [ ] metadata 読み取り失敗時の継続動作テストがある
- [ ] テストは実装前に失敗する

**Dependencies**:

- TASK-003: DB bootstrap
- TASK-006: walker

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-008: Implement ScanService and Scan Repositories

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 8  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`ScanService`、scan repositories、scan run tracking を実装して `scan` のコアを成立させる。

**Requirements Coverage**:

- REQ-LSP-001: Scan Command Entry Point
- REQ-LSP-003: Metadata Extraction
- REQ-LSP-004: SQLite Persistence
- REQ-LSP-006: Scan Reproducibility
- REQ-LSP-014: Auditability
- REQ-OBS-001: Structured Logging

**Acceptance Criteria**:

- [ ] `scan_run` を開始・完了できる
- [ ] file / metadata を逐次保存できる
- [ ] metadata error を file 単位で記録して継続できる
- [ ] TASK-007 のテストが通る

**Dependencies**:

- TASK-007: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-009: Refactor Scan Flow for Clear DTO and Logging Boundaries

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 2  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`scan` の request/result DTO、logging 境界、repository 呼び出しを整理する。

**Requirements Coverage**:

- REQ-OBS-001: Structured Logging
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] CLI と application の DTO 境界が分かれる
- [ ] ログ責務が service と CLI summary で分離される
- [ ] 既存テストが維持される

**Dependencies**:

- TASK-008: scan 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-010: Write Failing Tests for Path Sanitization and Length Policy

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
Windows 禁止文字、予約名、末尾不正、長パス危険判定に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-009: Windows Path Sanitization
- REQ-LSP-010: Path Length Risk Detection
- REQ-WIN-001: Windows Compatibility
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] 禁止文字置換テストがある
- [ ] 予約名安全化テストがある
- [ ] 末尾空白・末尾ピリオド処理テストがある
- [ ] 長パス危険判定テストがある
- [ ] テストは実装前に失敗する

**Dependencies**:

- TASK-001: package path 整備

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-011: Implement PathSanitizer and PathPolicy

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
Windows path sanitization と長パス risk 判定を実装する。

**Requirements Coverage**:

- REQ-LSP-009: Windows Path Sanitization
- REQ-LSP-010: Path Length Risk Detection
- REQ-WIN-001: Windows Compatibility

**Acceptance Criteria**:

- [ ] target path 正規化が実装される
- [ ] 長パス risk を返せる
- [ ] TASK-010 のテストが通る

**Dependencies**:

- TASK-010: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-012: Write Failing Tests for Plan Generation and Conflict Detection

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
保存済み scan 結果から plan item を作る処理と衝突検出の failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-007: Plan Generation
- REQ-LSP-008: Rule-Based Path Construction
- REQ-LSP-011: Conflict Detection
- REQ-LSP-012: Plan Review Output
- REQ-LSP-014: Auditability

**Acceptance Criteria**:

- [ ] plan item 生成テストがある
- [ ] metadata 欠損時の fallback / skip テストがある
- [ ] duplicate target / existing target の衝突テストがある
- [ ] テストは実装前に失敗する

**Dependencies**:

- TASK-008: scan 実装
- TASK-011: path policy

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-013: Implement OrganizationRules, ConflictDetector, and PlanService

**Priority**: P0  
**Story Points**: 8  
**Estimated Hours**: 10  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
target path 生成、fallback/skip 判定、衝突検出、plan 保存を含む `PlanService` を実装する。

**Requirements Coverage**:

- REQ-LSP-007: Plan Generation
- REQ-LSP-008: Rule-Based Path Construction
- REQ-LSP-010: Path Length Risk Detection
- REQ-LSP-011: Conflict Detection
- REQ-LSP-012: Plan Review Output
- REQ-LSP-014: Auditability

**Acceptance Criteria**:

- [ ] scan 結果から `plan_run` と `plan_items` を保存できる
- [ ] `move` / `skip` と reason を記録できる
- [ ] conflict / risk 状態を保存できる
- [ ] TASK-012 のテストが通る

**Dependencies**:

- TASK-012: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-014: Refactor Plan Flow for Streaming and Repository Separation

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`plan` が全件メモリ保持前提にならないように、scan query と plan persistence の境界を整理する。

**Requirements Coverage**:

- REQ-PERF-001: Scan Throughput
- REQ-REL-001: Crash Resilience
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] `plan` がページングまたは逐次処理しやすい構造になる
- [ ] repository の責務が query と write で分離される
- [ ] 既存テストが維持される

**Dependencies**:

- TASK-013: plan 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-015: Write Failing Tests for CLI Exit Codes and Command Output

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
CLI の引数エラー、正常終了、risk 検出時の終了コードと出力の failing tests を書く。

**Requirements Coverage**:

- REQ-LSP-012: Plan Review Output
- REQ-LSP-013: Exit Code Discipline
- REQ-OBS-001: Structured Logging

**Acceptance Criteria**:

- [ ] `scan` と `plan` の終了コードテストがある
- [ ] 引数不足時のコードが検証される
- [ ] risk/conflict 時のコードが検証される
- [ ] テストは実装前に失敗する

**Dependencies**:

- TASK-008: scan 実装
- TASK-013: plan 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-016: Implement CLI Commands for `scan` and `plan`

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
CLI entrypoint、subcommand 解析、終了コードマッピング、結果表示を実装する。

**Requirements Coverage**:

- REQ-LSP-001: Scan Command Entry Point
- REQ-LSP-007: Plan Generation
- REQ-LSP-012: Plan Review Output
- REQ-LSP-013: Exit Code Discipline

**Acceptance Criteria**:

- [ ] `scan` コマンドが service を呼び出せる
- [ ] `plan` コマンドが service を呼び出せる
- [ ] 終了コードが仕様どおり返る
- [ ] TASK-015 のテストが通る

**Dependencies**:

- TASK-015: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

## P1 Tasks

### TASK-017: Integration Tests for `scan -> plan`

**Priority**: P1  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
実 DB とテスト用ファイル群を使い、`scan -> plan` の主要経路を統合テストする。

**Requirements Coverage**:

- REQ-LSP-004: SQLite Persistence
- REQ-LSP-007: Plan Generation
- REQ-LSP-014: Auditability
- REQ-TEST-001: Testability

**Acceptance Criteria**:

- [ ] `scan` 後に `plan` が同じ DB を使って動く
- [ ] `plan_items` の保存結果を検証できる
- [ ] risk / conflict の保存を検証できる

**Dependencies**:

- TASK-016: CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-018: Windows-Specific Test Cases

**Priority**: P1  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
日本語 path、予約名、禁止文字、長パス近傍のテストケースを追加する。

**Requirements Coverage**:

- REQ-LSP-009: Windows Path Sanitization
- REQ-LSP-010: Path Length Risk Detection
- REQ-WIN-001: Windows Compatibility

**Acceptance Criteria**:

- [ ] 日本語 path ケースがある
- [ ] 予約名ケースがある
- [ ] 長パス近傍ケースがある

**Dependencies**:

- TASK-011: path policy 実装
- TASK-013: plan 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-019: Config Loading for Extension Rules and Organization Template

**Priority**: P1  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
拡張子ルール、organization template、DB path を設定から読み込めるようにする。

**Requirements Coverage**:

- REQ-LSP-002: Music File Detection
- REQ-LSP-004: SQLite Persistence
- REQ-LSP-008: Rule-Based Path Construction

**Acceptance Criteria**:

- [ ] config 読み込み層が追加される
- [ ] 拡張子ルールを外部設定化できる
- [ ] organization rule を外部設定化できる

**Dependencies**:

- TASK-016: CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

## P2 Tasks

### TASK-020: JSON Output Mode for Plan Review

**Priority**: P2  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
PowerShell や他ツールから消費しやすい JSON 出力を追加する。

**Requirements Coverage**:

- REQ-LSP-012: Plan Review Output
- REQ-OBS-001: Structured Logging

**Acceptance Criteria**:

- [ ] `--json` で machine-readable 出力が得られる
- [ ] source, target, action, reason, risk が含まれる

**Dependencies**:

- TASK-016: CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence
