#app_table.py
import os
import subprocess
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QLabel, QTextEdit, QSplitter, QHeaderView, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt
from database import SQLiteTableModel, load_app_data_from_db
from no_focus_frame_style import NoFocusFrameStyle


class AppTableWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = ""
        self.foreground_cycle_time_data = None
        self.setup_ui()

    def setup_ui(self):
        self.table_view = QTableView(self)
        self.table_view.setStyle(NoFocusFrameStyle())
        self.info_label = QLabel("데이터를 불러올 수 없습니다.", self)
        self.info_label.setAlignment(Qt.AlignCenter)

        self.text_box1 = QTextEdit(self)
        self.text_box2 = QTextEdit(self)
        self.text_box3 = QTextEdit(self)
        self.text_box4 = QTextEdit(self)

        for text_box in [self.text_box1, self.text_box2, self.text_box3, self.text_box4]:
            text_box.setReadOnly(True)

        # Prefetch 데이터 버튼 추가
        self.prefetch_button = QPushButton("Load Prefetch Data")
        self.prefetch_button.clicked.connect(self.load_prefetch_data)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.table_view)
        left_layout.addWidget(self.info_label)
        left_layout.addWidget(self.prefetch_button)
        left_widget.setLayout(left_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.text_box1)
        right_layout.addWidget(self.text_box2)
        right_layout.addWidget(self.text_box3)
        right_layout.addWidget(self.text_box4)
        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
        self.info_label.hide()

    def set_db_path(self, db_path):
        self.db_path = db_path
        self.load_app_data()

    def load_app_data(self):
        data, headers = load_app_data_from_db(self.db_path)
        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            self.table_view.hideColumn(1)
            header = self.table_view.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.Interactive)
            header.resizeSection(2, 340)
            self.info_label.hide()
        else:
            self.info_label.setText("데이터를 불러올 수 없습니다.")
            self.info_label.show()

    def load_prefetch_data(self):
        default_prefetch_path = r"C:\Windows\Prefetch"
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Prefetch Directory",
            default_prefetch_path if os.path.exists(default_prefetch_path) else ""
        )
        if not folder_path:
            return

        tool_path = os.path.join(os.getcwd(), "WinPrefetchView.exe")
        if not os.path.exists(tool_path):
            self.info_label.setText("WinPrefetchView.exe not found in the current directory.")
            self.info_label.show()
            return

        try:
            output_csv = "prefetch_output.csv"
            process = subprocess.Popen(
                [tool_path, "/folder", folder_path, "/scomma", output_csv],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=4096,
                text=True
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0 or stderr:
                self.info_label.setText(f"Error running WinPrefetchView: {stderr}")
                self.info_label.show()
                return

            if not os.path.exists(output_csv):
                self.info_label.setText("No output generated.")
                self.info_label.show()
                return

            # Load CSV data into the table view
            df = pd.read_csv(output_csv, encoding="utf-8", errors="replace")
            self.display_prefetch_data(df)

        except Exception as e:
            self.info_label.setText(f"Error loading Prefetch data: {e}")
            self.info_label.show()

    def display_prefetch_data(self, df):
        # Convert DataFrame to SQLiteTableModel for QTableView
        headers = list(df.columns)
        data = df.values.tolist()

        model = SQLiteTableModel(data, headers)
        self.table_view.setModel(model)
        self.info_label.hide()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = AppTableWidget()
    widget.show()
    sys.exit(app.exec())
