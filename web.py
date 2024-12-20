# web.py

import shutil
import sqlite3
import os
import glob
import re
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QTextEdit, QSplitter, QDialog, QMessageBox, QFrame, \
    QSpacerItem, QSizePolicy, QHBoxLayout, QLabel, QStyledItemDelegate
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
    Edge, Chrome 및 Whale 브라우저 제목에서 주요 정보만 추출하고 공백 문제를 해결
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

    # 5. Whale 브라우저 관련 패턴 제거
    title = re.sub(r" - Whale$", "", title)  # "- Whale" 제거
    title = re.sub(r" - 프로필 \d+ - Whale$", "", title)  # "- 프로필 Y - Whale" 제거
    title = re.sub(r"Naver Whale$", "", title)  # 단독 "Naver Whale" 제거

    # 6. 공백과 하이픈 정리
    title = title.strip("- ")  # 양쪽 불필요한 '-'와 공백 제거

    return title.strip() if title.strip() else None


class CenterAlignedDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.column() == related_data_column_index:  # Related Data 열의 인덱스
            option.displayAlignment = Qt.AlignCenter


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
            # ProxyModel로부터 SourceModel로 변환
            source_index = self.proxy_model.mapToSource(index) if hasattr(self, "proxy_model") else index
            row, column = source_index.row(), source_index.column()

            print(f"[DEBUG] setData called for row: {row}, column: {column}")
            print(f"[DEBUG] Current data before modification: {self._data[row]}")

            # 데이터 변경
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

    def removeRow(self, proxy_row, parent=QModelIndex()):
        # 프록시 인덱스를 소스 인덱스로 변환
        if hasattr(self, "proxy_model"):
            source_model = self.proxy_model.sourceModel()
            source_row = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0)).row()
        else:
            source_model = self
            source_row = proxy_row

        if 0 <= source_row < len(source_model._data):  # 소스 데이터에서 삭제
            print(f"[DEBUG] Removing row {source_row}: {source_model._data[source_row]}")
            source_model.beginRemoveRows(parent, source_row, source_row)
            del source_model._data[source_row]
            source_model.endRemoveRows()
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
        """모델 초기화 및 열 크기 고정."""
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterKeyColumn(1)  # 필터링 기준 열 설정
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table_view.setModel(self.proxy_model)

        # 열 크기를 바로 설정
        self.adjust_column_widths()

        # 브라우저 키워드 설정
        self.browser_keywords = ["Chrome", "Firefox", "Edge", "Whale"]
        self.filter_browser_data()

    def adjust_column_widths(self):
        """열 크기를 고정."""
        view = self.table_view
        model = view.model()

        if not model:
            return

        # 고정 열 크기 설정
        fixed_widths = {0: 150, 1: 300, 2: 200, 3: 100}  # 열 인덱스: 고정 너비
        for column in range(model.columnCount()):
            if column in fixed_widths:
                view.setColumnWidth(column, fixed_widths[column])
            else:
                view.resizeColumnToContents(column)

    def load_data(self):
        """데이터 로드 및 열 크기 고정."""
        if self.db_path:
            new_data, headers = load_web_data(self.db_path)
            print(f"[DEBUG] 로드된 데이터 개수: {len(new_data)}")

            if new_data:
                if "Related Data" not in headers:
                    headers.append("Related Data")

                # 기존 데이터를 유지하고 확장
                extended_data = []
                for row in new_data:
                    title = row[1]  # 타이틀
                    timestamp = row[2]  # 타임스탬프
                    related_data_status = self.check_related_data(timestamp, title)
                    extended_data.append(list(row) + [related_data_status])

                # 데이터 모델 갱신
                self._data = extended_data
                print(f"[DEBUG] 갱신된 데이터 개수: {len(self._data)}")

                # SourceModel과 ProxyModel 초기화
                model = SQLiteTableModel(self._data, headers)
                self.proxy_model.setSourceModel(model)
                self.table_view.setModel(self.proxy_model)

                # 데이터 로드 후 열 크기 고정
                self.adjust_column_widths()
                print("[DEBUG] 데이터가 성공적으로 로드되었습니다.")
            else:
                print("[DEBUG] 로드된 데이터가 비어 있습니다.")
                self._data = []
                self.table_view.setModel(None)

    def filter_browser_data(self):
        """브라우저 관련 데이터 필터링"""
        pattern = "|".join(self.browser_keywords)  # "Chrome|Firefox|Edge|Whale"
        self.proxy_model.setFilterRegularExpression(pattern)

    def set_history_db_path(self, history_file_path):
        """
        히스토리 DB 파일 경로 설정. 여러 경로를 관리할 수 있도록 확장.
        """
        # 기존 경로가 리스트가 아닌 경우 초기화
        if not hasattr(self, "history_db_paths") or not isinstance(self.history_db_paths, list):
            self.history_db_paths = []

        # 경로가 이미 리스트에 포함되어 있지 않으면 추가
        if history_file_path not in self.history_db_paths:
            self.history_db_paths.append(history_file_path)
            print(f"히스토리 파일 경로 추가됨: {history_file_path}")
        else:
            print(f"히스토리 파일 경로가 이미 추가되어 있습니다: {history_file_path}")

        # 기존 동작과 호환성을 위해 첫 번째 파일을 self.history_db_path로 설정
        self.history_db_path = self.history_db_paths[0] if self.history_db_paths else None

        # 기존 호출 유지
        self.display_related_history_data()

    def check_related_data(self, timestamp_ukg, title_ukg):
        """연관 데이터 확인 (여러 히스토리 파일 기반)"""
        # 히스토리 파일 리스트가 없거나 제목/타임스탬프가 None이면 X 반환
        if not hasattr(self,
                       "history_db_paths") or not self.history_db_paths or title_ukg is None or timestamp_ukg is None:
            return "X"

        # timestamp_ukg가 문자열일 경우 변환
        if isinstance(timestamp_ukg, str):
            try:
                timestamp_ukg = float(datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").timestamp()) * 1000
            except ValueError:
                return "X"

        simplified_title = simplify_title(title_ukg)

        # 모든 히스토리 파일을 순회하며 연관 데이터 확인
        for history_db_path in self.history_db_paths:
            conn = None
            try:
                # SQLite 연결 및 사용자 정의 REGEXP 함수 생성
                conn = sqlite3.connect(history_db_path)
                conn.create_function("REGEXP", 2, regexp)
                cursor = conn.cursor()

                # ukg.db 타임스탬프를 KST로 변환
                try:
                    kst_time_ukg = datetime.fromtimestamp(timestamp_ukg / 1000, tz=timezone.utc).astimezone(
                        timezone(timedelta(hours=9))
                    )
                    ukg_unix_timestamp = int(kst_time_ukg.timestamp())
                except ValueError:
                    continue

                # 히스토리 데이터와 연관성 확인
                query = "SELECT title, last_visit_time FROM urls WHERE title REGEXP ?"
                cursor.execute(query, (simplified_title,))
                data = cursor.fetchall()

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
                        return "O"  # 연관 데이터 있음

            except sqlite3.Error as e:
                print(f"[DEBUG] SQLite 오류 발생: {e}")
            finally:
                if conn:
                    conn.close()

        return "X"  # 모든 히스토리 파일에서 연관 데이터 없음

    def update_related_data_status(self):
        print("[DEBUG] update_related_data_status 호출됨.")
        if not self.history_db_path:
            print("[DEBUG] 히스토리 파일 경로가 설정되지 않았습니다.")
            return

        proxy_model = self.proxy_model
        source_model = proxy_model.sourceModel() if proxy_model else self

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
                model.setData(model.index(row, related_data_column_index), related_data_status)

        # Remove rows with 'X' that should not exist
        for proxy_row in reversed(rows_to_delete):  # Reverse to avoid index shifting
            print(f"[DEBUG] Removing row in proxy: {proxy_row}")
            if hasattr(model, "removeRow"):
                model.removeRow(proxy_row)
            else:
                print(f"[DEBUG] 'removeRow' 메서드가 모델에 정의되지 않았습니다.")

        print("[DEBUG] update_related_data_status 완료.")

    def display_related_history_data(self, indexes=None):
        """
        선택된 행의 관련 히스토리 데이터를 오른쪽 데이터 뷰어에 HTML 표 형식으로 표시합니다.
        """
        if not indexes:
            self.data_viewer.setHtml("<p>히스토리 데이터를 표시할 인덱스가 없습니다.</p>")
            return

        if not hasattr(self, "history_db_paths") or not self.history_db_paths:
            self.data_viewer.setHtml("<p>히스토리 파일 경로가 설정되지 않았습니다.</p>")
            return

        # 단일 QModelIndex를 리스트로 변환
        if isinstance(indexes, QModelIndex):
            indexes = [indexes]

        table_rows = []  # 테이블의 행 데이터를 저장

        for index in indexes:
            # 테이블에서 선택된 타이틀과 타임스탬프 가져오기
            selected_title = self.table_view.model().index(index.row(), 1).data()
            timestamp_ukg = self.table_view.model().index(index.row(), 2).data()

            if not selected_title or not timestamp_ukg:
                table_rows.append("<tr><td colspan='4'>선택된 타이틀 또는 타임스탬프가 비어 있습니다.</td></tr>")
                continue

            simplified_title = simplify_title(selected_title)

            for history_db_path in self.history_db_paths:
                try:
                    # SQLite 연결
                    conn = sqlite3.connect(history_db_path)
                    conn.create_function("REGEXP", 2, regexp)
                    cursor = conn.cursor()

                    # 타임스탬프를 KST로 변환
                    try:
                        kst_time = datetime.strptime(timestamp_ukg, "%Y-%m-%d %H:%M:%S").replace(
                            tzinfo=timezone(timedelta(hours=9))
                        )
                        unix_timestamp = int(kst_time.timestamp())
                    except ValueError as e:
                        table_rows.append(f"<tr><td colspan='4'>타임스탬프 변환 오류: {e}</td></tr>")
                        continue

                    # 히스토리 데이터 쿼리
                    query = "SELECT url, title, visit_count, last_visit_time FROM urls WHERE title REGEXP ?"
                    cursor.execute(query, (simplified_title,))
                    data = cursor.fetchall()

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
                            converted_time = convert_chrome_timestamp(row[3]).astimezone(
                                timezone(timedelta(hours=9))
                            )
                            table_rows.append(
                                f"<tr>"
                                f"<td style='border: 1px solid #ddd; padding: 8px; width: 200px; overflow: hidden; text-overflow: ellipsis;'>{row[0]}</td>"
                                f"<td style='border: 1px solid #ddd; padding: 8px; width: 200px; overflow: hidden; text-overflow: ellipsis;'>{row[1]}</td>"
                                f"<td style='border: 1px solid #ddd; padding: 8px; width: 100px; text-align: center;'>{row[2]}</td>"
                                f"<td style='border: 1px solid #ddd; padding: 8px; width: 150px;'>{converted_time}</td>"
                                f"</tr>"
                            )

                except sqlite3.Error as e:
                    table_rows.append(f"<tr><td colspan='4'>히스토리 데이터를 로드하는 중 오류: {e}</td></tr>")
                finally:
                    if conn:
                        conn.close()

        # 테이블 HTML 생성
        if table_rows:
            html_content = (
                    "<div style='width: 700px; height: 300px; overflow: auto; border: 1px solid #ddd;'>"
                    "<table style='width: 100%; border-collapse: collapse; font-size: 14px;'>"
                    "<thead>"
                    "<tr style='background-color: #f2f2f2;'>"
                    "<th style='border: 1px solid #ddd; padding: 10px; width: 200px;'>URL</th>"
                    "<th style='border: 1px solid #ddd; padding: 10px; width: 200px;'>Title</th>"
                    "<th style='border: 1px solid #ddd; padding: 10px; width: 100px; text-align: center;'>Visit Count</th>"
                    "<th style='border: 1px solid #ddd; padding: 10px; width: 150px;'>Last Visit Time</th>"
                    "</tr>"
                    "</thead>"
                    "<tbody>"
                    + "".join(table_rows) +
                    "</tbody>"
                    "</table>"
                    "</div>"
            )
        else:
            html_content = "<p>연관된 히스토리 데이터를 찾을 수 없습니다.</p>"

        # 텍스트 박스에 HTML 설정
        self.data_viewer.setHtml(html_content)

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
