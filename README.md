# music_folder_builder

音楽ファイルをメタデータに合わせて整理するツールです。  
基本の流れは `scan -> plan -> apply -> verify -> rollback` です。

この README は利用者向けです。開発用の設計資料は `steering/` と `storage/` にあります。実装と計画文書の対応は [steering/status.ja.md](steering/status.ja.md) を参照してください。

## できること

- 元の音楽フォルダを読み取る
- 整理後の移動先を事前確認する
- dry-run で安全確認してから本実行する
- 実行結果を verify する
- 必要なら rollback する
- GUI で履歴・進捗・ログを確認する

## 必要なもの

- Windowsで実際に整理する場合: Python 3.11 以上（GUIにはPython付属のTkも必要）
- Docker開発環境を使う場合のみ: Docker Desktop / Docker Compose
- コンテナでGUIを確認する場合: ホスト側でGUI表示が使えること

## 安全な実行環境

実際にファイルを移動する `apply`、移動を戻す `rollback`、実ファイルを確認する `verify` はWindowsネイティブのPython環境で実行してください。現在の計画とpath policyはWindowsパスを正本としており、Docker Composeのサンプルは元ライブラリを読み取り専用で `/music` にマウントします。Linuxコンテナから `D:\...` を直接変更する構成ではありません。

Dockerは開発、テスト、`scan`、`plan`、GUI確認、`apply --dry-run`、`rollback --dry-run` に使えます。コンテナには整理先の書き込みマウントを追加せず、本実行を誤って行わないでください。

## Windowsで使い始める

PowerShellで仮想環境を作成し、プロジェクトをインストールします。GUIにはPython付属のTkが必要です。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item config\local.toml.example config\local.toml
```

`config/local.toml` の `scan.source` と `plan.library_root` を実際のWindowsパスへ変更してから起動します。

```powershell
music-folder-builder-gui
```

CLIを使う場合も同じ設定を使います。

```powershell
music-folder-builder scan
```

## Docker開発環境の準備

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
source = "/music"
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
      - /path/to/your/music/source_library:/music:ro
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
```

`/path/to/your/music/source_library` は実際の音楽フォルダに置き換えてください。
この例ではコンテナ内から `/music` として見え、`config/local.toml` の `scan.source` と一致します。`:ro` を外さず、Dockerから元ライブラリを書き換えないでください。`plan.library_root` のWindowsパスは計画確認用であり、Docker内からそのパスへ本適用しません。

## コンテナを開く

```bash
docker compose build
docker compose run --rm app
```

`docker compose run --rm app` を実行すると、コンテナ内のシェルを開けます。
以降の GUI / CLI コマンドはその中で実行します。

## GUI を使う

Windowsネイティブ環境では `music-folder-builder-gui`、コンテナ内では次を実行します。

```bash
python -m music_folder_builder.gui
```

または:

```bash
music-folder-builder-gui
```

コンテナのGUIは開発・計画確認用です。実際の整理と巻き戻しはWindowsネイティブ環境から行います。

GUI は次の順に使います。

1. `はじめに` で全体の流れを確認
2. `設定` で元フォルダや保存先を確認
3. `フォルダ名・ファイル名` で整理後の名前ルールを必要に応じて変更
4. `1. 読み取り` で元フォルダを読み取る
5. `2. 整理予定` で整理後の配置を確認
6. `3. 整理実行` でテスト実行し、Windowsネイティブ環境では確認後に本実行する
7. `4. 元に戻す` で必要な場合だけ巻き戻す（本実行はWindowsネイティブ環境）
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

### Docker GUIが `couldn't connect to display ""` で起動しない場合

コンテナを終了し、WSL / Linux側で `echo $DISPLAY` を確認します。空の場合はWSLgを利用できるターミナルで開き直すか、Xサーバーを起動して `DISPLAY` を設定してください。値があるのに接続できない場合は、`docker-compose.override.yml` のX11 socketを環境に合わせます。WSLgでは通常、次のマウントを使います。

```yaml
services:
  app:
    environment:
      - DISPLAY=${DISPLAY}
    volumes:
      - /mnt/e/iTunes/iTunes Media/Music:/music:ro
      - /mnt/wslg/.X11-unix:/tmp/.X11-unix:rw
```

## コマンドラインで使う

GUIを使わずにCLIでも実行できます。次の完全なフローはWindowsネイティブ環境で実行します。Dockerでは `scan`、`plan` と、明示的な `--dry-run` までに限定します。

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

全テストは個別モジュールを列挙せず、discoverで実行します。これによりGUI、設定I/O、package layoutのテストも含まれます。

```bash
python -m unittest discover -v
```
