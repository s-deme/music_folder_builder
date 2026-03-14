# music_folder_builder

Windows 向けの音楽整理 CLI です。`scan -> plan -> apply -> verify -> rollback` の段階型ワークフローで、整理前の確認、実行、検証、巻き戻しまでを追跡可能な形で扱います。

このリポジトリは `musubi` を使った SDD と、Python 実装の両方を Docker 上で進める前提です。

## 前提

- Docker
- Docker Compose

## 起動

```bash
docker compose build
docker compose run --rm musubi
```

Python 仮想環境と `pip install -e .[dev]` はコンテナ起動時に自動実行されます。

```bash
python --version
```

その後、必要に応じて `musubi` を初期化します。

```bash
npx musubi-sdd init --codex
```

既存プロジェクトを解析する場合は `onboard` を使います。

```bash
npx musubi-sdd onboard
```

このリポジトリは既に初期化済みなので、通常はそのまま Python CLI を使えます。

## Docker のローカル上書き

共通設定は `docker-compose.yml` に置き、あなた固有の音楽フォルダは Git 管理外の `docker-compose.override.yml` に書きます。

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

例:

```yaml
services:
  musubi:
    volumes:
      - /path/to/your/music/source:/music:ro
```

これでコンテナ内から `/music` として見えるようになります。

## ローカル設定ファイル

ローカルの作業フォルダは `config/local.toml` に保存します。このファイルは Git には入らず、テンプレートの `config/local.toml.example` だけをコミットします。

```bash
mkdir -p config
cp config/local.toml.example config/local.toml
```

`config/local.toml` の例:

```toml
[scan]
source = "/music/source"
db = "/workspace/state.db"

[plan]
library_root = "D:/YourMusicLibrary"
db = "/workspace/state.db"

[apply]
db = "/workspace/state.db"
dry_run = true

[rollback]
db = "/workspace/state.db"
dry_run = true

[verify]
db = "/workspace/state.db"
```

CLI 実行時は `--config` を省略すると既定で `config/local.toml` を読みます。

設定の意味:

- `scan.source`: 走査対象ディレクトリ
- `scan.db`: SQLite の保存先
- `plan.library_root`: 整理先として想定するルート
- `apply.dry_run`: `apply` の既定を dry-run にするか
- `rollback.dry_run`: `rollback` の既定を dry-run にするか

パスやローカル固有値は CLI 引数に直書きせず、`config/local.toml` と `docker-compose.override.yml` で管理してください。push するのはテンプレートだけです。

## Python CLI の実行

CLI は次のコマンドを持っています。

```bash
python -m music_folder_builder --help
python -m music_folder_builder scan
python -m music_folder_builder plan --scan-run-id <SCAN_RUN_ID>
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID>
python -m music_folder_builder verify --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder rollback --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder verify --rollback-run-id <ROLLBACK_RUN_ID>
```

`scan` の `source` を `/music/...` にしたい場合は、先に `docker-compose.override.yml` で `/music` をマウントしてください。

## 典型的な手順

まず走査します。

```bash
python -m music_folder_builder scan
```

出力例:

```text
scan_run_id=... files=123 warnings=4
```

次に計画を作ります。

```bash
python -m music_folder_builder plan --scan-run-id <SCAN_RUN_ID>
```

出力例:

```text
plan_run_id=... items=120 conflicts=0 risks=0
```

安全確認として dry-run apply を実行します。

```bash
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID> --dry-run
```

問題なければ本実行します。

```bash
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID>
```

その後に verify します。

```bash
python -m music_folder_builder verify --execution-run-id <EXECUTION_RUN_ID>
```

戻したい場合は rollback です。

```bash
python -m music_folder_builder rollback --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder verify --rollback-run-id <ROLLBACK_RUN_ID>
```

## JSON 出力

すべてのサブコマンドで `--json` を使えます。

```bash
python -m music_folder_builder --json scan
python -m music_folder_builder --json plan --scan-run-id <SCAN_RUN_ID>
python -m music_folder_builder --json apply --plan-run-id <PLAN_RUN_ID>
python -m music_folder_builder --json verify --execution-run-id <EXECUTION_RUN_ID>
```

出力例:

```json
{"verify_run_id":"...","successes":10,"skips":0,"failures":0,"risks":0,"mode":"execution"}
```

PowerShell や他のスクリプトから扱うならこちらが便利です。

## テスト

```bash
python -m unittest tests.test_db_schema tests.test_apply_history_repository tests.test_apply_verify_repository tests.test_rollback_verify_repository tests.test_verify_service tests.test_file_walker tests.test_scan_service tests.test_path_policy tests.test_plan_service tests.test_cli tests.test_metadata_reader tests.test_apply_service tests.test_rollback_service -v
```
