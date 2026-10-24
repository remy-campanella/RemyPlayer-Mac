from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton,
    QSlider, QSplitter, QStackedWidget, QTableView, QVBoxLayout, QWidget,
)

from remyplayer.domain.library import format_time, group_tracks, track_key
from remyplayer.domain.queue import PlayMode


class TrackModel(QAbstractTableModel):
    HEADERS = ("文件名", "曲目标题", "作者", "专辑", "时长")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracks = []
        self.current_path = None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.tracks)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        track = self.tracks[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (track.filename, track.title, track.artist, track.album, format_time(track.duration))[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return track.path
        if track.path == self.current_path:
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor("#21624d")
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 4:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def replace(self, tracks):
        self.beginResetModel()
        self.tracks = list(tracks)
        self.endResetModel()

    def set_current(self, path):
        previous = self.current_path
        self.current_path = path
        for row, track in enumerate(self.tracks):
            if track.path in (previous, path):
                self.dataChanged.emit(self.index(row, 0), self.index(row, 4))


STYLE = """
QMainWindow, QWidget#root { background: #f7f6f1; color: #263a32; }
QWidget { font-family: '.AppleSystemUIFont', 'Helvetica Neue', sans-serif; font-size: 13px; }
QWidget#sidebar { background: #eeeee5; border-radius: 14px; }
QLabel { color: #263a32; }
QLabel#brand { font-size: 23px; font-weight: 700; }
QLabel#eyebrow { color: #66756a; font-size: 11px; letter-spacing: 2px; }
QLabel#heading { font-size: 29px; font-weight: 600; }
QLabel#muted, QLabel#status { color: #728075; }
QLabel#nowTitle { font-weight: 600; font-size: 15px; }
QPushButton { background: #e9ece4; color: #284a3b; border: none; border-radius: 8px; padding: 9px 14px; }
QPushButton:hover { background: #dce4d8; }
QPushButton:disabled { color: #a2aaa0; background: #eeeee9; }
QPushButton#primary { background: #285f4c; color: white; }
QPushButton#primary:hover { background: #35745c; }
QPushButton#play { background: #285f4c; color: white; font-size: 15px; font-weight: 600; }
QLineEdit, QComboBox { background: #fffef9; color: #263a32; border: 1px solid #dfe2d7; border-radius: 8px; padding: 8px 10px; }
QComboBox QAbstractItemView { background: #fffef9; color: #263a32; selection-background-color: #dce7d9; }
QListWidget { border: none; background: transparent; outline: none; padding-top: 8px; }
QListWidget::item { color: #45594b; padding: 11px 10px; border-radius: 8px; margin-bottom: 3px; }
QListWidget::item:selected { background: #dbe5d6; color: #244e3c; }
QListWidget::item:hover { background: #e2e7db; }
QTableView { background: #fffef9; alternate-background-color: #f8f9f3; color: #35463a; border: 1px solid #e5e6dc; border-radius: 10px; gridline-color: transparent; selection-background-color: #e2ebdc; selection-color: #244e3c; outline: none; }
QTableView::item { padding: 8px; border: none; }
QHeaderView::section { background: #f1f3eb; color: #778171; border: none; border-bottom: 1px solid #e3e5d9; padding: 12px 8px; text-align: left; }
QFrame#player { background: #eff1e9; border: 1px solid #e0e5d8; border-radius: 13px; }
QSlider::groove:horizontal { height: 4px; background: #d6ded0; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #46775b; border-radius: 2px; }
QSlider::handle:horizontal { background: #285f4c; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
QSplitter::handle { background: transparent; }
QCheckBox { color: #586a5b; }
QToolTip { background: #fffef9; color: #263a32; border: 1px solid #dfe2d7; padding: 4px; }
"""


class MainWindow(QMainWindow):
    chooseRequested = Signal()
    rescanRequested = Signal()
    cancelRequested = Signal()
    playRequested = Signal(object, int)
    toggleRequested = Signal()
    nextRequested = Signal()
    previousRequested = Signal()
    seekRequested = Signal(int)
    volumeRequested = Signal(int)
    modeRequested = Signal(str)
    dockRequested = Signal(bool)
    hidden = Signal()
    errorsRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RemyPlayer · 0.0.0")
        self.resize(1180, 780)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(STYLE)
        self.tracks = []
        self.root_path = ""
        self.groups = {}
        self._duration = 0
        self._position = 0
        self.allow_hide = False
        self.quitting = False
        self.model = TrackModel(self)
        self._build()
        self._shortcuts()

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(18)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 23, 18, 18)
        side.setSpacing(14)
        brand = QLabel("RemyPlayer")
        brand.setObjectName("brand")
        side.addWidget(brand)
        caption = QLabel("LOCAL MUSIC / 0.0.0")
        caption.setObjectName("eyebrow")
        side.addWidget(caption)
        side.addSpacing(12)
        self.choose = QPushButton("＋  选择音乐文件夹")
        self.choose.setObjectName("primary")
        self.choose.clicked.connect(self.chooseRequested)
        side.addWidget(self.choose)
        self.root_label = QLabel("尚未选择音乐库")
        self.root_label.setObjectName("muted")
        self.root_label.setWordWrap(True)
        side.addWidget(self.root_label)
        self.category = QComboBox()
        for label, key in (("按文件夹", "folder"), ("按作者", "artist"), ("按专辑", "album")):
            self.category.addItem(label, key)
        self.category.currentIndexChanged.connect(self.rebuild_groups)
        side.addWidget(self.category)
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self.refresh_tracks)
        side.addWidget(self.group_list, 1)
        self.rescan = QPushButton("重新扫描  ⌘R")
        self.rescan.setEnabled(False)
        self.rescan.clicked.connect(self.rescanRequested)
        side.addWidget(self.rescan)
        self.keep_dock = QCheckBox("后台播放时保留 Dock 图标")
        self.keep_dock.toggled.connect(self.dockRequested)
        side.addWidget(self.keep_dock)
        splitter.addWidget(sidebar)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(20, 2, 0, 0)
        body.setSpacing(15)
        eyebrow = QLabel("YOUR PERSONAL COLLECTION")
        eyebrow.setObjectName("eyebrow")
        body.addWidget(eyebrow)
        self.heading = QLabel("音乐库")
        self.heading.setObjectName("heading")
        body.addWidget(self.heading)
        self.summary = QLabel("从一个文件夹开始，按自己的顺序聆听。")
        self.summary.setObjectName("muted")
        body.addWidget(self.summary)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索文件名、标题、作者或专辑  ·  ⌘F")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_tracks)
        toolbar.addWidget(self.search, 1)
        self.play_list = QPushButton("播放此列表")
        self.play_list.setEnabled(False)
        self.play_list.clicked.connect(self.play_visible)
        toolbar.addWidget(self.play_list)
        body.addLayout(toolbar)
        self.pages = QStackedWidget()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 70)
        self.table.activated.connect(lambda index: self.playRequested.emit(list(self.model.tracks), index.row()))
        self.pages.addWidget(self.table)
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        symbol = QLabel("♫")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setStyleSheet("font-size: 64px; color: #8ba486;")
        empty_layout.addWidget(symbol)
        self.empty_title = QLabel("让音乐回到你的节奏")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setStyleSheet("font-size: 21px; font-weight: 600;")
        empty_layout.addWidget(self.empty_title)
        self.empty_text = QLabel("选择音乐文件夹，自动整理文件夹、作者与专辑。\n只读取音乐，不修改原文件。")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text.setObjectName("muted")
        self.empty_text.setStyleSheet("line-height: 1.6; padding: 12px;")
        self.empty_text.setWordWrap(True)
        empty_layout.addWidget(self.empty_text)
        empty_layout.addStretch()
        self.pages.addWidget(empty)
        self.pages.setCurrentIndex(1)
        body.addWidget(self.pages, 1)
        status_row = QHBoxLayout()
        self.status = QLabel("就绪 · 音乐库只读")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        self.error_button = QPushButton("查看问题")
        self.error_button.hide()
        self.error_button.clicked.connect(self.errorsRequested)
        status_row.addWidget(self.error_button)
        self.cancel = QPushButton("取消扫描")
        self.cancel.hide()
        self.cancel.clicked.connect(self.cancelRequested)
        status_row.addWidget(self.cancel)
        body.addLayout(status_row)
        splitter.addWidget(content)
        splitter.setSizes([250, 890])
        layout.addWidget(splitter, 1)

        player = QFrame()
        player.setObjectName("player")
        player_box = QVBoxLayout(player)
        player_box.setContentsMargins(20, 14, 20, 14)
        top = QHBoxLayout()
        now = QVBoxLayout()
        self.now_title = QLabel("尚未播放")
        self.now_title.setObjectName("nowTitle")
        self.now_title.setMaximumWidth(350)
        self.now_artist = QLabel("双击曲目，或播放当前列表")
        self.now_artist.setObjectName("muted")
        self.now_artist.setMaximumWidth(350)
        now.addWidget(self.now_title)
        now.addWidget(self.now_artist)
        top.addLayout(now, 1)
        self.previous_button = QPushButton("上一首")
        self.previous_button.clicked.connect(self.previousRequested)
        self.play_button = QPushButton("播放")
        self.play_button.setObjectName("play")
        self.play_button.setMinimumWidth(82)
        self.play_button.clicked.connect(self._play)
        self.next_button = QPushButton("下一首")
        self.next_button.clicked.connect(self.nextRequested)
        for button in (self.previous_button, self.play_button, self.next_button):
            top.addWidget(button)
        top.addSpacing(14)
        self.mode = QComboBox()
        for mode in PlayMode:
            self.mode.addItem(mode.value)
        self.mode.setCurrentText(PlayMode.ORDER.value)
        self.mode.currentTextChanged.connect(self.modeRequested)
        top.addWidget(self.mode)
        top.addSpacing(10)
        top.addWidget(QLabel("音量"))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedWidth(85)
        self.volume.valueChanged.connect(self.volumeRequested)
        top.addWidget(self.volume)
        player_box.addLayout(top)
        progress = QHBoxLayout()
        self.elapsed = QLabel("0:00")
        self.elapsed.setMinimumWidth(42)
        self.elapsed.setObjectName("muted")
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.setEnabled(False)
        self.seek.sliderReleased.connect(lambda: self.seekRequested.emit(self.seek.value()))
        self.seek.sliderMoved.connect(lambda value: self.elapsed.setText(format_time(value / 1000)))
        self.total = QLabel("0:00")
        self.total.setObjectName("muted")
        self.total.setMinimumWidth(42)
        progress.addWidget(self.elapsed)
        progress.addWidget(self.seek, 1)
        progress.addWidget(self.total)
        player_box.addLayout(progress)
        layout.addWidget(player)

    def _shortcuts(self):
        for title, shortcut, handler in (
            ("选择音乐库", QKeySequence.StandardKey.Open, self.chooseRequested.emit),
            ("重新扫描", QKeySequence("Ctrl+R"), self.rescanRequested.emit),
            ("搜索", QKeySequence.StandardKey.Find, self.search.setFocus),
        ):
            action = QAction(title, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(handler)
            self.addAction(action)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.table.hasFocus():
            self.play_visible()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space and not self.search.hasFocus():
            self._play()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_library(self, root, tracks):
        self.root_path = root
        self.tracks = sorted(tracks, key=track_key)
        self.root_label.setText(Path(root).name)
        self.root_label.setToolTip(root)
        self.rebuild_groups()

    def rebuild_groups(self, *_):
        current = self.group_list.currentItem()
        old = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.groups = group_tracks(self.tracks, self.category.currentData())
        self.group_list.blockSignals(True)
        self.group_list.clear()
        all_item = QListWidgetItem(f"全部曲目  ·  {len(self.tracks)}")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.group_list.addItem(all_item)
        selected = 0
        for key, tracks in self.groups.items():
            label, tooltip = self.group_display(key)
            item = QListWidgetItem(f"{label}  ·  {len(tracks)}")
            item.setToolTip(tooltip)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.group_list.addItem(item)
            if key == old:
                selected = self.group_list.count() - 1
        self.group_list.setCurrentRow(selected)
        self.group_list.blockSignals(False)
        self.refresh_tracks()

    def group_display(self, key):
        if key is None:
            return "全部曲目", "全部曲目"
        if self.category.currentData() == "folder":
            path = Path(self.root_path) / key
            return path.name or str(path), str(path)
        return key, key

    def refresh_tracks(self, *_):
        item = self.group_list.currentItem()
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        tracks = self.tracks if key is None else self.groups.get(key, [])
        query = self.search.text().strip().casefold()
        if query:
            tracks = [t for t in tracks if query in " ".join((t.filename, t.title, t.artist, t.album, t.relative_path)).casefold()]
        self.model.replace(tracks)
        title, tooltip = self.group_display(key)
        self.heading.setText(title if self.root_path else "音乐库")
        self.heading.setToolTip(tooltip)
        self.summary.setText(f"{len(tracks)} 首曲目  ·  {format_time(sum(t.duration for t in tracks))}  ·  文件名自然排序")
        self.pages.setCurrentIndex(0 if tracks else 1)
        self.play_list.setEnabled(bool(tracks))
        if self.root_path:
            self.empty_title.setText("没有匹配的曲目" if query else "这里还没有音乐")
            self.empty_text.setText("试试其他关键词。" if query else "扫描此文件夹，或选择另一个音乐库。\n无法识别的文件会列在扫描问题中。")

    def play_visible(self):
        if self.model.tracks:
            row = self.table.currentIndex().row()
            self.playRequested.emit(list(self.model.tracks), max(0, row))

    def _play(self):
        if self.model.current_path:
            self.toggleRequested.emit()
        else:
            self.play_visible()

    def set_track(self, track):
        self.model.set_current(track.path)
        self.now_title.setText(track.title)
        self.now_title.setToolTip(track.filename)
        self.now_artist.setText(f"{track.artist} · {track.album}")
        self.now_artist.setToolTip(f"{track.artist} · {track.album}")
        self.set_position(0)
        self.set_duration(0)

    def set_playing(self, playing):
        self.play_button.setText("暂停" if playing else "播放")

    def set_position(self, milliseconds):
        self._position = milliseconds
        if not self.seek.isSliderDown():
            self.seek.setValue(milliseconds)
            self.elapsed.setText(format_time(milliseconds / 1000))

    def set_duration(self, milliseconds):
        self._duration = milliseconds
        self.seek.setRange(0, milliseconds)
        self.seek.setEnabled(milliseconds > 0)
        self.total.setText(format_time(milliseconds / 1000))

    def set_busy(self, busy):
        self.choose.setEnabled(not busy)
        self.rescan.setEnabled(not busy and bool(self.root_path))
        self.cancel.setVisible(busy)
        if busy:
            self.status.setText("正在扫描音乐库…")

    def closeEvent(self, event):
        if not self.quitting and self.allow_hide:
            event.ignore()
            self.hide()
            self.hidden.emit()
        else:
            event.accept()
