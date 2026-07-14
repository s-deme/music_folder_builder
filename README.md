# music_folder_builder

音楽ファイルをメタデータに合わせて整理するツールです。  
基本の流れは `scan -> plan -> apply -> verify -> rollback` です。

この README は利用者向けです。開発用の設計資料は `steering/` と `storage/` にあります。

## できること

- 元の音楽フォルダを読み取る
- 整理後の移動先を事前確認する
- dry-run で安全確認してから本実行する
- 実行結果を verify する
- 必要なら rollback する
- GUI で履歴・進捗・ログを確認する

## 必要なもの

- Docker Desktop / Docker Compose
- GUI を使う場合: ホスト側で GUI 表示が使えること

## すぐ起動する

Windows 側のパスが `E:\script\music_folder_builder` の場合、WSL / Linux シェルでは
`/mnt/e/script/music_folder_builder` として開きます。

```bash
cd /mnt/e/script/music_folder_builder
docker compose build
docker compose run --rm app
```

コンテナのシェルが開いたら、GUI を起動します。

```bash
python -m music_folder_builder.gui
```

または:

```bash
music-folder-builder-gui
```

GUI が表示されない場合や、GUI 環境を使わずに確認したい場合は、コンテナ内で CLI を実行できます。

```bash
python -m music_folder_builder scan
```

現在のローカル設定は `config/local.toml`、Docker のマウント設定は
`docker-compose.override.yml` を確認してください。

### GUI が `couldn't connect to display ""` で起動しない場合

このエラーは、コンテナ内の `DISPLAY` が空で、GUI の表示先が渡っていない状態です。

まずコンテナから抜けます。

```bash
exit
```

WSL / Linux シェル側で `DISPLAY` を確認します。

```bash
echo $DISPLAY
```

何も表示されない場合は、そのシェルからは GUI 表示が使えません。WSLg が使える WSL
ターミナルで開き直すか、X サーバーを起動してから `DISPLAY` を設定してください。

`DISPLAY` に `:0` などが表示される場合は、そのシェルから起動し直します。

```bash
docker compose run --rm app
python -m music_folder_builder.gui
```

WSLg 環境で GUI がまだ接続できない場合は、`docker-compose.override.yml` の X11
ソケットのマウントを環境に合わせます。

```yaml
services:
  app:
    environment:
      - DISPLAY=${DISPLAY}
    volumes:
      - /mnt/e/iTunes/iTunes Media/Music:/music:ro
      - /mnt/wslg/.X11-unix:/tmp/.X11-unix:rw
```

## 最初の準備

`config/local.toml` はローカル専用ファイルです。Docker 用サンプルから作ってください。

1. 設定ファイルを作ります。

```bash
mkdir -p config
cp config/local.docker.toml.example config/local.toml
```

2. `config/local.toml` を編集します。

例:

```toml
[scan]
source = "/music/source_library"
db = "/workspace/state.db"

[plan]
library_root = "D:/Path/To/OrganizedLibrary"
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

設定の意味:

- `scan.source`: 元の音楽フォルダ
- `scan.db`: 作業記録の保存先
- `plan.library_root`: 整理後の置き場所の基準フォルダ
- `apply.dry_run`: apply を最初から dry-run にするか
- `rollback.dry_run`: rollback を最初から dry-run にするか

3. `docker-compose.override.yml` を作ります。

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

例:

```yaml
services:
  app:
    environment:
      - DISPLAY=${DISPLAY}
    volumes:
      - /path/to/your/music/source_library:/music/source_library:ro
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
```

`/path/to/your/music/source_library` は実際の音楽フォルダに置き換えてください。
この例ではコンテナ内から `/music/source_library` として見えるようになります。

## コンテナを開く

```bash
docker compose build
docker compose run --rm app
```

`docker compose run --rm app` を実行すると、コンテナ内のシェルを開けます。
以降の GUI / CLI コマンドはその中で実行します。

## GUI を使う

コンテナ内で次を実行します。

```bash
python -m music_folder_builder.gui
```

または:

```bash
music-folder-builder-gui
```

GUI は次の順に使います。

1. `はじめに` で全体の流れを確認
2. `設定` で元フォルダや保存先を確認
3. `フォルダ名・ファイル名` で整理後の名前ルールを必要に応じて変更
4. `1. 読み取り` で元フォルダを読み取る
5. `2. 整理予定` で整理後の配置を確認
6. `3. 整理実行` でテスト実行または本実行し、結果確認する
7. `4. 元に戻す` で必要な場合だけ巻き戻し
8. `ログと履歴整理` で詳細ログ確認と不要履歴の削除

注意:

- GUI 変更後は `docker compose build` をやり直してください。
- 日本語表示のためにコンテナへ CJK フォントを入れています。
- 履歴は自動削除されません。不要な履歴は GUI から手動削除してください。
- 時刻表示は既定で JST です。必要なら `display.timezone` を変えてください。
- 命名テンプレートでは `{track_no:02d}` のようなパディング指定と `[{track_no:02d}_]` のような条件付き表示が使えます。
- 元のファイル名をそのまま使いたい場合は、GUI の `フォルダ名・ファイル名` タブで設定できます。
- 画像ファイルに元のファイル名を使う設定では、同じ整理先で名前が重複した場合に `_2`, `_3` のような連番を付けます。
- `display` や `naming` を含む設定例は `config/local.docker.toml.example` に入っています。

## コマンドラインで使う

GUI を使わずに CLI でも実行できます。以下もコンテナ内で実行します。

```bash
python -m music_folder_builder scan
python -m music_folder_builder plan --scan-run-id <SCAN_RUN_ID>
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID>
python -m music_folder_builder verify --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder rollback --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder verify --rollback-run-id <ROLLBACK_RUN_ID>
```

典型的な流れ:

```bash
python -m music_folder_builder scan
python -m music_folder_builder plan --scan-run-id <SCAN_RUN_ID>
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID> --dry-run
python -m music_folder_builder apply --plan-run-id <PLAN_RUN_ID>
python -m music_folder_builder verify --execution-run-id <EXECUTION_RUN_ID>
```

戻したい場合:

```bash
python -m music_folder_builder rollback --execution-run-id <EXECUTION_RUN_ID>
python -m music_folder_builder verify --rollback-run-id <ROLLBACK_RUN_ID>
```

## 補足

- `apply` や `rollback` の前に dry-run を試すのを推奨します。
- `verify` は実行後の状態確認です。できるだけ毎回行ってください。
- 命名規則を変更した場合は、`2. 整理予定` を作り直して結果を確認してください。

## 開発者向け

開発用のテスト実行例:

```bash
python -m unittest tests.test_db_schema tests.test_apply_history_repository tests.test_apply_verify_repository tests.test_rollback_verify_repository tests.test_verify_service tests.test_file_walker tests.test_scan_service tests.test_path_policy tests.test_plan_service tests.test_cli tests.test_metadata_reader tests.test_apply_service tests.test_rollback_service tests.test_gui_query_service -v
```
