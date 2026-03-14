# Requirements Specification: library-rollback

## Overview

### Purpose

`library-rollback` は、`apply` で記録された実行履歴をもとに、直前または指定した execution run を安全に逆方向へ戻す機能セットである。対象は、成功した file mutation の巻き戻し、dry-run、rollback 実行ログ、unsafe 状態での source 保護を含む。

### Scope

**In Scope**

- CLI の `rollback` コマンド
- `execution_run` を入力にした rollback
- dry-run と本実行の分離
- same-volume / cross-volume の rollback 戦略
- rollback operation log の保存
- rollback 実行結果の永続化

**Out of Scope**

- 壊れた target を自動修復する高度な復旧
- 複数 execution run の一括 rollback
- UI 表示の高度化

### Business Context

`apply` が安全でも、誤った plan や誤ったメタデータで整理した場合は元に戻す必要がある。`library-rollback` の目的は、記録済み execution log を唯一の根拠として、安全に逆操作を行い、再実行性と追跡性を保ちながらライブラリを復旧可能にすることである。

---

## Stakeholders

| Role | Interest | Responsibility |
| --- | --- | --- |
| 個人アーカイブ管理者 | 誤整理時に戻したい | rollback 前に dry-run を確認する |
| スクリプト活用ユーザー | 自動処理後の巻き戻しをしたい | execution_id の指定と exit code 確認 |
| 将来の監査担当 | 何を戻したか追跡したい | rollback log 契約を維持する |

---

## Functional Requirements

### REQ-LRB-001: Rollback Input Source

WHEN the user invokes the `rollback` command,  
the system SHALL execute only against a previously persisted `execution_run`.

**Acceptance Criteria**:

- `rollback` は `execution_run_id` を入力として受け取る
- `plan_run_id` や `scan_run_id` から直接 rollback しない
- execution run が存在しない場合は状態エラーで終了する

**Priority**: P0  
**Status**: Draft

### REQ-LRB-002: Rollback Dry-Run Mode

WHEN the user requests dry-run mode,  
the system SHALL simulate rollback results without mutating any source or target file.

**Acceptance Criteria**:

- dry-run 中に move, copy, delete を行わない
- dry-run でも item ごとの予測結果を出力できる
- dry-run と本実行を出力上で区別できる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-003: Success-Only Rollback Eligibility

IF an operation log entry was not recorded as a successful apply mutation,  
THEN the system SHALL NOT attempt to rollback that item.

**Acceptance Criteria**:

- `result = success` の item のみ rollback 対象にできる
- `skip`, `failed`, `dry_run` は rollback 対象外になる
- rollback 対象外 item も log に記録できる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-004: Deterministic Reverse Ordering

WHEN the system rolls back an execution run,  
the system SHALL process eligible items in reverse execution order.

**Acceptance Criteria**:

- rollback 順序は `sequence_no` の逆順で決まる
- 同じ execution run に対して順序がぶれない
- rollback log に順序情報を残せる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-005: Same-Volume Reverse Move

WHEN a rollback item originated from a same-volume move,  
the system SHALL restore the file by moving it from target path back to source path.

**Acceptance Criteria**:

- target exists を確認できる
- source が既に存在する場合は overwrite しない
- reverse move の結果を log に保存できる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-006: Cross-Volume Reverse Copy-Verify-Delete

WHEN a rollback item originated from a cross-volume copy-delete flow,  
the system SHALL restore the file through copy, verification, and target deletion in that order.

**Acceptance Criteria**:

- cross-volume rollback で copy -> verify -> delete を実行できる
- verify 失敗時は target を削除しない
- source 復旧後のみ target delete を試みる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-007: No Mutation on Unsafe State

IF rollback detects missing target, existing source, verification failure, or execution error,  
THEN the system SHALL NOT delete the only known surviving file for that item.

**Acceptance Criteria**:

- target missing 時は source 側を削除しない
- source already exists 時は target 側を削除しない
- verify failure 時は surviving copy を消さない

**Priority**: P0  
**Status**: Draft

### REQ-LRB-008: Rollback Log Persistence

The system SHALL persist a rollback operation log for every attempted item.

**Acceptance Criteria**:

- source path, target path, rollback action, result, error message を保存できる
- rollback 実行と元 apply 実行を関連付けられる
- item 単位で成功と失敗を区別できる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-009: Rollback Execution Tracking

WHEN the system starts `rollback`,  
the system SHALL create and update a persisted rollback execution run record.

**Acceptance Criteria**:

- rollback 開始時に run record を作る
- 完了時に success, skipped, failed, risky 件数を保存する
- 中断時も partial or failed 状態を記録できる

**Priority**: P0  
**Status**: Draft

### REQ-LRB-010: Prevent Duplicate Rollback

WHEN the user attempts to rollback an item already restored by a prior successful rollback,  
the system SHALL detect the prior success and avoid duplicate mutation.

**Acceptance Criteria**:

- 同一 apply item に対する成功 rollback 履歴を参照できる
- 二重 rollback で重複 copy や二重 delete を避けられる
- 再実行時の扱いを log に残せる

**Priority**: P1  
**Status**: Draft

### REQ-LRB-011: Rollback Output Summary

WHEN `rollback` finishes,  
the system SHALL report counts for success, skipped, failed, and risky items.

**Acceptance Criteria**:

- 実行サマリに件数が含まれる
- dry-run と本実行を区別して表示できる
- 後続ツールが読める形に展開可能である

**Priority**: P1  
**Status**: Draft

### REQ-LRB-012: Exit Code Discipline for Rollback

WHEN `rollback` finishes,  
the system SHALL return deterministic exit codes for success, partial failure, and blocked execution.

**Acceptance Criteria**:

- 全成功時のコードが定義されている
- 一部失敗時のコードが定義されている
- 危険状態により rollback 不可な場合のコードが定義されている

**Priority**: P1  
**Status**: Draft

---

## Non-Functional Requirements

### REQ-REL-RB-001: Crash Resilience During Rollback

IF the process terminates during rollback,  
THEN the system SHALL preserve committed rollback records and keep unfinished items identifiable.

**Acceptance Criteria**:

- rollback の途中で停止しても開始済み run が残る
- 未完了 item を log から識別できる
- 再試行時に重複操作を避ける判断材料が残る

**Priority**: P1  
**Status**: Draft

### REQ-OBS-RB-001: Auditability of Rollback

The system SHALL make rollback behavior auditable from persisted state.

**Acceptance Criteria**:

- どの execution run を戻したか追跡できる
- item ごとの結果を DB から確認できる
- apply と rollback の対応関係を辿れる

**Priority**: P1  
**Status**: Draft

### REQ-TEST-RB-001: Testability of Rollback Workflow

The system SHALL keep rollback logic testable without requiring real Windows volumes.

**Acceptance Criteria**:

- filesystem mutation は gateway 経由で差し替えられる
- same-volume と cross-volume をテスト doubles で再現できる
- reverse ordering と unsafe 分岐を自動テストできる

**Priority**: P1  
**Status**: Draft

---

## Traceability Summary

| Requirement ID | Title | Priority |
| --- | --- | --- |
| REQ-LRB-001 | Rollback Input Source | P0 |
| REQ-LRB-002 | Rollback Dry-Run Mode | P0 |
| REQ-LRB-003 | Success-Only Rollback Eligibility | P0 |
| REQ-LRB-004 | Deterministic Reverse Ordering | P0 |
| REQ-LRB-005 | Same-Volume Reverse Move | P0 |
| REQ-LRB-006 | Cross-Volume Reverse Copy-Verify-Delete | P0 |
| REQ-LRB-007 | No Mutation on Unsafe State | P0 |
| REQ-LRB-008 | Rollback Log Persistence | P0 |
| REQ-LRB-009 | Rollback Execution Tracking | P0 |
| REQ-LRB-010 | Prevent Duplicate Rollback | P1 |
| REQ-LRB-011 | Rollback Output Summary | P1 |
| REQ-LRB-012 | Exit Code Discipline for Rollback | P1 |
| REQ-REL-RB-001 | Crash Resilience During Rollback | P1 |
| REQ-OBS-RB-001 | Auditability of Rollback | P1 |
| REQ-TEST-RB-001 | Testability of Rollback Workflow | P1 |
