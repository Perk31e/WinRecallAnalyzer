# Internal_Audit.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QSplitter,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QScrollArea, QGridLayout, QFrame, QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                              QDialogButtonBox, QMessageBox, QMenuBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QAction
import sqlite3
import os
from datetime import datetime
import re
import json

def replace_placeholders_recursive(text, name_to_term):
    """
    재귀(반복)적으로 {placeholder}를 치환하여
    더 이상 치환할 부분이 없을 때 최종 문자열을 반환
    """
    pattern = r'\{([^}]+)\}'
    
    while True:
        # re.sub에서 lambda로 매칭된 키를 체크하고, 있으면 치환, 없으면 그대로 둔다.
        new_text = re.sub(pattern, lambda m: f"({name_to_term[m.group(1).strip()]})" 
                            if m.group(1).strip() in name_to_term 
                            else m.group(0), text)
        
        if new_text == text:
            # 더 이상 치환되지 않았으면 break
            break
        text = new_text
    
    return text

class InternalAuditWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None  # db_path 초기화
        self.current_results = []  # 현재 결과를 저장할 리스트
        self.images_loaded = False  # 이미지 로드 여부 플래그
        self.current_selected_box = None  # 현재 선택된 set-box를 추적하기 위한 변수
        self.last_clicked_timestamp = None  # 마지막으로 클릭한 이미지의 타임스탬프
        self.last_clicked_token = None      # 마지막으로 클릭한 이미지의 토큰
        self.current_page = 1  # 현재 페이지
        self.images_per_page = 28  # 페이지당 이미지 수
        self.setup_ui()

    def setup_ui(self):
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        
        # 검색 레이아웃 추가 (QHBoxLayout 대신 QGridLayout 사용)
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)
        
        # 왼쪽 검색 영역
        left_layout = QHBoxLayout()
        left_layout.setSpacing(5)
        left_layout.setAlignment(Qt.AlignLeft)
        
        # 키워드 입력 박스 추가
        search_label = QLabel("검색어:")
        search_label.setToolTip("search example:\n"
                                "Single Search: 검색어\n"
                                "AND Search: 검색어1 && 검색어2\n"
                                "OR Search: 검색어1 || 검색어2\n"
                                "Window Title: %Title% == 검색어\n"
                                "App Name: %App% == 검색어\n"
                                "Web URL: %Web% == 검색어\n"
                                "File Path: %File% == 검색어\n"
                                "OCR Text: %OCR% == 검색어"
                                )

        search_label.setFixedWidth(50)
        left_layout.addWidget(search_label)
        
        self.keyword_search = QLineEdit()
        self.keyword_search.setPlaceholderText("검색어 입력")
        self.keyword_search.setToolTip("search example:\n"
                                    "Single Search: 검색어\n"
                                    "AND Search: 검색어1 && 검색어2\n"
                                    "OR Search: 검색어1 || 검색어2\n"
                                    "Window Title: %Title% == 검색어\n"
                                    "App Name: %App% == 검색어\n"
                                    "Web URL: %Web% == 검색어\n"
                                    "File Path: %File% == 검색어\n"
                                    "OCR Text: %OCR% == 검색어"
                                    )

        self.keyword_search.setFixedWidth(250)
        left_layout.addWidget(self.keyword_search)

        # Enter 키 시 search_images 호출
        self.keyword_search.returnPressed.connect(self.search_images)

        # 입력 박스의 높이를 가져와서 버튼 스타일에 적용
        input_height = self.keyword_search.sizeHint().height()

        # 버튼들의 스타일과 크기 설정
        button_style = f"""
            QPushButton {{
                max-width: 40px;
                min-width: 40px;
                height: {input_height}px;
                /* padding-top/bottom: 0px, padding-left/right: 5px */
                padding: 0px 5px;
            }}
        """

        # 검색 버튼
        search_button = QPushButton("검색")
        search_button.setStyleSheet(button_style)
        search_button.clicked.connect(self.search_images)
        left_layout.addWidget(search_button)

        # 고급 버튼
        advanced_search_button = QPushButton("고급")
        advanced_search_button.setStyleSheet(button_style)
        advanced_search_button.clicked.connect(self.show_advanced_search_dialog)
        left_layout.addWidget(advanced_search_button)

        # 초기화 버튼
        reset_button = QPushButton("초기화")
        reset_button.setStyleSheet(button_style)
        reset_button.clicked.connect(self.reset_search)
        left_layout.addWidget(reset_button)
        
        # 왼쪽 레이아웃을 검색 레이아웃에 추가
        search_layout.addLayout(left_layout)
        
        # 검색 컨테이너를 메인 레이아웃에 추가
        main_layout.addWidget(search_container)

        # 스플리터 생성
        splitter = QSplitter(Qt.Vertical)
        
        # 이미지 디스플레이를 위한 스크롤 영역 생성
        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidgetResizable(True)
        # self.image_scroll_area.setMinimumHeight(400)
        
        # 이미지 컨테이너 설정
        self.image_container = QWidget()
        self.image_container.setMinimumWidth(800)
        
        # 이미지 레이아웃 설정
        self.image_layout = QGridLayout(self.image_container)
        self.image_layout.setSpacing(2)
        self.image_layout.setHorizontalSpacing(2)
        self.image_layout.setVerticalSpacing(0)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_scroll_area.setWidget(self.image_container)
        
        # 하단 텍스트 박스
        self.lower_text_box = QTextEdit()
        self.lower_text_box.setReadOnly(True)
        # self.lower_text_box.setMinimumHeight(200)
        
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
        """OCR, App, Web, File 검색 수행"""
        # 검색 시작 시 현재 페이지를 1로 초기화
        self.current_page = 1
        
        original_keyword = self.keyword_search.text().strip()  # 원본 키워드 저장
        if not original_keyword:
            self.load_all_images()
            return
        
        if self.db_path is None:
            print("[Internal Audit] DB 경로가 설정되지 않았습니다.")
            return

        # {} 패턴 여부 확인
        has_braces = bool(re.search(r'\{([^}]+)\}', original_keyword))

        processed_keyword = original_keyword
        name_to_term = {}

        # {}가 있을 때만 search_terms.json 로드
        if has_braces and os.path.exists('search_terms.json'):
            try:
                with open('search_terms.json', 'r', encoding='utf-8') as f:
                    saved_terms = json.load(f)
                    print(f"[DEBUG] Loaded search_terms: {saved_terms}")
                    # saved_terms: [{'enabled': bool, 'name': str, 'term': str, ...}, ...]
                    for t in saved_terms:
                        if 'name' in t and 'term' in t:
                            name_to_term[t['name']] = t['term']
            except Exception as e:
                print(f"[Internal Audit] search_terms.json 로드 오류: {e}")

        # {}가 있을 때만 {} 패턴을 실제 검색어로 변환
        if has_braces:
            # 재귀적으로(반복적으로) {...} 패턴을 치환
            processed_keyword = replace_placeholders_recursive(original_keyword, name_to_term)
        
        print(f"[DEBUG] Final processed_keyword after braces replacement: '{processed_keyword}'")
        keyword = processed_keyword  # 이후 로직은 processed_keyword를 사용하여 검색

        try:
            print(f"[Internal Audit] 검색 시작 - 키워드: {keyword}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            params = []
            conditions = []

            # == 연산자를 사용한 검색 패턴
            field_patterns = {
                # 따옴표 없이 (\S+): 공백이 없는 문자열 매칭
                r'%Web%\s*==\s*([^\s()]+)': ('w.Uri LIKE ?', 'w.Uri IS NULL'),
                r'%Title%\s*==\s*([^\s()]+)': ('wc.WindowTitle LIKE ?', 'wc.WindowTitle IS NULL'),
                r'%App%\s*==\s*([^\s()]+)': ('a.Name LIKE ?', 'a.Name IS NULL'),
                r'%File%\s*==\s*([^\s()]+)': ('f.Path LIKE ?', 'f.Path IS NULL'),
                r'%OCR%\s*==\s*([^\s()]+)': ('wctc.c2 LIKE ?', 'wctc.c2 IS NULL'),
            }

            # 검색어 파싱
            remaining_text = keyword
            for pattern, (like_condition, null_condition) in field_patterns.items():
                matches = re.finditer(pattern, remaining_text)
                for match in matches:
                    search_term = match.group(1)  # (\S+) 캡처
                    if search_term.lower() == "n/a":
                        conditions.append(null_condition)  # 예: w.Uri IS NULL
                    else:
                        conditions.append(like_condition)  # 예: w.Uri LIKE ?
                        params.append(f"%{search_term}%")
                    remaining_text = remaining_text.replace(match.group(0), "")


            # 일반 검색어 처리 (남은 텍스트에서)
            remaining_text = remaining_text.strip()
            if remaining_text:
                # AND/OR 검색 처리
                def parse_expression(expression, patterns, param_list):
                    # 토큰화
                    tokens = re.split(r'(\s+\|\|\s+|\s+&&\s+|\(|\))', expression)
                    tokens = [token.strip() for token in tokens if token.strip()]
                    
                    # 조건 스택
                    conditions = []
                    operators = []
                    
                    def apply_operator():
                        if len(conditions) < 2:
                            return
                        right = conditions.pop()
                        left = conditions.pop()
                        operator = operators.pop()
                        if operator == '||':
                            conditions.append(f"({left} OR {right})")
                        else:  # AND
                            conditions.append(f"({left} AND {right})")
                    
                    for token in tokens:
                        if token == '(':
                            operators.append(token)
                        elif token == ')':
                            while operators and operators[-1] != '(':
                                apply_operator()
                            if operators:
                                operators.pop()  # '(' 제거
                        elif token in ['&&', '||']:
                            while operators and operators[-1] not in ['(']:
                                apply_operator()
                            operators.append('||' if token == '||' else 'AND')
                        else:
                            # 필드별 검색 패턴 확인
                            field_match = False
                            for pattern, (like_condition, null_condition) in patterns.items():
                                if re.match(pattern, token):
                                    match = re.match(pattern, token)
                                    search_term = match.group(1)
                                    if search_term.lower() == "n/a":
                                        conditions.append(null_condition)
                                    else:
                                        conditions.append(like_condition)
                                        param_list.append(f"%{search_term}%")
                                    field_match = True
                                    break
                            
                            # 일반 검색어 처리
                            if not field_match:
                                conditions.append(f"""
                    (wc.WindowTitle LIKE ? OR
                     a.Name LIKE ? OR
                     wctc.c2 LIKE ?)
                """)
                                param_list.extend([f"%{token}%" for _ in range(3)])
                    
                    while operators:
                        apply_operator()
                    
                    return conditions[0] if conditions else ""

            # 일반 검색어 처리 (남은 텍스트에서)
            remaining_text = keyword.strip()
            if remaining_text:
                condition = parse_expression(remaining_text, field_patterns, params)
                if condition:
                    conditions.append(condition)

            # 최종 쿼리 생성
            where_clause = " AND ".join(f"({cond})" for cond in conditions) if conditions else "1=1"
            
            query = f"""
            SELECT DISTINCT wc.TimeStamp, wc.ImageToken
            FROM WindowCapture wc
            LEFT JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
            LEFT JOIN WindowCaptureAppRelation wcar ON wc.Id = wcar.WindowCaptureId
            LEFT JOIN App a ON wcar.AppId = a.Id
            LEFT JOIN WindowCaptureWebRelation wcwr ON wc.Id = wcwr.WindowCaptureId
            LEFT JOIN Web w ON wcwr.WebId = w.Id
            LEFT JOIN WindowCaptureFileRelation wcfr ON wc.Id = wcfr.WindowCaptureId
            LEFT JOIN File f ON wcfr.FileId = f.Id
            WHERE {where_clause}
            ORDER BY wc.TimeStamp ASC;
            """
            
            print(f"[Internal Audit] 실행 SQL: {query}")
            print(f"[Internal Audit] 파라미터: {params}")
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            print(f"[Internal Audit] 검색 결과 수: {len(results)}개")

            if results:
                # 중복 제거 (TimeStamp 기준)
                unique_results = []
                seen_tokens = set()
                for timestamp, token in results:
                    if token is not None and token not in seen_tokens:
                        unique_results.append((timestamp, token))
                        seen_tokens.add(token)
                
                if unique_results:
                    print(f"[Internal Audit] 중복 제거된 결과 수: {len(unique_results)}개")
                    self.display_images(unique_results)
                    self.lower_text_box.setText(f"총 {len(unique_results)}개의 결과가 검색되었습니다. (중복 제거됨)")
                else:
                    self.clear_images()
                    self.lower_text_box.setText("검색 결과가 없습니다.")
                    self.current_results = []
                    self.current_page = 1
                    
            else:
                self.clear_images()
                self.lower_text_box.setText("검색 결과가 없습니다.")
                self.current_results = []
                self.current_page = 1
                
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
        
        # 전체 페이지 수 계산
        total_pages = (len(results) + self.images_per_page - 1) // self.images_per_page
        
        # 현재 페이지의 시작/끝 인덱스 계산
        start_idx = (self.current_page - 1) * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, len(results))
        
        # 현재 페이지의 결과만 표시
        current_page_results = results[start_idx:end_idx]

        # 페이지네이션 컨테이너 생성
        pagination_container = QWidget()
        pagination_layout = QHBoxLayout(pagination_container)
        pagination_layout.setAlignment(Qt.AlignCenter)
        
        # 이전 페이지 버튼
        prev_button = QPushButton("<")
        prev_button.setFixedSize(30, 30)
        prev_button.clicked.connect(lambda: self.change_page('prev'))
        prev_button.setEnabled(self.current_page > 1)
        pagination_layout.addWidget(prev_button)
        
        # 페이지 번호 버튼들
        current_section = (self.current_page - 1) // 10
        start_page = current_section * 10 + 1
        end_page = min(start_page + 9, total_pages)
        
        for page in range(start_page, end_page + 1):
            btn = QPushButton(str(page))
            btn.setFixedSize(30, 30)
            if page == self.current_page:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0078D7;
                        color: white;
                        border: none;
                        border-radius: 15px;
                        font-weight: bold;
                        font-size: 12pt;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f0f0f0;
                        color: #333333;
                        border: none;
                        border-radius: 15px;
                        font-weight: bold;
                        font-size: 12pt;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                """)
            btn.clicked.connect(lambda checked, p=page: self.change_page(p))
            pagination_layout.addWidget(btn)
        
        # 다음 페이지 버튼
        next_button = QPushButton(">")
        next_button.setFixedSize(30, 30)
        next_button.clicked.connect(lambda: self.change_page('next'))
        next_button.setEnabled(self.current_page < total_pages)
        pagination_layout.addWidget(next_button)
        
        # 이미지 레이아웃에 페이지네이션 추가
        if len(current_page_results) > 0:
            self.image_layout.addWidget(pagination_container, self.image_layout.rowCount(), 0, 1, -1)
        else:
            self.image_layout.addWidget(pagination_container, 0, 0, 1, -1)

        # 컨테이너 너비 계산 방식 수정
        container_width = self.image_scroll_area.width() - 12  # 스크롤바 영역을 명시적으로 제외
        
        # 디버깅을 위한 로그 추가
        print(f"[Internal Audit] 컨테이너 너비: {container_width}")
        print(f"[Internal Audit] 스크롤 영역 너비: {self.image_scroll_area.width()}")
        print(f"[Internal Audit] 뷰포트 너비: {self.image_scroll_area.viewport().width()}")
        print(f"[Internal Audit] 이미지 컨테이너 너비: {self.image_container.width()}")

        selection_border_width = 2  # 선택 상자의 테두리 두께
        grid_spacing = selection_border_width * 2  # 테두리 두께의 2배로 간격 설정
        self.image_layout.setSpacing(grid_spacing)  # 전체 간격 설정
        self.image_layout.setHorizontalSpacing(grid_spacing)  # 수평 간격 설정
        self.image_layout.setVerticalSpacing(0)  # 수직 간격은 0으로 유지
        self.image_layout.setContentsMargins(0, 0, 0, 0)  # 레이아웃의 여백 제거
        images_per_row = 4

        # 스크롤바 너비를 10px로 고정
        scrollbar_width = 10
        print(f"[Internal Audit] 스크롤바 너비: {scrollbar_width}")
        
        # 컨테이너 너비 조정
        adjusted_container_width = container_width - scrollbar_width - grid_spacing
        print(f"[Internal Audit] 조정된 컨테이너 너비: {adjusted_container_width}")
        
        # 이미지가 4개 이상일 때의 크기를 기준으로 고정
        fixed_image_width = (adjusted_container_width - (grid_spacing * (images_per_row - 1))) // images_per_row
        print(f"[Internal Audit] 계산된 이미지 너비: {fixed_image_width}")
        fixed_image_height = int(fixed_image_width * 0.7)
        timestamp_height = 17

        # 중앙 정렬을 위한 컨테이너 생성
        center_container = QWidget()
        center_layout = QGridLayout(center_container)
        center_layout.setSpacing(2)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # 이미지 배치
        for index, (timestamp, image_token) in enumerate(current_page_results):
            # 이미지 토큰이 None인 경우 건너뛰기
            if image_token is None:
                print(f"[Internal Audit] 이미지 토큰이 None인 항목 건너뛰기 - TimeStamp: {timestamp}")
                continue

            set_box = QFrame()
            set_layout = QVBoxLayout(set_box)
            set_layout.setSpacing(0)
            set_layout.setContentsMargins(0, 0, 0, 0)
            set_layout.setAlignment(Qt.AlignCenter)  # 레이아웃 전체 중앙 정렬
            
            # 처음부터 2px의 투명한 테두리를 가지도록 설정
            set_box.setStyleSheet("""
                border: 2px solid transparent;  /* 투명한 테두리로 공간 유지 */
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

    def update_pagination(self, total_pages):
        # 기존 페이지 번호 버튼 제거
        while self.page_numbers_layout.count():
            item = self.page_numbers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 현재 페이지가 속한 구간 계산
        current_section = (self.current_page - 1) // 10
        start_page = current_section * 10 + 1
        end_page = min(start_page + 9, total_pages)
        
        # 공통 버튼 스타일
        button_style = """
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: none;
                border-radius: 15px;
                font-weight: bold;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #a0a0a0;
            }
        """
        
        # 이전 버튼
        self.prev_button.setStyleSheet(button_style)
        self.prev_button.setEnabled(self.current_page > 1)
        
        # 페이지 번호 버튼 생성
        for page in range(start_page, end_page + 1):
            btn = QPushButton(str(page))
            btn.setFixedSize(30, 30)
            if page == self.current_page:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0078D7;
                        color: white;
                        border: none;
                        border-radius: 15px;
                        font-weight: bold;
                        font-size: 12pt;
                    }
                """)
            else:
                btn.setStyleSheet(button_style)
            btn.clicked.connect(lambda checked, p=page: self.change_page(p))
            self.page_numbers_layout.addWidget(btn)
        
        # 다음 버튼 (마지막에 추가)
        self.next_button.setStyleSheet(button_style)
        self.next_button.setEnabled(self.current_page < total_pages)

    def change_page(self, page_action):
        total_pages = (len(self.current_results) + self.images_per_page - 1) // self.images_per_page
        
        if isinstance(page_action, int):
            self.current_page = page_action
        elif page_action == 'prev':
            # 한 페이지씩 이동
            self.current_page = max(1, self.current_page - 1)
        elif page_action == 'next':
            # 한 페이지씩 이동
            self.current_page = min(total_pages, self.current_page + 1)
        
        self.display_images(self.current_results)

    def show_advanced_search_dialog(self):
        """고급 검색 대화상자 표시"""
        dialog = AdvancedSearchDialog(self)
        if dialog.exec() == QDialog.Accepted:
            search_query = dialog.get_search_query()
            if search_query:
                self.keyword_search.setText(search_query)
                self.search_images()

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
            print("[Internal Audit] 초기 데이터 로드 시도")
            self.load_all_images()
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
        try:
            print(f"[Internal Audit] OCR 내용 조회 - TimeStamp: {timestamp}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 현재 검색어 가져오기
            original_search = self.keyword_search.text().strip()

            # search_terms.json 로드해서 name_to_term 딕셔너리 구성
            # {} 패턴 여부 확인
            has_braces = bool(re.search(r'\{([^}]+)\}', original_search))
            name_to_term = {}
            if has_braces and os.path.exists('search_terms.json'):
                try:
                    with open('search_terms.json', 'r', encoding='utf-8') as f:
                        saved_terms = json.load(f)
                        for t in saved_terms:
                            if 'name' in t and 'term' in t:
                                name_to_term[t['name']] = t['term']
                except Exception as e:
                    print(f"[Internal Audit] search_terms.json 로드 오류: {e}")

            # {}가 있을 때만 실제 검색어로 변환
            processed_search = original_search
            if has_braces:
                processed_search = replace_placeholders_recursive(original_search, name_to_term)

            print(f"[DEBUG][show_ocr_content] 최종 processed_search: '{processed_search}'")
            # 실제 하이라이트할 검색어들 추출
            def extract_search_terms(search_str):
                # 연산자와 괄호를 개행으로 치환
                print(f"[DEBUG][extract_search_terms] raw search_str = '{search_str}'")
                temp = re.sub(r'(\|\||&&|==|\(|\))', '\n', search_str)
                # 개행 기준으로 split
                lines = [line.strip() for line in temp.split('\n') if line.strip()]
                print(f"[DEBUG][extract_search_terms] parsedlines = {lines}")
                return lines

            highlight_terms = extract_search_terms(processed_search)
            print(f"[DEBUG][show_ocr_content] highlight_terms = {highlight_terms}")
            # 검색어 표시용 함수
            def highlight_search_display(search_str, terms):
                print(f"[DEBUG][highlight_search_display] Called with search_str='{search_str}'")
                print(f"[DEBUG][highlight_search_display] highlight_terms={terms}")
                # 여기서 {} 안의 단어는 나중에 처리하므로 지금은 단어 강조만 처리
                display = search_str
                # term 강조 (파란색 굵게) - 하지만 {} 내는 나중에 처리
                # 우선 여기서는 기존처럼 일반 단어만 파란색 굵게 처리
                # 단, {검색어명} 형식은 나중에 별도 처리할테니 일단 이 함수에서는
                # highlight_terms(실제 jpg, png 등)만 처리하면 됨.
                
                # placeholder( {검색어명} )는 여기서 파란색 처리하지 않음.
                # highlight_terms에는 실제 파일 확장자나 단일 검색어들(jpg, png...)이 들어있음.
                
                # 우선 {..} 구문을 임시로 빼내어 단어 강조 -> 복원 로직 수행 X
                # 여기서는 highlight_terms는 단어 강조를 위해 색을 바꾸는데,
                # {..} 안에 있는 단어는 highlight하지 않을것이므로 그냥 단순히
                # search_str 내에서 highlight_terms에 있는 단어들을 파란색으로 표시한다.
                # 하지만 여기서 원 요청사항은 {} 안의 명칭을 파랗게 하고 싶지만
                # braces 자체는 파란색 하지 말라고 했다. 그러므로 아래에서는 일단
                # highlight_terms는 중괄호와 상관없이 일반 단어 강조.
                # 이후 별도의 단계에서 {검색어명}을 처리한다.

                # { ... } 구문은 나중에 처리하기 위해 임시 치환
                placeholders = re.findall(r'\{[^}]+\}', display)
                placeholder_map = {}
                for i, p in enumerate(placeholders):
                    placeholder_map[f"__PLACEHOLDER_{i}__"] = p
                temp_display = display
                for k, v in placeholder_map.items():
                    temp_display = temp_display.replace(v, k)

                # highlight_terms에 대해 파란색 굵게 처리
                # 하지만 highlight_terms는 jpg, png 같은 실제 검색어 단어들
                # 여기서는 검색어명 강조 안함
                for term in terms:
                    temp_display = re.sub(
                        re.escape(term),
                        f'<b style="font-size:14pt; color:#0078D7;">\\g<0></b>',
                        temp_display,
                        flags=re.IGNORECASE
                    )

                # placeholder 복원
                for k, v in placeholder_map.items():
                    temp_display = temp_display.replace(k, v)

                return temp_display

            # search_info 만들기
            search_info = ""
            if highlight_terms:
                display_search = highlight_search_display(original_search, highlight_terms)
                # 이제 {검색어명} 내 검색어명을 파란색 굵게 크게 표시 ({}는 그대로)
                # 예: {이미지 파일} -> {<b style="font-size:14pt; color:#0078D7;">이미지 파일</b>}
                display_search = re.sub(
                    r'\{([^}]+)\}',
                    r'{<b style="font-size:14pt; color:#0078D7; font-weight:bold;">\1</b>}',
                    display_search
                )

                search_info = f"""
                        <p><b style='font-size: 12pt;'>검색어</b> {display_search}가 포함된 이미지입니다.</p>
                        <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>
                        """

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

            def highlight_text(text, terms):
                print(f"[DEBUG][highlight_text] text[:100] = '{text[:100] if text else ''}...'") 
                print(f"[DEBUG][highlight_text] highlight_terms = {terms}")
                if not text:
                    return 'N/A'
                highlighted = text
                for t in terms:
                    pattern = re.escape(t)
                    highlighted = re.sub(
                        pattern,
                        r'<span style="background-color: yellow; font-weight: bold; font-size:14pt;">\g<0></span>',
                        highlighted,
                        flags=re.IGNORECASE
                    )
                return highlighted

            if result:
                timestamp, window_title, app_names, web_uris, file_paths, ocr_text = result
                
                dt = datetime.fromtimestamp(timestamp / 1000)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                
                output_text = f"""<div style='font-size: 12pt;'>
                                <p><b style='font-size: 12pt;'>Time:</b> {formatted_time}</p>
                                
                                {search_info}

                                <p><b style='font-size: 12pt;'>Window Title:</b> {highlight_text(window_title, highlight_terms) if window_title else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>애플리케이션 명:</b> {highlight_text(app_names, highlight_terms) if app_names else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>Web Uri:</b> {highlight_text(web_uris, highlight_terms) if web_uris else 'N/A'}</p>
                                <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>

                                <p><b style='font-size: 12pt;'>File Path:</b> {highlight_text(file_paths, highlight_terms) if file_paths else 'N/A'}</p>
                                """

                if ocr_text:
                    cleaned_text = self.clean_ocr_text(ocr_text)
                    highlighted_text = highlight_text(cleaned_text, highlight_terms)
                    
                    output_text += f"""
                                    <hr style='border: 1px solid #e0e0e0; margin: 10px 0;'>
                                    <p><b style='font-size: 12pt;'>OCR 출력물:</b></p>
                                    <p>{highlighted_text}</p>
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
        # 페이지를 1로 초기화
        self.current_page = 1
        
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
        # 이미 선택된 이미지를 다시 클릭했는지 확인
        if self.current_selected_box == clicked_box:
            # 더블클릭으로 간주하고 ImageTable로 이동
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
        
        # 단일 클릭 처리
        try:
            # 이전 선택된 박스가 유효한지 확인
            if self.current_selected_box and self.current_selected_box.parent():
                # 이전에 선택한 박스를 기본 스타일로 복원
                self.current_selected_box.setStyleSheet("""
                    border: 2px solid transparent;  /* 투명한 테두리로 공간 유지 */
                    padding: 0px;
                    margin: 0px;
                    background-color: #ffffff;
                """)
        except RuntimeError:
            # 이전 선택된 박스가 이미 삭제된 경우
            pass

        # 현재 클릭한 박스에 파란색 테두리 적용
        clicked_box.setStyleSheet("""
            border: 2px solid #007AFF;
            padding: 0px;
            margin: 0px;
            background-color: #ffffff;
        """)

        # 클릭한 박스를 맨 앞으로 이동
        clicked_box.raise_()

        # 현재 클릭한 이미지 정보 저장
        self.current_selected_box = clicked_box
        self.show_ocr_content(timestamp)

class AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("고급 검색")
        self.setFixedSize(750, 400)
        self.search_terms = self.load_search_terms()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 메뉴바 추가
        menu_bar = QMenuBar(self)
        file_menu = menu_bar.addMenu("Menu")
        
        save_action = QAction("검색어 저장", self)
        save_action.triggered.connect(self.save_search_terms)
        file_menu.addAction(save_action)
        
        main_layout.setMenuBar(menu_bar)
        
        # 스크롤 영역 생성
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 스크롤 영역에 들어갈 컨테이너 위젯
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        
        # 검색어 입력 영역
        self.search_entries = []
        initial_count = max(5, len(self.search_terms))  # 저장된 검색어 수와 5 중 큰 값 사용
        
        for i in range(initial_count):
            entry_layout = QHBoxLayout()
            
            # enabled 체크박스
            enabled_search = QCheckBox()
            entry_layout.addWidget(enabled_search)
            
            # 검색어명 입력
            name_edit = QLineEdit()
            name_edit.setPlaceholderText(f"검색어명{i+1}")
            name_edit.setFixedWidth(200)
            entry_layout.addWidget(name_edit)
            
            # 검색어 입력
            term_edit = QLineEdit()
            term_edit.setPlaceholderText("검색어를 입력하세요")
            term_edit.setFixedWidth(350)
            entry_layout.addWidget(term_edit)
            
            # AND/OR 체크박스
            and_checkbox = QCheckBox("AND")
            or_checkbox = QCheckBox("OR")
            entry_layout.addWidget(and_checkbox)
            entry_layout.addWidget(or_checkbox)
            
            # 체크박스 상태 연동 (변수명 개선 및 로직 단순화)
            def make_exclusive(current_checkbox, other_checkbox, checked):
                """한 체크박스가 선택되면 다른 체크박스는 선택 해제"""
                if checked:
                    other_checkbox.setChecked(False)
                
            and_checkbox.stateChanged.connect(
                lambda state, this_cb=and_checkbox, other_cb=or_checkbox: 
                make_exclusive(this_cb, other_cb, state)
            )
            or_checkbox.stateChanged.connect(
                lambda state, this_cb=or_checkbox, other_cb=and_checkbox: 
                make_exclusive(this_cb, other_cb, state)
            )
            
            layout.addLayout(entry_layout)
            self.search_entries.append({
                'enabled_search': enabled_search,
                'name': name_edit,
                'term': term_edit,
                'and_cb': and_checkbox,
                'or_cb': or_checkbox
            })

        # 추가 버튼
        add_button = QPushButton("(+) 사용자 지정 검색어 추가")
        add_button.clicked.connect(self.add_custom_search)
        layout.addWidget(add_button)

        # 스크롤 영역에 컨테이너 설정
        scroll_area.setWidget(container)
        
        # 메인 레이아웃에 스크롤 영역 추가
        main_layout.addWidget(scroll_area)

        # 확인/취소 버튼
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # 저장된 검색어 불러오기
        self.apply_saved_search_terms()

    def add_custom_search(self):
        """사용자 지정 검색어 입력란 추가"""
        # 스크롤 영역의 컨테이너 위젯 가져오기
        container = self.findChild(QScrollArea).widget()
        layout = container.layout()
        
        # 새로운 검색어 입력란 생성
        entry_layout = QHBoxLayout()
        
        # enabled 체크박스
        enabled_search = QCheckBox()
        entry_layout.addWidget(enabled_search)
        
        # 검색어명 입력
        name_edit = QLineEdit()
        name_edit.setPlaceholderText(f"검색어명{len(self.search_entries)+1}")
        name_edit.setFixedWidth(200)
        entry_layout.addWidget(name_edit)
        
        # 검색어 입력
        term_edit = QLineEdit()
        term_edit.setPlaceholderText("검색어를 입력하세요")
        term_edit.setFixedWidth(350)  # 기존 입력란과 동일한 너비로 고정
        entry_layout.addWidget(term_edit)
        
        # AND/OR 체크박스
        and_checkbox = QCheckBox("AND")
        or_checkbox = QCheckBox("OR")
        entry_layout.addWidget(and_checkbox)
        entry_layout.addWidget(or_checkbox)
        
        # 체크박스 상태 연동
        def make_exclusive(current_checkbox, other_checkbox, checked):
            """한 체크박스가 선택되면 다른 체크박스는 선택 해제"""
            if checked:
                other_checkbox.setChecked(False)
                
        and_checkbox.stateChanged.connect(
            lambda state, this_cb=and_checkbox, other_cb=or_checkbox: 
            make_exclusive(this_cb, other_cb, state)
        )
        or_checkbox.stateChanged.connect(
            lambda state, this_cb=or_checkbox, other_cb=and_checkbox: 
            make_exclusive(this_cb, other_cb, state)
        )
        
        # 새로운 입력란을 버튼 위에 추가
        layout.insertLayout(layout.count() - 1, entry_layout)
        
        self.search_entries.append({
            'enabled_search': enabled_search,
            'name': name_edit,
            'term': term_edit,
            'and_cb': and_checkbox,
            'or_cb': or_checkbox
        })

    def save_search_terms(self):
        """검색어 설정을 파일로 저장"""
        search_data = []
        for entry in self.search_entries:
            if entry['name'].text() and entry['term'].text():
                search_data.append({
                    'enabled': entry['enabled_search'].isChecked(),  # checkbox -> enabled_search
                    'name': entry['name'].text(),
                    'term': entry['term'].text(),
                    'and_checked': entry['and_cb'].isChecked(),
                    'or_checked': entry['or_cb'].isChecked()
                })
        
        try:
            with open('search_terms.json', 'w', encoding='utf-8') as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "저장 완료", "검색어 설정이 저장되었습니다.")
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", f"검색어 설정 저장 중 오류가 발생했습니다.\n{str(e)}")

    def load_search_terms(self):
        """저장된 검색어 설정 불러오기"""
        try:
            with open('search_terms.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def apply_saved_search_terms(self):
        """저장된 검색어 설정을 UI에 적용"""
        for i, term_data in enumerate(self.search_terms):
            if i < len(self.search_entries):
                entry = self.search_entries[i]
                entry['enabled_search'].setChecked(term_data.get('enabled', False))  # checkbox -> enabled_search
                entry['name'].setText(term_data.get('name', ''))
                entry['term'].setText(term_data.get('term', ''))
                entry['and_cb'].setChecked(term_data.get('and_checked', False))
                entry['or_cb'].setChecked(term_data.get('or_checked', False))

    def get_search_query(self):
        """선택된 검색어들을 {}로 감싸진 검색어명과 AND/OR로 연결하여 반환"""
        # 활성화된 검색어명들을 추출
        enabled_entries = [
            (entry['name'].text().strip(), entry['and_cb'].isChecked(), entry['or_cb'].isChecked())
            for entry in self.search_entries
            if entry['enabled_search'].isChecked() and entry['name'].text().strip()
        ]

        # enabled_entries는 [(name, and_checked, or_checked), ...] 형태
        # 예: [("원소", False, True), ("과학", False, False)] 등
        # 첫 번째 검색어 앞에는 연산자 없이, 두 번째 검색어부터는 선택한 연산자(|| 또는 &&)를 붙여줍니다.
        
        final_query = ""
        for i, (name, and_checked, or_checked) in enumerate(enabled_entries):
            # 검색어명에 {} 감싸기
            placeholder = f"{{{name}}}"

            if i == 0:
                # 첫 번째 검색어에는 연산자 없이 추가
                final_query = placeholder
            else:
                # 두 번째 검색어부터는 이전 검색어 뒤에 연산자와 함께 추가
                # AND가 체크되었다면 '&&', OR이 체크되었다면 '||'
                # 둘 다 체크가 안되거나 둘 다 체크된 경우 등은 발생하지 않는다고 가정
                # (만약 그런 경우가 있다면 기본 연산자를 설정하거나 추가 검증이 필요)
                operator = "||"
                if and_checked:
                    operator = "&&"
                elif or_checked:
                    operator = "||"
                
                final_query += f" {operator} {placeholder}"

        return final_query