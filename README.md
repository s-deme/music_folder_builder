# music_folder_builder

音楽ファイルをメタデータに合わせて整理するツールです。  
基本の流れは `scan -> plan -> apply -> verify -> rollback` です。

## できること

- 元の音楽フォルダを読み取る
- 整理後の移動先を事前確認する
- dry-run で安全確認してから本実行する
- 実行結果を verify する
- 必要なら rollback する
- GUI で履歴・進捗・ログを確認する

## 必要なもの

- Windowsで実際に整理する場合: Python 3.11 以上（GUIにはPython付属のTkも必要）

## 安全な実行環境

実際にファイルを移動する `apply`、移動を戻す `rollback`、実ファイルを確認する `verify` はWindowsネイティブのPython環境で実行してください。

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

## GUI を使う

Windowsネイティブ環境で `music-folder-builder-gui` を実行します。

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

- 履歴は自動削除されません。不要な履歴は GUI から手動削除してください。
- 時刻表示は既定で JST です。必要なら `display.timezone` を変えてください。
- 命名テンプレートでは `{track_no:02d}` のようなパディング指定と `[{track_no:02d}_]` のような条件付き表示が使えます。
- 元のファイル名をそのまま使いたい場合は、GUI の `フォルダ名・ファイル名` タブで設定できます。
- 画像ファイルに元のファイル名を使う設定では、同じ整理先で名前が重複した場合に `_2`, `_3` のような連番を付けます。
## コマンドラインで使う

GUIを使わずにCLIでも実行できます。次の完全なフローはWindowsネイティブ環境で実行します。

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
