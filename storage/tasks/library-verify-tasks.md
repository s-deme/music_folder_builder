# Task Breakdown: library-verify

## Overview

このタスク分解は `storage/design/library-verify-design.md` を実装可能な単位に分けたものである。最優先は、verify 専用テーブルを追加し、apply / rollback 実行後の expected state を read-only に検証できる最小構成を成立させることである。

---

## Execution Strategy

1. まず DB に `verify_runs` と `verify_logs` を追加する
2. apply verify / rollback verify 用 query を分けて実装する
3. read-only な `VerifyService` を実装する
4. CLI、終了コード、integration test を追加する

---

## P0 Tasks

### TASK-VF-001: Write Failing Tests for Verify Tables

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`verify_runs` と `verify_logs` の schema 追加に対する failing tests を書く。

**Requirements Coverage**:

- REQ-LVF-006: Verify Log Persistence
- REQ-LVF-007: Verify Run Tracking
- REQ-OBS-VF-001: Auditability of Verification

**Acceptance Criteria**:

- [ ] `verify_runs` の作成テストがある
- [ ] `verify_logs` の作成テストがある
- [ ] schema 拡張前はテストが失敗する

---

### TASK-VF-002: Implement Verify Schema Bootstrap

**Priority**: P0  
**Story Points**: 2  
**Estimated Hours**: 3  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
既存 schema に `verify_runs` と `verify_logs` を追加する。

**Requirements Coverage**:

- REQ-LVF-006: Verify Log Persistence
- REQ-LVF-007: Verify Run Tracking
- REQ-OBS-VF-001: Auditability of Verification

**Acceptance Criteria**:

- [ ] schema 初期化で verify 用テーブルが作られる
- [ ] 既存 schema と併存できる
- [ ] TASK-VF-001 のテストが通る

---

### TASK-VF-003: Write Failing Tests for Apply Verify Query

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
apply success item から verify 対象を組み立てる query の failing tests を書く。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-003: Post-Apply Expectation Checks
- REQ-LVF-008: Deterministic Verification Ordering

**Acceptance Criteria**:

- [ ] apply success item のみ取得するテストがある
- [ ] expected source/target state を含むテストがある
- [ ] deterministic order を検証するテストがある

---

### TASK-VF-004: Implement Apply Verify Repository

**Priority**: P0  
**Story Points**: 4  
**Estimated Hours**: 5  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`execution_run_id` を入力に verify 対象 item を返す `apply_verify_repository` を実装する。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-003: Post-Apply Expectation Checks
- REQ-LVF-008: Deterministic Verification Ordering

**Acceptance Criteria**:

- [ ] apply success item を順序付きで取得できる
- [ ] expected state を構築できる
- [ ] TASK-VF-003 のテストが通る

---

### TASK-VF-005: Write Failing Tests for Rollback Verify Query

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
rollback success item から verify 対象を組み立てる query の failing tests を書く。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-004: Post-Rollback Expectation Checks
- REQ-LVF-008: Deterministic Verification Ordering

**Acceptance Criteria**:

- [ ] rollback success item のみ取得するテストがある
- [ ] expected source/target state を含むテストがある
- [ ] deterministic order を検証するテストがある

---

### TASK-VF-006: Implement Rollback Verify Repository

**Priority**: P0  
**Story Points**: 4  
**Estimated Hours**: 5  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`rollback_run_id` を入力に verify 対象 item を返す `rollback_verify_repository` を実装する。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-004: Post-Rollback Expectation Checks
- REQ-LVF-008: Deterministic Verification Ordering

**Acceptance Criteria**:

- [ ] rollback success item を順序付きで取得できる
- [ ] expected state を構築できる
- [ ] TASK-VF-005 のテストが通る

---

### TASK-VF-007: Write Failing Tests for Verify Service

**Priority**: P0  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
apply / rollback の expected state を read-only に確認する `VerifyService` の failing tests を書く。

**Requirements Coverage**:

- REQ-LVF-002: Read-Only Verification
- REQ-LVF-003: Post-Apply Expectation Checks
- REQ-LVF-004: Post-Rollback Expectation Checks
- REQ-LVF-006: Verify Log Persistence
- REQ-LVF-007: Verify Run Tracking

**Acceptance Criteria**:

- [ ] apply success verify のテストがある
- [ ] rollback success verify のテストがある
- [ ] missing file / mismatch の failure テストがある

---

### TASK-VF-008: Implement Verify Repositories and Service

**Priority**: P0  
**Story Points**: 8  
**Estimated Hours**: 10  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`verify_run_repository`, `verify_log_repository`, `state_gateway`, `verify_service` を実装する。

**Requirements Coverage**:

- REQ-LVF-002: Read-Only Verification
- REQ-LVF-003: Post-Apply Expectation Checks
- REQ-LVF-004: Post-Rollback Expectation Checks
- REQ-LVF-006: Verify Log Persistence
- REQ-LVF-007: Verify Run Tracking
- REQ-LVF-009: Verify Output Summary

**Acceptance Criteria**:

- [ ] apply / rollback の verify が read-only で動く
- [ ] verify_runs / verify_logs が保存される
- [ ] TASK-VF-007 のテストが通る

---

### TASK-VF-009: Write Failing Tests for Verify CLI and Exit Codes

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`verify` CLI の引数、execution/rollback run 選択、mismatch 時終了コードの failing tests を書く。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-009: Verify Output Summary
- REQ-LVF-010: Exit Code Discipline for Verify

**Acceptance Criteria**:

- [ ] execution-run-id 指定のテストがある
- [ ] rollback-run-id 指定のテストがある
- [ ] 両方指定時の引数エラーテストがある
- [ ] failure 時 exit code テストがある

---

### TASK-VF-010: Implement `verify` CLI Command

**Priority**: P0  
**Story Points**: 3  
**Estimated Hours**: 4  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`verify` サブコマンド、summary 出力、exit code を CLI に追加する。

**Requirements Coverage**:

- REQ-LVF-001: Verify Input Source
- REQ-LVF-009: Verify Output Summary
- REQ-LVF-010: Exit Code Discipline for Verify

**Acceptance Criteria**:

- [ ] `python -m music_folder_builder verify --execution-run-id ...` が動く
- [ ] `python -m music_folder_builder verify --rollback-run-id ...` が動く
- [ ] TASK-VF-009 のテストが通る

---

## P1 Tasks

### TASK-VF-011: Add Size Comparison Checks

**Priority**: P1  
**Story Points**: 5  
**Estimated Hours**: 6  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
size comparison を verify service に追加し、size mismatch を failure にする。

**Requirements Coverage**:

- REQ-LVF-005: Size Consistency Check
- REQ-LVF-006: Verify Log Persistence

**Acceptance Criteria**:

- [ ] size mismatch を failure にできる
- [ ] size 情報が verify log に反映される
- [ ] compare 不可時の扱いを定義できる

### TASK-VF-012: Integration Tests for `apply -> verify` and `rollback -> verify`

**Priority**: P1  
**Story Points**: 8  
**Estimated Hours**: 8  
**Assignee**: Unassigned  
**Status**: Not Started

**Description**:  
`apply -> verify` と `rollback -> verify` の実行列を integration test で検証する。

**Requirements Coverage**:

- REQ-LVF-003: Post-Apply Expectation Checks
- REQ-LVF-004: Post-Rollback Expectation Checks
- REQ-OBS-VF-001: Auditability of Verification

**Acceptance Criteria**:

- [ ] apply 後 verify success ケースがある
- [ ] rollback 後 verify success ケースがある
- [ ] mismatch ケースがある
- [ ] verify log が保存される
