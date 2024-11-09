# main.py

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget, QFileDialog, QLabel, \
    QHBoxLayout, QLineEdit, QSplitter, QStatusBar, QStyledItemDelegate, QTabWidget, QTextEdit, QSizePolicy
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QSortFilterProxyModel
from database import SQLiteTableModel, load_data_from_db, load_app_data_from_db, load_web_data
from image_loader import ImageLoaderThread
from web import WebTableWidget as ImportedWebTableWidget
from file_table import FileTableModel

# 문자열 매핑 딕셔너리: 이벤트 이름을 간결한 이름으로 매핑
name_mapping = {
    "WindowCaptureEvent": "Capture",
    "WindowCreatedEvent": "Created",
    "WindowChangedEvent": "Changed",
    "WindowDestroyedEvent": "Destroyed",
    "ForegroundChangedEvent": "Foreground"
}

def map_name(name):
    return name_mapping.get(name, name) if name else 'N/A'

class CenteredDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReCall DATA Parser")
        self.resize(1800, 900)
        self.db_path = ""

        # 상단 메뉴바 생성
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("파일")
        open_file_action = QAction("파일 열기", self)
        open_file_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_file_action)

        open_history_action = QAction("히스토리 파일 열기", self)
        open_history_action.triggered.connect(self.open_history_file_dialog)
        file_menu.addAction(open_history_action)

        # 검색창 추가
        top_layout = QWidget(self)
        top_layout.setLayout(QHBoxLayout())
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요...")
        self.search_input.setFixedWidth(200)

        # 메뉴바 오른쪽에 검색창 추가
        top_layout.layout().addWidget(self.menu_bar)
        top_layout.layout().addStretch(5)
        top_layout.layout().addWidget(self.search_input)
        self.setMenuWidget(top_layout)

        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # UI 구성
        self.setup_ui()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.on_tab_changed(self.tab_widget.currentIndex())

        # image_label에 마우스 더블클릭 이벤트 핸들러 설정
        self.image_label.mouseDoubleClickEvent = self.on_image_label_double_click

    def setup_image_table_tab(self):
        try:
            from image_table_one import ImageTableWidget
            self.image_table_tab = ImageTableWidget()
            self.tab_widget.addTab(self.image_table_tab, "ImageTable")
        except ImportError:
            pass

    def setup_app_table_tab(self):
        try:
            from app_table import AppTableWidget
            self.app_table_tab = AppTableWidget()
            self.tab_widget.addTab(self.app_table_tab, "AppTable")
            if self.db_path:
                self.app_table_tab.set_db_path(self.db_path)
        except ImportError:
            print("AppTableWidget 모듈을 불러오지 못했습니다.")

    def on_tab_changed(self, index):
        tab_name = self.tab_widget.tabText(index)
        if tab_name == "ImageTable":
            self.search_input.hide()
            self.image_table_tab.setFocus()
        else:
            self.search_input.show()

    def on_image_label_double_click(self, event):
        if self.tab_widget.indexOf(self.image_table_tab) != -1:
            self.tab_widget.setCurrentWidget(self.image_table_tab)
            selected_index = self.table_view.selectionModel().currentIndex()
            image_token_index = self.proxy_model.index(selected_index.row(), 2)
            image_token = image_token_index.data()
            if image_token and hasattr(self.image_table_tab, 'display_image_from_token'):
                self.image_table_tab.display_image_from_token(image_token)

    def setup_ui(self):
        self.all_table_tab = QWidget()
        self.all_table_layout = QVBoxLayout(self.all_table_tab)
        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        self.all_table_layout.addWidget(self.horizontal_splitter)
        self.table_view = QTableView()
        self.horizontal_splitter.addWidget(self.table_view)
        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        self.horizontal_splitter.setStretchFactor(0, 3)
        self.horizontal_splitter.setStretchFactor(1, 1)

        self.image_label = QLabel("이미지 프리뷰")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(854, 480)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setScaledContents(True)
        self.vertical_splitter.addWidget(self.image_label)

        self.data_viewer = QTextEdit("데이터 프리뷰")
        self.data_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vertical_splitter.addWidget(self.data_viewer)

        self.all_table_tab.setLayout(self.all_table_layout)
        self.tab_widget.addTab(self.all_table_tab, "AllTable")

        self.setup_image_table_tab()
        self.setup_app_table_tab()

        self.web_table_tab = ImportedWebTableWidget()
        self.tab_widget.addTab(self.web_table_tab, "WebTable")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterKeyColumn(-1)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.selectionModel().selectionChanged.connect(self.update_image_display)
        self.search_input.textChanged.connect(self.filter_table)

    def open_file_dialog(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        db_path, _ = QFileDialog.getOpenFileName(
            self, "데이터베이스 파일 선택", desktop_path, "SQLite Files (*.db)"
        )

        if db_path:
            self.db_path = db_path
            self.load_data(db_path)

            if hasattr(self.app_table_tab, 'set_db_path'):
                self.app_table_tab.set_db_path(db_path)
            if hasattr(self.image_table_tab, 'set_db_path'):
                self.image_table_tab.set_db_path(db_path)
            if hasattr(self.web_table_tab, 'set_db_path'):
                self.web_table_tab.set_db_path(db_path)

    def load_data(self, db_path):
        self.db_path = db_path
        data, headers = load_data_from_db(db_path)

        if data:
            updated_data = []
            for row in data:
                row = list(row)
                row[1] = map_name(row[1])
                image_token = row[2]
                row.append("O" if image_token else "X")
                updated_data.append(row)

            headers.append("이미지")
            model = SQLiteTableModel(updated_data, headers)
            self.proxy_model.setSourceModel(model)

            self.table_view.resizeColumnToContents(0)
            self.table_view.resizeColumnToContents(1)
            self.table_view.resizeColumnToContents(5)

            self.table_view.hideColumn(2)
            self.table_view.hideColumn(6)
            self.table_view.hideColumn(7)
            self.table_view.resizeColumnToContents(len(headers) - 1)

            centered_delegate = CenteredDelegate(self.table_view)
            self.table_view.setItemDelegateForColumn(len(headers) - 1, centered_delegate)

            if hasattr(self.image_table_tab, 'set_db_path'):
                self.table_view.setSortingEnabled(True)
                self.table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
                self.table_view.scrollToTop()
        else:
            self.status_bar.showMessage("데이터를 불러오지 못했습니다.")

    def open_history_file_dialog(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        db_path, _ = QFileDialog.getOpenFileName(
            self, "히스토리 파일 선택", desktop_path, "All Files (*)"
        )
        if db_path:
            # web_table_tab에 set_history_db_path가 있는지 확인한 후 호출
            if hasattr(self.web_table_tab, 'set_history_db_path'):
                print(f"선택된 파일 경로: {db_path}")  # 경로 확인용 로그 추가
                self.web_table_tab.set_history_db_path(db_path)
            else:
                print("web_table_tab에 set_history_db_path 메서드가 없습니다.")

    def update_image_display(self, selected, deselected):
        for index in selected.indexes():
            row = index.row()
            file_path_index = self.proxy_model.index(row, 6)
            file_path = file_path_index.data()
            web_uri_index = self.proxy_model.index(row, 7)
            web_uri = web_uri_index.data()
            app_name_index = self.proxy_model.index(row, 4)
            app_name = app_name_index.data()
            window_title_index = self.proxy_model.index(row, 3)
            window_title = window_title_index.data()

            preview_text = f"""
                <div style="font-size: 11pt; line-height: 1;">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>File Path:</b> {file_path or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>Web URI:</b> {web_uri or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>App Name:</b> {app_name or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 0;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>Window Title:</b> {window_title or 'N/A'}</span>
                    </div>
                </div>
                """
            self.data_viewer.setHtml(preview_text)

            image_token_index = self.proxy_model.index(row, 2)
            image_token = image_token_index.data()
            if image_token:
                image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
                image_path = os.path.join(image_dir, image_token)
                if not os.path.exists(image_path):
                    self.image_label.setText(f"이미지 파일을 찾을 수 없습니다: {image_token}")
                    return
                self.load_image_in_thread(image_path)
            else:
                self.image_label.clear()
                self.image_label.setText("이미지 없음")
            break

    def load_image_in_thread(self, image_path):
        self.image_loader_thread = ImageLoaderThread(image_path)
        self.image_loader_thread.image_loaded.connect(self.display_image)
        self.image_loader_thread.start()

    def display_image(self, pixmap):
        scaled_pixmap = pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def filter_table(self):
        # 검색 입력에 따라 테이블 필터링
        filter_text = self.search_input.text()
        self.proxy_model.setFilterWildcard(f"*{filter_text}*")


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        if os.path.exists("style.qss"):
            with open("style.qss", "r", encoding="utf-8") as f:
                qss = f.read()
                app.setStyleSheet(qss)

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        print(f"애플리케이션 실행 중 예외 발생: {e}")
