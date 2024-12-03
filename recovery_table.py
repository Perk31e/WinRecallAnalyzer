# recovery_table.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt, QThread, Signal
from database import SQLiteTableModel, load_recovery_data_from_db
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
        
        # 기존의 self 시그널 연결 제거
        # self.recovery_info.connect(self.on_recovery_info)
        # self.recovery_error.connect(self.on_recovery_error)

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
            '''
            1. WindowCapture 테이블 확인
                - 데이터베이스의 WindowCapture 테이블을 검사
                - 삭제된 레코드가 있는지 확인
                - 복구가 필요한지 판단
            '''
            print("\n[1단계] WindowCapture 테이블 확인")
            print(f"확인할 DB 파일 경로: {recovered_db_path}")
            conn = sqlite3.connect(recovered_db_path)
            cursor = conn.cursor()

            # 테이블 존재 여부 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='WindowCapture'")
            if cursor.fetchone() is None:
                print(f"현재 DB에 존재하는 테이블 목록:")
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                for table in tables:
                    print(f"- {table[0]}")

            # 최소값과 최대값 조회
            cursor.execute("SELECT MIN(Id), MAX(Id) FROM WindowCapture;")
            window_capture_row = cursor.fetchone()
            window_capture_min_id = window_capture_row[0]
            window_capture_max_id = window_capture_row[1]

            # IdTable의 NextId 값 조회
            cursor.execute("SELECT NextId FROM IdTable;")
            id_table_row = cursor.fetchone()
            id_table_next_id = id_table_row[0] if id_table_row else None

            if not window_capture_row or window_capture_min_id is None:
                self.on_recovery_error("WindowCapture 테이블에서 최소 Id를 가져올 수 없습니다.")
                conn.close()
                return

            if window_capture_min_id <= 8:
                self.on_recovery_info(
                    f"WindowCapture 테이블의 최소 Id 및 최대 Id는 다음과 같습니다: {window_capture_min_id}, {window_capture_max_id}\n"
                    f"IdTable 테이블의 NextId 값: {id_table_next_id}\n"
                    "삭제된 레코드가 없어서 복구할 것이 없습니다."
                )
                conn.close()
                return

            conn.close()
            '''
            2. 복구 준비 작업
                - Recover_Output 디렉토리 설정
                - 기존 파일 정리
                - 복구 준비 작업 수행
            '''
            print("\n[2단계] 복구 준비 작업")
            
            # Recover_Output 디렉토리 설정
            recover_output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Recover_Output")
            if not os.path.exists(recover_output_dir):
                os.makedirs(recover_output_dir)
            
            # 기존 파일들의 연결을 닫고 삭제
            self.table_view.setModel(None)  # 테이블 모델 연결 해제
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            
            # recovered_with_sqlite_recovery.db 파일이 존재하면 삭제
            self.recovered_db_path = os.path.join(recover_output_dir, "recovered_with_sqlite_recovery.db")
            if os.path.exists(self.recovered_db_path):
                try:
                    os.remove(self.recovered_db_path)
                    print(f"기존 recovered_with_sqlite_recovery.db 파일을 삭제했습니다.")
                except Exception as e:
                    print(f"파일 삭제 중 오류 발생: {e}")
                
            # remained.db-wal 파일 경로 설정
            remained_wal = os.path.join(recover_output_dir, "remained.db-wal")
            
            # Recover_Output 디렉토리에서 remained.db-wal 파일 확인
            if not os.path.exists(remained_wal):
                print(f"WAL 파일을 찾을 수 없습니다: {remained_wal}")
            else:
                print(f"WAL 파일을 찾았습니다: {remained_wal}")
            
            # 경로 설정
            self.original_db_path = os.path.join(recover_output_dir, "recovered_with_wal.db")
            self.recovered_db_path = os.path.join(recover_output_dir, "recovered_with_sqlite_recovery.db")
            
            # 원본 DB 파일을 recovered_with_wal.db로 복사
            shutil.copy2(original_db_path, self.original_db_path)
            print(f"원본 DB를 복사했습니다: {self.original_db_path}")
            
            '''
            3. WAL 복구 실행 전 DB 연결 닫기
                - parse_recover.py 수행
                - 실제 SQLite 복구 작업 수행
                - 삭제된 레코드 복구 (lost and found 테이블 생성됨)
            '''
            print("\n[3단계] SQLite Recovery 실행")
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                print("기존 DB 연결을 닫았습니다.")
            
            current_dir = os.path.dirname(os.path.abspath(__file__))
            recovery_path = os.path.join(current_dir, "parse_recovery.py")
            try:
                result = subprocess.run(
                    [sys.executable, recovery_path, self.original_db_path, self.recovered_db_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"parse_recovery.py 실행 중 오류:\n출력: {e.stdout}\n오류: {e.stderr}")
                raise
            
            '''
            4. Process 실행
                - parse_process.py 수행
                - re_WindowCapture 테이블 생성
                - 생성된 lost and found 테이블에서 windowcapture 레코드를 추출하여 re_windowcapture 테이블에 저장
            '''
            print("\n[4단계] Process 실행")
            process_path = os.path.join(current_dir, "parse_process.py")
            try:
                result = subprocess.run(
                    [sys.executable, process_path, self.recovered_db_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"parse_process.py 실행 중 오류:\n출력: {e.stdout}\n오류: {e.stderr}")
                raise

            '''
            5. WAL 복구 실행
                - recovery-wal-app-gui.py 수행
                - WAL 파일에서 데이터 복구
            '''
            print("\n[5단계] WAL 복구 실행")
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                print("기존 DB 연결을 닫았습니다.")
            
            recovery_wal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovery-wal-app-gui.py")
            result = subprocess.run(
                [sys.executable, recovery_wal_path, self.original_db_path],
                check=True, capture_output=True, text=True
            )
            print(result.stdout)

            ''' 
            6. WAL DB에서 테이블 복사
                - 복구된 데이터베이스에서 테이블 복사
                - re_App, re_Web, re_WindowCaptureAppRelation, re_WindowCaptureWebRelation 테이블 복사
            '''
            print("\n[6단계] WAL DB에서 테이블 복사")
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
                    print("테이블 복사 작업이 완료되었습니다.")
                finally:
                    wal_conn.close()
                    recovery_conn.close()

            '''
            7. 복구 완료 메시지 표시
                - 복구 결과 확인
                - 결과 메시지 표시
                - 복구된 데이터 로드
            '''
            print("\n[7단계] 복구 ���료 ��시지 표시")
            self.on_recovery_info("복구 스크립트가 성공적으로 실행되었습니다.")
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

        # 성공적으로 스크립트가 실행된 경우, 복구 데이터를 드합니다.
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
            # database.py의 load_recovery_data_from_db 함수 사용
            data, headers = load_recovery_data_from_db(self.recovered_db_path)
            
            if data and headers:
                # SQLiteTableModel에 데이터와 헤더 전달
                model = SQLiteTableModel(data, headers)
                self.table_view.setModel(model)
                
                # 레코드 수 확인
                print(f"\n데이터베이스 경로: {self.recovered_db_path}")
                print(f"쿼리 결과 레코드 수: {len(data)}")
                
                # 첫 번째 레코드 내용 출력
                if data:
                    print("\n첫 번째 레코드 내용:")
                    for i, header in enumerate(headers):
                        print(f"{header}: {data[0][i]}")
            else:
                self.error_label.setText("데이터를 불러올 수 없습니다.")
                self.error_label.show()

        except Exception as e:
            error_msg = f"데이터 로드 중 예외 발생: {e}"
            print(f"\n오류: {error_msg}")
            self.error_label.setText(error_msg)
            self.error_label.show()

    def run_wal_recovery(self, recovery_wal_path):
        """WAL 복구 스크립를 실행합니다."""
        try:
            print(f"WAL 복구 시작: {self.original_db_path}")  # 디버깅을 위한 로그 추가
            result = subprocess.run(
                [sys.executable, recovery_wal_path, self.original_db_path], 
                check=True, capture_output=True, text=True
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
