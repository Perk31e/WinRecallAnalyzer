#app_table.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt
from database import SQLiteTableModel, load_app_data_from_db
from no_focus_frame_style import NoFocusFrameStyle

class AppTableWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = ""
        self.setup_ui()

    def setup_ui(self):
        # 테이블 뷰 및 데이터 없음 안내 레이블 추가
        self.table_view = QTableView(self)
        # NoFocusFrameStyle 적용
        self.table_view.setStyle(NoFocusFrameStyle())
        self.info_label = QLabel("데이터를 불러올 수 없습니다.", self)
        self.info_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table_view)
        layout.addWidget(self.info_label)
        self.info_label.hide()  # 데이터가 로드되면 숨김

    def set_db_path(self, db_path):
        self.db_path = db_path
        self.load_app_data()

    def load_app_data(self):
        data, headers = load_app_data_from_db(self.db_path)
        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            self.info_label.hide()  # 데이터가 로드되면 안내 레이블 숨김
        else:
            self.info_label.setText("데이터를 불러올 수 없습니다.")  # 데이터가 없을 때 안내 메시지 표시
            self.info_label.show()
