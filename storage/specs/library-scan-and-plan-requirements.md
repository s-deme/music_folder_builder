# Requirements Specification: library-scan-and-plan

## Overview

### Purpose

`library-scan-and-plan` は、Windows 上の音楽ファイル群を安全に整理するための最初の機能セットである。対象フォルダを走査して状態を保存し、その保存結果から移動計画を生成する。

### Scope

**In Scope**

- CLI の `scan` コマンド
- CLI の `plan` コマンド
- 音楽ファイル情報とメタデータの保存
- 整理ルールに基づく移動先候補の生成
- Windows 固有のパス制約と衝突候補の検出

**Out of Scope**

- 実ファイルの移動
- 適用後の検証
- ロールバック実行
- 外部メタデータツールとの本実装統合

### Business Context

本プロジェクトは、誤整理しにくい Windows CLI を目指している。`scan` と `plan` は、直接変更を加える前に状態を可視化し、再実行可能な計画を作るための基盤機能である。

---

## Stakeholders

| Role | Interest | Responsibility |
| --- | --- | --- |
| 個人アーカイブ管理者 | 音楽ライブラリを壊さず整理したい | 対象フォルダ、整理ルール、計画確認 |
| スクリプト活用ユーザー | PowerShell から自動化したい | CLI 実行、終了コード処理、ログ確認 |
| 将来の実装担当者 | `apply` 以降につなげたい | 追跡可能な保存形式と安定した契約の維持 |

---

## Functional Requirements

### REQ-LSP-001: Scan Command Entry Point

WHEN the user invokes the `scan` command with a source root,
the system SHALL traverse the target root and create a persisted scan result without modifying any source file.

**Acceptance Criteria**:

- `scan` 実行で対象 root の走査結果が保存される
- `scan` 実行中に rename, move, delete, overwrite を行わない
- source root 未指定時は引数エラーで終了する

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-002: Music File Detection

WHEN the system scans a directory tree,
the system SHALL identify candidate music files according to configured file extension rules.

**Acceptance Criteria**:

- 対象拡張子に一致するファイルだけを scan 対象として扱える
- 非対象ファイルは除外または非対象として記録できる
- 拡張子ルールは設定で変更可能である

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-003: Metadata Extraction

WHEN a candidate music file is discovered,
the system SHALL extract available metadata and persist both extracted values and missing-value state.

**Acceptance Criteria**:

- 少なくとも path, size, mtime, extension を保存できる
- artist, album_artist, album, title, track_no, disc_no, year の取得結果を保存できる
- 欠損メタデータは null 相当または欠損状態として区別できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-004: SQLite Persistence

The system SHALL persist scan outputs and plan outputs in SQLite so that later commands can reuse prior results.

**Acceptance Criteria**:

- `scan` の結果が後続の `plan` から参照できる
- 実行途中で中断しても保存済みデータを再利用できる
- 保存先 DB パスを CLI または設定で指定できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-005: Reparse Point Handling

WHILE traversing the filesystem on Windows,
the system SHALL NOT follow reparse points by default.

**Acceptance Criteria**:

- シンボリックリンクや junction を既定値では辿らない
- 非追跡時は無限再帰や想定外の探索拡大を起こさない
- 追跡有無は scan 結果またはログから判別できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-006: Scan Reproducibility

WHEN the user reruns `scan` against the same root and database,
the system SHALL preserve enough state to compare or reuse prior scan data.

**Acceptance Criteria**:

- 再実行時に同一ファイルを識別するための基本属性を保存できる
- 後続機能で差分判定に使える保存形式を持つ
- 再実行しても source file の内容は変更しない

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LSP-007: Plan Generation

WHEN the user invokes the `plan` command for a completed scan,
the system SHALL generate target path proposals for each eligible music file without modifying any source file.

**Acceptance Criteria**:

- `plan` は保存済み scan 結果を入力として扱う
- 各対象ファイルについて target path 候補または skip 理由を生成できる
- `plan` 実行中に source file の移動や削除を行わない

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-008: Rule-Based Path Construction

WHEN the system generates a target path,
the system SHALL derive the path from configured organization rules and available metadata.

**Acceptance Criteria**:

- アーティスト、アルバム、トラック番号、タイトルなどを使ったパス生成ができる
- 必要なメタデータが不足する場合は fallback または skip の扱いを明示できる
- 生成ルールはコードに固定せず設定または定義として扱える

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-009: Windows Path Sanitization

WHEN the system generates a target path for Windows,
the system SHALL sanitize invalid characters, reserved names, and invalid trailing characters before persisting the plan.

**Acceptance Criteria**:

- Windows 禁止文字を安全な代替文字へ変換できる
- `CON`, `PRN`, `NUL`, `AUX`, `COM1` などの予約名を安全化できる
- 末尾空白と末尾ピリオドを除去または安全化できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-010: Path Length Risk Detection

IF a generated target path exceeds the supported Windows path policy,
THEN the system SHALL mark the plan item as invalid or risky and record the reason.

**Acceptance Criteria**:

- 長すぎる target path を検出できる
- 検出結果に理由を保存できる
- 危険な path を正常候補として silently 扱わない

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-011: Conflict Detection

WHEN the system generates plan items,
the system SHALL detect name collisions and conflicting destinations before any apply phase exists.

**Acceptance Criteria**:

- 同一 target path を指す複数ファイルを検出できる
- 既存ファイルとの衝突候補を検出できる
- 衝突状態と理由を plan に保存できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LSP-012: Plan Review Output

WHEN the user requests plan output,
the system SHALL present plan results in a form suitable for human review and script consumption.

**Acceptance Criteria**:

- 人間向け表示と機械可読出力の少なくとも一方を提供できる
- 各 plan item に source path, target path, action, reason を含められる
- 危険状態や衝突状態を出力上で区別できる

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LSP-013: Exit Code Discipline

WHEN `scan` or `plan` finishes,
the system SHALL return deterministic exit codes for success, argument errors, and detected risk conditions.

**Acceptance Criteria**:

- 正常終了時のコードが定義されている
- 引数エラー時のコードが定義されている
- 衝突や危険状態の検出時に成功と区別できるコードを返せる

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LSP-014: Auditability

The system SHALL retain enough scan and plan information to explain why each file was included, skipped, or marked risky.

**Acceptance Criteria**:

- 対象化理由または除外理由を追跡できる
- `plan` で生成された action と reason を保存できる
- 後続の `apply` と `verify` が再利用できる識別子を持つ

**Priority**: P0
**Status**: Draft
**Traceability**:

---

## Non-Functional Requirements

### REQ-PERF-001: Scan Throughput

WHEN the system scans a local music library,
the system SHALL process files incrementally without requiring all scan results to be held in memory at once.

**Acceptance Criteria**:

- scan 実装が逐次保存またはチャンク処理可能な構造を持つ
- 数千件規模でメモリ保持前提の設計にしない
- 実装設計に中断再開を阻害する全件一括前提を置かない

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-REL-001: Crash Resilience

IF the process terminates during `scan` or `plan`,
THEN the system SHALL preserve previously committed state and allow a later run to continue from a consistent database state.

**Acceptance Criteria**:

- 中断後も DB が読み取り不能状態にならない
- 保存済みの scan または plan データを後続 run で利用できる
- 部分保存状態を識別できる設計である

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-WIN-001: Windows Compatibility

The system SHALL operate correctly against Windows-style paths, including Japanese characters and reserved-name constraints.

**Acceptance Criteria**:

- Windows パス区切りとドライブレターを扱える
- 日本語を含む path を識別・保存できる
- 予約名と禁止文字の処理が要件上定義されている

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-OBS-001: Structured Logging

WHEN `scan` or `plan` executes,
the system SHALL emit logs that distinguish progress, warnings, and errors independently from human-facing CLI summaries.

**Acceptance Criteria**:

- 進捗、警告、失敗を区別できるログを出力できる
- CLI 表示と内部ログの責務を分離できる
- 後続調査で利用できる最低限の文脈を残せる

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-TEST-001: Testability

The system SHALL be structured so that scan rules, path sanitization, and plan generation can be tested independently of the CLI.

**Acceptance Criteria**:

- ドメインロジックを CLI から切り離せる
- path sanitization を単体テストできる
- `scan -> plan` の統合経路を結合テストできる

**Priority**: P0
**Status**: Draft
**Traceability**:

---

## Requirements Coverage Matrix

| Requirement ID | Summary | Design | Implementation | Tests |
| --- | --- | --- | --- | --- |
| REQ-LSP-001 | scan の非破壊実行 |  |  |  |
| REQ-LSP-002 | 音楽ファイル判定 |  |  |  |
| REQ-LSP-003 | メタデータ抽出と欠損保持 |  |  |  |
| REQ-LSP-004 | SQLite 永続化 |  |  |  |
| REQ-LSP-005 | reparse point 非追跡 |  |  |  |
| REQ-LSP-006 | scan 再実行性 |  |  |  |
| REQ-LSP-007 | plan 生成 |  |  |  |
| REQ-LSP-008 | ルールベースのパス生成 |  |  |  |
| REQ-LSP-009 | Windows パス正規化 |  |  |  |
| REQ-LSP-010 | 長パス危険検出 |  |  |  |
| REQ-LSP-011 | 衝突検出 |  |  |  |
| REQ-LSP-012 | plan のレビュー出力 |  |  |  |
| REQ-LSP-013 | 終了コード規律 |  |  |  |
| REQ-LSP-014 | 監査可能性 |  |  |  |
| REQ-PERF-001 | 逐次処理前提 |  |  |  |
| REQ-REL-001 | 中断耐性 |  |  |  |
| REQ-WIN-001 | Windows 互換性 |  |  |  |
| REQ-OBS-001 | 構造化ログ |  |  |  |
| REQ-TEST-001 | テスト可能性 |  |  |  |
