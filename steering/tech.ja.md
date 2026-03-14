# Technology Stack

**Project**: music_folder_builder
**Last Updated**: 2026-03-14
**Version**: 1.0

---

## Overview

Windows CLI で動作する音楽ファイル整理ツールを Python で実装する。安全なファイル整理のため、内部状態は SQLite に保存し、処理は段階型ワークフローで進める。

---

## Primary Technologies

### Programming Language

| Technology | Version | Role | Notes |
|-----------|---------|------|-------|
| Python | 3.11+ | Primary implementation | 標準ライブラリを優先しつつ必要最小限の依存を追加する |

### Runtime and Packaging

| Technology | Role | Notes |
|-----------|------|-------|
| `pyproject.toml` | Project metadata and dependency management | 単一パッケージ構成 |
| Docker | Development environment | Node 系の MUSUBI 利用と Python 開発環境の共存に使う |

### Persistence and Data

| Technology | Role | Notes |
|-----------|------|-------|
| SQLite | Internal state store | 走査結果、計画、実行履歴、操作ログを保持する |
| JSON / JSONL | Export or debug artifacts | 計画確認や外部連携の補助に使う可能性がある |

---

## Technical Principles

1. **Python Standard Library First**
   - `pathlib`, `sqlite3`, `logging`, `hashlib`, `argparse` を基本に設計する。

2. **SQLite as Operational Backbone**
   - 実行途中で落ちても再開や検証ができるよう、状態を DB に残す。

3. **Windows Filesystem Awareness**
   - 長パス、禁止文字、予約名、reparse point を技術前提として扱う。

4. **CLI Compatibility**
   - PowerShell から扱いやすい終了コードと非対話実行を重視する。

5. **Loose Coupling with Metadata Sources**
   - 他ツールとは DB やエクスポートファイル経由の連携を優先し、直接依存は急がない。

---

## Expected Core Modules

- `cli`: サブコマンド、引数、終了コード、表示
- `application.services`: `scan`, `plan`, `apply`, `verify`, `rollback`, `doctor`
- `domain.models`: トラック、移動計画、ルール、操作結果
- `domain.policies`: 命名規則、衝突解決、メタデータ解釈、パス長制御
- `infrastructure.fs`: walker、mover、path sanitizer
- `infrastructure.db`: SQLite 接続、リポジトリ、将来の migration
- `infrastructure.metadata`: 埋め込みタグや外部メタデータの読み取り
- `infrastructure.logging`: CLI とは分離した操作ログ

---

## Dependency Guidance

現時点では依存を固定しすぎない。次の方針だけを採用する。

- CLI フレームワークは、標準ライブラリか軽量な選択肢を優先する
- メタデータ読み取りライブラリは requirements/design で選定する
- ハッシュアルゴリズムは要件次第で決める
- ORM は必須にしない。SQLite には薄いアクセス層を優先する

---

## Development Environment

### Required Tools

- Python 3.11+
- Git
- Docker / Docker Compose
- Codex CLI with MUSUBI prompts

### Recommended Tooling

- `pytest` for test execution
- `ruff` for lint / format
- `mypy` or equivalent static checking if type complexity grows

---

## Windows Constraints to Respect

- 長いパスを生成しすぎない
- 禁止文字を代替文字へ正規化する
- 予約名を安全な名前へ変換する
- reparse point をデフォルトで辿らない
- 異なるボリューム間移動時は copy/verify/delete を考慮する

---

## Testing Strategy

- Unit: パス正規化、命名規則、衝突解決、メタデータ解釈
- Integration: `scan -> plan -> apply -> verify`
- Recovery: 中断後の再実行、部分失敗、ロールバック
- Windows-specific: 日本語、絵文字、長パス、予約名、OneDrive や外付け媒体近傍

---

## Open Decisions

以下は現時点では未確定とし、feature の要件と設計で決める。

- メタデータ読み取りライブラリ
- SQLite スキーマ詳細
- ハッシュ方式
- 並列化範囲
- 外部メタデータツールとの接続形式
