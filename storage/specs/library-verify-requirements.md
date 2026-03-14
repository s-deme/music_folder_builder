# Requirements Specification: library-verify

## Overview

### Purpose

`library-verify` は、`apply` または `rollback` の実行後に、期待された source / target 状態が実ファイルシステム上で満たされているかを確認する機能セットである。対象は、execution run を入力にした検証、dry-run ではなく read-only な検証、結果保存、後続の運用判断に使える終了コードを含む。

### Scope

**In Scope**

- CLI の `verify` コマンド
- `execution_run_id` または `rollback_run_id` を入力にした検証
- existence と size を使った基本検証
- verify run / verify log の保存
- 実行結果サマリと終了コード

**Out of Scope**

- ハッシュベースの完全整合性検証
- 壊れた状態の自動修復
- 複数 run の一括検証

### Business Context

`apply` や `rollback` が成功を返しても、途中の I/O 問題や外部変更により実ファイル状態が期待とずれる可能性は残る。`library-verify` の目的は、実行後状態を read-only に確認し、追加作業なしで「整合している / ずれている」を判断可能にすることである。

---

## Functional Requirements

### REQ-LVF-001: Verify Input Source

WHEN the user invokes the `verify` command,  
the system SHALL execute against a previously persisted execution run identifier.

**Acceptance Criteria**:

- `verify` は `execution_run_id` または `rollback_run_id` を入力に受け取る
- 対象 run が存在しない場合は状態エラーで終了する
- 1 回の verify で 1 つの run のみ扱う

**Priority**: P0  
**Status**: Draft

### REQ-LVF-002: Read-Only Verification

WHEN the system performs verification,  
the system SHALL NOT mutate source or target files.

**Acceptance Criteria**:

- verify 中に move, copy, delete を行わない
- 読み取り専用の存在確認とサイズ確認のみで成立する
- verify 結果は別 run として保存される

**Priority**: P0  
**Status**: Draft

### REQ-LVF-003: Post-Apply Expectation Checks

WHEN verifying an apply execution run,  
the system SHALL confirm that successful items exist at target and no longer exist at source.

**Acceptance Criteria**:

- success `move` / `copy_delete` item は target exists を確認する
- `source_deleted = true` item は source missing を確認する
- skip / failed item は mutation を期待しない

**Priority**: P0  
**Status**: Draft

### REQ-LVF-004: Post-Rollback Expectation Checks

WHEN verifying a rollback execution run,  
the system SHALL confirm that restored items exist at source and deleted targets remain absent.

**Acceptance Criteria**:

- success rollback item は source exists を確認する
- `target_deleted = true` item は target missing を確認する
- skip / failed rollback item は mutation を期待しない

**Priority**: P0  
**Status**: Draft

### REQ-LVF-005: Size Consistency Check

WHEN both an expected file and its counterpart are available for comparison,  
the system SHALL compare file sizes to detect obvious corruption.

**Acceptance Criteria**:

- expected existing file の size を取得できる
- 比較対象がある場合に size mismatch を記録できる
- size 不明時は verify failure ではなく reason 付きで扱える

**Priority**: P1  
**Status**: Draft

### REQ-LVF-006: Verify Log Persistence

The system SHALL persist a verify log for every inspected item.

**Acceptance Criteria**:

- inspected path, expected state, actual state, result, error message を保存できる
- item 単位で success / skipped / failed を区別できる
- 元の execution / rollback run と関連付けできる

**Priority**: P0  
**Status**: Draft

### REQ-LVF-007: Verify Run Tracking

WHEN the system starts `verify`,  
the system SHALL create and update a persisted verify run record.

**Acceptance Criteria**:

- verify 開始時に run record を作る
- 完了時に success, skipped, failed, risky 件数を保存する
- 中断時も partial or failed 状態を記録できる

**Priority**: P0  
**Status**: Draft

### REQ-LVF-008: Deterministic Verification Ordering

WHEN the system verifies items,  
the system SHALL inspect them in a deterministic order.

**Acceptance Criteria**:

- apply / rollback の sequence に基づき安定順序を作れる
- 同じ run に対して順序がぶれない
- verify log に順序情報を残せる

**Priority**: P1  
**Status**: Draft

### REQ-LVF-009: Verify Output Summary

WHEN `verify` finishes,  
the system SHALL report counts for success, skipped, failed, and risky items.

**Acceptance Criteria**:

- 実行サマリに件数が含まれる
- 後続ツールが読める形に展開可能である
- 一部失敗を exit code に反映できる

**Priority**: P1  
**Status**: Draft

### REQ-LVF-010: Exit Code Discipline for Verify

WHEN `verify` finishes,  
the system SHALL return deterministic exit codes for success, mismatch detection, and blocked execution.

**Acceptance Criteria**:

- 全成功時のコードが定義されている
- mismatch / failure 時のコードが定義されている
- run 解決不可時のコードが定義されている

**Priority**: P1  
**Status**: Draft

---

## Non-Functional Requirements

### REQ-OBS-VF-001: Auditability of Verification

The system SHALL make verification behavior auditable from persisted state.

**Acceptance Criteria**:

- どの run を検証したか追跡できる
- item ごとの期待値と実測結果を確認できる
- apply / rollback / verify の対応関係を辿れる

**Priority**: P1  
**Status**: Draft

### REQ-TEST-VF-001: Testability of Verify Workflow

The system SHALL keep verify logic testable without requiring real Windows volumes.

**Acceptance Criteria**:

- filesystem reads は gateway 経由で差し替えられる
- apply と rollback の両方を fixture で再現できる
- existence / size mismatch を自動テストできる

**Priority**: P1  
**Status**: Draft
