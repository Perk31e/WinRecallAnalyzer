from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QSplitter,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import sqlite3
import os
from datetime import datetime
from FlowLayout import FlowLayout  # FlowLayout 임포트

class InternalAuditWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None  # db_path 초기화
        self.current_results = []  # 현재 결과를 저장할 리스트
        self.images_loaded = False  # 이미지 로드 여부 플래그
        self.setup_ui()

    def setup_ui(self):
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        
        # 검색 레이아웃 추가
        search_layout = QHBoxLayout()
        
        # 키워드 입력 박스 추가
        search_layout.addWidget(QLabel("검색어:"))
        self.keyword_search = QLineEdit()
        self.keyword_search.setPlaceholderText("OCR 검색")
        self.keyword_search.setFixedWidth(200)
        search_layout.addWidget(self.keyword_search)

        # Enter 키 시 search_images 호출
        self.keyword_search.returnPressed.connect(self.search_images)

        # 검색 버튼
        search_button = QPushButton("검색")
        search_button.clicked.connect(self.search_images)
        search_layout.addWidget(search_button)

        # 초기화 버튼
        reset_button = QPushButton("초기화")
        reset_button.clicked.connect(self.reset_search)
        search_layout.addWidget(reset_button)
        
        # 검색 레이아웃에 stretch 추가하여 나머지 공간 채우기
        search_layout.addStretch()
        
        # 검색 레이아웃을 메인 레이아웃에 추가
        main_layout.addLayout(search_layout)
        
        # 스플리터 생성
        splitter = QSplitter(Qt.Vertical)
        
        # 이미지 디스플레이를 위한 스크롤 영역 생성
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setMinimumHeight(400)  # 최소 높이 설정
        
        # 이미지 컨테이너 위젯 설정
        self.image_container = QWidget()
        self.image_container.setMinimumWidth(800)  # 최소 너비 설정
        
        # 이미지 컨테이너의 레이아웃을 QGridLayout으로 설정
        self.image_layout = QGridLayout(self.image_container)
        self.image_layout.setSpacing(2)  # 전체 간격을 2로 설정하여 여백 감소
        self.image_layout.setHorizontalSpacing(2)  # 수평 간격 설정
        self.image_layout.setVerticalSpacing(0)  # 수직 간격을 0으로 설정하여 상하 여백 제거
        self.image_layout.setContentsMargins(0, 0, 0, 0)  # 레이아웃의 여백 제거
        
        # 이미지 컨테이너를 스크롤 영역에 설정
        self.image_scroll_area.setWidget(self.image_container)
        
        # 하단 텍스트 상자 생성
        self.lower_text_box = QTextEdit()
        self.lower_text_box.setReadOnly(True)
        self.lower_text_box.setMinimumHeight(200)  # 최소 높이 설정
        
        # 스플리터에 위젯 추가
        splitter.addWidget(self.image_scroll_area)
        splitter.addWidget(self.lower_text_box)
        
        # 스플리터 비율 설정 (7:3)
        splitter.setSizes([700, 300])
        
        # 메인 레이아웃에 스플리터 추가
        main_layout.addWidget(splitter)
        
        # 초기 텍스트 설정
        self.lower_text_box.setText("하단 분석 결과가 여기에 표시됩니다.")

        # 이미지 컨테이너의 여백 제거
        self.image_container.setContentsMargins(0, 0, 0, 0)

    def set_db_path(self, db_path):
        """데이터베이스 경로 설정"""
        print(f"[Internal Audit] DB 경로 설정: {db_path}")  # 디버깅 메시지
        self.db_path = db_path

    def search_images(self):
        """OCR 검색 수행"""
        keyword = self.keyword_search.text().strip()
        if not keyword:
            self.load_all_images()  # 검색어가 없으면 모든 이미지 로드
            return
        
        if self.db_path is None:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")
            return

        try:
            print(f"[Internal Audit] 검색 시작 - 키워드: {keyword}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # c2 컬럼만 검색하도록 수정
            query = """
            SELECT wc.TimeStamp, wc.ImageToken
            FROM WindowCapture wc
            JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
            WHERE wctc.c2 LIKE ?
            ORDER BY wc.TimeStamp ASC;
            """
            
            wildcard_keyword = f"%{keyword}%"
            cursor.execute(query, (wildcard_keyword,))
            results = cursor.fetchall()
            conn.close()

            print(f"[Internal Audit] 검색 결과 수: {len(results)}개")

            if results:
                self.display_images(results)
                self.lower_text_box.setText(f"총 {len(results)}개의 결과가 검색되었습니다.")
            else:
                self.clear_images()
                self.lower_text_box.setText("검색 결과가 없습니다.")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")
            self.lower_text_box.setText(f"데이터베이스 오류: {e}")

    def display_images(self, results):
        """검색된 이미지를 표시"""
        self.clear_images()
        if not self.db_path:
            print("[Internal Audit] DB 경로가 설정되지 않아 이미지를 표시할 수 없습니다.")
            return
        self.current_results = results  # 현재 결과 저장

        # 이미지 컨테이너의 크기를 가져오기
        container_width = self.image_scroll_area.viewport().width()
        if container_width == 0:
            container_width = self.image_container.width()
        image_spacing = self.image_layout.spacing()  # 이미지 간의 간격
        images_per_row = 4  # 한 줄에 표시할 이미지 수

        # 이미지 크기 계산
        total_spacing = image_spacing * (images_per_row - 1)  # 양쪽 여백 제외
        image_width = (container_width - total_spacing) // images_per_row
        image_width = max(100, image_width)  # 최소 이미지 너비 설정

        # 이미지 높이를 너비의 80%로 설정하여 상하 여백 감소
        image_height = int(image_width * 0.65)

        image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
        
        for index, (timestamp, image_token) in enumerate(results):
            base_image_path = os.path.join(image_dir, image_token)
            base_image_path = os.path.normpath(base_image_path)
            possible_extensions = ['', '.jpg', '.jpeg', '.png']
            image_path_with_ext = None

            for ext in possible_extensions:
                temp_path = base_image_path + ext
                if os.path.exists(temp_path):
                    image_path_with_ext = temp_path
                    break

            if image_path_with_ext:
                try:
                    pixmap = QPixmap(image_path_with_ext)
                    if not pixmap.isNull():
                        label = QLabel()
                        label.setContentsMargins(0, 0, 0, 0)
                        label.setAlignment(Qt.AlignCenter)
                        label.setStyleSheet("padding: 0px; margin: 0px;")

                        scaled_pixmap = pixmap.scaled(
                            image_width, image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        label.setPixmap(scaled_pixmap)
                        label.setFixedSize(image_width, image_height)
                        
                        # 이미지 클릭 이벤트 추가
                        label.mousePressEvent = lambda e, t=timestamp: self.show_ocr_content(t)
                        
                        # 행과 열 계산
                        row = index // images_per_row
                        col = index % images_per_row
                        self.image_layout.addWidget(label, row, col)
                    else:
                        print(f"[Internal Audit] 이미지 로드 실패 (픽스맵이 NULL): {image_path_with_ext}")
                        continue
                except Exception as e:
                    print(f"[Internal Audit] 이미지 처리 중 오류 발생: {str(e)}")
                    continue
            else:
                print(f"[Internal Audit] 이미지 파일을 찾을 수 없음: {base_image_path}")
                continue

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 창 크기 변경 시 이미지를 다시 표시
        if self.current_results and event.oldSize().width() != event.size().width():
            self.display_images(self.current_results)

    def clear_images(self):
        """이미지 레이아웃 초기화"""
        for i in reversed(range(self.image_layout.count())):
            widget = self.image_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def reset_search(self):
        """검색 초기화"""
        self.keyword_search.clear()
        self.load_all_images()  # 초기화 시 모든 이미지 로드

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 창 크기 변경 시 이미지를 다시 표시
        if self.current_results and event.oldSize().width() != event.size().width():
            self.display_images(self.current_results)

    def showEvent(self, event):
        super().showEvent(event)
        # 처음으로 위젯이 표시될 때만 이미지를 로드
        if not self.images_loaded:
            self.images_loaded = True
            self.load_initial_data()

    def load_initial_data(self):
        """초기 데이터 로드"""
        if self.db_path:
            try:
                print("[Internal Audit] 초기 데이터 로드 시도")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 모든 이미지 토큰을 가져오는 쿼리
                query = """
                SELECT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                WHERE wc.ImageToken IS NOT NULL
                ORDER BY wc.TimeStamp ASC;
                """
                
                cursor.execute(query)
                results = cursor.fetchall()
                conn.close()

                print(f"[Internal Audit] 초기 데이터 로드 완료: {len(results)}개 이미지")

                if results:
                    # 이미지 파일이 존재하는 것만 필터링
                    filtered_results = self.filter_existing_images(results)
                    self.display_images(filtered_results)
                    self.lower_text_box.setText(f"총 {len(filtered_results)}개의 이미지가 로드되었습니다.")
                else:
                    print("[Internal Audit] 표시할 이미지가 없습니다.")
                    self.lower_text_box.setText("표시할 이미지가 없습니다.")
                    
            except sqlite3.Error as e:
                print(f"[Internal Audit] 데이터베이스 오류: {e}")
                self.lower_text_box.setText(f"데이터베이스 오류: {e}")
        else:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")

    def filter_existing_images(self, results):
        """이미지 파일이 존재하는 결과만 반환"""
        image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
        if not os.path.exists(image_dir):
            print(f"[Internal Audit] 이미지 디렉토리가 존재하지 않습니다: {image_dir}")
            return []

        filtered_results = []
        for timestamp, image_token in results:
            base_image_path = os.path.join(image_dir, image_token)
            base_image_path = os.path.normpath(base_image_path)
            possible_extensions = ['', '.jpg', '.jpeg', '.png']

            image_exists = False
            for ext in possible_extensions:
                temp_path = base_image_path + ext
                if os.path.exists(temp_path):
                    image_exists = True
                    break

            if image_exists:
                filtered_results.append((timestamp, image_token))
            else:
                print(f"[Internal Audit] 이미지 파일을 찾을 수 없음: {base_image_path}")

        return filtered_results

    def show_ocr_content(self, timestamp):
        """선택된 이미지의 OCR 내용을 표시"""
        try:
            print(f"[Internal Audit] OCR 내용 조회 - TimeStamp: {timestamp}")  # 디버깅용
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 쿼리 수정
            query = """
            SELECT GROUP_CONCAT(wctc.c2, ' ') as ocr_text
            FROM WindowCapture wc
            JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
            WHERE wc.TimeStamp = ?
            GROUP BY wc.Id;
            """
            
            cursor.execute(query, (timestamp,))
            result = cursor.fetchone()
            conn.close()

            print(f"[Internal Audit] 쿼리 결과: {result}")  # 디버깅용

            if result and result[0]:
                ocr_text = result[0]
                self.lower_text_box.setText(f"OCR 내용:\n{ocr_text}")
            else:
                self.lower_text_box.setText("OCR 내용을 찾을 수 없습니다.")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")
            self.lower_text_box.setText(f"데이터베이스 오류: {e}")

    def load_all_images(self):
        """모든 이미지를 로드"""
        if self.db_path:
            try:
                print("[Internal Audit] 모든 이미지 로드 시도")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 모든 이미지 토큰을 가져오는 쿼리
                query = """
                SELECT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                WHERE wc.ImageToken IS NOT NULL
                ORDER BY wc.TimeStamp ASC;
                """
                
                cursor.execute(query)
                results = cursor.fetchall()
                conn.close()

                print(f"[Internal Audit] 모든 이미지 로드 완료: {len(results)}개 이미지")

                if results:
                    # 이미지 파일이 존재하는 것만 필터링
                    filtered_results = self.filter_existing_images(results)
                    self.display_images(filtered_results)
                    self.lower_text_box.setText(f"총 {len(filtered_results)}개의 이미지가 로드되었습니다.")
                else:
                    print("[Internal Audit] 표시할 이미지가 없습니다.")
                    self.lower_text_box.setText("표시할 이미지가 없습니다.")
                    
            except sqlite3.Error as e:
                print(f"[Internal Audit] 데이터베이스 오류: {e}")
                self.lower_text_box.setText(f"데이터베이스 오류: {e}")
        else:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")
