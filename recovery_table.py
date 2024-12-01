# recovery_table.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt, QThread, Signal
from database import SQLiteTableModel
from no_focus_frame_style import NoFocusFrameStyle
import subprocess
import sys
import os
import sqlite3
import shutil
from datetime import datetime

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

            # parse_process.py 실
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
    # Signal 추가
    recovery_info = Signal(str)   # 정보 메시지 전달
    recovery_error = Signal(str)  # 오류 메시지 전달

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_db_path = ""
        self.recovered_db_path = ""
        self.thread = None
        self.setup_ui()
        
        # Signal 연결
        self.recovery_info.connect(self.on_recovery_info)
        self.recovery_error.connect(self.on_recovery_error)

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
        try:
            print(f"\nRecovery 프로세스 시작: {recovered_db_path}")
            
            recover_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Recover_Output")
            if not os.path.exists(recover_output_dir):
                os.makedirs(recover_output_dir)
            
            self.original_db_path = recovered_db_path
            self.recovered_db_path = os.path.join(recover_output_dir, "recovered_with_sqlite_recovery.db")

            # 1. SQLite Recovery 실행
            print("\n[1단계] SQLite Recovery 실행")
            current_dir = os.path.dirname(os.path.abspath(__file__))
            recovery_path = os.path.join(current_dir, "parse_recovery.py")
            result = subprocess.run(
                [sys.executable, recovery_path, self.original_db_path, self.recovered_db_path],
                check=True, capture_output=True, text=True
            )
            print(result.stdout)
            
            # 2. Process 실행 (re_WindowCapture 테이블 생성)
            print("\n[2단계] Process 실행")
            process_path = os.path.join(current_dir, "parse_process.py")
            result = subprocess.run(
                [sys.executable, process_path, self.recovered_db_path],
                check=True, capture_output=True, text=True
            )
            print(result.stdout)
            
            # 3. WAL 복구 실행
            print("\n[3단계] WAL 복구 실행")
            recovery_wal_path = os.path.join(current_dir, "recovery-wal-app-gui.py")
            result = subprocess.run(
                [sys.executable, recovery_wal_path, self.original_db_path],
                check=True, capture_output=True, text=True
            )
            print(result.stdout)
            
            # 4. WAL DB에서 테이블 복사
            wal_path = os.path.join(recover_output_dir, "recovered_with_wal.db")
            if os.path.exists(wal_path):
                wal_conn = sqlite3.connect(wal_path)
                recovery_conn = sqlite3.connect(self.recovered_db_path)
                
                cursor_wal = wal_conn.cursor()
                cursor_recovery = recovery_conn.cursor()
                
                try:
                    # App 테이블 복사
                    cursor_recovery.execute("DROP TABLE IF EXISTS re_App")
                    cursor_recovery.execute("""
                        CREATE TABLE re_App (
                            Id INTEGER PRIMARY KEY,
                            WindowsAppId TEXT,
                            IconUri TEXT,
                            Name TEXT,
                            Path TEXT,
                            Properties TEXT
                        )
                    """)
                    
                    cursor_wal.execute("SELECT Id, WindowsAppId, IconUri, Name, Path, Properties FROM App")
                    app_data = cursor_wal.fetchall()
                    cursor_recovery.executemany("INSERT INTO re_App VALUES (?, ?, ?, ?, ?, ?)", app_data)
                    print(f"\nApp 테이블 복사 완료: {len(app_data)}개 레코드")
                    
                    # Web 테이블 복사
                    cursor_recovery.execute("DROP TABLE IF EXISTS re_Web")
                    cursor_recovery.execute("""
                        CREATE TABLE re_Web (
                            Id INTEGER PRIMARY KEY,
                            Domain TEXT,
                            Uri TEXT,
                            IconUri TEXT,
                            Properties TEXT
                        )
                    """)
                    
                    cursor_wal.execute("SELECT Id, Domain, Uri, IconUri, Properties FROM Web")
                    web_data = cursor_wal.fetchall()
                    cursor_recovery.executemany("INSERT INTO re_Web VALUES (?, ?, ?, ?, ?)", web_data)
                    print(f"Web 테이블 복사 완료: {len(web_data)}개 레코드")
                    
                    # WindowCaptureAppRelation 테이블 복사
                    cursor_recovery.execute("DROP TABLE IF EXISTS re_WindowCaptureAppRelation")
                    cursor_recovery.execute("""
                        CREATE TABLE re_WindowCaptureAppRelation (
                            WindowCaptureId INTEGER,
                            AppId INTEGER,
                            PRIMARY KEY (WindowCaptureId, AppId)
                        )
                    """)
                    
                    cursor_wal.execute("SELECT WindowCaptureId, AppId FROM WindowCaptureAppRelation")
                    relation_data = cursor_wal.fetchall()
                    cursor_recovery.executemany("INSERT INTO re_WindowCaptureAppRelation VALUES (?, ?)", relation_data)
                    print(f"WindowCaptureAppRelation 테이블 복사 완료: {len(relation_data)}개 레코드")
                    
                    # WindowCaptureWebRelation 테이블 복사
                    cursor_recovery.execute("DROP TABLE IF EXISTS re_WindowCaptureWebRelation")
                    cursor_recovery.execute("""
                        CREATE TABLE re_WindowCaptureWebRelation (
                            WindowCaptureId INTEGER,
                            WebId INTEGER,
                            PRIMARY KEY (WindowCaptureId, WebId)
                        )
                    """)
                    
                    cursor_wal.execute("SELECT WindowCaptureId, WebId FROM WindowCaptureWebRelation")
                    web_relation_data = cursor_wal.fetchall()
                    cursor_recovery.executemany("INSERT INTO re_WindowCaptureWebRelation VALUES (?, ?)", web_relation_data)
                    print(f"WindowCaptureWebRelation 테이블 복사 완료: {len(web_relation_data)}개 레코드")
                    
                    recovery_conn.commit()
                finally:
                    wal_conn.close()
                    recovery_conn.close()

            self.load_recovery_data()

        except Exception as e:
            error_msg = f"복구 스크립트 실행 중 예외 발생: {e}"
            print(f"\n오류: {error_msg}")
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
        try:
            conn = sqlite3.connect(self.recovered_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
            SELECT 
                r.Id, 
                r.Name, 
                r.WindowTitle,
                COALESCE(a.Name, ' 이름 없음 (' || rel.AppId || ')') as AppName,
                COALESCE(w.Uri, '') as Uri,
                CASE 
                    WHEN r.TimeStamp IS NOT NULL 
                    THEN datetime(CAST(CAST(r.TimeStamp AS INTEGER) / 1000 AS INTEGER), 'unixepoch', 'localtime') || '.' ||
                         substr(CAST(CAST(r.TimeStamp AS INTEGER) % 1000 AS TEXT) || '000', 1, 3)
                END as TimeStamp,
                'X' as 이미지
            FROM re_WindowCapture r
            LEFT JOIN re_WindowCaptureAppRelation rel ON r.Id = rel.WindowCaptureId
            LEFT JOIN re_App a ON rel.AppId = a.Id
            LEFT JOIN re_WindowCaptureWebRelation wrel ON r.Id = wrel.WindowCaptureId
            LEFT JOIN re_Web w ON wrel.WebId = w.Id
            ORDER BY r.Id;
            """

            cursor.execute(query)
            data = cursor.fetchall()
            
            if data:
                headers = ["Id", "Name", "WindowTitle", "AppName", "Uri", "TimeStamp", "이미지"]
                formatted_data = []
                for row in data:
                    row_dict = dict(row)
                    formatted_data.append((
                        row_dict['Id'],
                        row_dict['Name'],
                        row_dict['WindowTitle'],
                        row_dict['AppName'],
                        row_dict['Uri'],
                        row_dict['TimeStamp'],
                        row_dict['이미지']
                    ))

                model = SQLiteTableModel(formatted_data, headers)
                self.table_view.setModel(model)
                self.table_view.resizeColumnsToContents()
                return True
            else:
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
            if 'conn' in locals():
                conn.close()

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
