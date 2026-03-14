# Product Context

**Project**: music_folder_builder
**Last Updated**: 2026-03-14
**Version**: 1.0

---

## Product Vision

**Vision Statement**: 音楽ファイル整理を、安全に再実行できる Windows CLI として提供する。

メタデータを元に音楽ライブラリを整理したいユーザーは多い一方で、直接移動を実行するツールは誤整理や衝突でライブラリを壊しやすい。このプロジェクトは、実行前に結果を確認でき、実行後も追跡と巻き戻しができる整理ツールを提供する。

最優先は「賢さ」ではなく「事故りにくさ」である。大量ファイル、長いパス、日本語ファイル名、タグ欠損、同名衝突といった現実的な問題を前提に、段階的に整理できることを価値とする。

**Mission**: `scan -> plan -> apply -> verify -> rollback` の段階型ワークフローで、音楽ライブラリ整理を安全に自動化する。

---

## Product Overview

### What is music_folder_builder?

`music_folder_builder` は、音楽ファイルの埋め込みメタデータや外部メタデータを参照し、ルールに基づいてフォルダ構成と保存場所を決定する Windows 向け CLI ツールである。

このツールは、いきなりファイルを移動しない。まず走査して状態を保存し、次に移動計画を作り、その計画を確認した上で適用する。適用後は整合性を検証し、必要に応じて巻き戻せる構成を基本とする。

### Problem Statement

個人の音楽ライブラリは、複数の保存先、揺れたタグ、禁止文字を含むタイトル、同名ファイル、長すぎるパスなどの問題を抱えやすい。単発スクリプトで一括移動すると、失敗時にどこまで進んだかが分からず、復旧も難しい。

Windows では特に、予約名、禁止文字、長いパス、reparse point の扱いが事故要因になる。これらを考慮しない整理処理は、実運用に耐えにくい。

### Solution

このプロジェクトは、整理処理を段階に分けて内部状態を保存する。走査結果、移動計画、適用履歴、検証結果を追跡可能にすることで、再実行性、説明可能性、ロールバック性を確保する。

加えて、Windows 固有のファイルシステム制約を最初から設計に含めることで、現実の音楽ライブラリに対して安全に使える CLI を目指す。

---

## Target Users

### Primary Users

#### User Persona 1: 個人アーカイブ管理者

- **Role**: 自分の音楽ライブラリを管理する個人ユーザー
- **Technical Level**: 中級
- **Goals**: メタデータに基づいて統一されたフォルダ構成へ整理したい
- **Pain Points**: 手作業のリネームが辛い、誤移動が怖い、実行結果を追跡したい
- **Use Cases**: 未整理フォルダの走査、整理計画の確認、適用後の検証

#### User Persona 2: スクリプト活用ユーザー

- **Role**: PowerShell やバッチから CLI を使うユーザー
- **Technical Level**: 中級から上級
- **Goals**: 自動化可能な終了コードとログを持つ整理ツールが欲しい
- **Pain Points**: 単発スクリプトは再実行性が低い、失敗時に状態が追えない
- **Use Cases**: 定期実行、dry-run 出力確認、失敗時の再試行や巻き戻し

### Secondary Users

- **メタデータ整備ツール利用者**: 既存のメタデータ正規化結果を整理処理に渡したいユーザー
- **将来の GUI 利用者**: 将来的に CLI 以外のインターフェースから同じコア機能を使いたいユーザー

---

## Core Product Capabilities

### Must-Have Features (MVP)

1. **Scan**
   - **Description**: 対象フォルダを走査し、ファイル情報とメタデータを保存する
   - **User Value**: 現在の状態を壊さず可視化できる
   - **Priority**: P0

2. **Plan**
   - **Description**: 保存済みデータから移動先候補と衝突情報を生成する
   - **User Value**: 実行前に結果と危険箇所を確認できる
   - **Priority**: P0

3. **Apply**
   - **Description**: 計画 ID を指定して移動を適用し、結果を操作ログに残す
   - **User Value**: 実際の整理を追跡可能な形で実行できる
   - **Priority**: P0

4. **Verify**
   - **Description**: 適用結果を検証し、欠落や不整合を検出する
   - **User Value**: 実行後の安心感を得られる
   - **Priority**: P0

### High-Priority Features (Post-MVP)

5. **Rollback**
   - **Description**: 直前の実行履歴を元に逆方向の操作を行う
   - **User Value**: 誤整理時に戻せる
   - **Priority**: P1

6. **Doctor**
   - **Description**: 長パス、権限、禁止文字、リンク追跡設定などを事前診断する
   - **User Value**: 本番実行前に危険状態を把握できる
   - **Priority**: P1

### Future Features (Roadmap)

7. **External Metadata Integration**
   - **Description**: 外部 SQLite や JSONL から正規化済みメタデータを読み込む
   - **User Value**: 既存ツール群と疎結合で連携できる
   - **Priority**: P2

8. **Profile-Based Rules**
   - **Description**: 複数の整理ルールプロファイルを切り替える
   - **User Value**: 用途別に整理方針を使い分けられる
   - **Priority**: P2

---

## Product Principles

1. **Safety Before Mutation**
   - 直接移動よりも、計画と検証を優先する。

2. **Reproducibility**
   - 走査結果、計画、実行結果は再利用できる形で保存する。

3. **Windows Reality First**
   - 禁止文字、予約名、長パス、reparse point を設計時点から扱う。

4. **CLI Automation Friendly**
   - 明確な終了コード、ログ、非対話実行を前提にする。

5. **Separation of Metadata and Movement**
   - メタデータ正規化とファイル移動は疎結合に保つ。

---

## Success Metrics

- dry-run なしで直接変更する機能を持たない
- 主要コマンドが再実行可能である
- 適用結果をログと DB から追跡できる
- Windows で日本語パスと禁止文字ケースを扱える
- 誤整理時にロールバック可能な設計を維持する
