# main.py

import sys
import os
import subprocess
import shutil
import glob
import pandas as pd
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableView, QVBoxLayout, QWidget, QLabel, \
    QHBoxLayout, QLineEdit, QSplitter, QStatusBar, QStyledItemDelegate, QTabWidget, QTextEdit, QSizePolicy, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QSortFilterProxyModel
from database import SQLiteTableModel, load_data_from_db, load_app_data_from_db, load_web_data
from image_loader import ImageLoaderThread
from web import WebTableWidget as ImportedWebTableWidget
from app_table import AppTableWidget
from file_table import FileTableWidget
from recovery_table import RecoveryTableWidget
from no_focus_frame_style import NoFocusFrameStyle
from Internal_Audit import InternalAuditWidget

# 문자열 매핑 딕셔너리: 이벤트 이름을 간결한 이름으로 매핑
name_mapping = {
    "WindowCaptureEvent": "Capture",
    "WindowCreatedEvent": "Created",
    "WindowChangedEvent": "Changed",
    "WindowDestroyedEvent": "Destroyed",
    "ForegroundChangedEvent": "Foreground"
}

def map_name(name):
    return name_mapping.get(name, name) if name else 'N/A'

class CenteredDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReCall DATA Parser")
        self.resize(1800, 900)

        # 초기화 변수
        self.db_path = ""  # ukg.db 파일 경로
        self.history_db_path = ""  # history 파일 경로
        self.srudb_path = ""  # SRUDB.dat 파일 경로
        self.software_path = ""  # SOFTWARE 파일 경로
        self.current_mode = None  # 모드 상태를 저장하는 변수

        # 모드 선택 (새로운 로직 추가)
        self.setup_mode()

        # 상단 메뉴바 생성
        self.menu_bar = self.menuBar()
        file_menu = self.menu_bar.addMenu("파일")

        # "파일 열기" 메뉴 항목 추가
        open_file_action = QAction("파일 열기", self)
        open_file_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_file_action)

        # "히스토리 파일 열기" 메뉴 항목을 open_additional_files_dialog로 변경
        open_history_action = QAction("히스토리 파일 열기", self)
        open_history_action.triggered.connect(
            self.open_additional_files_dialog)  # open_history_file_dialog -> open_additional_files_dialog로 변경
        file_menu.addAction(open_history_action)

        # "SRUM 열기" 메뉴 항목 추가
        open_srum_action = QAction("SRUM 열기", self)
        open_srum_action.triggered.connect(self.open_srum_files_dialog)
        file_menu.addAction(open_srum_action)

        # 검색창 추가
        top_layout = QWidget(self)
        top_layout.setLayout(QHBoxLayout())
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요...")
        self.search_input.setFixedWidth(200)

        # 메뉴바 오른쪽에 검색창 추가
        top_layout.layout().addWidget(self.menu_bar)
        top_layout.layout().addStretch(5)
        top_layout.layout().addWidget(self.search_input)
        self.setMenuWidget(top_layout)

        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # UI 구성
        self.setup_ui()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.on_tab_changed(self.tab_widget.currentIndex())

        # image_label에 마우스 더블클릭 이벤트 핸들러 설정
        self.image_label.mouseDoubleClickEvent = self.on_image_label_double_click

        # AppTableWidget에 파일 경로 전달 및 분석 기능 실행
        if hasattr(self.app_table_tab, 'analyze_srum_data'):
            self.app_table_tab.analyze_srum_data(self.srudb_path, self.software_path)

    def setup_image_table_tab(self):
        """이미지 테이블 탭 초기화"""
        try:
            from image_table_one import ImageTableWidget
            self.image_table_tab = ImageTableWidget()
            self.tab_widget.addTab(self.image_table_tab, "ImageTable")
            if self.db_path:
                self.image_table_tab.set_db_path(self.db_path)
        except ImportError:
            print("ImageTableWidget 모듈을 불러오지 못했습니다.")
            self.image_table_tab = None

    def setup_app_table_tab(self):
        """앱 테이블 탭 초기화"""
        try:
            self.app_table_tab = AppTableWidget(mode=self.current_mode)  # 모드 전달
            self.tab_widget.addTab(self.app_table_tab, "AppTable")
            if self.db_path:
                self.app_table_tab.set_db_path(self.db_path)  # DB 경로 설정
        except ImportError:
            print("AppTableWidget 모듈을 불러오지 못했습니다.")

    def setup_file_table_tab(self):
        """FileTable 탭 초기화"""
        self.file_table_tab = FileTableWidget()
        self.tab_widget.addTab(self.file_table_tab, "FileTable")
        if self.db_path:
            self.file_table_tab.set_db_path(self.db_path)

    def setup_recovery_table_tab(self):
        """RecoveryTable 탭 초기화"""
        self.recovery_table_tab = RecoveryTableWidget()
        self.tab_widget.addTab(self.recovery_table_tab, "RecoveryTable")

    def setup_internal_audit_tab(self):
        """Internal Audit 탭 초기화"""
        try:
            from Internal_Audit import InternalAuditWidget
            self.internal_audit_tab = InternalAuditWidget()
            self.tab_widget.addTab(self.internal_audit_tab, "InternalAudit")
            if self.db_path:
                print(f"[Main] InternalAuditWidget에 db_path 설정: {self.db_path}")
                self.internal_audit_tab.set_db_path(self.db_path)
            else:
                print("[Main] db_path가 설정되지 않았습니다.")
        except ImportError as e :
            print(f"InternalAuditWidget 초기화 중 오류 발생: {e}")
            self.internal_audit_tab = None

    def on_tab_changed(self, index):
        """탭 변경 시 이벤트 처리"""
        tab_name = self.tab_widget.tabText(index)
        if tab_name in ["ImageTable", "InternalAudit"]:  # ImageTable과 InternalAudit 탭에서는 검색창 숨김
            self.search_input.hide()
            if tab_name == "ImageTable" and self.image_table_tab:
                self.image_table_tab.setFocus()
        else:
            self.search_input.show()

    def on_image_label_double_click(self, event):
        """이미지 라벨 더블 클릭 시 이벤트 처리"""
        if self.tab_widget.indexOf(self.image_table_tab) != -1:
            self.tab_widget.setCurrentWidget(self.image_table_tab)
            selected_index = self.table_view.selectionModel().currentIndex()
            image_token_index = self.proxy_model.index(selected_index.row(), 2)
            image_token = image_token_index.data()
            if image_token and hasattr(self.image_table_tab, 'display_image_from_token'):
                self.image_table_tab.display_image_from_token_with_index(image_token)

    def setup_mode(self):
        """분석 모드 선택 메시지 표시 및 모드 설정"""
        reply = QMessageBox.question(
            self,
            "모드 선택",
            "분석 모드를 선택하세요:\n\n"
            "Yes: 대상 PC 모드 (복사 및 파싱 기능 사용)\n"
            "No: 분석 모드 (파일 지정 후 파싱 실행)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        print(f"QMessageBox 반환값: {reply}")  # 디버깅 추가
        if reply == QMessageBox.Yes:
            self.current_mode = 'target'
            print("사용자가 Yes를 눌렀습니다. current_mode = 'target'")  # 디버깅 추가
        else:
            self.current_mode = 'analysis'
            print("사용자가 No를 눌렀습니다. current_mode = 'analysis'")  # 디버깅 추가

    def initialize_mode(self):
        """모드에 따라 초기화 작업 수행"""
        print(f"initialize_mode 호출됨. current_mode = {self.current_mode}")  # 디버깅 추가
        if self.current_mode == 'target':
            print("initialize_target_mode 호출 예정")  # 디버깅 추가
            self.initialize_target_mode()
        elif self.current_mode == 'analysis':
            print("initialize_analysis_mode 호출 예정")  # 디버깅 추가
            self.initialize_analysis_mode()

    def initialize_target_mode(self):
        """대상 PC 모드 초기화"""
        self.collect_files()  # 데이터 복사
        self.statusBar().showMessage("대상 PC 모드로 초기화 완료.")

    def initialize_analysis_mode(self):
        """분석 PC 모드 초기화"""
        self.statusBar().showMessage("분석 PC 모드로 초기화 완료.")

    # main.py - collect_files 메서드 수정
    def collect_files(self):
        """대상 PC 모드에서 데이터 복사 및 SRUM 파싱"""
        if self.current_mode != 'target':
            print("분석 모드에서 데이터 복사를 건너뜁니다.")
            return  # 분석 모드에서는 복사 기능 비활성화

        # Recall_load 폴더 경로 설정
        desktop_path = os.path.expanduser("~\\Desktop")
        recall_load_dir = os.path.join(desktop_path, "Recall_load")
        os.makedirs(recall_load_dir, exist_ok=True)

        # Recover_Output 폴더 경로 설정
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Recover_Output")
        os.makedirs(output_dir, exist_ok=True)

        # 브라우저 히스토리 파일 복사
        try:
            if hasattr(self.web_table_tab, 'copy_history_files') and self.web_table_tab:
                print("copy_history_files 호출 시작...")
                self.web_table_tab.copy_history_files(destination_folder=recall_load_dir)
                print("브라우저 히스토리 파일 복사 완료")
            else:
                print("WebTableWidget이 초기화되지 않았거나 copy_history_files 함수가 존재하지 않습니다.")
        except Exception as e:
            print(f"브라우저 히스토리 파일 복사 중 오류 발생: {e}")

        # SRUM 및 SOFTWARE 파일 복사
        try:
            if hasattr(self.app_table_tab, 'copy_srum_files_and_backup'):
                self.app_table_tab.copy_srum_files_and_backup(destination_folder=recall_load_dir)
                print("SRUDB.dat 및 SOFTWARE 파일 복사 완료")
            else:
                print("AppTableWidget이 초기화되지 않았거나 copy_srum_files_and_backup 함수가 없습니다.")
        except Exception as e:
            print(f"SRUM 및 SOFTWARE 파일 복사 중 오류 발생: {e}")

        # ukg.db 파일 복사
        try:
            user_path = os.path.expanduser("~")
            ukp_folder_path = os.path.join(user_path, r"AppData\Local\CoreAIPlatform.00\UKP")
            guid_folders = glob.glob(os.path.join(ukp_folder_path, "{*}"))

            ukg_db_source = None
            for folder in guid_folders:
                potential_path = os.path.join(folder, "ukg.db")
                if os.path.exists(potential_path):
                    ukg_db_source = potential_path
                    break

            if ukg_db_source:
                ukg_db_destination = os.path.join(recall_load_dir, "ukg.db")
                shutil.copyfile(ukg_db_source, ukg_db_destination)
                print(f"ukg.db 파일 복사 완료: {ukg_db_destination}")
            else:
                print("ukg.db 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"ukg.db 파일 복사 중 오류 발생: {e}")

        # ukg.db-wal 파일 복사 및 이름 변경
        try:
            ukg_wal_source = None
            for folder in guid_folders:
                potential_wal_path = os.path.join(folder, "ukg.db-wal")
                if os.path.exists(potential_wal_path):
                    ukg_wal_source = potential_wal_path
                    break

            if ukg_wal_source:
                wal_destination = os.path.join(output_dir, "remained.db-wal")
                shutil.copyfile(ukg_wal_source, wal_destination)
                print(f"ukg.db-wal 파일을 {wal_destination}로 복사 및 이름 변경 완료")
            else:
                print("ukg.db-wal 파일을 찾을 수 없습니다.")
        except Exception as e:
            print(f"ukg.db-wal 파일 복사 중 오류 발생: {e}")

        # SRUM 데이터 파싱
        try:
            self.app_table_tab.srudb_path = os.path.join(recall_load_dir, "SRU_Artifacts", "SRUDB.dat")
            self.app_table_tab.software_path = os.path.join(recall_load_dir, "SRU_Artifacts", "SOFTWARE")

            if not os.path.exists(self.app_table_tab.srudb_path) or not os.path.exists(
                    self.app_table_tab.software_path):
                print("SRUM 파일이 없습니다. SRUM 파싱을 건너뜁니다.")
                return

            print("SRUM 데이터 파싱 시작")
            self.app_table_tab.analyze_srum_data_for_analysis_mode()  # run_srum_tool 대체
            print("SRUM 데이터 파싱 완료")
        except Exception as e:
            print(f"SRUM 데이터 파싱 중 오류 발생: {e}")

    def open_srum_files_dialog(self):
        """SRUM 파일과 SOFTWARE 파일을 선택하도록 하는 다이얼로그"""
        if self.current_mode == 'target':
            # 대상 PC 모드에서는 이미 복사된 파일 사용
            recall_load_path = os.path.join(os.path.expanduser("~"), "Desktop", "Recall_load", "AppTable_DATA",
                                            "SRU_Artifacts")
            self.srudb_path = os.path.join(recall_load_path, "SRUDB.dat")
            self.software_path = os.path.join(recall_load_path, "SOFTWARE")

            if not os.path.exists(self.srudb_path) or not os.path.exists(self.software_path):
                print("대상 PC 모드에서 복사된 파일이 존재하지 않습니다.")
                return

            print("대상 PC 모드에서 복사된 파일을 사용합니다:")
            print(f"SRUDB.dat: {self.srudb_path}")
            print(f"SOFTWARE: {self.software_path}")

            # 대상 PC 모드에서는 바로 분석 실행
            self.analyze_srum_data_for_target_mode()
            return

        # 분석 PC 모드: 파일 선택
        sru_file, _ = QFileDialog.getOpenFileName(
            self, "SRUDB.dat 파일 선택", os.path.expanduser("~"), "All Files (*)"
        )
        if not sru_file:
            print("SRUM 파일을 선택하지 않았습니다. SRUM 파싱을 건너뜁니다.")
            return

        software_file, _ = QFileDialog.getOpenFileName(
            self, "SOFTWARE 파일 선택", os.path.expanduser("~"), "All Files (*)"
        )
        if not software_file:
            print("SOFTWARE 파일을 선택하지 않았습니다. SRUM 파싱을 건너뜁니다.")
            return

        # 파일 경로 저장
        self.srudb_path = sru_file
        self.software_path = software_file

        print("분석 PC 모드에서 SRUM 및 SOFTWARE 파일이 지정되었습니다.")
        print(f"SRUDB.dat: {self.srudb_path}")
        print(f"SOFTWARE: {self.software_path}")

        # 분석 실행
        self.analyze_srum_data_for_analysis_mode()

    def setup_ui(self):
        """기존 UI 초기화"""
        # AllTable Tab 초기화
        self.all_table_tab = QWidget()
        self.all_table_layout = QVBoxLayout(self.all_table_tab)
        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        self.all_table_layout.addWidget(self.horizontal_splitter)

        # 좌측: 테이블 뷰
        self.table_view = QTableView()
        self.horizontal_splitter.addWidget(self.table_view)

        # 우측: 이미지 및 데이터 프리뷰
        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        self.horizontal_splitter.setStretchFactor(0, 3)
        self.horizontal_splitter.setStretchFactor(1, 1)

        # 이미지 프리뷰 라벨
        self.image_label = QLabel("이미지 프리뷰")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(854, 480)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setScaledContents(True)
        self.vertical_splitter.addWidget(self.image_label)

        # 데이터 프리뷰 텍스트 에디터
        self.data_viewer = QTextEdit("데이터 프리뷰")
        self.data_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vertical_splitter.addWidget(self.data_viewer)

        self.all_table_tab.setLayout(self.all_table_layout)
        self.tab_widget.addTab(self.all_table_tab, "AllTable")

        # 이미지 테이블 탭 추가
        self.setup_image_table_tab()

        # 앱 테이블 탭 추가
        self.setup_app_table_tab()

        # 웹 테이블 탭 추가
        self.web_table_tab = ImportedWebTableWidget()
        self.tab_widget.addTab(self.web_table_tab, "WebTable")

        # 파일 테이블 탭 추가
        self.setup_file_table_tab()

        # 리커버리 테이블 탭 추가
        self.setup_recovery_table_tab()

        # 내부 감사 탭 추가
        self.setup_internal_audit_tab()

        # 상태 표시줄 추가
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 테이블 뷰 필터 및 모델 설정
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterKeyColumn(-1)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.selectionModel().selectionChanged.connect(self.update_image_display)
        self.search_input.textChanged.connect(self.filter_table)

        #NoFocusFrameStyle 적용
        self.table_view.setStyle(NoFocusFrameStyle())

        self.initialize_mode()

    def analyze_srum_data(self):
        """SRUM 데이터 분석"""
        if not self.srudb_path or not self.software_path:
            print("SRUDB.dat 및 SOFTWARE 파일이 모두 지정되어야 합니다.")
            return

        print("SRUM 데이터 처리를 시작합니다.")

        # 출력 디렉터리 생성
        output_folder = os.path.join(os.path.dirname(self.srudb_path), "Output_File")
        os.makedirs(output_folder, exist_ok=True)

        # SrumECmd 실행
        self.app_table_tab.srudb_path = self.srudb_path
        self.app_table_tab.software_path = self.software_path
        self.app_table_tab.analyze_srum_data_for_analysis_mode()

        # ForegroundCycleTime 데이터 로드
        self.load_foreground_cycle_time(output_folder)

        # CSV 데이터를 AppTableWidget에 전달
        if self.csv_data is not None:
            print("[DEBUG] CSV 데이터를 AppTableWidget에 전달 중...")
            self.app_table_tab.set_csv_data(self.csv_data)
        else:
            print("[DEBUG] CSV 데이터가 None입니다. AppTableWidget에 전달할 수 없습니다.")

    def load_data(self, db_path=None):
        """ukg.db 데이터 로드 및 테이블 업데이트"""
        # db_path 인자를 제공하지 않으면, 인스턴스 변수를 사용
        if not db_path:
            db_path = self.db_path

        if not db_path or not os.path.exists(db_path):
            print("유효한 ukg.db 경로가 아닙니다.")
            self.status_bar.showMessage("ukg.db 파일 경로가 유효하지 않습니다.")
            return

        self.db_path = db_path
        print(f"ukg.db 데이터를 로드합니다: {db_path}")

        # 데이터베이스에서 데이터 및 헤더 가져오기
        data, headers = load_data_from_db(db_path)

        if data:
            updated_data = []
            for row in data:
                row = list(row)
                row[1] = map_name(row[1])  # 이벤트 이름 매핑
                image_token = row[2]
                row.append("O" if image_token else "X")  # 이미지 열 추가
                updated_data.append(row)

            headers.append("이미지")  # 새로운 열 헤더 추가
            model = SQLiteTableModel(updated_data, headers)
            self.proxy_model.setSourceModel(model)

            # 테이블 열 크기 조정
            self.table_view.resizeColumnToContents(0)
            self.table_view.resizeColumnToContents(1)
            self.table_view.resizeColumnToContents(5)

            # 숨길 열 설정
            self.table_view.hideColumn(2)
            self.table_view.hideColumn(6)
            self.table_view.hideColumn(7)
            self.table_view.resizeColumnToContents(len(headers) - 1)

            # 열을 가운데 정렬
            centered_delegate = CenteredDelegate(self.table_view)
            self.table_view.setItemDelegateForColumn(len(headers) - 1, centered_delegate)

            # 정렬 및 스크롤 초기화
            self.table_view.setSortingEnabled(True)
            self.table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
            self.table_view.scrollToTop()

            # 이미지 테이블 탭 업데이트
            if hasattr(self.image_table_tab, 'set_db_path'):
                self.image_table_tab.set_db_path(db_path)

            # 로그 출력
            self.status_bar.showMessage("ukg.db 데이터가 성공적으로 로드되었습니다.")
        else:
            # 데이터가 없을 경우 메시지 표시
            self.status_bar.showMessage("ukg.db 데이터를 불러오지 못했습니다.")
            print("ukg.db 데이터를 로드할 수 없습니다.")

    def open_file_dialog(self):
        """ukg.db 파일 선택 및 이후 관련 파일 선택"""
        import sqlite3  # sqlite3 명시적 임포트
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")  # 바탕화면 경로로 설정

        # Recover_Output 디렉토리 생성 (파일을 복사할 디렉토리)
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Recover_Output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # ukg.db 파일 선택
        db_path = self.open_file("ukg.db 파일 선택", desktop_path, "All Files (*)")

        if db_path:
            print(f"[DEBUG] ukg.db 파일 선택됨: {db_path}")
            self.db_path = db_path  # 선택한 파일 경로 저장

            # 분석 PC 모드 처리
            if self.current_mode == 'analysis':
                wal_file = self.open_file("ukg.db-wal 파일 선택", desktop_path, "All Files (*)")
                if wal_file:
                    remained_wal = os.path.join(output_dir, "remained.db-wal")
                    shutil.copyfile(wal_file, remained_wal)
                    print(f"[DEBUG] wal 파일 복사됨: {remained_wal}")
                else:
                    print("[DEBUG] wal 파일이 선택되지 않았습니다.")

            # 원본 디렉토리에서 ukg.db와 ukg.db-wal 파일 찾기
            original_dir = os.path.dirname(db_path)
            ukg_db_path = os.path.join(original_dir, "ukg.db")
            recovered_wal_db = os.path.join(output_dir, "recovered_with_wal.db")

            if os.path.exists(recovered_wal_db):
                os.remove(recovered_wal_db)

            if os.path.exists(ukg_db_path):
                shutil.copyfile(ukg_db_path, recovered_wal_db)
                print(f"[DEBUG] ukg.db 파일 복사됨: {recovered_wal_db}")
            else:
                print("[ERROR] ukg.db 파일을 찾을 수 없습니다.")
                return

            # DB 파일 로드 및 관련 데이터 설정
            self.load_data(self.db_path)

            # 다른 탭에 db_path 전달
            if hasattr(self.app_table_tab, 'set_db_path'):
                self.app_table_tab.set_db_path(self.db_path)
            if hasattr(self.image_table_tab, 'set_db_path'):
                self.image_table_tab.set_db_path(self.db_path)
            if hasattr(self.web_table_tab, 'set_db_path'):
                self.web_table_tab.set_db_path(self.db_path)
            if hasattr(self.file_table_tab, 'set_db_path'):
                self.file_table_tab.set_db_path(self.db_path)
            if hasattr(self.recovery_table_tab, 'set_db_paths'):
                self.recovery_table_tab.set_db_paths(db_path, recovered_wal_db)
            if hasattr(self.internal_audit_tab, 'set_db_path'):
                self.internal_audit_tab.set_db_path(self.db_path)

            # 대상 PC 모드에서 히스토리 파일 경로 설정
            if self.current_mode == 'target':
                chrome_history_path = os.path.join(desktop_path, "Recall_load", "Browser_History", "Chrome_History")
                edge_history_path = os.path.join(desktop_path, "Recall_load", "Browser_History", "Edge_History")

                for history_path, browser in [(chrome_history_path, "Chrome"), (edge_history_path, "Edge")]:
                    if os.path.exists(history_path):
                        print(f"[DEBUG] {browser} 히스토리 파일 경로 설정: {history_path}")
                        try:
                            self.web_table_tab.set_history_db_path(history_path)

                            # SQLite 파일 검증
                            with sqlite3.connect(history_path) as conn:
                                conn.execute("SELECT 1;")
                                print(f"[DEBUG] {history_path}는 유효한 SQLite 파일입니다.")

                            # 관련 데이터 갱신
                            self.web_table_tab.update_related_data_status()
                            print(f"[DEBUG] {browser} 히스토리 관련 데이터 갱신 완료.")
                        except sqlite3.Error as e:
                            print(f"[ERROR] {browser} 히스토리 파일 SQLite 오류: {e}")
                        except Exception as e:
                            print(f"[ERROR] {browser} 히스토리 데이터 처리 중 오류 발생: {e}")
                    else:
                        print(f"[DEBUG] {browser} 히스토리 파일이 존재하지 않습니다: {history_path}")

                # 테이블 뷰 새로고침
                self.web_table_tab.table_view.model().layoutChanged.emit()
                self.web_table_tab.table_view.viewport().update()
                print("[DEBUG] 테이블 뷰 강제 새로고침 완료.")

            # 분석 PC 모드에서 후속 파일 선택 실행
            if self.current_mode == 'analysis':
                self.open_additional_files_dialog()
        else:
            QMessageBox.warning(self, "파일 선택 취소", "ukg.db 파일이 선택되지 않았습니다.")

    def open_additional_files_dialog(self):
        """히스토리 파일 및 추가 파일 선택 후 데이터 병합"""
        try:
            desktop_path = os.path.expanduser("~/Desktop")  # 기본 경로

            # History 파일 선택
            history_files, _ = QFileDialog.getOpenFileNames(
                self, "히스토리 파일 선택", desktop_path, "All Files (*)"
            )

            if history_files:
                print(f"[DEBUG] 히스토리 파일이 선택되었습니다: {history_files}")

                # 기존 데이터 가져오기
                existing_model = self.web_table_tab.table_view.model()
                if isinstance(existing_model, QSortFilterProxyModel):
                    source_model = existing_model.sourceModel()
                else:
                    source_model = existing_model

                existing_data = []
                headers = []
                if source_model:
                    for row_index in range(source_model.rowCount()):
                        row = [
                            source_model.index(row_index, col).data()
                            for col in range(source_model.columnCount())
                        ]
                        existing_data.append(row)
                    headers = [
                        source_model.headerData(col, Qt.Horizontal)
                        for col in range(source_model.columnCount())
                    ]

                # 새 데이터 처리
                new_data = []
                for history_file in history_files:
                    if hasattr(self.web_table_tab, "set_history_db_path"):
                        self.web_table_tab.set_history_db_path(history_file)
                        self.web_table_tab.update_related_data_status()

                        # 모델에서 새 데이터 가져오기
                        current_model = self.web_table_tab.table_view.model()
                        if isinstance(current_model, QSortFilterProxyModel):
                            current_source_model = current_model.sourceModel()
                        else:
                            current_source_model = current_model

                        if current_source_model:
                            for row_index in range(current_source_model.rowCount()):
                                row = [
                                    current_source_model.index(row_index, col).data()
                                    for col in range(current_source_model.columnCount())
                                ]
                                new_data.append(row)

                # 병합 및 중복 제거
                merged_data_dict = {}

                # 기존 데이터 추가
                for row in existing_data:
                    key = (row[1], row[2], row[0])  # title, timestamp, uri를 키로 사용
                    if key not in merged_data_dict or merged_data_dict[key][3] == "X":
                        merged_data_dict[key] = row

                # 새로운 데이터 병합
                for row in new_data:
                    key = (row[1], row[2], row[0])  # title, timestamp, uri를 키로 사용
                    if key not in merged_data_dict or merged_data_dict[key][3] == "X":
                        merged_data_dict[key] = row

                # 최종 데이터 생성
                unique_rows = list(merged_data_dict.values())

                # 새로운 모델 생성 및 설정
                updated_model = SQLiteTableModel(unique_rows, headers)
                if isinstance(existing_model, QSortFilterProxyModel):
                    existing_model.setSourceModel(updated_model)
                    self.web_table_tab.table_view.setModel(existing_model)
                else:
                    self.web_table_tab.table_view.setModel(updated_model)

                # UI 갱신
                self.web_table_tab.table_view.viewport().update()
                print("[DEBUG] 히스토리 파일 데이터가 성공적으로 병합되었습니다.")

            else:
                print("히스토리 파일 선택이 건너뛰어졌습니다.")

            # SRUDB.dat 파일 선택
            srudb_file = self.open_file("SRUDB.dat 파일 선택", desktop_path, "All Files (*)")
            if srudb_file:
                self.srudb_path = srudb_file
                print(f"SRUDB.dat 파일이 선택되었습니다: {self.srudb_path}")
                if hasattr(self.app_table_tab, 'srudb_path'):
                    self.app_table_tab.srudb_path = srudb_file  # AppTableWidget에 경로 전달
            else:
                print("SRUDB.dat 파일 선택이 건너뛰어졌습니다.")
                return  # SRUDB 파일 없으면 분석 중단

            # SOFTWARE 파일 선택
            software_file = self.open_file("SOFTWARE 파일 선택", desktop_path, "All Files (*)")
            if software_file:
                self.software_path = software_file
                print(f"SOFTWARE 파일이 선택되었습니다: {self.software_path}")
                if hasattr(self.app_table_tab, 'software_path'):
                    self.app_table_tab.software_path = software_file  # AppTableWidget에 경로 전달
            else:
                print("SOFTWARE 파일 선택이 건너뛰어졌습니다.")
                return  # SOFTWARE 파일 없으면 분석 중단

            # 파일이 모두 선택된 경우에만 SRUM 분석 호출
            if self.srudb_path and self.software_path:
                print("SRUM 분석 함수 호출 시작")
                if hasattr(self.app_table_tab, 'analyze_srum_data_for_analysis_mode'):
                    self.app_table_tab.analyze_srum_data_for_analysis_mode()
                else:
                    print("[DEBUG] app_table_tab에 analyze_srum_data_for_analysis_mode 메서드가 없습니다.")
            else:
                print("SRUDB.dat 또는 SOFTWARE 파일이 누락되었습니다. 분석을 진행할 수 없습니다.")

        except Exception as e:
            print(f"open_additional_files_dialog에서 예외 발생: {e}")

    def open_file(self, title, default_path, file_filter="All Files (*)"):
        """파일 선택 다이얼로그 공통 메서드"""
        file_path, _ = QFileDialog.getOpenFileName(self, title, default_path, file_filter)
        return file_path if file_path else None

    def load_history_data(self, history_db_path):
        """히스토리 데이터 로드"""
        if not os.path.exists(history_db_path):
            print("히스토리 파일 경로가 유효하지 않습니다.")
            return

        self.history_db_path = history_db_path
        print(f"히스토리 데이터를 로드합니다: {history_db_path}")

        # WebTable 탭에 히스토리 데이터 전달
        if hasattr(self, 'web_table_tab') and self.web_table_tab:
            try:
                self.web_table_tab.set_history_db_path(history_db_path)
                print("WebTable 탭에 히스토리 경로를 전달했습니다.")
            except Exception as e:
                print(f"WebTable 탭에 히스토리를 전달하는 중 오류 발생: {e}")
        else:
            print("WebTable 탭이 초기화되지 않았습니다.")

    def load_srum_data(self, srudb_path, software_path):
        """SRUM 데이터 로드"""
        if not os.path.exists(srudb_path) or not os.path.exists(software_path):
            print("SRUM 데이터 파일 경로가 유효하지 않습니다.")
            return

        self.srudb_path = srudb_path
        self.software_path = software_path
        print(f"SRUDB.dat: {srudb_path}, SOFTWARE: {software_path} 데이터를 로드합니다.")

        # AppTable 탭에 SRUM 데이터 전달
        if hasattr(self, 'app_table_tab') and self.app_table_tab:
            try:
                self.app_table_tab.set_srum_paths(srudb_path, software_path)
                print("AppTable 탭에 SRUM 경로를 전달했습니다.")
            except Exception as e:
                print(f"AppTable 탭에 SRUM 데이터를 전달하는 중 오류 발생: {e}")
        else:
            print("AppTable 탭이 초기화되지 않았습니다.")

    def update_image_display(self, selected, deselected):
        for index in selected.indexes():
            row = index.row()
            file_path_index = self.proxy_model.index(row, 6)
            file_path = file_path_index.data()
            web_uri_index = self.proxy_model.index(row, 7)
            web_uri = web_uri_index.data()
            app_name_index = self.proxy_model.index(row, 4)
            app_name = app_name_index.data()
            window_title_index = self.proxy_model.index(row, 3)
            window_title = window_title_index.data()

            preview_text = f"""
                <div style="font-size: 11pt; line-height: 1;">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>File Path:</b> {file_path or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>Web URI:</b> {web_uri or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>App Name:</b> {app_name or 'N/A'}</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 0;">
                        <hr style="width: 80px; height: 1px; margin-right: 10px; border: none; background-color: black;">
                        <span style="flex-grow: 1;"><b>Window Title:</b> {window_title or 'N/A'}</span>
                    </div>
                </div>
                """
            self.data_viewer.setHtml(preview_text)

            image_token_index = self.proxy_model.index(row, 2)
            image_token = image_token_index.data()
            if image_token:
                image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
                image_path = os.path.join(image_dir, image_token)
                if not os.path.exists(image_path):
                    self.image_label.setText(f"이미지 파일을 찾을 수 없습니다: {image_token}")
                    return

                # 먼저 이미지를 image_label에 표시
                self.load_image_in_thread(image_path)
                # 이미지 클릭 이벤트 연결
                self.image_label.mousePressEvent = lambda e: self.on_image_label_double_click(image_token)
            else:
                self.image_label.clear()
                self.image_label.setText("이미지 없음")
                # 이미지가 없을 때는 클릭 이벤트 제거
                self.image_label.mousePressEvent = None
            break

    def load_image_in_thread(self, image_path):
        self.image_loader_thread = ImageLoaderThread(image_path)
        self.image_loader_thread.image_loaded.connect(self.display_image)
        self.image_loader_thread.start()

    def display_image(self, pixmap):
        scaled_pixmap = pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def filter_table(self):
        filter_text = self.search_input.text()
        self.proxy_model.setFilterWildcard(f"*{filter_text}*")

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        if os.path.exists("style.qss"):
            with open("style.qss", "r", encoding="utf-8") as f:
                qss = f.read()
                app.setStyleSheet(qss)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"애플리케이션 실행 중 예외 발생: {e}")