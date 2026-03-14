# Task Breakdown: library-rollback

## Overview

このタスク分解は `storage/design/library-rollback-design.md` を実装可能な単位に分けたものである。最優先は、rollback 専用テーブルを追加し、successful apply item のみを逆順で dry-run / 本実行できる最小構成を成立させることである。

---

## Execution Strategy

1. まず DB に `rollback_runs` と `rollback_logs` を追加する
2. apply 履歴を逆順に読む query を成立させる
3. dry-run rollback の基本ループを実装する
4. same-volume reverse move を実装する
5. cross-volume reverse copy/verify/delete を実装する
6. CLI、終了コード、duplicate rollback guard を追加する

---

## P0 Tasks

### TASK-RB-001: Write Failing Tests for Rollback Tables

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`rollback_runs` と `rollback_logs` の schema 追加に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-008: Rollback Log Persistence
- REQ-LRB-009: Rollback Execution Tracking
- REQ-OBS-RB-001: Auditability of Rollback
- REQ-REL-RB-001: Crash Resilience During Rollback

**Acceptance Criteria**:

- [ ] `rollback_runs` の作成テストがある
- [ ] `rollback_logs` の作成テストがある
- [ ] schema 拡張前はテストが失敗する

**Dependencies**:

- None

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-002: Implement Rollback Schema Bootstrap

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
既存 schema に `rollback_runs` と `rollback_logs` を追加する。

**Requirements Coverage**:

- REQ-LRB-008: Rollback Log Persistence
- REQ-LRB-009: Rollback Execution Tracking
- REQ-OBS-RB-001: Auditability of Rollback

**Acceptance Criteria**:

- [ ] schema 初期化で rollback 用テーブルが作られる
- [ ] 既存 schema と併存できる
- [ ] TASK-RB-001 のテストが通る

**Dependencies**:

- TASK-RB-001: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-003: Write Failing Tests for Apply History Query

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
successful apply item のみを `sequence_no DESC` で返す history query の failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-001: Rollback Input Source
- REQ-LRB-003: Success-Only Rollback Eligibility
- REQ-LRB-004: Deterministic Reverse Ordering
- REQ-TEST-RB-001: Testability of Rollback Workflow

**Acceptance Criteria**:

- [ ] success apply item のみ取得するテストがある
- [ ] `dry_run`, `skip`, `failed` を除外するテストがある
- [ ] reverse order を検証するテストがある

**Dependencies**:

- TASK-RB-002: schema 追加

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-004: Implement Apply History Repository

**Priority**: P0  
**Story Points**: 4  
**Estimated Hours**: 5  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`execution_run_id` を入力に rollback 対象 item を逆順で返す `apply_history_repository` を実装する。

**Requirements Coverage**:

- REQ-LRB-001: Rollback Input Source
- REQ-LRB-003: Success-Only Rollback Eligibility
- REQ-LRB-004: Deterministic Reverse Ordering

**Acceptance Criteria**:

- [ ] success apply item を逆順で取得できる
- [ ] rollback 対象外 action を除外できる
- [ ] TASK-RB-003 のテストが通る

**Dependencies**:

- TASK-RB-003: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-005: Write Failing Tests for Dry-Run Rollback

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
dry-run rollback がファイル変更をせず rollback log を残す failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-002: Rollback Dry-Run Mode
- REQ-LRB-008: Rollback Log Persistence
- REQ-LRB-009: Rollback Execution Tracking
- REQ-LRB-011: Rollback Output Summary

**Acceptance Criteria**:

- [ ] dry-run で source / target が変わらないテストがある
- [ ] dry-run で `rollback_runs` / `rollback_logs` が保存されるテストがある
- [ ] rollback 対象外 item を skip として記録するテストがある

**Dependencies**:

- TASK-RB-004: history query

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-006: Implement Rollback Repositories and Dry-Run Service Loop

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`rollback_run_repository`, `rollback_log_repository`, `rollback_service` の dry-run 中心ループを実装する。

**Requirements Coverage**:

- REQ-LRB-002: Rollback Dry-Run Mode
- REQ-LRB-008: Rollback Log Persistence
- REQ-LRB-009: Rollback Execution Tracking
- REQ-LRB-011: Rollback Output Summary

**Acceptance Criteria**:

- [ ] `execution_run_id` を入力に rollback を開始できる
- [ ] dry-run で mutation を行わず summary を保存できる
- [ ] TASK-RB-005 のテストが通る

**Dependencies**:

- TASK-RB-005: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-007: Write Failing Tests for Same-Volume Reverse Move

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume rollback の成功、target missing failure、source exists skip の failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-005: Same-Volume Reverse Move
- REQ-LRB-007: No Mutation on Unsafe State
- REQ-LRB-004: Deterministic Reverse Ordering

**Acceptance Criteria**:

- [ ] reverse move 成功ケースがある
- [ ] target missing による failure ケースがある
- [ ] source exists による skip ケースがある

**Dependencies**:

- TASK-RB-006: dry-run rollback

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-008: Implement Same-Volume Rollback Strategy

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume reverse move 戦略と rollback log 保存を実装する。

**Requirements Coverage**:

- REQ-LRB-005: Same-Volume Reverse Move
- REQ-LRB-007: No Mutation on Unsafe State
- REQ-TEST-RB-001: Testability of Rollback Workflow

**Acceptance Criteria**:

- [ ] same-volume で `target -> source` move が実行される
- [ ] unsafe 状態では surviving file を保持する
- [ ] TASK-RB-007 のテストが通る

**Dependencies**:

- TASK-RB-007: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-009: Write Failing Tests for Cross-Volume Reverse Copy

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
cross-volume rollback の copy/verify/delete と verify failure 時の surviving copy 保護に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-006: Cross-Volume Reverse Copy-Verify-Delete
- REQ-LRB-007: No Mutation on Unsafe State
- REQ-TEST-RB-001: Testability of Rollback Workflow

**Acceptance Criteria**:

- [ ] copy -> verify -> delete 成功ケースがある
- [ ] verify failure で source / target を保持するケースがある
- [ ] target delete failure で partial failure のケースがある

**Dependencies**:

- TASK-RB-006: dry-run rollback

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-010: Implement Cross-Volume Rollback Strategy

**Priority**: P0  
**Story Points**: 8  
**Estimated Hours**: 10  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
copy/verify/delete の順で実行する cross-volume rollback 戦略を実装する。

**Requirements Coverage**:

- REQ-LRB-006: Cross-Volume Reverse Copy-Verify-Delete
- REQ-LRB-007: No Mutation on Unsafe State
- REQ-LRB-008: Rollback Log Persistence
- REQ-REL-RB-001: Crash Resilience During Rollback

**Acceptance Criteria**:

- [ ] cross-volume item を reverse copy/verify/delete できる
- [ ] verify failure 時に surviving copy を保持する
- [ ] TASK-RB-009 のテストが通る

**Dependencies**:

- TASK-RB-009: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-011: Write Failing Tests for Rollback CLI and Exit Codes

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`rollback` CLI の引数、dry-run、partial failure、blocked execution の終了コードに対する failing tests を書く。

**Requirements Coverage**:

- REQ-LRB-011: Rollback Output Summary
- REQ-LRB-012: Exit Code Discipline for Rollback
- REQ-OBS-RB-001: Auditability of Rollback

**Acceptance Criteria**:

- [ ] rollback 成功時 exit code のテストがある
- [ ] partial failure 時 exit code のテストがある
- [ ] blocked / risky 状態の exit code テストがある

**Dependencies**:

- TASK-RB-008: same-volume rollback 実装
- TASK-RB-010: cross-volume rollback 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

### TASK-RB-012: Implement `rollback` CLI Command

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`rollback` サブコマンド、`--dry-run`、summary 出力、exit code を CLI に追加する。

**Requirements Coverage**:

- REQ-LRB-001: Rollback Input Source
- REQ-LRB-002: Rollback Dry-Run Mode
- REQ-LRB-011: Rollback Output Summary
- REQ-LRB-012: Exit Code Discipline for Rollback

**Acceptance Criteria**:

- [ ] `python -m music_folder_builder rollback --execution-run-id ...` が動く
- [ ] `--dry-run` を受け取れる
- [ ] TASK-RB-011 のテストが通る

**Dependencies**:

- TASK-RB-011: failing tests

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

---

## P1 Tasks

### TASK-RB-013: Re-Run Guard and Duplicate Rollback Validation

**Priority**: P1  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
duplicate rollback guard と rollback 履歴の完全性を追加検証する。

**Requirements Coverage**:

- REQ-LRB-010: Prevent Duplicate Rollback
- REQ-LRB-008: Rollback Log Persistence
- REQ-OBS-RB-001: Auditability of Rollback

**Acceptance Criteria**:

- [ ] 同一 operation log の二重 rollback 防止が実装される
- [ ] duplicate rollback 時の log を記録できる
- [ ] 監査に必要な source/target/action/result が必ず残る

**Dependencies**:

- TASK-RB-010: cross-volume rollback 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence

### TASK-RB-014: Integration Tests for `apply -> rollback`

**Priority**: P1  
**Story Points**: 8  
**Estimated Hours**: 8  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
same-volume / cross-volume の `apply -> rollback` を integration test で検証する。

**Requirements Coverage**:

- REQ-LRB-005: Same-Volume Reverse Move
- REQ-LRB-006: Cross-Volume Reverse Copy-Verify-Delete
- REQ-LRB-007: No Mutation on Unsafe State
- REQ-REL-RB-001: Crash Resilience During Rollback

**Acceptance Criteria**:

- [ ] same-volume の往復成功ケースがある
- [ ] cross-volume の往復成功ケースがある
- [ ] verify failure ケースがある
- [ ] rollback log が保存される

**Dependencies**:

- TASK-RB-012: rollback CLI 実装

**Test-First Checklist**:

- [ ] Tests written BEFORE implementation
- [ ] Red: Failing test committed
- [ ] Green: Minimal implementation passes test
- [ ] Blue: Refactored with confidence
