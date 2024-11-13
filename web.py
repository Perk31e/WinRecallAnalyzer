#web.py


import shutil
import sqlite3
import os
import glob
from datetime import datetime, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel, QSplitter, QDialog, QMessageBox, QFrame, \
    QSpacerItem, QSizePolicy, QHBoxLayout

from database import SQLiteTableModel, load_web_data, convert_unix_timestamp, convert_timestamp
from no_focus_frame_style import NoFocusFrameStyle

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
        self.user_path = os.path.expanduser("~")
        self.history_folder = os.path.join(self.user_path, "Desktop", "History_load")
        self.setup_ui()

        # 데이터베이스를 열기 전에 파일 복사 여부를 묻는 창 띄우기
        reply = QMessageBox.question(self, "파일 복사", "브라우저 히스토리 및 ukg.db 파일을 바탕화면에 복사하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        self.copy_files = reply == QMessageBox.Yes
        if self.copy_files:
            self.copy_history_files()  # 사용자가 '예'를 선택한 경우에만 파일 복사 수행

        # 복사 후에 데이터베이스 로드
        if self.db_path:
            self.load_web_data()

    def setup_ui(self):
        layout = QSplitter(Qt.Horizontal, self)

        # History 테이블 뷰
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)  # 정렬 활성화
        layout.addWidget(self.table_view)

        # 테이블 셀 더블클릭 시 show_detail_dialog 메서드 호출
        self.table_view.doubleClicked.connect(lambda index: self.show_detail_dialog(index, self.table_view))

        # UKG.db 테이블 뷰
        self.history_table = QTableView()
        self.history_table.setSortingEnabled(True)  # 정렬 활성화
        layout.addWidget(self.history_table)

        # 테이블 셀 더블클릭 시 show_detail_dialog 메서드 호출
        self.history_table.doubleClicked.connect(lambda index: self.show_detail_dialog(index, self.history_table))

        # 메인 레이아웃 설정
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(layout)

        # 데이터 로드 실패 시 안내 레이블
        self.info_label = QLabel("데이터를 로드할 수 없습니다.")
        self.info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.info_label)
        self.info_label.hide()
        self.table_view.setStyle(NoFocusFrameStyle())
        self.history_table.setStyle(NoFocusFrameStyle())


    def set_db_path(self, db_path):
        """
        사용자가 웹 데이터 DB 파일을 선택한 경우 호출됩니다.
        """
        self.db_path = db_path
        self.load_web_data(update_history=False)  # 히스토리 테이블을 초기화하지 않도록 설정

    def set_history_db_path(self, db_path):
        """
        사용자가 히스토리 파일을 선택한 경우 호출됩니다.
        """
        self.db_path = db_path
        print(f"새로운 히스토리 파일 경로가 설정되었습니다: {self.db_path}")
        self.history_table.setModel(None)  # 이전 데이터 제거
        self.load_browser_history_data()  # 새로운 경로로 데이터 로드

    def load_web_data(self, update_history=True):
        """
        웹 데이터를 로드합니다. update_history 플래그에 따라 히스토리 데이터를 갱신할지 결정합니다.
        """
        print(f"Loading Web data from: {self.db_path}")
        keywords = ["Edge"]
        data, headers = load_web_data(self.db_path, keywords=keywords)

        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            self.headers = headers  # headers 저장
            self.info_label.hide()

            for i, header in enumerate(headers):
                if "Timestamp" in header or "Last Visit Time" in header:
                    self.table_view.resizeColumnToContents(i)
        else:
            self.table_view.setModel(None)

        # update_history가 True일 때만 히스토리 데이터를 초기화
        if update_history:
            self.load_browser_history_data()

    def load_browser_history_data(self):
        """
        브라우저 히스토리 데이터를 로드하고, history_table에 설정합니다.
        데이터가 없는 경우 info_label을 숨깁니다.
        """
        # 현재 설정된 db_path 출력 확인
        print(f"Loading browser history from: {self.db_path}")

        # 브라우저 히스토리 데이터 로드
        history_data, history_headers = self.load_browser_history()

        # 데이터 유무를 확인하고, 출력해 봄
        if history_data:
            print("히스토리 데이터 로드 성공, 테이블에 설정 중...")
            history_model = SQLiteTableModel(history_data, history_headers)
            self.history_table.setModel(history_model)

            for i, header in enumerate(history_headers):
                if "Timestamp" in header or "Last Visit Time" in header:
                    self.history_table.resizeColumnToContents(i)
        else:
            print("히스토리 데이터가 비어 있습니다.")
            self.history_table.setModel(None)  # 데이터가 없을 경우 테이블 비우기
            self.info_label.hide()  # 메시지를 표시하지 않음

    def show_detail_dialog(self, index, table):
        row_data = []
        headers = []

        # 선택된 행의 데이터와 열 이름을 가져와서 row_data와 headers에 추가
        for column in range(table.model().columnCount()):
            item = table.model().index(index.row(), column).data()
            header = table.model().headerData(column, Qt.Horizontal)
            row_data.append(item)
            headers.append(header)

        # DetailDialog 창 열기
        detail_dialog = DetailDialog(row_data, headers, self)
        detail_dialog.exec_()

    def copy_history_files(self):
        # 각 브라우저의 히스토리 파일 경로
        history_paths = {
            "Chrome": os.path.join(self.user_path, r"AppData\Local\Google\Chrome\User Data\Default\History"),
            "Firefox": os.path.join(self.user_path, r"AppData\Roaming\Mozilla\Firefox\Profiles", "default-release",
                                    "places.sqlite"),
            "Edge": os.path.join(self.user_path, r"AppData\Local\Microsoft\Edge\User Data\Default\History"),
            "Whale": os.path.join(self.user_path, r"AppData\Local\Naver\Naver Whale\User Data\Default\History")
        }

        # 바탕화면의 History_load 폴더 생성
        os.makedirs(self.history_folder, exist_ok=True)

        # 브라우저 히스토리 파일 복사
        for browser, path in history_paths.items():
            try:
                if os.path.exists(path):
                    shutil.copy2(path, os.path.join(self.history_folder, f"{browser}_History"))
                    print(f"{browser} 히스토리 파일이 성공적으로 복사되었습니다.")
            except Exception as e:
                print(f"{browser} 히스토리 파일 복사 중 오류: {e}")

        # CoreAI ukg.db 파일 복사
        ukp_folder_path = os.path.join(self.user_path, r"AppData\Local\CoreAIPlatform.00\UKP")
        guid_folders = glob.glob(os.path.join(ukp_folder_path, "{*}"))  # GUID 형식 폴더 검색

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

    def load_browser_history(self):
        results = []
        for browser in ["Chrome", "Edge", "Whale", "Firefox"]:
            data = self.load_browser_data(browser)
            if data:  # 빈 데이터가 아닌 경우에만 추가
                results.extend(data)
        # 데이터가 없을 경우 빈 리스트와 빈 헤더 리스트 반환
        return results or [], ["URL", "Title", "Visit Count", "Total Visit Duration (seconds)", "TimeStamp"]

    def load_browser_data(self, browser):
        db_path = self.db_path  # 사용자 지정 파일 경로 사용
        print(f"브라우저 데이터베이스 파일 경로: {db_path}")

        # 파일이 실제로 존재하는지 확인
        if not os.path.exists(db_path):
            print(f"{browser} 히스토리 파일을 찾을 수 없습니다: {db_path}")
            return []

        try:
            # 데이터베이스 연결 시도
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 각 브라우저에 맞는 쿼리
            if browser in ["Chrome", "Edge", "Whale"]:
                query = """
                SELECT urls.url, urls.title, urls.visit_count,
                       urls.last_visit_time,
                       SUM(visits.visit_duration) AS total_visit_duration
                FROM urls
                LEFT JOIN visits ON urls.id = visits.url
                GROUP BY urls.url, urls.title, urls.visit_count, urls.last_visit_time
                ORDER BY urls.visit_count DESC
                """
            elif browser == "Firefox":
                query = """
                SELECT moz_places.url, moz_places.title, moz_places.visit_count, 
                       MIN(moz_historyvisits.visit_date) AS first_visit,
                       MAX(moz_historyvisits.visit_date) AS last_visit
                FROM moz_places
                JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
                GROUP BY moz_places.url, moz_places.title, moz_places.visit_count
                ORDER BY moz_places.visit_count DESC
                """

            # 쿼리 실행 및 결과 확인
            cursor.execute(query)
            rows = cursor.fetchall()
            print(f"로드된 행 수: {len(rows)}")  # 로드된 데이터의 개수를 출력

            # 데이터가 비어있다면 빈 리스트 반환
            if not rows:
                print(f"{browser} 데이터가 없습니다.")
                return []

            # 데이터 변환 및 반환
            results = []
            for row in rows:
                if browser == "Firefox":
                    url, title, visit_count, first_visit, last_visit = row
                    if first_visit and last_visit:
                        visit_duration = (last_visit - first_visit) / 1_000_000
                        timestamp = datetime.fromtimestamp(last_visit / 1_000_000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        visit_duration = 0
                        timestamp = None
                else:
                    url, title, visit_count, last_visit_time, visit_duration = row
                    if last_visit_time:
                        timestamp = datetime(1601, 1, 1) + timedelta(microseconds=last_visit_time)
                        timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp = None

                results.append([url, title, visit_count, visit_duration, timestamp])

            return results

        except sqlite3.Error as e:
            print(f"{browser} 히스토리 데이터베이스 오류: {e}")
            return []
        finally:
            conn.close()
