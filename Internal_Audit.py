from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QSplitter,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import sqlite3
import os
from datetime import datetime

class InternalAuditWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None  # db_path 초기화
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
        
        # 이미지 레이아웃 설정
        self.image_layout = QGridLayout(self.image_container)
        self.image_layout.setSpacing(10)  # 이미지 간 간격 설정
        self.image_layout.setContentsMargins(10, 10, 10, 10)  # 여백 설정
        
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

    def set_db_path(self, db_path):
        """데이터베이스 경로 설정"""
        print(f"[Internal Audit] DB 경로 설정: {db_path}")  # 디버깅 메시지
        self.db_path = db_path

        # 초기 데이터 로드
        try:
            print("[Internal Audit] 초기 데이터 로드 시도")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 최근 10개의 이미지 토큰을 가져오는 쿼리
            query = """
            SELECT wc.TimeStamp, wc.ImageToken
            FROM WindowCapture wc
            WHERE wc.ImageToken IS NOT NULL
            ORDER BY wc.TimeStamp DESC
            LIMIT 10;
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            print(f"[Internal Audit] 초기 데이터 로드 완료: {len(results)}개 이미지")

            if results:
                self.display_images(results)
                self.lower_text_box.setText(f"총근 {len(results)}개의 이미지가 로드되었습니다.")
            else:
                print("[Internal Audit] 표시할 이미지가 없습니다.")
                self.lower_text_box.setText("표시할 이미지가 없습니다.")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")
            self.lower_text_box.setText(f"데이터베이스 오류: {e}")

    def search_images(self):
        """OCR 검색 수행"""
        keyword = self.keyword_search.text().strip()
        if not keyword:
            self.reset_search()
            return
        
        if self.db_path is None:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")  # 디버깅 메시지
            return

        try:
            print(f"[Internal Audit] 검색 시작 - 키워드: {keyword}")  # 디버깅 메시지
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT wc.TimeStamp, wc.ImageToken
            FROM WindowCapture wc
            JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
            WHERE wctc.c1 LIKE ? OR wctc.c2 LIKE ?
            ORDER BY wc.TimeStamp ASC;
            """
            
            wildcard_keyword = f"%{keyword}%"
            cursor.execute(query, (wildcard_keyword, wildcard_keyword))
            results = cursor.fetchall()
            conn.close()

            print(f"[Internal Audit] 검색 결과 수: {len(results)}개")  # 디버깅 메시지

            if results:
                self.display_images(results)
                self.lower_text_box.setText(f"총 {len(results)}개의 결과가 검색되었습니다.")
            else:
                self.clear_images()
                self.lower_text_box.setText("검색 결과가 없습니다.")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")  # 디버깅 메시지
            self.lower_text_box.setText(f"데이터베이스 오류: {e}")

    def display_images(self, results):
        """검색된 이미지를 표시"""
        self.clear_images()
        if not hasattr(self, 'db_path') or self.db_path is None:
            print("[Internal Audit] DB 경로가 설정되지 않아 이미지를 표시할 수 없습니다.")
            return

        image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
        print(f"[Internal Audit] 이미지 디렉토리: {image_dir}")
        
        if not os.path.exists(image_dir):
            print(f"[Internal Audit] 이미지 디렉토리가 존재하지 않습니다: {image_dir}")
            return
        
        for index, (timestamp, image_token) in enumerate(results):
            print(f"[Internal Audit] 처리 중인 이미지 {index + 1}/{len(results)}")
            print(f"[Internal Audit] 타임스탬프: {timestamp}, 이미지 토큰: {image_token}")
            
            base_image_path = os.path.join(image_dir, image_token)
            base_image_path = os.path.normpath(base_image_path)
            print(f"[Internal Audit] 기본 이미지 경로: {base_image_path}")
            
            # 이미지 파일 존재 여부 확인 (확장자 시도)
            possible_extensions = ['', '.jpg', '.jpeg', '.png']
            image_path_with_ext = None
            
            for ext in possible_extensions:
                temp_path = base_image_path + ext
                if os.path.exists(temp_path):
                    image_path_with_ext = temp_path
                    print(f"[Internal Audit] 이미지 파일 찾음: {temp_path}")
                    break
            
            if image_path_with_ext:
                try:
                    pixmap = QPixmap(image_path_with_ext)
                    if not pixmap.isNull():
                        label = QLabel()
                        scaled_pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        label.setPixmap(scaled_pixmap)
                        row = index // 4
                        col = index % 4
                        self.image_layout.addWidget(label, row, col)
                        print(f"[Internal Audit] 이미지 표시 성공 - 위치: ({row}, {col})")
                    else:
                        print(f"[Internal Audit] 이미지 로드 실패 (픽스맵이 NULL): {image_path_with_ext}")
                except Exception as e:
                    print(f"[Internal Audit] 이미지 처리 중 오류 발생: {str(e)}")
            else:
                print(f"[Internal Audit] 이미지 파일을 찾을 수 없음: {base_image_path}")

    def clear_images(self):
        """이미지 레이아웃 초기화"""
        for i in reversed(range(self.image_layout.count())):
            widget = self.image_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    def reset_search(self):
        """검색 초기화"""
        self.keyword_search.clear()
        self.clear_images()
        self.lower_text_box.setText("하단 분석 결과가 여기에 표시됩니다.")
