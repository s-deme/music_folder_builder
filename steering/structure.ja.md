# Project Structure

**Project**: music_folder_builder
**Last Updated**: 2026-08-31
**Version**: 1.0

---

## Architecture Pattern

**Primary Pattern**: Library-First なレイヤード CLI / GUI

コア機能はライブラリとして実装し、CLI と GUI はその上に載せる。現在の処理は `scan -> plan -> apply -> verify -> rollback` の段階型ワークフローとして分離する。`doctor` は将来機能であり、現行CLIには存在しない。

`apply` は単独でファイルシステムを走査しない。必ず事前に生成された計画を入力として使い、各段階の成果物と結果を永続化する。

---

## Layers

### Domain

- 役割: 業務ルールと純粋な判定ロジック
- 内容: `Track`, `FileRecord`, `MovePlan`, `FolderRule` などのモデル
- 制約: ファイル I/O、DB、CLI 引数処理を持たない

### Application

- 役割: ユースケースの実行制御
- 内容: `scan`, `plan`, `apply`, `verify`, `rollback` のサービス
- 制約: 直接 I/O せず、必要な操作はポート経由で依存する

### Infrastructure

- 役割: ファイルシステム、SQLite、メタデータ読み取り、ログ出力
- 内容: walker、mover、path sanitizer、metadata reader、SQLite repository
- 制約: 業務判断は Domain/Application に持ち込まない

### CLI

- 役割: サブコマンド、オプション、終了コード、表示
- 内容: `scan`, `plan`, `apply`, `verify`, `rollback`
- 制約: 実処理を直接持たず、Application を呼ぶだけにする

### GUI

- 役割: 設定、段階型ワークフロー、進捗、履歴、ログのデスクトップ表示
- 内容: Tkinter の画面と GUI 用 query service
- 制約: ファイル操作の規則は Application / Domain に委譲する

---

## Current Directory Layout

現在の主要構成は次のとおり。

```text
music_folder_builder/
├── src/music_folder_builder/
│   ├── cli/
│   │   └── commands/
│   ├── application/
│   │   ├── dto/
│   │   └── services/
│   ├── domain/
│   │   ├── models/
│   │   ├── policies/
│   │   └── errors/
│   ├── infrastructure/
│   │   ├── db/
│   │   ├── fs/
│   │   ├── logging/
│   │   └── metadata/
│   └── gui/
├── tests/*.py
├── config/
├── storage/
│   ├── specs/
│   ├── design/
│   └── tasks/
└── steering/
```

---

## Command Model

CLI は現在、次のサブコマンドを持つ。

- `scan`: 対象ファイルとメタデータを収集して保存する
- `plan`: 整理ルールから移動計画を生成する
- `apply`: 計画 ID を指定して計画を適用する
- `verify`: 適用後の整合性を検証する
- `rollback`: 実行履歴を元に巻き戻す

`doctor` は計画中であり、現行CLIのサブコマンドではない。

グローバルオプションは `--config` と `--json` である。`--db` は各サブコマンド、`--dry-run` は `apply` と `rollback` のオプションとして指定する。

---

## Workflow Rules

1. `scan` は音楽ファイルを変更しないが、SQLite の走査状態は更新する。
2. `plan` は移動候補と衝突情報を保存するが、変更はしない。
3. `apply` は plan 済みデータのみを入力にして実行する。
4. `verify` は適用後の状態確認を担当する。
5. `rollback` は `apply` の操作ログを元に戻す。
6. 危険な直接変更は CLI の通常経路に置かない。

---

## Persistence Boundaries

- 走査結果、計画、実行履歴、操作ログは SQLite に保存する
- SDD 文書は `storage/` 配下に保存する
- ログは機械可読性を意識し、CLI 表示とは分離する

SQLite の具体スキーマは `src/music_folder_builder/infrastructure/db/schema.py` と `storage/design/` の各設計文書で管理する。

---

## Windows-Specific Structural Constraints

- reparse point はデフォルトで追跡しない
- パス生成は専用の sanitizer を経由する
- 長パス対策は path policy で扱う。将来の `doctor` でも事前診断する計画である
- 予約名、禁止文字、末尾空白、末尾ピリオドを正規化対象に含める

---

## Testing Structure

- 現在のテストは `tests/test_*.py` にフラット配置する
- Unit: ドメインモデル、命名規則、衝突解決、パス正規化
- Integration: `scan -> plan -> apply -> verify -> rollback` の主要経路
- GUI / config / package layout も同じ discovery 対象に含める
- 完全な実行コマンドは `python -m unittest discover -v`

テストは各 feature を library-first で追加し、CLI テストは Application/Infrastructure の結合点として最小限に保つ。
