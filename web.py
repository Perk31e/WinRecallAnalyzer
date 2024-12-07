# web.py

import shutil
import sqlite3
import os
import glob
import re
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
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
    """
    Edge 및 Chrome 브라우저 제목에서 주요 정보만 추출하고 공백 문제를 해결
    """
    if not title:
        return None

    # 1. 보이지 않는 공백 문자 제거 (예: \u200b, \xa0 등)
    title = re.sub(r"[\u200b\xa0]+", " ", title)

    # 2. 일반 공백으로 통일
    title = re.sub(r"\s+", " ", title)

    # 3. Edge 브라우저 관련 패턴 제거
    title = re.sub(r" 외 페이지 \d+개", "", title)  # "외 페이지 X개" 제거
    title = re.sub(r" - 프로필 \d+", "", title)    # "- 프로필 Y" 제거
    title = re.sub(r" - Microsoft Edge$", "", title)  # "- Microsoft Edge" 제거
    title = re.sub(r"Microsoft Edge$", "", title)     # 단독 "Microsoft Edge" 제거

    # 4. Chrome 브라우저 관련 패턴 제거
    title = re.sub(r" - Chrome$", "", title)  # "- Chrome" 제거

    # 5. 공백과 하이픈 정리
    title = title.strip("- ")  # 양쪽 불필요한 '-'와 공백 제거

    return title.strip() if title.strip() else None

class DetailDialog(QDialog):
    def __init__(self, data, headers):
        super().__init__
        self.data = data
        self.headers = headers

        self.setup_ui()

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

# SQLiteTableModel 클래스
class SQLiteTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super().__init__()
        self._data = data
        self._headers = headers

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._data[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._headers[section]
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole and index.isValid():
            # proxy_model에서 source_model로 매핑
            if hasattr(self, "proxy_model"):
                source_index = self.proxy_model.mapToSource(index)
                row, column = source_index.row(), source_index.column()
            else:
                row, column = index.row(), index.column()

            print(f"[DEBUG] setData called for row: {row}, column: {column}")
            print(f"[DEBUG] Current data before modification: {self._data[row]}")

            # 실제 데이터 업데이트
            self._data[row][column] = value
            print(f"[DEBUG] Updated data: {self._data[row]}")

            # 데이터 변경 알림
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True
        return False

    def sort(self, column, order=Qt.AscendingOrder):
        """Sort data by column."""
        self.layoutAboutToBeChanged.emit()
        self._data.sort(
            key=lambda row: (row[column] is None, row[column]),
            reverse=(order == Qt.DescendingOrder)
        )
        self.layoutChanged.emit()

    def removeRow(self, row, parent=QModelIndex()):
        if 0 <= row < len(self._data):
            print(f"[DEBUG] Removing row {row}: {self._data[row]}")
            self.beginRemoveRows(parent, row, row)
            del self._data[row]
            self.endRemoveRows()
            return True
        return False


class WebTableWidget(QWidget):
    def __init__(self, db_path=None, current_mode=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path  # 부모로부터 전달받은 DB 경로
        self.current_mode = current_mode  # 부모로부터 전달받은 모드
        self.history_db_path = None
        self.user_path = os.path.expanduser("~")
        self.history_folder = os.path.join(self.user_path, "Desktop", "Recall_load", "Browser_History")

        # UI 및 모델 초기화
        self.setup_ui()
        self.setup_model()

        # 데이터 로드
        if self.db_path:
            self.load_data()

    def set_db_path(self, db_path):
        """DB 경로 설정"""
        if not db_path or not os.path.exists(db_path):
            print("WebTable에서 잘못된 데이터베이스 경로가 전달되었습니다.")
            return  # 잘못된 경로인 경우 로직 종료

        print(f"WebTable에서 데이터베이스 경로가 설정되었습니다: {db_path}")

        # DB 경로 저장
        self.db_path = db_path

        try:
            # 데이터 로드 실행
            self.load_data()
        except Exception as e:
            print(f"WebTable 데이터 로드 중 오류 발생: {e}")


    def setup_ui(self):
        """UI 설정"""
        layout = QSplitter(Qt.Horizontal, self)

        # 테이블 뷰
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)
        self.table_view.setStyle(NoFocusFrameStyle())  # 포커스 프레임 스타일 적용
        layout.addWidget(self.table_view)

        # 데이터 뷰어
        self.data_viewer = QTextEdit("데이터 프리뷰")
        self.data_viewer.setReadOnly(True)
        layout.addWidget(self.data_viewer)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(layout)
        self.setLayout(main_layout)

        # 클릭 이벤트 연결
        self.table_view.clicked.connect(self.display_related_history_data)

    def setup_model(self):
        """필터 및 ��렬 모델 설정"""
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterKeyColumn(1)  # Window Title 열 필터링
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_view.setModel(self.proxy_model)

        # 브라우저 키워드 설정
        self.browser_keywords = ["Chrome", "Firefox", "Edge", "Whale"]
        self.filter_browser_data()

    def load_data(self):
        """테이블에 데이터를 로드하면서 연관 데이터를 바로 비교하여 설정합니다."""
        if self.db_path:
            new_data, headers = load_web_data(self.db_path)
            print(f"[DEBUG] 로드된 데이터 개수: {len(new_data)}")  # 디버깅: 로드된 데이터 개수 확인

            if new_data:
                # Related Data 열 추가
                if "Related Data" not in headers:
                    headers.append("Related Data")

                # 기존 데이터를 유지하고 확장
                extended_data = []
                for row in new_data:
                    title = row[1]  # 타이틀
                    timestamp = row[2]  # 타임스탬프

                    # Related Data 상태 확인
                    related_data_status = self.check_related_data(timestamp, title)

                    # 기존 행에 상태 추가
                    extended_data.append(list(row) + [related_data_status])

                # 데이터 모델 갱신
                self._data = extended_data
                print(f"[DEBUG] 갱신된 데이터 개수: {len(self._data)}")  # 디버깅

                # 새로운 모델 생성 및 설정
                model = SQLiteTableModel(self._data, headers)
                self.proxy_model.setSourceModel(model)
                self.table_view.setModel(self.proxy_model)
                self.table_view.resizeColumnToContents(len(headers) - 1)

                print("[DEBUG] 데이터가 성공적으로 로드되었습니다.")
            else:
                print("[DEBUG] 로드된 데이터가 비어 있습니다.")
                self._data = []  # 데이터를 초기화
                self.table_view.setModel(None)

    def filter_browser_data(self):
        """브라우저 관련 데이터 필터링"""
        pattern = "|".join(self.browser_keywords)  # "Chrome|Firefox|Edge|Whale"
        self.proxy_model.setFilterRegularExpression(pattern)

    def set_history_db_path(self, history_file_path):
        """히스토리 DB 파일 경로 설정"""
        self.history_db_path = history_file_path
        print(f"히스토리 파일 경로 설정됨: {self.history_db_path}")

        # 그 외 필요한 후속 작업
        self.display_related_history_data()  # 필요에 따라 추가

    def check_related_data(self, timestamp_ukg, title_ukg):
        """연관 데이터 확인 (히스토리 파일 기반)"""
        if not self.history_db_path or title_ukg is None or timestamp_ukg is None:
            return "X"  # 연관 데이터 없음 (X)

        conn = None
        try:
            # timestamp_ukg가 문자열일 경우 변환
            if isinstance(timestamp_ukg, str):
                try:
                    timestamp_ukg = float(datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").timestamp()) * 1000
                except ValueError:
                    return "X"  # 변환 실패 시 연관 데이터 없음 (X)

            # SQLite 연결 및 사용자 정의 REGEXP 함수 생성
            conn = sqlite3.connect(self.history_db_path)
            conn.create_function("REGEXP", 2, regexp)
            cursor = conn.cursor()

            # ukg.db 타임스탬프를 KST로 변환
            try:
                kst_time_ukg = datetime.fromtimestamp(timestamp_ukg / 1000, tz=timezone.utc).astimezone(
                    timezone(timedelta(hours=9))
                )
                ukg_unix_timestamp = int(kst_time_ukg.timestamp())
            except ValueError:
                return "X"  # 변환 실패 시 연관 데이터 없음 (X)

            # 타이틀 간소화
            simplified_title = simplify_title(title_ukg)

            # 히스토리 데이터와 연관성 확인
            query = "SELECT title, last_visit_time FROM urls WHERE title REGEXP ?"
            cursor.execute(query, (simplified_title,))
            data = cursor.fetchall()

            if not data:
                return "X"  # 연관 데이터 없음 (X)

            # 연관 데이터 검증
            for row in data:
                chrome_title = row[0]
                chrome_time = row[1]

                try:
                    # Chrome 타임스탬프 변환
                    kst_time_converted = convert_chrome_timestamp(chrome_time).astimezone(
                        timezone(timedelta(hours=9))
                    )
                    browser_unix_timestamp = int(kst_time_converted.timestamp())
                except Exception:
                    continue

                # ±1초의 매칭 허용
                if chrome_title == simplified_title and abs(browser_unix_timestamp - ukg_unix_timestamp) <= 1:
                    return "O"  # 연관 데이터 있음 (O)

            return "X"  # 연관 데이터 없음 (X)

        except sqlite3.Error:
            return "X"  # 오류 발생 시 연관 데이터 없음 (X)

        finally:
            if conn:
                conn.close()

    def update_related_data_status(self):
        print("[DEBUG] update_related_data_status 호출됨.")
        if not self.history_db_path:
            print("[DEBUG] 히스토리 파일 경로가 설정되지 않았습니다.")
            return

        model = self.table_view.model()
        if not model:
            print("[DEBUG] 모델이 초기화되지 않았습니다.")
            return

        # "Related Data" 열의 인덱스 확인
        related_data_column_index = -1
        for column_index in range(model.columnCount()):
            header_data = model.headerData(column_index, Qt.Horizontal)
            if header_data == "Related Data":
                related_data_column_index = column_index
                break

        if related_data_column_index == -1:
            print("[DEBUG] 'Related Data' 열을 찾을 수 없습니다.")
            return

        rows_to_delete = []

        for row in range(model.rowCount()):
            title = model.index(row, 1).data()  # 타이틀 열
            timestamp = model.index(row, 2).data()  # 타임스탬프 열
            simplified_title = simplify_title(title)

            if not simplified_title:
                continue

            # Check if the data is related
            related_data_status = self.check_related_data(timestamp, simplified_title)
            current_status = model.index(row, related_data_column_index).data()

            # If current status is 'X' but should be 'O', mark for deletion
            if current_status == "X" and related_data_status == "O":
                rows_to_delete.append(row)

            # Update only if the status changes
            if current_status != related_data_status:
                print(f"[DEBUG] 행 {row}의 Related Data 변경: {current_status} -> {related_data_status}")
                model.setData(
                    model.index(row, related_data_column_index), related_data_status
                )

        # Remove rows with 'X' that should not exist
        for row in reversed(rows_to_delete):  # Reverse to avoid index shifting
            print(f"[DEBUG] Removing row {row}: {model._data[row]}")
            model.removeRow(row)

        model.layoutChanged.emit()  # Refresh the view
        print("[DEBUG] update_related_data_status 완료.")

    def display_related_history_data(self, index=None):
        """
        선택된 행의 관련 히스토리 데이터를 오른쪽 데이터 뷰어에 표시합니다.
        """
        if index is None:
            self.data_viewer.setText("히스토리 데이터를 표시할 인덱스가 없습니다.")
            return

        if not self.history_db_path:
            self.data_viewer.setText("히스토리 파일 경로가 설정되지 않았습니다.")
            return

        # 테이블에서 선택된 타이틀과 타임스탬프 가져오기
        selected_title = self.table_view.model().index(index.row(), 1).data()
        timestamp_ukg = self.table_view.model().index(index.row(), 2).data()

        if not selected_title or not timestamp_ukg:
            self.data_viewer.setText("선택된 타이틀 또는 타임스탬프가 비어 있습니다.")
            return

        # 타이틀 간소화
        simplified_title = simplify_title(selected_title)

        try:
            # SQLite 연결
            conn = sqlite3.connect(self.history_db_path)
            conn.create_function("REGEXP", 2, regexp)
            cursor = conn.cursor()

            # 타임스탬프를 KST로 변환
            try:
                kst_time = datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone(timedelta(hours=9))
                )
                unix_timestamp = int(kst_time.timestamp())
            except ValueError as e:
                self.data_viewer.setText(f"타임스탬프 변환 오류가 발생했습니다: {e}")
                return

            # 히스토리 데이터 쿼리
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
                browser_unix_timestamp = int(kst_time_converted.timestamp())

                # ±1초 허용
                if (
                        simplified_title == chrome_title
                        and abs(browser_unix_timestamp - unix_timestamp) <= 1
                ):
                    related_data.append(row)

            # 데이터 뷰어에 결과 표시
            if related_data:
                formatted_data = []
                for row in related_data:
                    last_visit_time = row[3]
                    converted_time = convert_chrome_timestamp(last_visit_time).astimezone(
                        timezone(timedelta(hours=9))
                    )
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

    def copy_history_files(self, destination_folder):
        """브라우저 히스토리 파일 복사"""
        # Browser_History 폴더 경로 설정
        browser_history_folder = os.path.join(destination_folder, "Browser_History")
        os.makedirs(browser_history_folder, exist_ok=True)

        history_paths = {
            "Chrome": os.path.join(self.user_path, r"AppData\Local\Google\Chrome\User Data\Default\History"),
            "Edge": os.path.join(self.user_path, r"AppData\Local\Microsoft\Edge\User Data\Default\History"),
        }

        for browser, path in history_paths.items():
            try:
                if os.path.exists(path):
                    dst_path = os.path.join(browser_history_folder, f"{browser}_History")
                    shutil.copy2(path, dst_path)
                    print(f"{browser} 히스토리 파일이 성공적으로 복사되었습니다: {dst_path}")
                else:
                    print(f"{browser} 히스토리 파일 경로가 존재하지 않습니다: {path}")
            except Exception as e:
                print(f"{browser} 히스토리 파일 복사 중 오류: {e}")
