# Requirements Specification: library-apply

## Overview

### Purpose

`library-apply` は、`plan` で生成された移動計画を安全に実行する機能セットである。対象はファイル移動そのものだけでなく、dry-run、実行ログ、検証可能な結果保存、将来の rollback に必要な履歴の保持を含む。

### Scope

**In Scope**

- CLI の `apply` コマンド
- dry-run と本実行の分離
- 同一ボリューム・異ボリュームでの適用方式の切り分け
- operation log の保存
- 実行結果の永続化
- rollback 可能な履歴の保持

**Out of Scope**

- rollback コマンド本体の実装
- 完全な post-apply 検証コマンド
- UI 表示の高度化

### Business Context

`scan` と `plan` で非破壊に整理計画を作れたとしても、`apply` が unsafe ならライブラリは壊れる。`library-apply` の目的は、計画を唯一の入力として、再実行性と追跡性を保ちながら実ファイルへ変更を反映することである。

---

## Stakeholders

| Role | Interest | Responsibility |
| --- | --- | --- |
| 個人アーカイブ管理者 | 誤移動せず整理したい | dry-run 確認、apply 実行判断 |
| スクリプト活用ユーザー | 自動実行しても壊れないこと | 終了コード確認、ログ収集 |
| 将来の rollback 実装担当者 | 戻せる履歴が必要 | operation log 契約の維持 |

---

## Functional Requirements

### REQ-LAP-001: Apply Input Source

WHEN the user invokes the `apply` command,
the system SHALL execute only against a previously persisted `plan_run`.

**Acceptance Criteria**:

- `apply` は `plan_run_id` を入力として受け取る
- `scan` 結果から直接 apply しない
- plan が存在しない場合は引数または状態エラーで終了する

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-002: Dry-Run Mode

WHEN the user requests dry-run mode,
the system SHALL simulate apply results without mutating any source or target file.

**Acceptance Criteria**:

- dry-run 実行中に move, copy, delete, overwrite を行わない
- dry-run でも action ごとの結果予測を出力できる
- dry-run と本実行を出力上で区別できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-003: Move Execution for Same Volume

WHEN a plan item targets a destination on the same volume as the source file,
the system SHALL execute the item using a move or rename strategy.

**Acceptance Criteria**:

- 同一ボリューム判定ができる
- 同一ボリューム時は copy-first を必須にしない
- 実行結果を operation log に保存できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-004: Copy-Verify-Delete for Cross Volume

WHEN a plan item targets a destination on a different volume from the source file,
the system SHALL apply the item through copy, verification, and source deletion in that order.

**Acceptance Criteria**:

- 異ボリューム判定ができる
- copy 成功後に検証ステップを挟める
- 検証失敗時は source を削除しない

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-005: No Source Deletion on Unsafe State

IF a plan item has conflict, risk, verification failure, or execution error,
THEN the system SHALL NOT delete the source file for that item.

**Acceptance Criteria**:

- conflict 状態では source を維持する
- risk 状態では source を維持する
- copy 後の検証失敗では source を維持する

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-006: Operation Log Persistence

The system SHALL persist an operation log for every attempted plan item execution.

**Acceptance Criteria**:

- source path, target path, action, result, error message を保存できる
- 成功と失敗を item 単位で区別できる
- rollback で再利用できる識別子を保存できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-007: Execution Run Tracking

WHEN the system starts `apply`,
the system SHALL create and update a persisted execution run record.

**Acceptance Criteria**:

- apply 実行開始時に run record を作る
- 完了時に成功件数、失敗件数、スキップ件数を保存する
- 中断時も partial or failed 状態を記録できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-008: Respect Plan Skip Decisions

WHEN a persisted plan item is marked as `skip`,
the system SHALL NOT mutate the corresponding source file during apply.

**Acceptance Criteria**:

- `plan_items.action = skip` は apply で変更しない
- skip 理由を execution output に引き継げる
- skip item も execution log に記録できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-009: Existing Target Protection

IF the target path already exists and the plan item is not explicitly approved for replacement,
THEN the system SHALL skip the item and record the reason.

**Acceptance Criteria**:

- 既存 target を検出できる
- デフォルトでは overwrite しない
- skip 理由が保存される

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-010: Idempotent Apply Guard

WHEN the user attempts to re-run apply for the same plan item after a recorded success,
the system SHALL detect the prior success and avoid unsafe duplicate mutation.

**Acceptance Criteria**:

- 同一 plan item の成功履歴を参照できる
- 二重実行で重複コピーや二重削除を避けられる
- 再実行時の扱いを execution log に残せる

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LAP-011: Rollback-Ready History

The system SHALL persist enough information during apply to support a future rollback command.

**Acceptance Criteria**:

- 元パスと新パスを保存できる
- delete 実行有無を保存できる
- 実行順序または時系列を保存できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-LAP-012: Apply Output Summary

WHEN `apply` finishes,
the system SHALL report counts for success, skipped, failed, and risky items.

**Acceptance Criteria**:

- 実行サマリに件数が含まれる
- dry-run と本実行を区別して表示できる
- 後続ツールが読める形に展開可能である

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LAP-013: Exit Code Discipline for Apply

WHEN `apply` finishes,
the system SHALL return deterministic exit codes for success, partial failure, and blocked execution.

**Acceptance Criteria**:

- 全成功時のコードが定義されている
- 一部失敗時のコードが定義されている
- 危険状態により apply 不可な場合のコードが定義されている

**Priority**: P1
**Status**: Draft
**Traceability**:

### REQ-LAP-014: Execution Ordering

WHEN the system applies plan items,
the system SHALL execute them in a deterministic order.

**Acceptance Criteria**:

- 実行順序が source path などの安定条件で決まる
- 同じ plan に対して順序がぶれない
- operation log に順序情報を残せる

**Priority**: P1
**Status**: Draft
**Traceability**:

---

## Non-Functional Requirements

### REQ-REL-AP-001: Crash Resilience During Apply

IF the process terminates during apply,
THEN the system SHALL preserve committed execution records and keep unfinished items identifiable.

**Acceptance Criteria**:

- 実行途中でもログが消えない
- 中断後に completed / partial / failed を識別できる
- 後続 run で再開戦略を判断できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-OBS-AP-001: Auditability of File Mutation

The system SHALL record enough execution detail to audit every file mutation decision after apply.

**Acceptance Criteria**:

- どのファイルがいつどう動いたか追跡できる
- skip と failure の理由を後から読める
- 人間向けサマリと内部記録を分離できる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-TEST-AP-001: Testability of Apply Workflow

The system SHALL structure apply logic so that dry-run, same-volume move, cross-volume copy, and failure handling can be tested independently.

**Acceptance Criteria**:

- ファイル移動処理をモックまたは差し替え可能にできる
- dry-run を単体テストできる
- 失敗時の source 保護を単体または結合テストできる

**Priority**: P0
**Status**: Draft
**Traceability**:

### REQ-WIN-AP-001: Windows-Compatible Mutation

WHEN applying a plan on Windows,
the system SHALL preserve the path sanitization guarantees established during planning.

**Acceptance Criteria**:

- apply 時に unsanitized path を使って再計算しない
- plan に保存した sanitized path を基準にできる
- Windows 上の rename / copy 失敗を item 単位で扱える

**Priority**: P0
**Status**: Draft
**Traceability**:

---

## Requirements Coverage Matrix

| Requirement ID | Summary | Design | Implementation | Tests |
| --- | --- | --- | --- | --- |
| REQ-LAP-001 | apply は plan_run を唯一入力にする |  |  |  |
| REQ-LAP-002 | dry-run |  |  |  |
| REQ-LAP-003 | 同一ボリューム move |  |  |  |
| REQ-LAP-004 | 異ボリューム copy/verify/delete |  |  |  |
| REQ-LAP-005 | unsafe 時 source を消さない |  |  |  |
| REQ-LAP-006 | operation log 保存 |  |  |  |
| REQ-LAP-007 | execution run tracking |  |  |  |
| REQ-LAP-008 | plan の skip を尊重 |  |  |  |
| REQ-LAP-009 | existing target 保護 |  |  |  |
| REQ-LAP-010 | 再実行ガード |  |  |  |
| REQ-LAP-011 | rollback-ready history |  |  |  |
| REQ-LAP-012 | apply サマリ |  |  |  |
| REQ-LAP-013 | apply の終了コード |  |  |  |
| REQ-LAP-014 | deterministic ordering |  |  |  |
| REQ-REL-AP-001 | apply 中断耐性 |  |  |  |
| REQ-OBS-AP-001 | 監査可能性 |  |  |  |
| REQ-TEST-AP-001 | apply のテスト可能性 |  |  |  |
| REQ-WIN-AP-001 | Windows 互換な変更適用 |  |  |  |
