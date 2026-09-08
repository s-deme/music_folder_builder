# Music Folder Builder

- 音楽整理は scan -> plan -> apply -> verify -> rollback の順を守り、既存の整理先を既定で上書きしない。
- 実ファイルを変更する apply・rollback・verify は Windows ネイティブ環境でだけ実行する。Docker は開発・dry-run用で、元ライブラリは読み取り専用マウントに保つ。
- config/local.toml と状態DBはローカル設定として扱い、コミットしない。
