# Task Breakdown: library-apply

## Overview

このタスク分解は `storage/design/library-apply-design.md` を実装可能な単位に分けたものである。最優先は、安全な `apply` を dry-run 付きで成立させ、same-volume / cross-volume の基本戦略と operation log 保存を先に固定することである。

---

## Execution Strategy

1. まず DB に `execution_runs` と `operation_logs` を追加する
2. dry-run のみで `apply` の基本ループを成立させる
3. same-volume move を実装する
4. cross-volume copy/verify/delete を実装する
5. CLI、終了コード、integration test を追加する

---

## P0 Tasks

### TASK-AP-001: Write Failing Tests for Execution Tables

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`execution_runs` と `operation_logs` の schema 追加に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-007: Execution Run Tracking
- REQ-LAP-011: Rollback-Ready History
- REQ-REL-AP-001: Crash Resilience During Apply

**Acceptance Criteria**:

- [ ] `execution_runs` の作成テストがある
- [ ] `operation_logs` の作成テストがある
- [ ] schema 拡張前はテストが失敗する

**Dependencies**:

- None

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-002: Implement Execution Schema Bootstrap

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
既存 schema に `execution_runs` と `operation_logs` を追加する。

**Requirements Coverage**:

- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-007: Execution Run Tracking
- REQ-LAP-011: Rollback-Ready History

**Acceptance Criteria**:

- [ ] schema 初期化で apply 用テーブルが作られる
- [ ] 既存 schema と併存できる
- [ ] TASK-AP-001 のテストが通る

**Dependencies**:

- TASK-AP-001: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-003: Write Failing Tests for Dry-Run Apply

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
dry-run がファイル変更をせず execution log を残す failing tests を書く。

**Requirements Coverage**:

- REQ-LAP-001: Apply Input Source
- REQ-LAP-002: Dry-Run Mode
- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-007: Execution Run Tracking
- REQ-LAP-008: Respect Plan Skip Decisions

**Acceptance Criteria**:

- [ ] dry-run で source が変わらないテストがある
- [ ] dry-run で `execution_runs` / `operation_logs` が保存されるテストがある
- [ ] `skip` item の尊重を検証するテストがある

**Dependencies**:

- TASK-AP-002: schema 追加

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-004: Implement Apply Repositories and Dry-Run Service Loop

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`execution_repository`, `operation_log_repository`, `plan_query_repository` と dry-run 中心の `ApplyService` を実装する。

**Requirements Coverage**:

- REQ-LAP-001: Apply Input Source
- REQ-LAP-002: Dry-Run Mode
- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-007: Execution Run Tracking
- REQ-LAP-012: Apply Output Summary

**Acceptance Criteria**:

- [ ] `plan_run_id` を入力に apply を開始できる
- [ ] dry-run で mutation を行わず summary を保存できる
- [ ] TASK-AP-003 のテストが通る

**Dependencies**:

- TASK-AP-003: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-005: Write Failing Tests for Same-Volume Move

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume move の成功、target exists skip、missing source failure の failing tests を書く。

**Requirements Coverage**:

- REQ-LAP-003: Move Execution for Same Volume
- REQ-LAP-005: No Source Deletion on Unsafe State
- REQ-LAP-009: Existing Target Protection
- REQ-LAP-014: Execution Ordering

**Acceptance Criteria**:

- [ ] same-volume move 成功ケースがある
- [ ] target exists による skip ケースがある
- [ ] missing source による failure ケースがある

**Dependencies**:

- TASK-AP-004: dry-run apply

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-006: Implement Same-Volume Mutation Strategy

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume move/rename 戦略と operation log 保存を実装する。

**Requirements Coverage**:

- REQ-LAP-003: Move Execution for Same Volume
- REQ-LAP-005: No Source Deletion on Unsafe State
- REQ-LAP-009: Existing Target Protection
- REQ-WIN-AP-001: Windows-Compatible Mutation

**Acceptance Criteria**:

- [ ] same-volume で move が実行される
- [ ] unsafe 状態では source を保持する
- [ ] TASK-AP-005 のテストが通る

**Dependencies**:

- TASK-AP-005: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-007: Write Failing Tests for Cross-Volume Copy-Verify-Delete

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
cross-volume の copy/verify/delete と verify failure 時の source 保護に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LAP-004: Copy-Verify-Delete for Cross Volume
- REQ-LAP-005: No Source Deletion on Unsafe State
- REQ-LAP-011: Rollback-Ready History
- REQ-TEST-AP-001: Testability of Apply Workflow

**Acceptance Criteria**:

- [ ] copy -> verify -> delete 成功ケースがある
- [ ] verify failure で source 保持のケースがある
- [ ] delete failure で partial failure のケースがある

**Dependencies**:

- TASK-AP-004: dry-run apply

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-008: Implement Cross-Volume Strategy and Verification Gateway

**Priority**: P0  
**Story Points**: 8  
**Estimated Hours**: 10  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
copy/verify/delete の順で実行する cross-volume 戦略と verification gateway を実装する。

**Requirements Coverage**:

- REQ-LAP-004: Copy-Verify-Delete for Cross Volume
- REQ-LAP-005: No Source Deletion on Unsafe State
- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-011: Rollback-Ready History
- REQ-REL-AP-001: Crash Resilience During Apply

**Acceptance Criteria**:

- [ ] cross-volume item を copy/verify/delete できる
- [ ] verify failure 時に source を保持する
- [ ] source_deleted 状態を operation log に保存できる
- [ ] TASK-AP-007 のテストが通る

**Dependencies**:

- TASK-AP-007: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-009: Write Failing Tests for Apply CLI and Exit Codes

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`apply` CLI の引数、dry-run、partial failure、blocked execution の終了コードに対する failing tests を書く。

**Requirements Coverage**:

- REQ-LAP-012: Apply Output Summary
- REQ-LAP-013: Exit Code Discipline for Apply
- REQ-OBS-AP-001: Auditability of File Mutation

**Acceptance Criteria**:

- [ ] apply 成功時 exit code のテストがある
- [ ] partial failure 時 exit code のテストがある
- [ ] blocked / risky 状態の exit code テストがある

**Dependencies**:

- TASK-AP-006: same-volume 実装
- TASK-AP-008: cross-volume 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-010: Implement `apply` CLI Command

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`apply` サブコマンド、`--dry-run`、summary 出力、exit code を CLI に追加する。

**Requirements Coverage**:

- REQ-LAP-001: Apply Input Source
- REQ-LAP-002: Dry-Run Mode
- REQ-LAP-012: Apply Output Summary
- REQ-LAP-013: Exit Code Discipline for Apply

**Acceptance Criteria**:

- [ ] `python -m music_folder_builder apply --plan-run-id ...` が動く
- [ ] `--dry-run` を受け取れる
- [ ] TASK-AP-009 のテストが通る

**Dependencies**:

- TASK-AP-009: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

## P1 Tasks

### TASK-AP-011: Integration Tests for `plan -> apply(dry-run)`

**Priority**: P1  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`plan` から `apply --dry-run` までの一連を integration test で検証する。

**Requirements Coverage**:

- REQ-LAP-001: Apply Input Source
- REQ-LAP-002: Dry-Run Mode
- REQ-LAP-006: Operation Log Persistence
- REQ-LAP-007: Execution Run Tracking

**Acceptance Criteria**:

- [ ] dry-run execution log が保存される
- [ ] source / target が変更されない
- [ ] summary が保存される

**Dependencies**:

- TASK-AP-010: apply CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-012: Integration Tests for Real Apply

**Priority**: P1  
**Story Points**: 8  
**Estimated Hours**: 8  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume / cross-volume の real apply を integration test で検証する。

**Requirements Coverage**:

- REQ-LAP-003: Move Execution for Same Volume
- REQ-LAP-004: Copy-Verify-Delete for Cross Volume
- REQ-LAP-005: No Source Deletion on Unsafe State
- REQ-REL-AP-001: Crash Resilience During Apply

**Acceptance Criteria**:

- [ ] same-volume success ケースがある
- [ ] cross-volume success ケースがある
- [ ] verify failure ケースがある
- [ ] operation log が保存される

**Dependencies**:

- TASK-AP-010: apply CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-AP-013: Re-Run Guard and Rollback-Ready Validation

**Priority**: P1  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
re-run guard と rollback に必要な履歴の完全性を追加検証する。

**Requirements Coverage**:

- REQ-LAP-010: Idempotent Apply Guard
- REQ-LAP-011: Rollback-Ready History
- REQ-OBS-AP-001: Auditability of File Mutation

**Acceptance Criteria**:

- [ ] 同一 plan item の二重適用防止が実装される
- [ ] rollback に必要な source/target/source_deleted が必ず残る
- [ ] 再実行時の log を記録できる

**Dependencies**:

- TASK-AP-008: cross-volume 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence
