from __future__ import annotations

import csv
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from music_folder_builder.application.dto.apply_request import ApplyRequest
from music_folder_builder.application.dto.plan_request import PlanRequest
from music_folder_builder.application.dto.rollback_request import RollbackRequest
from music_folder_builder.application.dto.scan_request import ScanRequest
from music_folder_builder.application.dto.verify_request import VerifyRequest
from music_folder_builder.application.services.apply_service import ApplyService
from music_folder_builder.application.services.plan_service import PlanService
from music_folder_builder.application.services.rollback_service import RollbackService
from music_folder_builder.application.services.scan_service import ScanService
from music_folder_builder.application.services.verify_service import VerifyService
from music_folder_builder.cli.config import get_command_config, load_config, save_config
from music_folder_builder.domain.policies.organization_rules import OrganizationRules
from music_folder_builder.gui.query_service import GuiQueryService, PlanItemRow, RunRow


@dataclass(frozen=True, slots=True)
class RunTreeSpec:
    title: str
    primary_heading: str
    secondary_heading: str
    detail_heading: str


@dataclass(slots=True)
class PagingState:
    offset: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class DeleteResult:
    label: str
    run_id: str


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _show(self, _: object) -> None:
        if self._window is not None:
            return
        x = self._widget.winfo_rootx() + 18
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._window = tk.Toplevel(self._widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._window,
            text=self._text,
            justify="left",
            relief="solid",
            borderwidth=1,
            background="#fff9d6",
            padx=8,
            pady=4,
            wraplength=420,
        )
        label.pack()

    def _hide(self, _: object) -> None:
        if self._window is None:
            return
        self._window.destroy()
        self._window = None


class MusicFolderBuilderApp:
    _DEFAULT_TIMEZONE = "Asia/Tokyo"
    _PAGE_SIZE = 200
    _COMMON_TIMEZONES = (
        "Asia/Tokyo",
        "UTC",
        "Asia/Seoul",
        "Asia/Shanghai",
        "Europe/London",
        "America/New_York",
        "America/Los_Angeles",
    )

    def __init__(self, *, default_config_path: Path) -> None:
        self._default_config_path = default_config_path
        self._root = tk.Tk()
        self._root.title("music_folder_builder GUI")
        self._root.geometry("1600x980")
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._running = False
        self._configure_fonts()

        self._source_var = tk.StringVar()
        self._db_var = tk.StringVar()
        self._library_root_var = tk.StringVar()
        self._timezone_var = tk.StringVar(value=self._DEFAULT_TIMEZONE)
        self._artist_dir_template_var = tk.StringVar(value="{album_artist}")
        self._album_dir_template_var = tk.StringVar(value="{album}")
        self._disc_dir_template_var = tk.StringVar(value="[{disc_no:02d}]")
        self._filename_template_var = tk.StringVar(value="[{track_no:02d}_]{title}{extension}")
        self._use_source_filename_var = tk.BooleanVar(value=False)
        self._plan_warnings_only_var = tk.BooleanVar(value=False)

        self._status_var = tk.StringVar(value="待機中")
        self._result_var = tk.StringVar(value="まだ実行していません。")

        self._plan_scan_choice_var = tk.StringVar()
        self._apply_plan_choice_var = tk.StringVar()
        self._review_run_choice_var = tk.StringVar()
        self._rollback_execution_choice_var = tk.StringVar()
        self._rollback_run_choice_var = tk.StringVar()
        self._logs_execution_choice_var = tk.StringVar()
        self._logs_rollback_choice_var = tk.StringVar()
        self._logs_verify_choice_var = tk.StringVar()

        self._scan_choice_map: dict[str, str] = {}
        self._plan_choice_map: dict[str, str] = {}
        self._execution_choice_map: dict[str, str] = {}
        self._rollback_choice_map: dict[str, str] = {}
        self._verify_choice_map: dict[str, str] = {}

        self._plan_scan_combo: ttk.Combobox
        self._apply_plan_combo: ttk.Combobox
        self._review_run_combo: ttk.Combobox
        self._rollback_execution_combo: ttk.Combobox
        self._rollback_run_combo: ttk.Combobox
        self._logs_execution_combo: ttk.Combobox
        self._logs_rollback_combo: ttk.Combobox
        self._logs_verify_combo: ttk.Combobox

        self._scan_tree: ttk.Treeview
        self._plan_tree: ttk.Treeview
        self._execution_tree: ttk.Treeview
        self._verify_tree: ttk.Treeview
        self._rollback_tree: ttk.Treeview
        self._plan_items_tree: ttk.Treeview
        self._operation_log_tree: ttk.Treeview
        self._rollback_log_tree: ttk.Treeview
        self._verify_log_tree: ttk.Treeview
        self._progress_bar: ttk.Progressbar
        self._filename_template_entry: ttk.Entry
        self._tree_sort_state: dict[str, tuple[str, bool]] = {}
        self._plan_items_paging = PagingState()
        self._operation_logs_paging = PagingState()
        self._rollback_logs_paging = PagingState()
        self._verify_logs_paging = PagingState()
        self._plan_items_page_var = tk.StringVar(value="")
        self._operation_logs_page_var = tk.StringVar(value="")
        self._rollback_logs_page_var = tk.StringVar(value="")
        self._verify_logs_page_var = tk.StringVar(value="")

        self._build_layout()
        self._load_config()
        self.refresh_all_views()
        self._root.after(150, self._poll_events)

    def run(self) -> None:
        self._root.mainloop()

    def _configure_fonts(self) -> None:
        available = set(tkfont.families(self._root))
        preferred_families = (
            "Noto Sans CJK JP",
            "Noto Sans JP",
            "IPAGothic",
            "TakaoGothic",
            "Yu Gothic UI",
            "Meiryo",
        )
        family = next((name for name in preferred_families if name in available), None)
        if family is None:
            return
        for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(font_name).configure(family=family)

    def _build_layout(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=1)
        self._build_header()
        self._build_tabs()

    def _build_header(self) -> None:
        frame = ttk.Frame(self._root, padding=12)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        progress_button = ttk.Button(frame, text="進行状況を確認", command=self._check_progress_on_demand)
        progress_button.grid(row=0, column=0, sticky="w")
        ToolTip(progress_button, "今動いている処理があれば、その時点の進み具合を表示します。自動更新はしません。")

        self._progress_bar = ttk.Progressbar(frame, mode="indeterminate", length=220)
        self._progress_bar.grid(row=0, column=1, sticky="w", padx=(12, 12))
        ttk.Label(frame, textvariable=self._status_var).grid(row=0, column=2, sticky="e")
        ttk.Label(frame, textvariable=self._result_var).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _build_tabs(self) -> None:
        notebook = ttk.Notebook(self._root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        intro_tab = ttk.Frame(notebook, padding=10)
        settings_tab = ttk.Frame(notebook, padding=10)
        naming_tab = ttk.Frame(notebook, padding=10)
        scan_tab = ttk.Frame(notebook, padding=10)
        plan_tab = ttk.Frame(notebook, padding=10)
        apply_tab = ttk.Frame(notebook, padding=10)
        rollback_tab = ttk.Frame(notebook, padding=10)
        logs_tab = ttk.Frame(notebook, padding=10)

        notebook.add(intro_tab, text="はじめに")
        notebook.add(settings_tab, text="設定")
        notebook.add(naming_tab, text="フォルダ名・ファイル名")
        notebook.add(scan_tab, text="1. 読み取り")
        notebook.add(plan_tab, text="2. 整理予定")
        notebook.add(apply_tab, text="3. 整理実行")
        notebook.add(rollback_tab, text="4. 元に戻す")
        notebook.add(logs_tab, text="ログと履歴整理")

        self._build_intro_tab(intro_tab)
        self._build_settings_tab(settings_tab)
        self._build_naming_tab(naming_tab)
        self._build_scan_tab(scan_tab)
        self._build_plan_tab(plan_tab)
        self._build_apply_tab(apply_tab)
        self._build_rollback_tab(rollback_tab)
        self._build_logs_tab(logs_tab)

    def _build_intro_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        guide = tk.Text(parent, wrap="word", relief="flat", height=18)
        guide.grid(row=0, column=0, sticky="nsew")
        guide.insert(
            "1.0",
            "\n".join(
                (
                    "このアプリは、音楽フォルダを安全に整理するためのツールです。",
                    "",
                    "使う順番",
                    "1. 設定: 元フォルダ、作業記録の保存先、表示タイムゾーンを決めます。",
                    "2. フォルダ名・ファイル名: 整理後の名前ルールを必要に応じて変えます。",
                    "3. 読み取り: 元フォルダを読み取って、整理対象を登録します。",
                    "4. 整理予定: 整理後にどこへ置かれるかを確認します。",
                    "5. 整理実行: まずテスト実行で確認し、問題なければ実際に整理します。",
                    "6. 結果確認: 整理後の状態が想定どおりか確認します。",
                    "7. 元に戻す: 必要な場合だけ使います。",
                    "8. ログと履歴整理: 詳細ログ確認と不要履歴の削除を行います。",
                    "",
                    "ボタンや一覧、入力欄にマウスを合わせると補足説明が出ます。",
                    "履歴は自動削除されません。不要になった履歴は GUI から手動削除してください。",
                )
            ),
        )
        guide.configure(state="disabled")

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        form = ttk.LabelFrame(parent, text="基本設定", padding=12)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        self._add_setting_row(
            form,
            row=0,
            label="Source",
            help_text="整理したい音楽ファイルが入っている元フォルダです。",
            variable=self._source_var,
            browse_command=lambda: self._pick_directory(self._source_var),
            tooltip="このフォルダを読み取って整理対象を作ります。",
        )
        self._add_setting_row(
            form,
            row=1,
            label="Database",
            help_text="作業記録の保存先です。履歴や整理予定をここへ保存します。",
            variable=self._db_var,
            browse_command=lambda: self._pick_file(self._db_var, save=True),
            tooltip="削除しない限り履歴が残ります。後からログ確認や履歴削除にも使います。",
        )
        self._add_setting_row(
            form,
            row=2,
            label="Library Root",
            help_text="整理後の置き場所の基準フォルダです。",
            variable=self._library_root_var,
            browse_command=lambda: self._pick_directory(self._library_root_var),
            tooltip="整理予定タブで使います。ここを変えると整理後の場所全体が変わります。",
        )

        ttk.Label(form, text="Time Zone", width=14).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        timezone_combo = ttk.Combobox(form, textvariable=self._timezone_var, values=self._COMMON_TIMEZONES)
        timezone_combo.grid(row=3, column=1, sticky="ew", pady=4)
        ToolTip(timezone_combo, "履歴一覧の開始時刻と終了時刻を表示するときのタイムゾーンです。既定は JST です。")

        save_button = ttk.Button(form, text="設定を保存", command=self._save_basic_settings)
        save_button.grid(row=4, column=1, sticky="w", pady=(12, 0))
        ToolTip(save_button, "Source / Database / Library Root / Time Zone を config/local.toml に保存します。")

    def _add_setting_row(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        help_text: str,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        tooltip: str,
    ) -> None:
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
        field = ttk.Frame(parent)
        field.grid(row=row, column=1, sticky="ew", pady=4)
        field.columnconfigure(0, weight=1)
        entry = ttk.Entry(field, textvariable=variable)
        entry.grid(row=0, column=0, sticky="ew")
        ToolTip(entry, tooltip)
        button = ttk.Button(field, text="選択", command=browse_command)
        button.grid(row=0, column=1, padx=(8, 0))
        ToolTip(button, help_text)
        ttk.Label(field, text=help_text, wraplength=920).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_naming_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        caption = ttk.Label(
            parent,
            text="整理後のフォルダ名・ファイル名の作り方を決めます。マウスを合わせると使えるタグ例が出ます。",
        )
        caption.grid(row=0, column=0, sticky="w")

        form = ttk.LabelFrame(parent, text="命名ルール", padding=12)
        form.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        form.columnconfigure(1, weight=1)

        self._add_naming_row(
            form,
            row=0,
            label="アーティストフォルダ",
            variable=self._artist_dir_template_var,
            help_text="例: {album_artist} / {artist}",
        )
        self._add_naming_row(
            form,
            row=1,
            label="アルバムフォルダ",
            variable=self._album_dir_template_var,
            help_text="例: {album} / [{year}_]{album}",
        )
        self._add_naming_row(
            form,
            row=2,
            label="ディスクフォルダ",
            variable=self._disc_dir_template_var,
            help_text="例: [{disc_no:02d}] / 空欄で作らない",
        )
        self._add_naming_row(
            form,
            row=3,
            label="ファイル名",
            variable=self._filename_template_var,
            help_text="例: [{track_no:02d}_]{title}{extension} / {track_no:03d}-{title}{extension}",
            entry_attr_name="_filename_template_entry",
        )

        keep_name_check = ttk.Checkbutton(
            form,
            text="元のファイル名をそのまま使う",
            variable=self._use_source_filename_var,
            command=self._update_filename_template_state,
        )
        keep_name_check.grid(row=4, column=1, sticky="w", pady=(8, 0))
        ToolTip(
            keep_name_check,
            "ON にすると、ファイル名は整理前と同じ名前を使います。ファイル名テンプレートは無視されます。",
        )

        help_label = ttk.Label(
            form,
            text="使えるタグ: {artist} {album_artist} {album} {title} {source_stem} {track_no} {disc_no} {extension}\n"
            "パディング例: {track_no:02d} / 条件付き表示: [{track_no:02d}_]",
            justify="left",
        )
        help_label.grid(row=5, column=1, sticky="w", pady=(8, 0))
        ToolTip(help_label, "[] で囲んだ部分は、中の値が空なら丸ごと表示されません。")

        save_button = ttk.Button(form, text="命名ルールを保存", command=self._save_naming_settings)
        save_button.grid(row=6, column=1, sticky="w", pady=(12, 0))
        ToolTip(save_button, "今の命名テンプレートを config/local.toml に保存します。")

    def _add_naming_row(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        help_text: str,
        entry_attr_name: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label, width=18).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        ToolTip(entry, help_text)
        if entry_attr_name is not None:
            setattr(self, entry_attr_name, entry)
        ttk.Label(parent, text=help_text).grid(row=row, column=2, sticky="w", padx=(8, 0))

    def _build_scan_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self._add_tab_caption(parent, "元フォルダを読み取って整理対象を登録します。先に『設定』タブの Source と Database を確認してください。")

        controls = ttk.Frame(parent, padding=(0, 8, 0, 8))
        controls.grid(row=1, column=0, sticky="ew")
        run_button = ttk.Button(controls, text="読み取りを実行", command=self._start_scan)
        run_button.pack(side="left")
        ToolTip(run_button, "Source の中身を読み取って、整理対象の一覧を作ります。最初に使うボタンです。")
        reload_button = ttk.Button(controls, text="一覧を更新", command=self._refresh_scan_views)
        reload_button.pack(side="left", padx=(8, 0))
        ToolTip(reload_button, "表示中の読み取り履歴を、今の記録ファイルから読み直します。")
        delete_button = ttk.Button(controls, text="選択した履歴を削除", command=self._delete_selected_scan_run)
        delete_button.pack(side="left", padx=(8, 0))
        ToolTip(delete_button, "選択した読み取り履歴を削除します。下流の履歴も一緒に消える場合があります。")

        self._scan_tree = self._create_run_tree(
            parent,
            row=2,
            spec=RunTreeSpec("読み取り履歴", "ファイル数", "警告数", "元フォルダ"),
        )
        self._scan_tree.bind("<<TreeviewSelect>>", self._on_scan_tree_selected)
        ToolTip(self._scan_tree, "ここで選んだ履歴は『整理予定』タブの候補にも反映されます。")

    def _build_plan_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=6)
        self._add_tab_caption(parent, "整理後にどこへ置かれるかを確認するタブです。ここで内容を見てから整理を実行してください。")

        controls = ttk.LabelFrame(parent, text="整理予定を作る", padding=10)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="読み取り結果").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._plan_scan_combo = ttk.Combobox(controls, textvariable=self._plan_scan_choice_var, state="readonly")
        self._plan_scan_combo.grid(row=0, column=1, sticky="ew")
        ToolTip(self._plan_scan_combo, "どの読み取り結果を元に整理予定を作るか選びます。")
        reload_button = ttk.Button(controls, text="候補を更新", command=self._refresh_scan_candidates)
        reload_button.grid(row=0, column=2, padx=(8, 0))
        ToolTip(reload_button, "読み取り履歴の候補を最新化します。")
        plan_button = ttk.Button(controls, text="整理予定を作成", command=self._start_plan)
        plan_button.grid(row=0, column=3, padx=(8, 0))
        ToolTip(plan_button, "今の命名ルールを使って整理後の場所を計算します。ファイルはまだ動きません。")
        export_button = ttk.Button(controls, text="TSV出力", command=self._export_plan_items_tsv)
        export_button.grid(row=0, column=4, padx=(8, 0))
        ToolTip(
            export_button,
            "選択中の整理予定を TSV で保存します。『注意・競合だけ表示』が ON の場合は、表示中の内容だけを出力します。",
        )
        warnings_only_check = ttk.Checkbutton(
            controls,
            text="注意・競合だけ表示",
            variable=self._plan_warnings_only_var,
            command=self._refresh_selected_plan_preview,
        )
        warnings_only_check.grid(row=1, column=1, sticky="w", pady=(8, 0))
        ToolTip(
            warnings_only_check,
            "ON にすると、注意がある項目と競合している項目だけを整理後一覧に表示します。",
        )

        self._plan_tree = self._create_run_tree(
            parent,
            row=2,
            spec=RunTreeSpec("整理予定の履歴", "予定件数", "注意件数", "元の読み取り結果"),
        )
        self._plan_tree.bind("<<TreeviewSelect>>", self._on_plan_tree_selected)

        items_panel = ttk.LabelFrame(parent, text="整理後一覧", padding=6)
        items_panel.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        items_panel.columnconfigure(0, weight=1)
        items_panel.rowconfigure(1, weight=1)
        pager = ttk.Frame(items_panel)
        pager.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        pager.columnconfigure(1, weight=1)
        ttk.Button(pager, text="前へ", command=lambda: self._change_plan_items_page(-1)).grid(row=0, column=0)
        ttk.Label(pager, textvariable=self._plan_items_page_var).grid(row=0, column=1, sticky="e", padx=8)
        ttk.Button(pager, text="次へ", command=lambda: self._change_plan_items_page(1)).grid(row=0, column=2)
        self._plan_items_tree = self._create_scrolled_tree(
            items_panel,
            row=1,
            columns=("source", "target", "action", "reason"),
            headings={
                "source": "元ファイル",
                "target": "整理後の場所",
                "action": "動作",
                "reason": "理由",
            },
            widths={
                "source": 520,
                "target": 620,
                "action": 110,
                "reason": 420,
            },
        )
        ToolTip(self._plan_items_tree, "この一覧が一番重要です。整理後にどこへ移るかをここで確認します。")

    def _build_apply_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        parent.rowconfigure(3, weight=1)
        self._add_tab_caption(parent, "整理予定を使って、実際に整理するタブです。先に『整理予定』タブで内容確認をしてください。")

        controls = ttk.LabelFrame(parent, text="整理を実行する", padding=10)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="整理予定").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._apply_plan_combo = ttk.Combobox(controls, textvariable=self._apply_plan_choice_var, state="readonly")
        self._apply_plan_combo.grid(row=0, column=1, sticky="ew")
        ToolTip(self._apply_plan_combo, "どの整理予定を使うか選びます。")
        reload_plan_button = ttk.Button(controls, text="候補を更新", command=self._refresh_plan_candidates)
        reload_plan_button.grid(row=0, column=2, padx=(8, 0))
        ToolTip(reload_plan_button, "整理予定の候補を最新化します。")
        test_button = ttk.Button(controls, text="整理を試す", command=lambda: self._start_apply(dry_run=True))
        test_button.grid(row=0, column=3, padx=(8, 0))
        ToolTip(test_button, "ファイルは動かさず、整理するとどうなるかだけを記録します。最初はこちらを推奨します。")
        apply_button = ttk.Button(controls, text="実際に整理する", command=lambda: self._start_apply(dry_run=False))
        apply_button.grid(row=0, column=4, padx=(8, 0))
        ToolTip(apply_button, "実際にファイルを移動またはコピーします。")

        ttk.Label(controls, text="確認したい整理結果").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self._review_run_combo = ttk.Combobox(controls, textvariable=self._review_run_choice_var, state="readonly")
        self._review_run_combo.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ToolTip(self._review_run_combo, "結果確認したい整理実行履歴を選びます。")
        reload_exec_button = ttk.Button(controls, text="候補を更新", command=self._refresh_execution_views)
        reload_exec_button.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        ToolTip(reload_exec_button, "整理実行履歴の候補を最新化します。")
        verify_button = ttk.Button(controls, text="結果を確認する", command=self._start_verify_execution)
        verify_button.grid(row=1, column=3, padx=(8, 0), pady=(8, 0))
        ToolTip(verify_button, "整理後の状態が予定どおりかを確認して、確認履歴を作ります。")

        self._execution_tree = self._create_run_tree(
            parent,
            row=2,
            spec=RunTreeSpec("整理実行履歴", "成功数", "失敗数", "実行種別"),
        )
        self._execution_tree.bind("<<TreeviewSelect>>", self._on_execution_tree_selected)
        self._verify_tree = self._create_run_tree(
            parent,
            row=3,
            spec=RunTreeSpec("結果確認履歴", "成功数", "失敗数", "確認対象"),
        )

    def _build_rollback_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self._add_tab_caption(parent, "整理結果を元に戻したいときだけ使います。通常は使いません。")

        controls = ttk.LabelFrame(parent, text="元に戻す", padding=10)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="戻したい整理結果").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._rollback_execution_combo = ttk.Combobox(
            controls, textvariable=self._rollback_execution_choice_var, state="readonly"
        )
        self._rollback_execution_combo.grid(row=0, column=1, sticky="ew")
        ToolTip(self._rollback_execution_combo, "元に戻したい整理実行履歴を選びます。")
        exec_reload = ttk.Button(controls, text="候補を更新", command=self._refresh_execution_candidates)
        exec_reload.grid(row=0, column=2, padx=(8, 0))
        ToolTip(exec_reload, "整理実行履歴の候補を最新化します。")
        test_button = ttk.Button(controls, text="元に戻す前に試す", command=lambda: self._start_rollback(dry_run=True))
        test_button.grid(row=0, column=3, padx=(8, 0))
        ToolTip(test_button, "実際には戻さず、戻した場合の処理結果だけ記録します。")
        rollback_button = ttk.Button(controls, text="実際に元に戻す", command=lambda: self._start_rollback(dry_run=False))
        rollback_button.grid(row=0, column=4, padx=(8, 0))
        ToolTip(rollback_button, "整理前の場所へファイルを戻します。")

        ttk.Label(controls, text="確認したい元に戻し結果").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self._rollback_run_combo = ttk.Combobox(controls, textvariable=self._rollback_run_choice_var, state="readonly")
        self._rollback_run_combo.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ToolTip(self._rollback_run_combo, "結果確認したい元に戻し履歴を選びます。")
        rollback_reload = ttk.Button(controls, text="候補を更新", command=self._refresh_rollback_views)
        rollback_reload.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        ToolTip(rollback_reload, "元に戻し履歴の候補を最新化します。")
        verify_button = ttk.Button(controls, text="結果を確認する", command=self._start_verify_rollback)
        verify_button.grid(row=1, column=3, padx=(8, 0), pady=(8, 0))
        ToolTip(verify_button, "元に戻した後の状態が想定どおりかを確認します。")

        self._rollback_tree = self._create_run_tree(
            parent,
            row=2,
            spec=RunTreeSpec("元に戻した履歴", "成功数", "失敗数", "実行種別"),
        )
        self._rollback_tree.bind("<<TreeviewSelect>>", self._on_rollback_tree_selected)

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self._add_tab_caption(parent, "詳細ログ確認と、不要履歴の削除を行うタブです。履歴は自動では消えません。")

        controls = ttk.LabelFrame(parent, text="ログ対象と履歴削除", padding=10)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(4, weight=1)
        controls.columnconfigure(7, weight=1)

        ttk.Label(controls, text="整理実行ログ").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._logs_execution_combo = ttk.Combobox(
            controls, textvariable=self._logs_execution_choice_var, state="readonly"
        )
        self._logs_execution_combo.grid(row=0, column=1, sticky="ew")
        self._logs_execution_combo.bind("<<ComboboxSelected>>", self._on_logs_execution_selected)
        ttk.Label(controls, text="元に戻しログ").grid(row=0, column=3, sticky="w", padx=(16, 8))
        self._logs_rollback_combo = ttk.Combobox(
            controls, textvariable=self._logs_rollback_choice_var, state="readonly"
        )
        self._logs_rollback_combo.grid(row=0, column=4, sticky="ew")
        self._logs_rollback_combo.bind("<<ComboboxSelected>>", self._on_logs_rollback_selected)
        ttk.Label(controls, text="確認ログ").grid(row=0, column=6, sticky="w", padx=(16, 8))
        self._logs_verify_combo = ttk.Combobox(controls, textvariable=self._logs_verify_choice_var, state="readonly")
        self._logs_verify_combo.grid(row=0, column=7, sticky="ew")
        self._logs_verify_combo.bind("<<ComboboxSelected>>", self._on_logs_verify_selected)

        refresh_button = ttk.Button(controls, text="候補を更新", command=self._refresh_logs_candidates)
        refresh_button.grid(row=0, column=8, padx=(12, 0))
        ToolTip(refresh_button, "ドロップダウンに出る候補を最新化します。")
        show_button = ttk.Button(controls, text="ログ表示を更新", command=self._refresh_log_views)
        show_button.grid(row=0, column=9, padx=(8, 0))
        ToolTip(show_button, "今選ばれている候補のログを下の一覧へ読み込みます。")
        delete_verify_button = ttk.Button(controls, text="選択中の確認履歴を削除", command=self._delete_selected_verify_run)
        delete_verify_button.grid(row=0, column=10, padx=(8, 0))
        ToolTip(delete_verify_button, "選んでいる確認履歴と、その詳細ログを削除します。")

        logs_notebook = ttk.Notebook(parent)
        logs_notebook.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        execution_tab = ttk.Frame(logs_notebook, padding=6)
        rollback_tab = ttk.Frame(logs_notebook, padding=6)
        verify_tab = ttk.Frame(logs_notebook, padding=6)
        logs_notebook.add(execution_tab, text="整理実行ログ")
        logs_notebook.add(rollback_tab, text="元に戻しログ")
        logs_notebook.add(verify_tab, text="確認ログ")

        self._operation_log_tree = self._create_paged_log_tree(
            execution_tab,
            page_var=self._operation_logs_page_var,
            previous_command=lambda: self._change_operation_logs_page(-1),
            next_command=lambda: self._change_operation_logs_page(1),
        )
        self._rollback_log_tree = self._create_paged_log_tree(
            rollback_tab,
            page_var=self._rollback_logs_page_var,
            previous_command=lambda: self._change_rollback_logs_page(-1),
            next_command=lambda: self._change_rollback_logs_page(1),
        )
        self._verify_log_tree = self._create_paged_tree(
            verify_tab,
            page_var=self._verify_logs_page_var,
            previous_command=lambda: self._change_verify_logs_page(-1),
            next_command=lambda: self._change_verify_logs_page(1),
            columns=("seq", "subject", "counterpart", "result", "error", "expected", "actual"),
            headings={
                "seq": "#",
                "subject": "対象",
                "counterpart": "比較先",
                "result": "結果",
                "error": "エラー",
                "expected": "期待状態",
                "actual": "実際の状態",
            },
            widths={
                "seq": 70,
                "subject": 360,
                "counterpart": 360,
                "result": 100,
                "error": 160,
                "expected": 360,
                "actual": 360,
            },
        )

    def _add_tab_caption(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text).grid(row=0, column=0, sticky="w")

    def _create_run_tree(self, parent: ttk.Frame, *, row: int, spec: RunTreeSpec) -> ttk.Treeview:
        panel = ttk.LabelFrame(parent, text=spec.title, padding=6)
        panel.grid(row=row, column=0, sticky="nsew", pady=(0, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        return self._create_scrolled_tree(
            panel,
            columns=("id", "status", "started", "finished", "duration", "primary", "secondary", "detail"),
            headings={
                "id": "Run ID",
                "status": "状態",
                "started": "開始時刻",
                "finished": "終了時刻",
                "duration": "処理時間",
                "primary": spec.primary_heading,
                "secondary": spec.secondary_heading,
                "detail": spec.detail_heading,
            },
            widths={
                "id": 240,
                "status": 90,
                "started": 210,
                "finished": 210,
                "duration": 120,
                "primary": 110,
                "secondary": 110,
                "detail": 420,
            },
        )

    def _create_log_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        return self._create_scrolled_tree(
            parent,
            columns=("seq", "source", "target", "action", "result", "error"),
            headings={
                "seq": "#",
                "source": "元",
                "target": "先",
                "action": "処理内容",
                "result": "結果",
                "error": "エラー",
            },
            widths={
                "seq": 70,
                "source": 430,
                "target": 430,
                "action": 120,
                "result": 100,
                "error": 180,
            },
        )

    def _create_paged_log_tree(
        self,
        parent: ttk.Frame,
        *,
        page_var: tk.StringVar,
        previous_command: Callable[[], None],
        next_command: Callable[[], None],
    ) -> ttk.Treeview:
        return self._create_paged_tree(
            parent,
            page_var=page_var,
            previous_command=previous_command,
            next_command=next_command,
            columns=("seq", "source", "target", "action", "result", "error"),
            headings={
                "seq": "#",
                "source": "元",
                "target": "先",
                "action": "処理内容",
                "result": "結果",
                "error": "エラー",
            },
            widths={
                "seq": 70,
                "source": 430,
                "target": 430,
                "action": 120,
                "result": 100,
                "error": 180,
            },
        )

    def _create_paged_tree(
        self,
        parent: ttk.Frame,
        *,
        page_var: tk.StringVar,
        previous_command: Callable[[], None],
        next_command: Callable[[], None],
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
    ) -> ttk.Treeview:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        pager = ttk.Frame(parent)
        pager.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        pager.columnconfigure(1, weight=1)
        ttk.Button(pager, text="前へ", command=previous_command).grid(row=0, column=0)
        ttk.Label(pager, textvariable=page_var).grid(row=0, column=1, sticky="e", padx=8)
        ttk.Button(pager, text="次へ", command=next_command).grid(row=0, column=2)
        return self._create_scrolled_tree(
            parent,
            row=1,
            columns=columns,
            headings=headings,
            widths=widths,
        )

    def _create_scrolled_tree(
        self,
        parent: ttk.Frame,
        *,
        row: int = 0,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
    ) -> ttk.Treeview:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        for key in columns:
            tree.heading(key, text=headings[key], command=lambda column=key, current_tree=tree: self._sort_tree(current_tree, column))
            tree.column(key, width=widths.get(key, 140), anchor="w")
        self._attach_tree_scrollbars(parent, tree, row=row)
        return tree

    def _attach_tree_scrollbars(self, parent: ttk.Frame, tree: ttk.Treeview, *, row: int) -> None:
        tree.grid(row=row, column=0, sticky="nsew")
        y_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        y_scrollbar.grid(row=row, column=1, sticky="ns")
        x_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        x_scrollbar.grid(row=row + 1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

    def _load_config(self) -> None:
        config = load_config(self._default_config_path)
        scan_config = get_command_config(config, "scan")
        plan_config = get_command_config(config, "plan")
        display_config = get_command_config(config, "display")
        naming_config = get_command_config(config, "naming")

        self._source_var.set(str(scan_config.get("source", "")))
        self._db_var.set(str(scan_config.get("db", plan_config.get("db", ""))))
        self._library_root_var.set(str(plan_config.get("library_root", "")))
        self._timezone_var.set(str(display_config.get("timezone", self._DEFAULT_TIMEZONE)))
        self._artist_dir_template_var.set(str(naming_config.get("artist_dir_template", "{album_artist}")))
        self._album_dir_template_var.set(str(naming_config.get("album_dir_template", "{album}")))
        self._disc_dir_template_var.set(str(naming_config.get("disc_dir_template", "[{disc_no:02d}]")))
        self._filename_template_var.set(
            str(naming_config.get("filename_template", "[{track_no:02d}_]{title}{extension}"))
        )
        self._use_source_filename_var.set(bool(naming_config.get("use_source_filename", False)))
        self._update_filename_template_state()

    def _save_basic_settings(self) -> None:
        config = load_config(self._default_config_path)
        config["scan"] = {
            **get_command_config(config, "scan"),
            "source": self._source_var.get().strip(),
            "db": self._db_var.get().strip(),
        }
        config["plan"] = {
            **get_command_config(config, "plan"),
            "db": self._db_var.get().strip(),
            "library_root": self._library_root_var.get().strip(),
        }
        config["display"] = {
            **get_command_config(config, "display"),
            "timezone": self._timezone_var.get().strip() or self._DEFAULT_TIMEZONE,
        }
        save_config(self._default_config_path, config)
        self._result_var.set(f"設定を保存しました: {self._default_config_path}")

    def _save_naming_settings(self) -> None:
        config = load_config(self._default_config_path)
        config["naming"] = {
            **get_command_config(config, "naming"),
            "artist_dir_template": self._artist_dir_template_var.get(),
            "album_dir_template": self._album_dir_template_var.get(),
            "disc_dir_template": self._disc_dir_template_var.get(),
            "filename_template": self._filename_template_var.get(),
            "use_source_filename": self._use_source_filename_var.get(),
        }
        save_config(self._default_config_path, config)
        self._result_var.set(f"命名ルールを保存しました: {self._default_config_path}")

    def _update_filename_template_state(self) -> None:
        state = "disabled" if self._use_source_filename_var.get() else "normal"
        self._filename_template_entry.configure(state=state)

    def refresh_all_views(self) -> None:
        self._refresh_scan_views()
        self._refresh_plan_views()
        self._refresh_execution_views()
        self._refresh_rollback_views()
        self._refresh_verify_views()
        self._refresh_log_views()

    def _refresh_scan_views(self) -> None:
        db_path = self._db_path()
        self._clear_tree(self._scan_tree)
        if db_path is None:
            self._set_combobox_options(self._plan_scan_combo, self._plan_scan_choice_var, {})
            return
        rows = GuiQueryService(db_path).list_scan_runs()
        self._populate_run_tree(self._scan_tree, rows)
        self._scan_choice_map = self._format_choice_map(rows, self._format_scan_choice)
        self._set_combobox_options(self._plan_scan_combo, self._plan_scan_choice_var, self._scan_choice_map)

    def _refresh_scan_candidates(self) -> None:
        self._refresh_scan_views()

    def _refresh_plan_views(self) -> None:
        db_path = self._db_path()
        self._clear_tree(self._plan_tree)
        self._clear_tree(self._plan_items_tree)
        if db_path is None:
            self._plan_items_paging = PagingState()
            self._plan_items_page_var.set("")
            self._set_combobox_options(self._apply_plan_combo, self._apply_plan_choice_var, {})
            return
        rows = GuiQueryService(db_path).list_plan_runs()
        self._populate_run_tree(self._plan_tree, rows)
        self._plan_choice_map = self._format_choice_map(rows, self._format_plan_choice)
        self._set_combobox_options(self._apply_plan_combo, self._apply_plan_choice_var, self._plan_choice_map)
        selected_plan_id = self._get_selected_tree_run_id(self._plan_tree)
        if selected_plan_id:
            self._refresh_plan_preview(selected_plan_id)

    def _refresh_plan_candidates(self) -> None:
        self._refresh_plan_views()

    def _refresh_execution_views(self) -> None:
        db_path = self._db_path()
        self._clear_tree(self._execution_tree)
        if db_path is None:
            self._set_combobox_options(self._review_run_combo, self._review_run_choice_var, {})
            self._set_combobox_options(self._rollback_execution_combo, self._rollback_execution_choice_var, {})
            self._set_combobox_options(self._logs_execution_combo, self._logs_execution_choice_var, {})
            return
        rows = GuiQueryService(db_path).list_execution_runs()
        self._populate_run_tree(self._execution_tree, rows)
        self._execution_choice_map = self._format_choice_map(rows, self._format_execution_choice)
        self._set_combobox_options(self._review_run_combo, self._review_run_choice_var, self._execution_choice_map)
        self._set_combobox_options(
            self._rollback_execution_combo, self._rollback_execution_choice_var, self._execution_choice_map
        )
        self._set_combobox_options(self._logs_execution_combo, self._logs_execution_choice_var, self._execution_choice_map)

    def _refresh_execution_candidates(self) -> None:
        self._refresh_execution_views()

    def _refresh_rollback_views(self) -> None:
        db_path = self._db_path()
        self._clear_tree(self._rollback_tree)
        if db_path is None:
            self._set_combobox_options(self._rollback_run_combo, self._rollback_run_choice_var, {})
            self._set_combobox_options(self._logs_rollback_combo, self._logs_rollback_choice_var, {})
            return
        rows = GuiQueryService(db_path).list_rollback_runs()
        self._populate_run_tree(self._rollback_tree, rows)
        self._rollback_choice_map = self._format_choice_map(rows, self._format_rollback_choice)
        self._set_combobox_options(self._rollback_run_combo, self._rollback_run_choice_var, self._rollback_choice_map)
        self._set_combobox_options(self._logs_rollback_combo, self._logs_rollback_choice_var, self._rollback_choice_map)

    def _refresh_verify_views(self) -> None:
        db_path = self._db_path()
        self._clear_tree(self._verify_tree)
        if db_path is None:
            self._set_combobox_options(self._logs_verify_combo, self._logs_verify_choice_var, {})
            return
        rows = GuiQueryService(db_path).list_verify_runs()
        self._populate_run_tree(self._verify_tree, rows)
        self._verify_choice_map = self._format_choice_map(rows, self._format_verify_choice)
        self._set_combobox_options(self._logs_verify_combo, self._logs_verify_choice_var, self._verify_choice_map)

    def _refresh_logs_candidates(self) -> None:
        self._refresh_execution_views()
        self._refresh_rollback_views()
        self._refresh_verify_views()

    def _populate_run_tree(self, tree: ttk.Treeview, rows: list[RunRow]) -> None:
        self._clear_tree(tree)
        for row in rows:
            tree.insert(
                "",
                "end",
                iid=row.run_id,
                values=(
                    row.run_id,
                    self._render_status(row.status),
                    self._format_iso_datetime(row.started_at),
                    self._format_iso_datetime(row.finished_at),
                    self._format_duration(row.started_at, row.finished_at),
                    row.primary_count,
                    row.secondary_count,
                    row.detail,
                ),
            )

    def _render_status(self, status: str) -> str:
        return {
            "running": "実行中",
            "completed": "完了",
            "partial": "一部失敗",
        }.get(status, status)

    def _format_iso_datetime(self, value: str | None) -> str:
        if not value:
            return ""
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        try:
            timezone = ZoneInfo(self._timezone_var.get() or self._DEFAULT_TIMEZONE)
        except ZoneInfoNotFoundError:
            timezone = ZoneInfo(self._DEFAULT_TIMEZONE)
        return parsed.astimezone(timezone).isoformat(timespec="seconds")

    def _format_duration(self, started_at: str, finished_at: str | None) -> str:
        if not finished_at:
            return ""
        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
        except ValueError:
            return ""
        duration = finished - started
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_choice_map(self, rows: list[RunRow], formatter: Callable[[RunRow], str]) -> dict[str, str]:
        return {formatter(row): row.run_id for row in rows}

    def _set_combobox_options(self, combo: ttk.Combobox, variable: tk.StringVar, mapping: dict[str, str]) -> None:
        labels = list(mapping.keys())
        combo["values"] = labels
        if not labels:
            variable.set("")
            return
        if variable.get() in mapping:
            return
        variable.set(labels[0])

    def _refresh_plan_preview(self, plan_run_id: str) -> None:
        db_path = self._db_path()
        self._clear_tree(self._plan_items_tree)
        if db_path is None or not plan_run_id:
            self._plan_items_paging = PagingState()
            self._plan_items_page_var.set("")
            return
        query_service = GuiQueryService(db_path)
        total = query_service.count_plan_items(
            plan_run_id=plan_run_id,
            warnings_only=self._plan_warnings_only_var.get(),
        )
        self._plan_items_paging.total = total
        self._plan_items_paging.offset = min(self._plan_items_paging.offset, self._page_start(total))
        rows = self._list_visible_plan_items(plan_run_id, query_service=query_service)
        for row in rows:
            self._plan_items_tree.insert(
                "",
                "end",
                values=(
                    row.source_path,
                    row.target_path or "",
                    self._render_plan_action(row.action),
                    self._render_plan_reason(row),
                ),
            )
        self._plan_items_page_var.set(self._format_page_text(self._plan_items_paging))

    def _refresh_selected_plan_preview(self) -> None:
        self._plan_items_paging.offset = 0
        self._refresh_plan_preview(self._get_selected_tree_run_id(self._plan_tree))

    def _list_visible_plan_items(
        self,
        plan_run_id: str,
        *,
        query_service: GuiQueryService | None = None,
        paged: bool = True,
    ) -> list[PlanItemRow]:
        db_path = self._db_path()
        if db_path is None or not plan_run_id:
            return []
        service = query_service or GuiQueryService(db_path)
        if paged:
            rows = service.list_plan_items(
                plan_run_id=plan_run_id,
                warnings_only=self._plan_warnings_only_var.get(),
                limit=self._PAGE_SIZE,
                offset=self._plan_items_paging.offset,
            )
        else:
            rows = service.list_plan_items(
                plan_run_id=plan_run_id,
                warnings_only=self._plan_warnings_only_var.get(),
            )
        return rows

    def _export_plan_items_tsv(self) -> None:
        plan_run_id = self._get_selected_tree_run_id(self._plan_tree)
        if not plan_run_id:
            self._show_info("Selection Required", "TSV を出力したい整理予定を一覧から選んでください。")
            return
        rows = self._list_visible_plan_items(plan_run_id, paged=False)
        if not rows:
            self._show_info("No Data", "出力できる整理予定がありません。表示条件を見直してください。")
            return
        selected = filedialog.asksaveasfilename(
            initialfile=f"plan_items_{plan_run_id[:8]}.tsv",
            defaultextension=".tsv",
            filetypes=[("TSV", "*.tsv"), ("All files", "*.*")],
        )
        if not selected:
            return
        with Path(selected).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(("元ファイル", "整理後の場所", "動作", "競合", "注意", "理由"))
            for row in rows:
                writer.writerow(
                    (
                        row.source_path,
                        row.target_path or "",
                        self._render_plan_action(row.action),
                        self._render_reason(row.conflict_status),
                        self._render_reason(row.risk_status),
                        self._render_plan_reason(row),
                    )
                )
        self._result_var.set(f"整理後一覧を TSV 出力しました: {selected}")

    def _refresh_log_views(self) -> None:
        db_path = self._db_path()
        for tree in (self._operation_log_tree, self._rollback_log_tree, self._verify_log_tree):
            self._clear_tree(tree)
        if db_path is None:
            self._operation_logs_paging = PagingState()
            self._rollback_logs_paging = PagingState()
            self._verify_logs_paging = PagingState()
            self._operation_logs_page_var.set("")
            self._rollback_logs_page_var.set("")
            self._verify_logs_page_var.set("")
            return
        query_service = GuiQueryService(db_path)
        execution_run_id = self._selected_id_from_choice(self._logs_execution_choice_var, self._execution_choice_map)
        if execution_run_id:
            total = query_service.count_operation_logs(execution_run_id=execution_run_id)
            self._operation_logs_paging.total = total
            self._operation_logs_paging.offset = min(self._operation_logs_paging.offset, self._page_start(total))
            for row in query_service.list_operation_logs(
                execution_run_id=execution_run_id,
                limit=self._PAGE_SIZE,
                offset=self._operation_logs_paging.offset,
            ):
                self._operation_log_tree.insert(
                    "",
                    "end",
                    values=(
                        row.sequence_no,
                        row.source_path,
                        row.target_path,
                        self._render_operation_action(row.action),
                        self._render_status_word(row.result),
                        self._render_reason(row.error_message or ""),
                    ),
                )
            self._operation_logs_page_var.set(self._format_page_text(self._operation_logs_paging))
        else:
            self._operation_logs_paging = PagingState()
            self._operation_logs_page_var.set("")
        rollback_run_id = self._selected_id_from_choice(self._logs_rollback_choice_var, self._rollback_choice_map)
        if rollback_run_id:
            total = query_service.count_rollback_logs(rollback_run_id=rollback_run_id)
            self._rollback_logs_paging.total = total
            self._rollback_logs_paging.offset = min(self._rollback_logs_paging.offset, self._page_start(total))
            for row in query_service.list_rollback_logs(
                rollback_run_id=rollback_run_id,
                limit=self._PAGE_SIZE,
                offset=self._rollback_logs_paging.offset,
            ):
                self._rollback_log_tree.insert(
                    "",
                    "end",
                    values=(
                        row.sequence_no,
                        row.source_path,
                        row.target_path,
                        self._render_operation_action(row.action),
                        self._render_status_word(row.result),
                        self._render_reason(row.error_message or ""),
                    ),
                )
            self._rollback_logs_page_var.set(self._format_page_text(self._rollback_logs_paging))
        else:
            self._rollback_logs_paging = PagingState()
            self._rollback_logs_page_var.set("")
        verify_run_id = self._selected_id_from_choice(self._logs_verify_choice_var, self._verify_choice_map)
        if verify_run_id:
            total = query_service.count_verify_logs(verify_run_id=verify_run_id)
            self._verify_logs_paging.total = total
            self._verify_logs_paging.offset = min(self._verify_logs_paging.offset, self._page_start(total))
            for row in query_service.list_verify_logs(
                verify_run_id=verify_run_id,
                limit=self._PAGE_SIZE,
                offset=self._verify_logs_paging.offset,
            ):
                self._verify_log_tree.insert(
                    "",
                    "end",
                    values=(
                        row.sequence_no,
                        row.subject_path,
                        row.counterpart_path or "",
                        self._render_status_word(row.result),
                        self._render_reason(row.error_message or ""),
                        row.expected_state,
                        row.actual_state,
                    ),
                )
            self._verify_logs_page_var.set(self._format_page_text(self._verify_logs_paging))
        else:
            self._verify_logs_paging = PagingState()
            self._verify_logs_page_var.set("")

    def _selected_id_from_choice(self, variable: tk.StringVar, mapping: dict[str, str]) -> str:
        return mapping.get(variable.get(), "")

    def _on_scan_tree_selected(self, _: object) -> None:
        self._sync_choice_from_tree(self._scan_tree, self._scan_choice_map, self._plan_scan_choice_var)

    def _on_plan_tree_selected(self, _: object) -> None:
        run_id = self._get_selected_tree_run_id(self._plan_tree)
        if not run_id:
            return
        self._plan_items_paging.offset = 0
        self._sync_choice_from_tree(self._plan_tree, self._plan_choice_map, self._apply_plan_choice_var)
        self._refresh_plan_preview(run_id)

    def _on_execution_tree_selected(self, _: object) -> None:
        run_id = self._get_selected_tree_run_id(self._execution_tree)
        if not run_id:
            return
        self._operation_logs_paging.offset = 0
        label = self._find_label_by_run_id(self._execution_choice_map, run_id)
        if label:
            self._review_run_choice_var.set(label)
            self._rollback_execution_choice_var.set(label)
            self._logs_execution_choice_var.set(label)

    def _on_rollback_tree_selected(self, _: object) -> None:
        self._rollback_logs_paging.offset = 0
        self._sync_choice_from_tree(self._rollback_tree, self._rollback_choice_map, self._rollback_run_choice_var)

    def _on_logs_execution_selected(self, _: object) -> None:
        self._operation_logs_paging.offset = 0

    def _on_logs_rollback_selected(self, _: object) -> None:
        self._rollback_logs_paging.offset = 0

    def _on_logs_verify_selected(self, _: object) -> None:
        self._verify_logs_paging.offset = 0

    def _change_plan_items_page(self, direction: int) -> None:
        if not self._advance_page(self._plan_items_paging, direction):
            return
        self._refresh_plan_preview(self._get_selected_tree_run_id(self._plan_tree))

    def _change_operation_logs_page(self, direction: int) -> None:
        if not self._advance_page(self._operation_logs_paging, direction):
            return
        self._refresh_log_views()

    def _change_rollback_logs_page(self, direction: int) -> None:
        if not self._advance_page(self._rollback_logs_paging, direction):
            return
        self._refresh_log_views()

    def _change_verify_logs_page(self, direction: int) -> None:
        if not self._advance_page(self._verify_logs_paging, direction):
            return
        self._refresh_log_views()

    def _sync_choice_from_tree(self, tree: ttk.Treeview, mapping: dict[str, str], variable: tk.StringVar) -> None:
        run_id = self._get_selected_tree_run_id(tree)
        if not run_id:
            return
        label = self._find_label_by_run_id(mapping, run_id)
        if label:
            variable.set(label)

    def _get_selected_tree_run_id(self, tree: ttk.Treeview) -> str:
        selection = tree.selection()
        return selection[0] if selection else ""

    def _start_scan(self) -> None:
        source_root = self._required_path(self._source_var.get(), "Source")
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        if source_root is None or db_path is None:
            return
        self._run_in_background(
            "読み取り",
            lambda: ScanService().execute(ScanRequest(source_root=source_root, db_path=db_path)),
        )

    def _start_plan(self) -> None:
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        library_root = self._required_path(self._library_root_var.get(), "Library Root", must_exist=False)
        scan_run_id = self._selected_id_from_choice(self._plan_scan_choice_var, self._scan_choice_map)
        if db_path is None or library_root is None:
            return
        if not scan_run_id:
            self._show_error("Selection Required", "このタブ内のドロップダウンで、整理予定を作る元の読み取り結果を選んでください。")
            return
        organization_rules = OrganizationRules(
            artist_dir_template=self._artist_dir_template_var.get(),
            album_dir_template=self._album_dir_template_var.get(),
            disc_dir_template=self._disc_dir_template_var.get(),
            filename_template="{source_stem}{extension}"
            if self._use_source_filename_var.get()
            else self._filename_template_var.get(),
        )
        self._run_in_background(
            "整理予定作成",
            lambda: PlanService(organization_rules=organization_rules).execute(
                PlanRequest(db_path=db_path, scan_run_id=scan_run_id, library_root=library_root)
            ),
        )

    def _start_apply(self, *, dry_run: bool) -> None:
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        plan_run_id = self._selected_id_from_choice(self._apply_plan_choice_var, self._plan_choice_map)
        if db_path is None:
            return
        if not plan_run_id:
            self._show_error("Selection Required", "このタブ内のドロップダウンで、実行したい整理予定を選んでください。")
            return
        stage_name = "整理テスト実行" if dry_run else "整理実行"
        self._run_in_background(
            stage_name,
            lambda: ApplyService().execute(ApplyRequest(db_path=db_path, plan_run_id=plan_run_id, dry_run=dry_run)),
        )

    def _start_verify_execution(self) -> None:
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        execution_run_id = self._selected_id_from_choice(self._review_run_choice_var, self._execution_choice_map)
        if db_path is None:
            return
        if not execution_run_id:
            self._show_error("Selection Required", "このタブ内のドロップダウンで、確認したい整理実行履歴を選んでください。")
            return
        self._run_in_background(
            "整理結果確認",
            lambda: VerifyService().execute(VerifyRequest(db_path=db_path, execution_run_id=execution_run_id)),
        )

    def _start_rollback(self, *, dry_run: bool) -> None:
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        execution_run_id = self._selected_id_from_choice(self._rollback_execution_choice_var, self._execution_choice_map)
        if db_path is None:
            return
        if not execution_run_id:
            self._show_error("Selection Required", "このタブ内のドロップダウンで、元に戻したい整理実行履歴を選んでください。")
            return
        stage_name = "元に戻す前の確認" if dry_run else "元に戻す"
        self._run_in_background(
            stage_name,
            lambda: RollbackService().execute(
                RollbackRequest(db_path=db_path, execution_run_id=execution_run_id, dry_run=dry_run)
            ),
        )

    def _start_verify_rollback(self) -> None:
        db_path = self._required_path(self._db_var.get(), "Database", must_exist=False)
        rollback_run_id = self._selected_id_from_choice(self._rollback_run_choice_var, self._rollback_choice_map)
        if db_path is None:
            return
        if not rollback_run_id:
            self._show_error("Selection Required", "このタブ内のドロップダウンで、確認したい元に戻し履歴を選んでください。")
            return
        self._run_in_background(
            "元に戻した結果確認",
            lambda: VerifyService().execute(VerifyRequest(db_path=db_path, rollback_run_id=rollback_run_id)),
        )

    def _delete_selected_scan_run(self) -> None:
        self._delete_run_from_tree(self._scan_tree, "読み取り履歴", lambda service, run_id: service.delete_scan_run(scan_run_id=run_id))

    def _delete_selected_plan_run(self) -> None:
        self._delete_run_from_tree(self._plan_tree, "整理予定履歴", lambda service, run_id: service.delete_plan_run(plan_run_id=run_id))

    def _delete_selected_execution_run(self) -> None:
        self._delete_run_from_tree(
            self._execution_tree,
            "整理実行履歴",
            lambda service, run_id: service.delete_execution_run(execution_run_id=run_id),
        )

    def _delete_selected_rollback_run(self) -> None:
        self._delete_run_from_tree(
            self._rollback_tree,
            "元に戻し履歴",
            lambda service, run_id: service.delete_rollback_run(rollback_run_id=run_id),
        )

    def _delete_selected_verify_run(self) -> None:
        run_id = self._selected_id_from_choice(self._logs_verify_choice_var, self._verify_choice_map)
        if not run_id:
            self._show_info("Selection Required", "削除したい確認履歴をドロップダウンで選んでください。")
            return
        if not self._confirm_delete("確認履歴", run_id):
            return
        db_path = self._db_path()
        if db_path is None:
            return
        self._run_in_background(
            "確認履歴削除",
            lambda: self._delete_verify_run_in_background(db_path=db_path, run_id=run_id),
        )

    def _delete_run_from_tree(
        self,
        tree: ttk.Treeview,
        label: str,
        deleter: Callable[[GuiQueryService, str], None],
    ) -> None:
        run_id = self._get_selected_tree_run_id(tree)
        if not run_id:
            self._show_info("Selection Required", f"削除したい{label}を一覧から選んでください。")
            return
        if not self._confirm_delete(label, run_id):
            return
        db_path = self._db_path()
        if db_path is None:
            return
        self._run_in_background(
            f"{label}削除",
            lambda: self._delete_run_in_background(db_path=db_path, label=label, run_id=run_id, deleter=deleter),
        )

    def _confirm_delete(self, label: str, run_id: str) -> bool:
        return messagebox.askyesno(
            "Confirm Delete",
            f"{label} {run_id} を削除します。\n関連する下位履歴も一緒に削除される場合があります。\n続けますか？",
        )

    def _check_progress_on_demand(self) -> None:
        db_path = self._db_path()
        if db_path is None:
            self._status_var.set("Database が未設定です")
            return
        progress = GuiQueryService(db_path).find_active_progress()
        if progress is None:
            self._status_var.set("現在進行中の処理はありません")
            return
        if progress.total is None:
            text = f"{progress.stage} 実行中: {progress.processed}件"
        else:
            text = f"{progress.stage} 実行中: {progress.processed}/{progress.total}"
        self._status_var.set(f"{text} [{progress.run_id[:8]}]")

    def _run_in_background(self, stage: str, action: Callable[[], object]) -> None:
        if self._running:
            self._show_info("Busy", "別の処理がまだ実行中です。完了してから次を実行してください。")
            return
        self._running = True
        self._status_var.set(f"{stage} を開始しました")
        self._result_var.set(f"{stage} を実行中です。必要なら上の『進行状況を確認』を押してください。")
        self._progress_bar.start(12)

        def worker() -> None:
            try:
                result = action()
            except Exception as error:
                self._events.put(("error", (stage, str(error))))
                return
            self._events.put(("result", (stage, result)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event_type, payload = self._events.get_nowait()
                if event_type == "error":
                    stage, message = payload  # type: ignore[misc]
                    self._running = False
                    self._progress_bar.stop()
                    self._status_var.set(f"{stage} に失敗しました")
                    self._result_var.set(message)
                    self._show_error("Run Failed", message)
                    self.refresh_all_views()
                elif event_type == "result":
                    stage, result = payload  # type: ignore[misc]
                    self._running = False
                    self._progress_bar.stop()
                    self._status_var.set(f"{stage} が完了しました")
                    if isinstance(result, DeleteResult):
                        self._result_var.set(f"{result.label} {result.run_id[:8]} を削除しました")
                        self._refresh_views_after_delete(result.label)
                    else:
                        self._result_var.set(self._format_result(stage, result))
                        self.refresh_all_views()
                        self._sync_choices_after_result(stage, result)
        except queue.Empty:
            pass
        self._root.after(150, self._poll_events)

    def _delete_run_in_background(
        self,
        *,
        db_path: Path,
        label: str,
        run_id: str,
        deleter: Callable[[GuiQueryService, str], None],
    ) -> DeleteResult:
        deleter(GuiQueryService(db_path), run_id)
        return DeleteResult(label=label, run_id=run_id)

    def _delete_verify_run_in_background(self, *, db_path: Path, run_id: str) -> DeleteResult:
        GuiQueryService(db_path).delete_verify_run(verify_run_id=run_id)
        return DeleteResult(label="確認履歴", run_id=run_id)

    def _refresh_views_after_delete(self, label: str) -> None:
        if label == "読み取り履歴":
            self._refresh_scan_views()
            self._refresh_plan_views()
            self._refresh_execution_views()
            self._refresh_rollback_views()
            self._refresh_verify_views()
            self._refresh_log_views()
            return
        if label == "整理予定履歴":
            self._refresh_plan_views()
            self._refresh_execution_views()
            self._refresh_rollback_views()
            self._refresh_verify_views()
            self._refresh_log_views()
            return
        if label == "整理実行履歴":
            self._refresh_execution_views()
            self._refresh_rollback_views()
            self._refresh_verify_views()
            self._refresh_log_views()
            return
        if label == "元に戻し履歴":
            self._refresh_rollback_views()
            self._refresh_verify_views()
            self._refresh_log_views()
            return
        if label == "確認履歴":
            self._refresh_verify_views()
            self._refresh_log_views()

    def _sync_choices_after_result(self, stage: str, result: object) -> None:
        scan_run_id = getattr(result, "scan_run_id", None)
        if isinstance(scan_run_id, str):
            self._set_choice_to_run_id(self._plan_scan_choice_var, self._scan_choice_map, scan_run_id)
        plan_run_id = getattr(result, "plan_run_id", None)
        if isinstance(plan_run_id, str):
            self._set_choice_to_run_id(self._apply_plan_choice_var, self._plan_choice_map, plan_run_id)
            self._refresh_plan_preview(plan_run_id)
        execution_run_id = getattr(result, "execution_run_id", None)
        if isinstance(execution_run_id, str):
            self._set_choice_to_run_id(self._review_run_choice_var, self._execution_choice_map, execution_run_id)
            self._set_choice_to_run_id(self._rollback_execution_choice_var, self._execution_choice_map, execution_run_id)
            self._set_choice_to_run_id(self._logs_execution_choice_var, self._execution_choice_map, execution_run_id)
        rollback_run_id = getattr(result, "rollback_run_id", None)
        if isinstance(rollback_run_id, str):
            self._set_choice_to_run_id(self._rollback_run_choice_var, self._rollback_choice_map, rollback_run_id)
            self._set_choice_to_run_id(self._logs_rollback_choice_var, self._rollback_choice_map, rollback_run_id)
        verify_run_id = getattr(result, "verify_run_id", None)
        if isinstance(verify_run_id, str):
            self._set_choice_to_run_id(self._logs_verify_choice_var, self._verify_choice_map, verify_run_id)

    def _set_choice_to_run_id(self, variable: tk.StringVar, mapping: dict[str, str], run_id: str) -> None:
        label = self._find_label_by_run_id(mapping, run_id)
        if label:
            variable.set(label)

    def _format_result(self, stage: str, result: object) -> str:
        pairs: list[str] = [f"{stage} 完了"]
        for key in (
            "scan_run_id",
            "plan_run_id",
            "execution_run_id",
            "rollback_run_id",
            "verify_run_id",
            "file_count",
            "warning_count",
            "item_count",
            "conflict_count",
            "risk_count",
            "success_count",
            "skipped_count",
            "failed_count",
            "risky_count",
        ):
            value = getattr(result, key, None)
            if value is not None:
                pairs.append(f"{key}={value}")
        return " / ".join(pairs)

    def _required_path(self, value: str, label: str, *, must_exist: bool = True) -> Path | None:
        text = value.strip()
        if not text:
            self._show_error("Missing Setting", f"{label} を設定してください。")
            return None
        path = Path(text)
        if must_exist and not path.exists():
            self._show_error("Invalid Path", f"{label} が存在しません: {path}")
            return None
        return path

    def _db_path(self) -> Path | None:
        value = self._db_var.get().strip()
        return Path(value) if value else None

    def _pick_directory(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(initialdir=variable.get() or ".")
        if selected:
            variable.set(selected)

    def _pick_file(self, variable: tk.StringVar, *, save: bool = False) -> None:
        if save:
            selected = filedialog.asksaveasfilename(
                initialfile=Path(variable.get()).name or "state.db",
                defaultextension=".db",
                filetypes=[("Database", "*.db"), ("All files", "*.*")],
            )
        else:
            selected = filedialog.askopenfilename(filetypes=[("Database", "*.db"), ("All files", "*.*")])
        if selected:
            variable.set(selected)

    def _format_scan_choice(self, row: RunRow) -> str:
        return f"{self._format_iso_datetime(row.started_at)} | files={row.primary_count} | {row.run_id[:8]}"

    def _format_plan_choice(self, row: RunRow) -> str:
        return f"{self._format_iso_datetime(row.started_at)} | items={row.primary_count} | warn={row.secondary_count} | {row.run_id[:8]}"

    def _format_execution_choice(self, row: RunRow) -> str:
        return f"{self._format_iso_datetime(row.started_at)} | {row.detail} | ok={row.primary_count} ng={row.secondary_count} | {row.run_id[:8]}"

    def _format_rollback_choice(self, row: RunRow) -> str:
        return f"{self._format_iso_datetime(row.started_at)} | {row.detail} | ok={row.primary_count} ng={row.secondary_count} | {row.run_id[:8]}"

    def _format_verify_choice(self, row: RunRow) -> str:
        return f"{self._format_iso_datetime(row.started_at)} | {row.detail} | ok={row.primary_count} ng={row.secondary_count} | {row.run_id[:8]}"

    @staticmethod
    def _find_label_by_run_id(mapping: dict[str, str], run_id: str) -> str | None:
        for label, value in mapping.items():
            if value == run_id:
                return label
        return None

    def _render_plan_action(self, action: str) -> str:
        return {"move": "整理する", "skip": "整理しない"}.get(action, action)

    def _render_operation_action(self, action: str) -> str:
        return {
            "dry_run": "テスト実行",
            "move": "移動",
            "copy": "コピー",
            "copy_delete": "コピー後に元を削除",
            "rollback_dry_run": "元に戻す前の確認",
            "reverse_move": "元へ移動",
            "reverse_copy": "元へコピー",
            "skip": "何もしない",
        }.get(action, action)

    def _render_status_word(self, value: str) -> str:
        return {"success": "成功", "failed": "失敗", "skipped": "スキップ"}.get(value, value)

    def _render_reason(self, value: str) -> str:
        mapping = {
            "none": "",
            "duplicate_target": "同じ整理先あり",
            "duplicate_target_path": "同じ整理先のため",
            "invalid_target": "整理先が不正",
            "path_too_long": "パスが長すぎる",
            "path_length_exceeded": "パス長超過",
            "component_too_long": "フォルダ名またはファイル名が長すぎる",
            "companion_without_music": "同じフォルダに整理対象の音楽ファイルがない",
            "companion_target_ambiguous": "整理先フォルダを一意に決められない",
            "already_applied": "すでに整理済み",
            "target_already_exists": "整理先に同名ファイルあり",
            "source_missing": "元ファイルなし",
            "cross_volume_verify_failed": "コピー後の確認失敗",
            "already_rolled_back": "すでに元へ戻済み",
            "source_already_exists": "元の場所に同名ファイルあり",
            "target_missing": "戻し先ファイルなし",
            "rollback_verify_failed": "元に戻した後の確認失敗",
            "rollback_not_implemented": "未対応の戻し方",
            "size_mismatch": "サイズ不一致",
            "apply_expectation_mismatch": "整理結果が想定と不一致",
            "rollback_expectation_mismatch": "元に戻した結果が想定と不一致",
        }
        return mapping.get(value, value)

    def _render_plan_reason(self, row: PlanItemRow) -> str:
        base_reason = self._render_reason(row.reason or "")
        if not row.target_path:
            return base_reason
        path_length = len(row.target_path)
        longest_component = max((len(part) for part in PurePath(row.target_path).parts), default=0)
        if row.reason == "path_length_exceeded":
            return f"{base_reason} ({path_length}文字)"
        if row.reason == "component_too_long":
            return f"{base_reason} (最長 {longest_component}文字 / 全体 {path_length}文字)"
        return base_reason

    def _show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def _show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        tree.delete(*tree.get_children())

    def _advance_page(self, paging: PagingState, direction: int) -> bool:
        if paging.total <= 0:
            return False
        new_offset = paging.offset + (direction * self._PAGE_SIZE)
        new_offset = max(0, min(new_offset, self._page_start(paging.total)))
        if new_offset == paging.offset:
            return False
        paging.offset = new_offset
        return True

    def _format_page_text(self, paging: PagingState) -> str:
        if paging.total <= 0:
            return "0 / 0"
        start = paging.offset + 1
        end = min(paging.offset + self._PAGE_SIZE, paging.total)
        return f"{start}-{end} / {paging.total}"

    def _page_start(self, total: int) -> int:
        if total <= 0:
            return 0
        return ((total - 1) // self._PAGE_SIZE) * self._PAGE_SIZE

    def _sort_tree(self, tree: ttk.Treeview, column: str) -> None:
        tree_id = str(tree)
        previous = self._tree_sort_state.get(tree_id)
        descending = previous[0] == column and not previous[1] if previous else False
        rows = [(tree.set(item_id, column), item_id) for item_id in tree.get_children("")]
        rows.sort(key=lambda item: self._normalize_sort_value(item[0]), reverse=descending)
        for index, (_, item_id) in enumerate(rows):
            tree.move(item_id, "", index)
        self._tree_sort_state[tree_id] = (column, descending)

    def _normalize_sort_value(self, value: str) -> tuple[int, object]:
        text = value.strip()
        if not text:
            return (3, "")
        if len(text) == 8 and text.count(":") == 2:
            parts = text.split(":")
            if all(part.isdigit() for part in parts):
                hours, minutes, seconds = (int(part) for part in parts)
                return (0, hours * 3600 + minutes * 60 + seconds)
        if text.isdigit():
            return (0, int(text))
        try:
            return (1, datetime.fromisoformat(text))
        except ValueError:
            return (2, text.casefold())
