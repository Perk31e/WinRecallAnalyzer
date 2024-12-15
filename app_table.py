#app_table.py

import os
import shutil
import subprocess
import ctypes
import time
import pytz
from ctypes import wintypes
import pandas as pd
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel, QTextEdit, QSplitter, QHeaderView, QStyledItemDelegate
from PySide6.QtCore import Qt, QAbstractTableModel
from database import SQLiteTableModel, load_app_data_from_db


class SQLiteTableModel(QAbstractTableModel):
    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self._data = data  # 데이터: 리스트 형태로 가정
        self._headers = headers  # 헤더: 리스트 형태로 가정
        self._sort_order = Qt.AscendingOrder  # 기본 정렬 순서

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self._data[index.row()][index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._headers[section]
        return section + 1

    def sort(self, column, order):
        """특정 열을 기준으로 데이터 정렬"""
        if not self._data or column < 0 or column >= len(self._headers):
            print("정렬할 수 없는 상태입니다.")
            return

        self.beginResetModel()  # 모델 리셋 시작
        self._sort_order = order

        # 데이터를 정렬 (오름차순 또는 내림차순)
        reverse = (order == Qt.DescendingOrder)
        try:
            self._data.sort(key=lambda row: row[column], reverse=reverse)
        except Exception as e:
            print(f"정렬 중 오류 발생: {e}")

        self.endResetModel()  # 모델 리셋 완료

class AppTableWidget(QWidget):
    def __init__(self, mode='analysis'):
        super().__init__()
        self.db_path = ""
        self.current_mode = mode
        self.srudb_path = None  # 초기화 추가
        self.software_path = None  # 초기화 추가
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

        self.table_view.setSortingEnabled(True)  # 정렬 기능 활성화

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
        if not db_path:
            print("set_db_path 호출 시 db_path가 비어 있습니다!")
            return
        self.db_path = db_path
        print(f"db_path가 설정됨: {self.db_path}")  # 디버깅용 로그
        self.load_app_data()
        if self.current_mode == 'target':  # 대상 PC 모드에서만 복사 및 파싱
            recall_load_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Recall_load")
            self.copy_srum_files_and_backup(recall_load_dir)

    def load_app_data(self):
        data, headers = load_app_data_from_db(self.db_path)
        if data:
            model = SQLiteTableModel(data, headers)
            self.table_view.setModel(model)
            self.table_view.hideColumn(0)
            self.table_view.hideColumn(1)

            header = self.table_view.horizontalHeader()

            # 열 크기 조정
            header.setSectionResizeMode(2, QHeaderView.Interactive)  # 3번째 열: 수동 조정 가능
            header.setSectionResizeMode(3, QHeaderView.Interactive)  # 4번째 열: 수동 조정 가능
            header.setSectionResizeMode(4, QHeaderView.Interactive)  # 5번째 열: 수동 조정 가능
            header.resizeSection(2, 440)  # 2번째 열 초기 너비 수동 설정
            header.resizeSection(3, 150)  # 3번째 열 초기 너비 수동 설정
            header.resizeSection(4, 75)  # 4번째 열 초기 너비 수동 설정

            self.table_view.resizeColumnToContents(5)  # 6번째 열: 데이터 길이에 맞춤

            # 열 정렬 활성화
            self.table_view.setSortingEnabled(True)

            # 초기 정렬 (4번 열: HourStartTimeStamp 기준 오름차순)
            self.table_view.sortByColumn(5, Qt.AscendingOrder)  # 5번째 열을 기준으로 오름차순 정렬

            self.info_label.hide()
            selection_model = self.table_view.selectionModel()
            if selection_model:
                selection_model.selectionChanged.connect(self.on_table_selection_changed)
        else:
            self.info_label.setText("데이터를 불러올 수 없습니다.")
            self.info_label.show()

    def set_csv_data(self, csv_data):
        """Main에서 로드된 CSV 데이터를 설정."""
        if csv_data is None:
            print("[DEBUG] 전달된 CSV 데이터가 None입니다.")
            return

        self.csv_data = csv_data
        print(f"[DEBUG] AppTableWidget에 CSV 데이터가 설정되었습니다. 총 {len(self.csv_data)}개의 행")

    def on_table_selection_changed(self, selected, deselected):
        selected_indexes = self.table_view.selectionModel().selectedIndexes()
        if selected_indexes:
            row = selected_indexes[0].row()
            model = self.table_view.model()
            if model:
                app_path = model.data(model.index(row, 2))  # Path 열
                app_time = model.data(model.index(row, 5))  # TimeStamp 열
                print(f"[DEBUG] 선택된 테이블 데이터 - Path: {app_path}, TimeStamp: {app_time}")

                # SRUM 데이터와 비교
                if hasattr(self, 'csv_data') and self.csv_data is not None:
                    srum_data = self.get_srum_related_data(app_path, app_time)
                    self.text_box4.setText(srum_data)
                else:
                    print("[DEBUG] CSV 데이터가 AppTableWidget에 설정되지 않았습니다.")
                    self.text_box4.setText("CSV 데이터가 없습니다.")

    def convert_foreground_cycle_time_to_seconds(self, foreground_cycle_time):
        """
        ForegroundCycleTime 값을 초 단위로 변환합니다.
        """
        return foreground_cycle_time / 10_000_000  # 100나노초 단위를 초로 변환

    def format_seconds_to_minutes_and_seconds(self, seconds):
        """
        초 단위를 분과 초 형식으로 변환합니다.
        """
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}분 {remaining_seconds}초"

    def get_srum_related_data(self, app_path, app_time):
        """
        CSV 데이터와 테이블 데이터를 비교하여 연관된 ForegroundCycleTime 값을 반환.
        초는 무시하고 분 단위 ±1 범위로 비교.
        """
        if not hasattr(self, 'csv_data') or self.csv_data is None:
            print("[DEBUG] CSV 데이터가 self.csv_data에 없습니다.")
            return "CSV 데이터가 없습니다."

        try:
            # 파일명만 추출
            app_file_name = os.path.basename(app_path)
            print(f"[DEBUG] 비교를 위한 파일명: {app_file_name}")

            # `ExeInfo`에서 파일명 매칭 후 명시적 복사
            filtered_data = self.csv_data[
                self.csv_data["ExeInfo"].str.contains(app_file_name, na=False, case=False)].copy()
            if filtered_data.empty:
                print(f"[DEBUG] ExeInfo에 {app_file_name} 관련 데이터가 없습니다.")
                return "ExeInfo 데이터 없음"

            print(f"[DEBUG] ExeInfo에서 {app_file_name} 관련 데이터 필터링 완료.")
            print(filtered_data[["ExeInfo", "Timestamp", "ForegroundCycleTime"]].head())

            # 테이블의 TimeStamp를 24시간제로 변환 (초 제거) 및 KST로 설정
            if app_time:
                app_time_24h = pd.to_datetime(app_time, format='%Y-%m-%d %H:%M:%S').floor('min')
                kst_zone = pytz.timezone("Asia/Seoul")
                app_time_24h = kst_zone.localize(app_time_24h)  # KST로 타임존 설정
                print(f"[DEBUG] 테이블에서 변환된 TimeStamp (분 단위, KST): {app_time_24h}")

            # SRUM 데이터의 Timestamp를 KST로 변환 후 분 단위로 변환
            filtered_data["Timestamp_KST"] = pd.to_datetime(
                filtered_data["Timestamp"], format='%Y-%m-%d %H:%M:%S', utc=True
            ).dt.tz_convert("Asia/Seoul").dt.floor('min')  # 초 제거, 분 단위로 변환

            print(f"[DEBUG] 변환된 CSV 데이터 (분 단위):")
            print(filtered_data[["ExeInfo", "Timestamp_KST"]].head())

            # ±1분 범위로 Timestamp 비교
            matched_rows = filtered_data[
                abs((filtered_data["Timestamp_KST"] - app_time_24h).dt.total_seconds()) <= 60
                ]

            if not matched_rows.empty:
                foreground_cycle_time_raw = matched_rows["ForegroundCycleTime"].iloc[0]
                foreground_cycle_time_seconds = self.convert_foreground_cycle_time_to_seconds(foreground_cycle_time_raw)
                formatted_time = self.format_seconds_to_minutes_and_seconds(foreground_cycle_time_seconds)
                print(f"[DEBUG] 매칭된 ForegroundCycleTime (원본): {foreground_cycle_time_raw}")
                print(f"[DEBUG] 매칭된 ForegroundCycleTime (초 단위): {foreground_cycle_time_seconds}")
                print(f"[DEBUG] 매칭된 ForegroundCycleTime (포맷): {formatted_time}")
                return f"ForegroundCycleTime: {formatted_time}"
            else:
                print("[DEBUG] 일치하는 CSV 데이터가 없습니다.")
                return "연관된 ForegroundCycleTime 데이터 없음"

        except Exception as e:
            print(f"[DEBUG] 데이터 처리 중 오류 발생: {e}")
            return f"데이터 처리 중 오류 발생: {e}"

    def is_time_within_range(self, target_time, reference_time):
        """
        두 시간 간 차이가 ±1분 이내인지 확인 (초 무시).
        target_time: CSV 데이터의 TimeStamp (24시간제)
        reference_time: 테이블의 TimeStamp (24시간제)
        """
        # 시간 형식을 분 단위로 변환
        target = pd.to_datetime(target_time, format='%Y-%m-%d %H:%M:%S').floor('min')
        reference = pd.to_datetime(reference_time, format='%Y-%m-%d %H:%M:%S').floor('min')

        # 분 단위 차이 계산
        delta = abs((target - reference).total_seconds()) / 60  # 분 단위 차이
        return delta <= 1  # ±1분 조건

    def set_srum_paths(self, srudb_path, software_path):
        """SRUM 데이터 경로 설정"""
        self.srudb_path = srudb_path
        self.software_path = software_path
        print(f"[DEBUG] AppTableWidget에 SRUM 경로가 설정되었습니다: SRUDB.dat={srudb_path}, SOFTWARE={software_path}")

    def copy_srum_files_and_backup(self, destination_folder):
        """SRUM 및 SOFTWARE 파일 복사만 수행"""
        srudb_src_path = r"C:\Windows\System32\sru\SRUDB.dat"
        srudb_dst_path = os.path.join(destination_folder, "SRU_Artifacts", "SRUDB.dat")
        software_dst_path = os.path.join(destination_folder, "SRU_Artifacts", "SOFTWARE")
        srum_tool_output_dir = os.path.join(destination_folder, "Output_File")

        # SRUDB.dat 파일 복사
        try:
            os.makedirs(os.path.dirname(srudb_dst_path), exist_ok=True)
            file_data = self.read_file(srudb_src_path)
            with open(srudb_dst_path, "wb") as f:
                f.write(file_data)
            print(f"SRUDB.dat 파일 복사 완료: {srudb_dst_path}")
        except Exception as e:
            print(f"SRUDB.dat 파일 복사 실패: {e}")

        # SOFTWARE 하이브 복사
        try:
            self.backup_registry_hive(software_dst_path)
            print(f"SOFTWARE 하이브 복사 완료: {software_dst_path}")
        except Exception as e:
            print(f"SOFTWARE 하이브 복사 실패: {e}")

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
                self.csv_data = None
                return

            csv_file_path = os.path.join(output_csv_dir, csv_files[0])
            print(f"CSV 파일 로드 중: {csv_file_path}")

            df = pd.read_csv(csv_file_path)
            print("[DEBUG] CSV 파일의 열:", df.columns.tolist())

            # TimeStamp를 24시간제로 유지
            if "Timestamp" in df.columns:
                df["Timestamp"] = pd.to_datetime(df["Timestamp"]).dt.strftime('%Y-%m-%d %H:%M:%S')

            # ForegroundCycleTime 처리 (기존 로직 유지)
            if "ForegroundCycleTime" in df.columns:
                self.foreground_cycle_time_data = df["ForegroundCycleTime"].iloc[0]
                print(f"ForegroundCycleTime: {self.foreground_cycle_time_data}")
                self.analyze_relationship()

            self.csv_data = df  # CSV 데이터를 self.csv_data에 저장
            print(f"[DEBUG] CSV 데이터 로드 성공 - 총 {len(self.csv_data)}개의 행")

        except Exception as e:
            print(f"ForegroundCycleTime 값을 로드하는 중 오류 발생: {e}")
            self.foreground_cycle_time_data = None
            self.csv_data = None

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

    def analyze_srum_data_for_analysis_mode(self):
        """분석 PC 모드 전용 SRUM 데이터 처리"""
        if not self.srudb_path or not self.software_path:
            print("SRUDB.dat 및 SOFTWARE 파일이 모두 지정되어야 합니다.")
            return

        print("분석 PC 모드에서 SRUM 데이터 처리를 시작합니다.")

        # 출력 디렉터리 생성
        output_folder = os.path.join(os.path.dirname(self.srudb_path), "Output_File")
        os.makedirs(output_folder, exist_ok=True)

        # SrumECmd.exe 실행 경로
        srum_tool_path = os.path.join(os.getcwd(), "SrumECmd.exe")
        if not os.path.exists(srum_tool_path):
            print(f"SrumECmd.exe 파일이 {srum_tool_path} 경로에 존재하지 않습니다.")
            return

        # 실행 명령어 생성
        command = [
            srum_tool_path,
            "-f", self.srudb_path,
            "-r", self.software_path,
            "--csv", output_folder
        ]

        print(f"실행할 명령어: {' '.join(command)}")

        # 명령어 실행 (subprocess 사용)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # 명령어 실행 후 바로 종료 (출력은 로그에 저장되지 않음)
            process.wait()  # 이 라인 추가로 프로세스 종료를 기다림

            if process.returncode == 0:
                print("SrumECmd 실행 완료")
                # ForegroundCycleTime 데이터 로드
                self.load_foreground_cycle_time(output_folder)
            else:
                print("SrumECmd 실행 실패")

        except Exception as e:
            print(f"SrumECmd 실행 중 오류 발생: {e}")
