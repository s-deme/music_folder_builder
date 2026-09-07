# Implementation Status

**Project**: music_folder_builder
**Updated**: 2026-08-31

この文書は、ソースツリーから確認できる実装状況の案内である。実機受け入れ、性能評価、実データでの安全性検証が完了したことを示すものではない。

## 現在確認できる入口

- CLI: `music-folder-builder` / `python -m music_folder_builder`
- GUI: `music-folder-builder-gui` / `python -m music_folder_builder.gui`
- CLIサブコマンド: `scan`, `plan`, `apply`, `verify`, `rollback`
- 完全なテスト探索: `python -m unittest discover -v`

`doctor` は製品・構造文書に残る将来機能であり、現行CLIには実装されていない。

## 実行環境の境界

実ファイルを変更する `apply` / `rollback` と、その結果を確認する `verify` はWindowsネイティブ環境で行う。Docker Compose例は元ライブラリを読み取り専用でマウントし、開発、テスト、走査、計画、GUI確認、dry-runに使う。

## SDD文書の読み方

`storage/specs/`, `storage/design/`, `storage/tasks/` は設計経緯と要求トレーサビリティを保持する。古い `Draft` や `Not Started` の見出し・チェック状態だけで現在の実装有無を判断せず、ソース、テスト、READMEと合わせて確認する。機能の受け入れ完了を主張する場合は、対象リビジョンと実行結果を別途記録する。
