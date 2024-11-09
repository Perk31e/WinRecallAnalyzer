# recovery_table.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt, QThread, Signal
from database import SQLiteTableModel, load_recovery_data
from no_focus_frame_style import NoFocusFrameStyle
from PySide6.QtWidgets import QHeaderView
import subprocess
import sys
import os
import sqlite3

class RecoveryThread(QThread):
    """백그라운드에서 복구 스크립트를 실행하는 스레드."""
    recovery_info = Signal(str)   # 정보 메시지 전달
    recovery_error = Signal(str)  # 오류 메시지 전달

    def __init__(self, parse_recovery_path, parse_process_path, original_db, recovered_db):
        super().__init__()
        self.parse_recovery_path = parse_recovery_path
        self.parse_process_path = parse_process_path
        self.original_db = original_db
        self.recovered_db = recovered_db

    def run(self):
        try:
            # 원본 데이터베이스에 연결
            conn = sqlite3.connect(self.original_db)
            cursor = conn.cursor()
            '''
            # 1. idTable의 첫 번째 Attribute의 NextId 값 확인
            cursor.execute("SELECT NextId FROM idTable LIMIT 1;")
            id_table_row = cursor.fetchone()
            if not id_table_row:
                self.recovery_error.emit("idTable에서 NextId를 가져올 수 없습니다.")
                conn.close()
                return
            next_id = id_table_row[0]
            if next_id <= 10001:
                self.recovery_info.emit(f"idTable의 NextId가 10001 이하입니다: {next_id}\n삭제된 레코드가 없어서 복구할 것이 없습니다.")
                conn.close()
                return
            '''

            # 2. WindowCapture 테이블의 가장 낮은 Id 값 확인
            cursor.execute("SELECT MIN(Id) FROM WindowCapture;")
            window_capture_min_id_row = cursor.fetchone()
            if not window_capture_min_id_row or window_capture_min_id_row[0] is None:
                self.recovery_error.emit("WindowCapture 테이블에서 최소 Id를 가져올 수 없습니다.")
                conn.close()
                return
            window_capture_min_id = window_capture_min_id_row[0]
            if window_capture_min_id <= 8:
                self.recovery_info.emit(f"WindowCapture 테이블의 최소 Id가 8 이하입니다: {window_capture_min_id}\n삭제된 레코드가 없어서 복구할 것이 없습니다.")
                conn.close()
                return

            conn.close()  # 원본 DB 연결 종료

            # 조건을 모두 만족하므로 복구 스크립트 실행

            # parse_recovery.py 실행
            cmd_recovery = [sys.executable, self.parse_recovery_path, self.original_db, self.recovered_db]
            result_recovery = subprocess.run(cmd_recovery, capture_output=True, text=True)
            recovery_output = result_recovery.stdout + "\n" + result_recovery.stderr
            if result_recovery.returncode != 0:
                self.recovery_error.emit(f"parse_recovery.py 오류: {result_recovery.stderr}")
                return

            # parse_process.py 실행
            cmd_process = [sys.executable, self.parse_process_path, self.recovered_db]
            result_process = subprocess.run(cmd_process, capture_output=True, text=True)
            process_output = result_process.stdout + "\n" + result_process.stderr
            if result_process.returncode != 0:
                self.recovery_error.emit(f"parse_process.py 오류: {result_process.stderr}")
                return

            # 모든 출력 메시지를 결합하여 전달
            combined_output = recovery_output + "\n" + process_output
            self.recovery_info.emit("복구 스크립트가 성공적으로 실행되었습니다.")
        except sqlite3.Error as e:
            self.recovery_error.emit(f"원본 데이터베이스 접근 중 오류 발생: {e}")
        except Exception as e:
            self.recovery_error.emit(f"복구 스크립트 실행 중 예외 발생: {e}")

class RecoveryTableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_db_path = ""
        self.recovered_db_path = ""
        self.thread = None  # 현재 실행 중인 스레드
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 상태 레이블 추가
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # QTableView 설정
        self.table_view = QTableView()
        # NoFocusFrameStyle 적용 (필요 시 사용)
        self.table_view.setStyle(NoFocusFrameStyle())
        self.table_view.setSortingEnabled(True)
        layout.addWidget(self.table_view)

        # 정보 메시지 레이블 추가
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.info_label)
        self.info_label.hide()

        # 오류 메시지 레이블 추가
        self.error_label = QLabel("데이터를 불러올 수 없습니다.")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.error_label)
        self.error_label.hide()

    def set_db_paths(self, original_db_path, recovered_db_path):
        """
        데이터베이스 경로를 설정하고 복구 스크립트를 실행합니다.
        """
        # 이전 스레드가 실행 중인 경우 처리 (예: 취소하거나 기다림)
        if self.thread and self.thread.isRunning():
            print("이전 복구 작업이 아직 실행 중입니다. 새로운 복구 작업을 시작합니다.")
            # 필요 시, 스레드를 취소하거나 사용자에게 알림을 추가할 수 있습니다.

        self.original_db_path = original_db_path
        self.recovered_db_path = recovered_db_path

        # GUI 요소 초기화
        self.status_label.setText("복구 조건을 확인 중입니다...")
        self.info_label.hide()
        self.error_label.hide()
        self.table_view.setModel(None)

        # 스크립트 경로 설정 (스크립트가 현재 파일과 같은 디렉토리에 있다고 가정)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parse_recovery_path = os.path.join(current_dir, "parse_recovery.py")
        parse_process_path = os.path.join(current_dir, "parse_process.py")

        # 스크립트 실행 전 기존 recovered_db_path 삭제 (필요 시)
        if os.path.exists(self.recovered_db_path):
            try:
                os.remove(self.recovered_db_path)
                print(f"기존 복구 데이터베이스 파일 '{self.recovered_db_path}'을(를) 삭제했습니다.")
            except Exception as e:
                self.error_label.setText(f"복구 DB 파일 삭제 중 오류 발생: {e}")
                self.error_label.show()
                self.status_label.setText("복구 조건 확인 중 오류가 발생했습니다.")
                return

        # 백그라운드 스레드에서 복구 스크립트 실행
        self.thread = RecoveryThread(
            parse_recovery_path=parse_recovery_path,
            parse_process_path=parse_process_path,
            original_db=self.original_db_path,
            recovered_db=self.recovered_db_path
        )
        self.thread.recovery_info.connect(self.on_recovery_info)
        self.thread.recovery_error.connect(self.on_recovery_error)
        self.thread.start()
        self.status_label.setText("복구 스크립트를 실행 중입니다...")

    def on_recovery_info(self, message):
        """
        정보 메시지를 처리합니다.
        """
        self.status_label.setText("복구 작업 완료.")
        self.info_label.setText(message)
        self.info_label.show()
        self.error_label.hide()

        # 성공적으로 스크립트가 실행된 경우, 복구 데이터를 로드합니다.
        if "성공적으로 실행되었습니다" in message:
            self.load_recovery_data()

    def on_recovery_error(self, message):
        """
        오류 메시지를 처리합니다.
        """
        self.status_label.setText("복구 작업 중 오류 발생.")
        self.error_label.setText(message)
        self.error_label.show()
        self.info_label.hide()

    def load_recovery_data(self):
        """
        re_WindowCapture 테이블에서 데이터를 로드하여 테이블에 설정합니다.
        """
        if not self.recovered_db_path:
            self.error_label.setText("복구된 데이터베이스 경로가 설정되지 않았습니다.")
            self.error_label.show()
            self.table_view.setModel(None)
            return

        data, headers = load_recovery_data(self.recovered_db_path)
        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            self.table_view.resizeColumnsToContents()

            # 헤더 객체 가져오기
            header = self.table_view.horizontalHeader()

            try:
                # 'WindowTitle' 컬럼 인덱스 찾기
                window_title_col = headers.index("WindowTitle")
                # 다른 컬럼 인덱스 (필요 시 추가)
                id_col = headers.index("Id")
                name_col = headers.index("Name")
                app_name_col = headers.index("AppName")
                timestamp_col = headers.index("TimeStamp")
                image_col = headers.index("이미지")

                # 'WindowTitle' 컬럼의 Resize Mode 설정
                header.setSectionResizeMode(window_title_col, QHeaderView.Interactive)
                # 'WindowTitle' 컬럼의 최대 너비 설정 (예: 300)
                self.table_view.setColumnWidth(window_title_col, 300)

                # 다른 컬럼의 Resize Mode 설정 (필요 시 조정)
                header.setSectionResizeMode(id_col, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(name_col, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(app_name_col, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(timestamp_col, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(image_col, QHeaderView.ResizeToContents)

                # 필요 시 다른 컬럼의 너비도 조정
                # 예: self.table_view.setColumnWidth(name_col, 150)
            except ValueError as e:
                print(f"헤더 이름 오류: {e}")

            self.error_label.hide()
            self.info_label.hide()
        else:
            self.table_view.setModel(None)
            self.error_label.setText("re_WindowCapture 데이터를 불러올 수 없습니다.")
            self.error_label.show()
