#web.py


import shutil
import sqlite3
import os
import glob
import re
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QTextEdit, QSplitter, QDialog, QMessageBox, QFrame, \
    QSpacerItem, QSizePolicy, QHBoxLayout, QLabel
from database import SQLiteTableModel, load_web_data, load_data_from_db
from no_focus_frame_style import NoFocusFrameStyle

# 사용자 정의 정규 표현식 매칭 함수
def regexp(pattern, input_str):
    if input_str is None:
        return False
    return re.search(pattern, input_str) is not None

# 타임스탬프 변환 함수
def convert_chrome_timestamp(chrome_timestamp):
    base_date = datetime(1601, 1, 1, tzinfo=timezone.utc)
    timestamp_seconds = chrome_timestamp / 1_000_000  # 마이크로초를 초 단위로 변환
    converted_time = base_date + timedelta(seconds=timestamp_seconds)
    return converted_time

def convert_unix_timestamp(unix_timestamp):
    return datetime.fromtimestamp(unix_timestamp / 1000, tz=timezone.utc).replace(microsecond=0)

# Helper function to simplify Title
def simplify_title(title):
    return re.sub(r"( - Chrome)$", "", title)

class DetailDialog(QDialog):
    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")
        self.setFixedSize(500, 400)

        layout = QVBoxLayout(self)
        frame = QFrame(self)
        frame_layout = QVBoxLayout(frame)

        for header, value in zip(headers, data):
            row_layout = QHBoxLayout()
            label_header = QLabel(f"{header}:")
            label_header.setStyleSheet("font-weight: bold;")
            label_value = QLabel(str(value))
            label_value.setWordWrap(True)
            row_layout.addWidget(label_header)
            row_layout.addWidget(label_value)
            frame_layout.addLayout(row_layout)

            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            frame_layout.addWidget(separator)

        frame_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addWidget(frame)

class WebTableWidget(QWidget):
    def __init__(self, db_path=""):
        super().__init__()
        self.db_path = db_path
        self.history_db_path = None
        self.user_path = os.path.expanduser("~")
        self.history_folder = os.path.join(self.user_path, "Desktop", "History_load")
        self.setup_ui()

        # 필터링 및 정렬 모델 설정
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterKeyColumn(1)  # Window Title 열 필터링
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)  # 테이블 정렬 활성화

        # 브라우저 키워드 목록 추가
        self.browser_keywords = ["Chrome", "Firefox", "Edge", "Whale"]
        self.filter_browser_data()

        # 데이터베이스를 열기 전에 파일 복사 여부를 묻는 창 띄우기
        reply = QMessageBox.question(self, "파일 복사", "브라우저 히스토리 및 ukg.db 파일을 바탕화면에 복사하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        self.copy_files = reply == QMessageBox.Yes
        if self.copy_files:
            self.copy_history_files()

        # 데이터베이스 로드
        if self.db_path:
            self.load_data()

    def setup_ui(self):
        layout = QSplitter(Qt.Horizontal, self)
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)
        # 포커스 프레임 스타일 적용
        self.table_view.setStyle(NoFocusFrameStyle())
        layout.addWidget(self.table_view)

        # 데이터 뷰어 추가
        self.data_viewer = QTextEdit("데이터 프리뷰")
        self.data_viewer.setReadOnly(True)
        layout.addWidget(self.data_viewer)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(layout)
        self.setLayout(main_layout)

        self.table_view.clicked.connect(self.display_related_history_data)

    def filter_browser_data(self):
        pattern = "|".join(self.browser_keywords)  # "Chrome|Firefox|Edge|Whale"
        self.proxy_model.setFilterRegularExpression(pattern)

    def set_db_path(self, db_path):
        self.db_path = db_path
        self.load_data()

    def set_history_db_path(self, history_db_path):
        self.history_db_path = history_db_path
        print(f"새로운 히스토리 파일 경로가 설정되었습니다: {self.history_db_path}")

    def load_data(self):
        if self.db_path:
            data, headers = load_web_data(self.db_path)
            if data:
                # 연관 데이터 유/무를 표시하기 위해 데이터 수정
                extended_data = []
                for row in data:
                    title = row[1]  # 타이틀 열의 인덱스
                    timestamp = row[2]  # TimeStamp가 있는 열의 인덱스
                    has_related_data = self.check_related_data(timestamp, title)
                    row = list(row)  # 튜플을 리스트로 변환
                    row.append("O" if has_related_data else "X")  # "O" 또는 "X" 추가
                    extended_data.append(row)

                headers.append("Related Data")  # 새로운 열 헤더 추가
                model = SQLiteTableModel(extended_data, headers)
                self.proxy_model.setSourceModel(model)  # proxy_model에 모델 설정
                self.table_view.setModel(self.proxy_model)  # 정렬이 작동하도록 모델 설정

                # 새로 추가된 열의 너비 조정
                self.table_view.resizeColumnToContents(len(headers) - 1)
            else:
                self.table_view.setModel(None)

    def update_related_data_status(self):
        model = self.table_view.model()
        if not model:
            return

        for row in range(model.rowCount()):
            title = model.index(row, 1).data()
            timestamp = model.index(row, 2).data()
            related_data_exists = self.check_related_data(timestamp, title)
            status = "O" if related_data_exists else "X"
            model.setData(model.index(row, 3), status)

        model.layoutChanged.emit()

    def check_related_data(self, timestamp_ukg, title_ukg):
        if not self.history_db_path or title_ukg is None or timestamp_ukg is None:
            return False

        conn = None
        try:
            # Check if timestamp_ukg is a string and try to parse it correctly
            if isinstance(timestamp_ukg, str):
                try:
                    # Try to convert timestamp from string to float
                    timestamp_ukg = float(datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").timestamp()) * 1000
                except ValueError:
                    return False

            conn = sqlite3.connect(self.history_db_path)
            conn.create_function("REGEXP", 2, regexp)
            cursor = conn.cursor()

            # Convert ukg.db timestamp to KST (seconds)
            try:
                kst_time_ukg = datetime.fromtimestamp(timestamp_ukg / 1000, tz=timezone.utc).astimezone(
                    timezone(timedelta(hours=9))
                )
                ukg_unix_timestamp = int(kst_time_ukg.timestamp())
            except ValueError:
                return False

            # Simplify the Title: Remove " - Chrome" at the end
            simplified_title = re.sub(r" - Chrome$", "", title_ukg)

            # Query to fetch related data from the browser history
            query = "SELECT title, last_visit_time FROM urls WHERE title REGEXP ?"
            cursor.execute(query, (simplified_title,))
            data = cursor.fetchall()

            for row in data:
                chrome_title = row[0]
                chrome_time = row[1]
                kst_time_converted = convert_chrome_timestamp(chrome_time).astimezone(
                    timezone(timedelta(hours=9))
                )
                browser_unix_timestamp = int(kst_time_converted.timestamp())

                if chrome_title == simplified_title and browser_unix_timestamp == ukg_unix_timestamp:
                    return True

            return False

        except sqlite3.Error:
            return False

        finally:
            if conn:
                conn.close()

    def display_related_history_data(self, index):
        if not self.history_db_path:
            self.data_viewer.setText("히스토리 파일 경로가 설정되지 않았습니다.")
            return

        selected_title = self.table_view.model().index(index.row(), 1).data()
        timestamp_ukg = self.table_view.model().index(index.row(), 2).data()
        if not selected_title or not timestamp_ukg:
            self.data_viewer.setText("선택된 타이틀 또는 타임스탬프가 비어 있습니다.")
            return

        simplified_title = re.sub(r" - Chrome$", "", selected_title)

        try:
            conn = sqlite3.connect(self.history_db_path)
            conn.create_function("REGEXP", 2, regexp)
            cursor = conn.cursor()

            # 타임스탬프를 KST로 변환
            try:
                kst_time = datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone(timedelta(hours=9))
                )
                unix_timestamp = int(kst_time.timestamp())
            except ValueError:
                self.data_viewer.setText("타임스탬프 변환 오류가 발생했습니다.")
                return

            query = "SELECT url, title, visit_count, last_visit_time FROM urls WHERE title REGEXP ?"
            cursor.execute(query, (simplified_title,))
            data = cursor.fetchall()

            related_data = []
            for row in data:
                chrome_title = row[1]
                chrome_time = row[3]
                # Chrome 시간도 KST로 변환
                kst_time_converted = convert_chrome_timestamp(chrome_time).astimezone(
                    timezone(timedelta(hours=9))
                )

                if simplified_title == chrome_title and int(kst_time_converted.timestamp()) == unix_timestamp:
                    related_data.append(row)

            if related_data:
                formatted_data = []
                for row in related_data:
                    last_visit_time = row[3]
                    # KST로 변환된 시간을 표시
                    converted_time = convert_chrome_timestamp(last_visit_time).astimezone(timezone(timedelta(hours=9)))
                    formatted_data.append(
                        f"URL: {row[0]}\nTitle: {row[1]}\nVisit Count: {row[2]}\nLast Visit Time: {converted_time}\n---"
                    )
                self.data_viewer.setText("\n".join(formatted_data))
            else:
                self.data_viewer.setText("연관된 히스토리 데이터를 찾을 수 없습니다.")

        except sqlite3.Error as e:
            self.data_viewer.setText(f"히스토리 데이터를 로드하는 중 오류가 발생했습니다: {e}")

        finally:
            if conn:
                conn.close()

    def show_detail_dialog(self, index):
        row_data = []
        headers = []

        for column in range(self.table_view.model().columnCount()):
            item = self.table_view.model().index(index.row(), column).data()
            header = self.table_view.model().headerData(column, Qt.Horizontal)
            row_data.append(item)
            headers.append(header)

        detail_dialog = DetailDialog(row_data, headers, self)
        detail_dialog.exec_()

    def copy_history_files(self):
        history_paths = {
            "Chrome": os.path.join(self.user_path, r"AppData\Local\Google\Chrome\User Data\Default\History"),
            "Firefox": os.path.join(self.user_path, r"AppData\Roaming\Mozilla\Firefox\Profiles", "default-release",
                                    "places.sqlite"),
            "Edge": os.path.join(self.user_path, r"AppData\Local\Microsoft\Edge\User Data\Default\History"),
            "Whale": os.path.join(self.user_path, r"AppData\Local\Naver\Naver Whale\User Data\Default\History")
        }

        os.makedirs(self.history_folder, exist_ok=True)

        for browser, path in history_paths.items():
            try:
                if os.path.exists(path):
                    shutil.copy2(path, os.path.join(self.history_folder, f"{browser}_History"))
                    print(f"{browser} 히스토리 파일이 성공적으로 복사되었습니다.")
            except Exception as e:
                print(f"{browser} 히스토리 파일 복사 중 오류: {e}")

        ukp_folder_path = os.path.join(self.user_path, r"AppData\Local\CoreAIPlatform.00\UKP")
        guid_folders = glob.glob(os.path.join(ukp_folder_path, "{*}"))

        core_ai_path = None
        for folder in guid_folders:
            potential_file = os.path.join(folder, "ukg.db")
            if os.path.exists(potential_file):
                core_ai_path = potential_file
                break

        if core_ai_path:
            try:
                shutil.copy2(core_ai_path, os.path.join(self.history_folder, "ukg.db"))
                print("CoreAI ukg.db 파일이 성공적으로 복사되었습니다.")
            except Exception as e:
                print(f"CoreAI ukg.db 파일 복사 중 오류: {e}")
        else:
            print("CoreAI ukg.db 파일을 찾을 수 없습니다.")
