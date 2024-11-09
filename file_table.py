# file_table.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QSplitter, QLabel, QTextEdit, QSizePolicy
from PySide6.QtCore import Qt
from database import SQLiteTableModel, load_file_data_from_db
from no_focus_frame_style import NoFocusFrameStyle

class FileTableWidget(QWidget):
    def __init__(self, db_path=""):
        super().__init__()
        self.db_path = db_path
        self.setup_ui()
        if self.db_path:
            self.load_data(self.db_path)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)

        # 왼쪽 테이블 뷰
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)
        self.table_view.setStyle(NoFocusFrameStyle())
        self.splitter.addWidget(self.table_view)

        # 빈 모델 설정 추가
        self.table_view.setModel(SQLiteTableModel([], []))

        # 오른쪽 위젯 (추가로 필요한 내용이 있다면 여기서 구성)
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)

        # 예시로 파일 상세 정보를 표시하는 QTextEdit 추가
        self.detail_viewer = QTextEdit()
        self.detail_viewer.setReadOnly(True)
        self.detail_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_layout.addWidget(self.detail_viewer)

        self.splitter.addWidget(self.right_widget)

        # 테이블 셀 클릭 시 상세 정보 업데이트
        self.table_view.selectionModel().selectionChanged.connect(self.update_detail_view)

    def set_db_path(self, db_path):
        self.db_path = db_path
        self.load_data(db_path)

    def load_data(self, db_path):
        data, headers = load_file_data_from_db(db_path)
        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            
            # 모든 칼럼의 너비를 내용에 맞게 조정
            self.table_view.resizeColumnsToContents()
            
            # Path 칼럼의 인덱스 가져오기
            path_column_index = headers.index('Path')
            
            # Path 칼럼의 너비를 원하는 픽셀 값으로 설정 (예: 300)
            self.table_view.setColumnWidth(path_column_index, 300)
        else:
            self.table_view.setModel(None)


    def update_detail_view(self, selected, deselected):
        for index in selected.indexes():
            row = index.row()
            data = []
            for column in range(self.table_view.model().columnCount()):
                item = self.table_view.model().index(row, column).data()
                header = self.table_view.model().headerData(column, Qt.Horizontal)
                data.append(f"<b>{header}:</b> {item}")
            self.detail_viewer.setHtml("<br>".join(data))
            break
