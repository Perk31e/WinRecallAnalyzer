#app_table.py

import os
import shutil
import subprocess
import ctypes
import time
from ctypes import wintypes
import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel, QTextEdit, QSplitter, QHeaderView
from PySide6.QtCore import Qt
from database import SQLiteTableModel, load_app_data_from_db


class AppTableWidget(QWidget):
    def __init__(self, mode='analysis'):
        super().__init__()
        self.db_path = ""
        self.current_mode = mode  # 모드 설정
        self.foreground_cycle_time_data = None
        self.setup_ui()


    def setup_ui(self):
        self.table_view = QTableView(self)
        self.info_label = QLabel("데이터를 불러올 수 없습니다.", self)
        self.info_label.setAlignment(Qt.AlignCenter)

        self.text_box1 = QTextEdit(self)
        self.text_box2 = QTextEdit(self)
        self.text_box3 = QTextEdit(self)
        self.text_box4 = QTextEdit(self)

        for text_box in [self.text_box1, self.text_box2, self.text_box3, self.text_box4]:
            text_box.setReadOnly(True)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.table_view)
        left_layout.addWidget(self.info_label)
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
        if self.current_mode == 'target':  # 대상 PC 모드에서만 복사 및 파싱
            self.copy_srum_files_and_backup()

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
            selection_model = self.table_view.selectionModel()
            if selection_model:
                selection_model.selectionChanged.connect(self.on_table_selection_changed)
        else:
            self.info_label.setText("데이터를 불러올 수 없습니다.")
            self.info_label.show()

    def on_table_selection_changed(self, selected, deselected):
        selected_indexes = self.table_view.selectionModel().selectedIndexes()
        if selected_indexes:
            row = selected_indexes[0].row()
            model = self.table_view.model()
            if model:
                app_data = model.data(model.index(row, 0))
                self.text_box1.setText(f"선택된 App 데이터: {app_data}")
                self.text_box2.setText("LNK 관련 데이터 표시 예정")
                self.text_box3.setText("Jumplist 관련 데이터 표시 예정")
                self.text_box4.setText("SRUM 데이터는 여기에 표시됩니다.")

    def copy_srum_files_and_backup(self):
        """SRUM 및 SOFTWARE 파일 복사 또는 분석"""
        # 공통 변수 설정
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        app_table_data_path = os.path.join(desktop_path, "AppTable_data")
        srudb_dst_path = os.path.join(app_table_data_path, "SRUDB.dat")
        software_dst_path = os.path.join(app_table_data_path, "SOFTWARE")
        srum_tool_path = os.path.join(os.getcwd(), "SrumECmd.exe")
        output_csv_dir = os.path.join(app_table_data_path, "Output_File")

        os.makedirs(app_table_data_path, exist_ok=True)

        # 분석 PC 모드라면, 이미 선택된 파일 사용
        if getattr(self, 'current_mode', None) == 'analysis':
            print(f"분석 모드: SRUM 파일 경로: {self.srudb_path}, SOFTWARE 파일 경로: {self.software_path}")
            if not os.path.exists(self.srudb_path) or not os.path.exists(self.software_path):
                print("분석 모드에서 지정된 파일 경로가 유효하지 않습니다.")
                return

            srudb_dst_path = self.srudb_path
            software_dst_path = self.software_path
        else:
            # 대상 PC 모드: 파일 복사
            srudb_src_path = r"C:\Windows\System32\sru\SRUDB.dat"
            print("SRUDB.dat 파일 복사 중...")
            if not os.path.exists(srudb_src_path):
                print(f"SRUDB.dat 파일이 {srudb_src_path} 경로에 존재하지 않습니다. 복사를 건너뜁니다.")
                return

            try:
                file_data = self.read_file(srudb_src_path, buffer_size=50 * 1024 * 1024)
                with open(srudb_dst_path, "wb") as f:
                    f.write(file_data)
                print(f"SRUDB.dat 파일 복사 완료: {srudb_dst_path}")
            except Exception as e:
                print(f"SRUDB.dat 파일 복사 실패: {e}")
                return

            # SOFTWARE 파일 복사
            print("SOFTWARE 하이브 백업 중...")
            if not os.path.exists("C:\\Windows\\System32\\config\\SOFTWARE"):
                print("SOFTWARE 하이브 파일이 존재하지 않습니다. 복사를 건너뜁니다.")
                return

            try:
                self.backup_registry_hive(software_dst_path)
                print(f"SOFTWARE 하이브 백업 완료: {software_dst_path}")
            except Exception as e:
                print(f"SOFTWARE 하이브 백업 실패: {e}")
                return

        # SrumECmd 실행
        print("SrumECmd 실행 중...")
        try:
            self.run_srum_tool(srum_tool_path, srudb_dst_path, software_dst_path, output_csv_dir)
            print("SrumECmd 실행 완료")
        except Exception as e:
            print(f"SrumECmd 실행 중 오류 발생: {e}")
            return

        # ForegroundCycleTime 데이터 로드
        self.load_foreground_cycle_time(output_csv_dir)

    def read_file(self, file_path, buffer_size=50 * 1024 * 1024):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001 | 0x00000002 | 0x00000004
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

        file_handle = kernel32.CreateFileW(
            file_path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None
        )
        if file_handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

        print(f"File handle obtained for {file_path}")

        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_read = wintypes.DWORD(0)
        data = b""

        try:
            while True:
                success = kernel32.ReadFile(file_handle, buffer, buffer_size, ctypes.byref(bytes_read), None)
                if not success or bytes_read.value == 0:
                    break
                data += buffer.raw[:bytes_read.value]
        finally:
            kernel32.CloseHandle(file_handle)

        return data

    def load_foreground_cycle_time(self, output_csv_dir):
        try:
            csv_files = [f for f in os.listdir(output_csv_dir) if f.endswith('.csv')]
            if not csv_files:
                print("CSV 파일이 존재하지 않습니다. SRUM 작업 실패")
                self.foreground_cycle_time_data = None
                return

            csv_file_path = os.path.join(output_csv_dir, csv_files[0])
            print(f"CSV 파일 로드 중: {csv_file_path}")

            df = pd.read_csv(csv_file_path)
            if "ForegroundCycleTime" in df.columns:
                self.foreground_cycle_time_data = df["ForegroundCycleTime"].iloc[0]
                print(f"ForegroundCycleTime: {self.foreground_cycle_time_data}")
                self.analyze_relationship()
            else:
                print("ForegroundCycleTime 열이 없습니다. 데이터를 건너뜁니다.")
                self.foreground_cycle_time_data = None
        except Exception as e:
            print(f"ForegroundCycleTime 값을 로드하는 중 오류 발생: {e}")
            self.foreground_cycle_time_data = None

    def analyze_relationship(self):
        if self.foreground_cycle_time_data is None:
            print("ForegroundCycleTime 데이터가 없습니다.")
            return

        print(f"ForegroundCycleTime: {self.foreground_cycle_time_data}와 App 데이터를 연관 분석합니다.")

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def backup_registry_hive(self, dst_path):
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            command = f'reg save HKLM\\SOFTWARE "{dst_path}" /y'
            result = subprocess.run(command, shell=True, text=True, encoding="cp949", capture_output=True)

            if result.returncode == 0:
                print(result.stdout)
                print("SOFTWARE 하이브가 성공적으로 백업되었습니다.")
            else:
                print(result.stderr)
                print("SOFTWARE 하이브 백업 중 오류 발생.")
        except subprocess.CalledProcessError as e:
            print(f"레지스트리 하이브 백업 중 예외 발생: {e}")

    def run_srum_tool(self, srum_tool_path, srudb_path, software_hive_path, output_csv_dir):
        # SRUM 파일이 존재하지 않으면 건너뜁니다.
        if not os.path.exists(srum_tool_path):
            print(f"SrumECmd.exe 파일이 경로 {srum_tool_path} 에 존재하지 않습니다.")
            return

        if not os.path.exists(srudb_path):
            print(f"SRUDB.dat 파일이 경로 {srudb_path} 에 존재하지 않습니다. SRUM 파싱을 건너뜁니다.")
            return

        if not os.path.exists(software_hive_path):
            print(f"SOFTWARE 파일이 경로 {software_hive_path} 에 존재하지 않습니다. SRUM 파싱을 건너뜁니다.")
            return

        try:
            os.makedirs(output_csv_dir, exist_ok=True)
            command = [
                srum_tool_path,
                "-f", srudb_path,
                "-r", software_hive_path,
                "--csv", output_csv_dir
            ]

            print(f"실행할 명령어: {' '.join(command)}")

            result = subprocess.run(command, check=True, text=True, capture_output=True)

            if result.returncode == 0:
                print(f"SrumECmd 실행 완료: {result.stdout}")
            else:
                print(f"SrumECmd 실행 중 오류 발생: {result.stderr}")

        except subprocess.CalledProcessError as e:
            print(f"SrumECmd 실행 중 오류 발생: {e}")
            print(f"출력된 에러 메시지: {e.stderr}")
