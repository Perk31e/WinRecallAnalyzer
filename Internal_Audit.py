from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QSplitter,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea, QGridLayout, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import sqlite3
import os
from datetime import datetime
from FlowLayout import FlowLayout  # FlowLayout 임포트
import re

class InternalAuditWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None  # db_path 초기화
        self.current_results = []  # 현재 결과를 저장할 리스트
        self.images_loaded = False  # 이미지 로드 여부 플래그
        self.current_selected_box = None  # 현재 선택된 set-box를 추적하기 위한 변수
        self.last_clicked_timestamp = None  # 마지막으로 클릭한 이미지의 토릃타임스탬프
        self.last_clicked_token = None      # 마지막으로 클릭한 이미지의 토큰
        self.setup_ui()

    def setup_ui(self):
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        
        # 검색 레이아웃 추가
        search_layout = QHBoxLayout()
        
        # 키워드 입력 박스 추가
        search_label = QLabel("검색어:")
        search_label.setToolTip("search example:\n"
                              "Single Search: 검색어\n"
                              "AND Search: 검색어1 && 검색어2\n"
                              "OR Search: 검색어1 || 검색어2")
        search_layout.addWidget(search_label)
        
        self.keyword_search = QLineEdit()
        self.keyword_search.setPlaceholderText("검색어 입력")
        self.keyword_search.setFixedWidth(150)
        self.keyword_search.setToolTip("search example:\n"
                                     "Single Search: 검색어\n"
                                     "AND Search: 검색어1 && 검색어2\n"
                                     "OR Search: 검색어1 || 검색어2")
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
        
        # 메인 레이아웃에 스플리 추가
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
            self.load_all_images()
            return
        
        if self.db_path is None:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")
            return

        try:
            print(f"[Internal Audit] 검색 시작 - 키워드: {keyword}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # AND 연산 (&&)
            if "&&" in keyword:
                terms = [term.strip() for term in keyword.split("&&")]
                params = []
                conditions = []
                for term in terms:
                    params.append(f"%{term}%")
                    conditions.append(f"EXISTS (SELECT 1 FROM WindowCaptureTextIndex_content wctc2 WHERE wctc2.c0 = wc.Id AND wctc2.c2 LIKE ?)")
                
                query = f"""
                SELECT DISTINCT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                WHERE {" AND ".join(conditions)}
                ORDER BY wc.TimeStamp ASC;
                """
                cursor.execute(query, params)
                
            # OR 연산 (||)
            elif "||" in keyword:
                terms = [term.strip() for term in keyword.split("||")]
                conditions = []
                params = []
                for term in terms:
                    conditions.append("wctc.c2 LIKE ?")
                    params.append(f"%{term}%")
                
                query = f"""
                SELECT DISTINCT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
                WHERE {" OR ".join(conditions)}
                ORDER BY wc.TimeStamp ASC;
                """
                cursor.execute(query, params)
                
            # 일반 검색
            else:
                query = """
                SELECT DISTINCT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
                WHERE wctc.c2 LIKE ?
                ORDER BY wc.TimeStamp ASC;
                """
                cursor.execute(query, (f"%{keyword}%",))

            results = cursor.fetchall()
            conn.close()

            print(f"[Internal Audit] 검색 결과 수: {len(results)}개")

            if results:
                # 중복 제거 (TimeStamp 기준)
                unique_results = []
                seen_tokens = set()
                for timestamp, token in results:
                    if token not in seen_tokens:
                        unique_results.append((timestamp, token))
                        seen_tokens.add(token)
                
                self.display_images(unique_results)
                self.lower_text_box.setText(f"총 {len(unique_results)}개의 결과가 검색되었습니다. (중복 제거됨)")
            else:
                self.clear_images()
                self.lower_text_box.setText("검색 결과가 없습니다.")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")
            self.lower_text_box.setText(f"데이터베이스 오류: {e}")

    def display_images(self, results):
        self.clear_images()
        if not self.db_path:
            print("[Internal Audit] DB 경로가 설정되지 않아 이미지를 표시할 수 없습니다.")
            return
        self.current_results = results
        self.current_selected_box = None

        # 고정된 이미지 크기 계산
        container_width = self.image_scroll_area.viewport().width()
        if container_width == 0:
            container_width = self.image_container.width()
        image_spacing = self.image_layout.spacing()
        images_per_row = 4

        # 스크롤바 너비를 고려하여 컨테이너 너비 조정 (스크롤바의 폭까지 고려해야 이미지 선택해서 파란생 상자의 오른쪽이 잘려서 보이는걸 방지함)
        scrollbar_width = self.image_scroll_area.verticalScrollBar().width()
        adjusted_container_width = container_width - (scrollbar_width // 3) # 3으로 나눠야 적당해보였음 (4로 나누면 파란상자가 살짝 잘려보임)
        # 이미지가 4개 이상일 때의 크기를 기준으로 고정
        fixed_image_width = (adjusted_container_width - (image_spacing * (images_per_row - 1))) // images_per_row
        fixed_image_height = int(fixed_image_width * 0.65)
        timestamp_height = 15

        # 중앙 정렬을 위한 컨테이너 생성
        center_container = QWidget()
        center_layout = QGridLayout(center_container)
        center_layout.setSpacing(2)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # 이미지 배치
        for index, (timestamp, image_token) in enumerate(results):
            set_box = QFrame()
            set_layout = QVBoxLayout(set_box)
            set_layout.setSpacing(0)
            set_layout.setContentsMargins(0, 0, 0, 0)
            set_layout.setAlignment(Qt.AlignCenter)  # 레이아웃 전체 중앙 정렬
            
            # 3D 효과 제거: NoFrame + Plain
            set_box.setFrameShape(QFrame.NoFrame)
            set_box.setFrameShadow(QFrame.Plain)
            
            # 평평한 흰색 바탕에 연한 회색 테두리
            set_box.setStyleSheet("""
                border: 1px solid #e0e0e0;
                padding: 0px;
                margin: 0px;
                background-color: #ffffff;
            """)

            image_box = QLabel()
            image_box.setAlignment(Qt.AlignCenter)
            image_box.setContentsMargins(0, 0, 0, 0)
            image_box.setStyleSheet("border: none; background-color: #ffffff;")

            timestamp_box = QLabel()
            timestamp_box.setAlignment(Qt.AlignCenter)  # Qt.AlignCenter는 수직/수평 모두 중앙 정렬
            timestamp_box.setContentsMargins(0, 0, 0, 0)
            timestamp_box.setStyleSheet("""
                border: none; 
                border-top: 1px solid #e0e0e0; 
                background-color: #ffffff;
                padding: 0px;
                font-size: 12pt;
                font-weight: bold;
            """)
            timestamp_box.setFixedHeight(timestamp_height)

            # 타임스탬프 박스를 위한 컨테이너 생성
            timestamp_container = QWidget()
            timestamp_layout = QVBoxLayout(timestamp_container)
            timestamp_layout.setContentsMargins(0, 0, 0, 0)
            timestamp_layout.setSpacing(0)
            timestamp_layout.addWidget(timestamp_box, 0, Qt.AlignCenter)  # 수직 중앙 정렬
            
            dt = datetime.fromtimestamp(timestamp / 1000)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            timestamp_box.setText(formatted_time)

            base_image_path = os.path.join(os.path.dirname(self.db_path), "ImageStore", image_token)
            base_image_path = os.path.normpath(base_image_path)
            possible_extensions = ['', '.jpg', '.jpeg', '.png']
            image_path_with_ext = None

            for ext in possible_extensions:
                temp_path = base_image_path + ext
                if os.path.exists(temp_path):
                    image_path_with_ext = temp_path
                    break

            if image_path_with_ext:
                pixmap = QPixmap(image_path_with_ext)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        fixed_image_width, fixed_image_height,  # 고정된 크기 사용
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    image_box.setPixmap(scaled_pixmap)
                    timestamp_box.setFixedWidth(fixed_image_width)  # 고정된 너비 사용
                    image_box.setFixedSize(fixed_image_width, fixed_image_height)  # 고정된 크기 사용

                    # 클릭 이벤트 연결
                    set_box.mousePressEvent = lambda e, box=set_box, t=timestamp: self.handle_image_click(box, t)

                    set_layout.addWidget(image_box)
                    set_layout.addWidget(timestamp_container)  # timestamp_box 대신 container 추가

                    # 그리드 레이아웃에 추가
                    row = index // images_per_row
                    col = index % images_per_row
                    center_layout.addWidget(set_box, row, col, Qt.AlignLeft | Qt.AlignTop)  # 왼쪽 상단 정렬
                else:
                    print("[Internal Audit] 이미지 로드 실패 (픽스맵이 NULL입니다):", image_path_with_ext)
            else:
                print("[Internal Audit] 이미지 파일을 찾을 수 없음:", base_image_path)

        # 빈 공간을 채우기 위한 스페이서 추가
        center_layout.setColumnStretch(images_per_row, 1)
        
        # 중앙 컨테이너를 이미지 레이아웃에 추가
        self.image_layout.addWidget(center_container, 0, 0, Qt.AlignLeft | Qt.AlignTop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 창 크기 변경 시 이미지를 다시 표시
        if self.current_results and event.oldSize().width() != event.size().width():
            self.display_images(self.current_results)

    def clear_images(self):
        """이미지 레이아웃 초기화"""
        self.current_selected_box = None  # 선택 초기화
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
        """
        위젯이 화면에 표시될 때 호출되는 이벤트 핸들러
        위젯이 처음 표시될 때만 이미지를 로드하여 불필요한 중복 로딩 방지
        """
        super().showEvent(event)
        # 이미지가 아직 로드되지 않은 경우에만 초기 데이터 로드 수행
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

    def clean_ocr_text(self, text):
        """OCR 텍스트를 정제하는 함수"""
        if not text:
            return ""
            
        # 허용할 수문자 목록
        allowed_chars = r'[()<>\[\];/]'
        
        # 1. 연속된 공백을 하나로 치환
        text = re.sub(r'\s+', ' ', text)
        
        # 2. 허용된 특수문자는 보존하면서 나머지 텍스트 정제
        cleaned_text = ''
        for line in text.split('\n'):
            # 특수문자와 기본 텍스트 보존
            cleaned_line = re.sub(r'[^a-zA-Z가-힣0-9\s,.:()<>\[\];/]', '', line)
            # 앞뒤 공백 제거
            cleaned_line = cleaned_line.strip()
            if cleaned_line:
                cleaned_text += cleaned_line + '\n'
        
        return cleaned_text.strip()

    def show_ocr_content(self, timestamp):
        """선택된 이미지의 OCR 내용을 표시"""
        try:
            print(f"[Internal Audit] OCR 내용 조회 - TimeStamp: {timestamp}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 현재 검색어 가져오기
            current_search = self.keyword_search.text().strip()
            search_terms = []
            if "&&" in current_search:
                search_terms = [term.strip() for term in current_search.split("&&")]
            elif "||" in current_search:
                search_terms = [term.strip() for term in current_search.split("||")]
            elif current_search:
                search_terms = [current_search]
            
            query = """
            SELECT 
                wc.TimeStamp,
                wc.WindowTitle,
                GROUP_CONCAT(DISTINCT a.Name) as app_names,
                GROUP_CONCAT(DISTINCT w.Uri) as web_uris,
                GROUP_CONCAT(DISTINCT f.Path) as file_paths,
                GROUP_CONCAT(wctc.c2, ' ') as ocr_text
            FROM WindowCapture wc
            LEFT JOIN WindowCaptureAppRelation wcar ON wc.Id = wcar.WindowCaptureId
            LEFT JOIN App a ON wcar.AppId = a.Id
            LEFT JOIN WindowCaptureWebRelation wcwr ON wc.Id = wcwr.WindowCaptureId
            LEFT JOIN Web w ON wcwr.WebId = w.Id
            LEFT JOIN WindowCaptureFileRelation wcfr ON wc.Id = wcfr.WindowCaptureId
            LEFT JOIN File f ON wcfr.FileId = f.Id
            LEFT JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
            WHERE wc.TimeStamp = ?
            GROUP BY wc.Id;
            """
            
            cursor.execute(query, (timestamp,))
            result = cursor.fetchone()
            conn.close()

            if result:
                timestamp, window_title, app_names, web_uris, file_paths, ocr_text = result
                
                # Unix timestamp를 datetime으로 변환
                dt = datetime.fromtimestamp(timestamp / 1000)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # 결과 텍스트 구성 (HTML 형식 사용, 스타일 개선)
                output_text = f"""<div style='font-size: 12pt;'>
                                <p><b style='font-size: 12pt;'>Time:</b> {formatted_time}</p>

                                <p><b style='font-size: 12pt;'>Window Title:</b> {window_title if window_title else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>애플리케이션 명:</b> {app_names if app_names else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>Web Uri:</b> {web_uris if web_uris else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>File Path:</b> {file_paths if file_paths else 'N/A'}</p>
                                """

                if ocr_text:
                    # 검색어 강조 처리 (글자 크기 증가)
                    highlighted_text = ocr_text
                    if search_terms:
                        # 검색어 목록을 정규식 패턴으로 변환
                        pattern = '|'.join(map(re.escape, search_terms))
                        # 대소문자 구분 없이 검색어 찾기
                        highlighted_text = re.sub(
                            f'({pattern})', 
                            r'<b style="font-size: 14pt; background-color: yellow;">\1</b>', 
                            highlighted_text, 
                            flags=re.IGNORECASE
                        )
                    
                    # OCR 텍스트 정제 (검색어 강조 이후)
                    cleaned_text = self.clean_ocr_text(highlighted_text)
                    
                    # 검색어 정보 추가 - 연산자를 더 직관적으로 표시
                    if search_terms:
                        operator = " AND " if "&&" in current_search else " OR " if "||" in current_search else " "
                        search_terms_str = operator.join(f'<b style="font-size: 14pt; color: #0078D7;">{term}</b>' for term in search_terms)
                        output_text += f"""
                                        <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>
                                        <p><b style='font-size: 12pt;'>검색어</b> ({search_terms_str})가 포함된 이미지입니다.</p>
                                        """
                    
                    output_text += f"""
                                    <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>
                                    <p><b style='font-size: 12pt;'>OCR 출력물:</b></p>
                                    <p>{cleaned_text}</p>
                                    """
                
                output_text += "</div>"
                self.lower_text_box.setHtml(output_text)
            else:
                self.lower_text_box.setHtml("<p style='font-size: 10pt;'>내용을 찾을 수 없습니다.</p>")
                
        except sqlite3.Error as e:
            print(f"[Internal Audit] 데이터베이스 오류: {e}")
            self.lower_text_box.setHtml(f"<p style='font-size: 10pt;'>데이터베이스 오류: {e}</p>")

    def load_all_images(self):
        """모든 이미미지를 로드"""
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

    def handle_image_click(self, clicked_box, timestamp):
        """이미지 클릭 이벤트 처리"""
        if self.current_selected_box:
            # 이전에 선택한 박스를 기본 스타일로 복원
            self.current_selected_box.setStyleSheet("""
                border: 1px solid #e0e0e0;
                padding: 0px;
                margin: 0px;
                background-color: #ffffff;
            """)

        # 현재 클릭한 박스에 파란색 테두리 적용
        clicked_box.setStyleSheet("""
            border: 2px solid #0078D7;
            padding: 0px;
            margin: 0px;
            background-color: #ffffff;
        """)

        # 클릭한 박스를 맨 앞으로 이동
        clicked_box.raise_()

        # 같은 이미지를 두 번 클릭했는지 확인
        if timestamp == self.last_clicked_timestamp:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT ImageToken FROM WindowCapture WHERE TimeStamp = ?", (timestamp,))
                result = cursor.fetchone()
                conn.close()

                if result and result[0]:
                    main_window = self.window()
                    if hasattr(main_window, 'tab_widget') and hasattr(main_window, 'image_table_tab'):
                        main_window.tab_widget.setCurrentWidget(main_window.image_table_tab)
                        main_window.image_table_tab.display_image_from_token_with_index(result[0])
                    return
            except sqlite3.Error as e:
                print(f"[Internal Audit] 데이터베이스 오류: {e}")

        # 현재 클릭한 이미지 정보 저장
        self.last_clicked_timestamp = timestamp
        self.current_selected_box = clicked_box
        self.show_ocr_content(timestamp)