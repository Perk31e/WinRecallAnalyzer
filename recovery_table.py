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
        self.thread = None
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
        print(f"Recovery 프로세스 시작: {original_db_path}")
        self.original_db_path = original_db_path
        self.recovered_db_path = recovered_db_path
        
        # GUI 요소 초기화
        self.status_label.setText("복구 조건을 확인 중입니다...")
        self.info_label.hide()
        self.error_label.hide()
        self.table_view.setModel(None)

        # 스크립트 경로 설정
        current_dir = os.path.dirname(os.path.abspath(__file__))
        recovery_wal_path = os.path.join(current_dir, "recovery-wal-app-gui.py")
        parse_recovery_path = os.path.join(current_dir, "parse_recovery.py")
        parse_process_path = os.path.join(current_dir, "parse_process.py")

        # WAL 복구 실행
        try:
            print("WAL 복구 시작")
            result = subprocess.run(
                [sys.executable, recovery_wal_path, self.recovered_db_path], 
                check=True,
                capture_output=True,
                text=True
            )
            print("WAL 복구 출력:")
            print(result.stdout)
            if result.stderr:
                print("WAL 복구 오류 출력:")
                print(result.stderr)
            print("WAL 복구 완료")

            # 복구 스크립트 실행
            self.thread = RecoveryThread(
                parse_recovery_path=parse_recovery_path,
                parse_process_path=parse_process_path,
                original_db=self.recovered_db_path,
                recovered_db=os.path.join(os.path.dirname(self.recovered_db_path), "recovered_with_sqlite_recovery.db")
            )
            self.thread.recovery_info.connect(self.on_recovery_info)
            self.thread.recovery_error.connect(self.on_recovery_error)
            self.thread.start()
            
        except subprocess.CalledProcessError as e:
            error_msg = f"WAL 복구 중 오류 발생:\n"
            error_msg += f"표준 출력: {e.stdout}\n"
            error_msg += f"오류 출력: {e.stderr}"
            print(error_msg)
            self.error_label.setText(error_msg)
            self.error_label.show()

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
        복구된 데이터를 로드합니다.
        """
        if not self.recovered_db_path or not self.original_db_path:
            print("데이터베이스 경로가 설정되지 않음")
            self.error_label.setText("데이터베이스 경로가 설정되지 않았습니다.")
            self.error_label.show()
            self.table_view.setModel(None)
            return

        try:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Recover_Output")
            print(f"Output 디렉토리: {output_dir}")
            
            # recovered_with_sqlite_recovery.db에서 re_WindowCapture 데이터 로드
            recovery_path = os.path.join(output_dir, "recovered_with_sqlite_recovery.db")
            print(f"복구 DB 경로: {recovery_path}")
            if not os.path.exists(recovery_path):
                print(f"복구 DB 파일 없음: {recovery_path}")
                raise sqlite3.Error(f"복구된 데이터베이스 파일을 찾을 수 없습니다: {recovery_path}")
            recovery_conn = sqlite3.connect(recovery_path)
            
            # recovered_with_wal.db에서 App과 WindowCaptureAppRelation 데이터 로드
            wal_path = os.path.join(output_dir, "recovered_with_wal.db")
            print(f"WAL DB 경로: {wal_path}")
            if not os.path.exists(wal_path):
                print(f"WAL DB 파일 없음: {wal_path}")
                # WAL 파일이 없는 경우 re_WindowCapture 테이블만 사용
                query = """
                SELECT 
                    Id, 
                    Name, 
                    WindowTitle,
                    '' as AppName,
                    TimeStamp,
                    'X' as 이미지
                FROM re_WindowCapture
                ORDER BY Id;
                """
                print("WAL 없이 쿼리 실행")
                cursor = recovery_conn.cursor()
            else:
                print("WAL DB 연결 시도")
                recovery_conn.execute(f"ATTACH DATABASE '{wal_path}' AS wal_db")
                query = """
                SELECT 
                    r.Id, 
                    r.Name, 
                    r.WindowTitle,
                    COALESCE(a.Name, '') as AppName,
                    r.TimeStamp,
                    'X' as 이미지
                FROM re_WindowCapture r
                LEFT JOIN wal_db.WindowCaptureAppRelation w ON r.Id = w.WindowCaptureId
                LEFT JOIN wal_db.App a ON w.AppId = a.Id
                ORDER BY r.Id;
                """
                print("WAL DB와 함께 쿼리 실행")
                cursor = recovery_conn.cursor()

            print("쿼리 실행 시작")
            cursor.execute(query)
            print("쿼리 실행 완료")
            data = cursor.fetchall()
            print(f"가져온 데이터 수: {len(data)}")
            headers = ["Id", "Name", "WindowTitle", "AppName", "TimeStamp", "이미지"]

            if data:
                print("데이터 모델 생성")
                model = SQLiteTableModel(data, headers)
                self.table_view.setModel(model)
                self.table_view.resizeColumnsToContents()
                print("테이블 뷰 업데이트 완료")
                return True
            else:
                print("가져온 데이터 없음")
                self.error_label.setText("복구된 데이터가 없습니다.")
                self.error_label.show()
                return False

        except sqlite3.Error as e:
            print(f"SQLite 오류: {e}")
            self.error_label.setText(f"데이터 로드 오류: {e}")
            self.error_label.show()
            return False
        except Exception as e:
            print(f"일반 오류: {e}")
            self.error_label.setText(f"데이터 로드 오류: {e}")
            self.error_label.show()
            return False
        finally:
            if 'recovery_conn' in locals():
                print("DB 연결 종료")
                recovery_conn.close()

    def run_wal_recovery(self, recovery_wal_path):
        """WAL 복구 스크립를 실행합니다."""
        try:
            print(f"WAL 복구 시작: {self.original_db_path}")  # 디버깅을 위한 로그 추가
            result = subprocess.run(
                [sys.executable, recovery_wal_path, self.original_db_path], 
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)  # 표준 출력 내용 출력
            print("WAL 복구가 완료되었습니다.")
            self.status_label.setText("WAL 복구가 완료되었습니다.")
            self.load_recovery_data()  # WAL 복구가 완료된 후 데이터 로드
        except subprocess.CalledProcessError as e:
            error_msg = f"WAL 복구 중 오류 발생: {e}\n표준 출력: {e.stdout}\n오류 출력: {e.stderr}"
            print(error_msg)  # 터미널에 오류 내용 출력
            self.error_label.setText(error_msg)
            self.error_label.show()
            self.status_label.setText("WAL 복구 중 오류가 발생했습니다.")
