# image_table_one.py
# ver 1.7

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateTimeEdit, QSizePolicy, QApplication, QLineEdit
from PySide6.QtCore import Qt, QDateTime, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QKeyEvent, QDoubleValidator
import sqlite3
import os
from datetime import datetime

# 이미지 로딩을 위한 신호를 정의할 클래스
class ImageLoader(QObject):
    image_loaded = Signal(QPixmap)

    def load_image(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_loaded.emit(pixmap)
        else:
            self.image_loaded.emit(QPixmap())  # 빈 QPixmap을 보내어 로드 실패를 알림

class ImageTableWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = None
        self.images = []
        self.current_image_index = 0

        # 자동 이동 관련 속성
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.auto_move)
        self.auto_move_direction = None  # 'prev' 또는 'next'

        # 메인 레이아웃 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 통합된 컨트롤 레이아웃 (타임스탬프, 검색, 자동 이동)
        control_layout = QHBoxLayout()

        # --- 타임스탬프 및 검색 위젯 그룹 ---
        search_group = QHBoxLayout()

        # 시작 시간 설정 (기본값으로 현재 시간 대신 빈 값 설정)
        search_group.addWidget(QLabel("시작 시간:"))
        self.start_time = QDateTimeEdit()
        self.start_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time.setMinimumWidth(180)
        search_group.addWidget(self.start_time)

        # 종료 시간 설정 (기본값으로 현재 시간 대신 빈 값 설정)
        search_group.addWidget(QLabel("종료 시간:"))
        self.end_time = QDateTimeEdit()
        self.end_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time.setMinimumWidth(180)
        search_group.addWidget(self.end_time)

        # 키워드 입력 박스 추가
        search_group.addWidget(QLabel("검색어:"))
        self.keyword_search = QLineEdit()
        self.keyword_search.setPlaceholderText("OCR 검색")
        self.keyword_search.setFixedWidth(150)
        search_group.addWidget(self.keyword_search)

        # Enter 키 시 search_images 호출
        self.keyword_search.returnPressed.connect(self.search_images)

        # 검색 버튼
        search_button = QPushButton("검색")
        search_button.clicked.connect(self.search_images)
        search_group.addWidget(search_button)

        # 초기화 버튼
        reset_button = QPushButton("초기화")
        reset_button.clicked.connect(self.reset_search)
        search_group.addWidget(reset_button)

        # --- 자동 이동 컨트롤 그룹 ---
        auto_move_group = QHBoxLayout()

        # 이전 자동 이동 버튼
        self.auto_prev_button = QPushButton("<= Auto Prev")
        self.auto_prev_button.setCheckable(True)
        self.auto_prev_button.clicked.connect(self.toggle_auto_prev)
        auto_move_group.addWidget(self.auto_prev_button)

        # 속도 입력 상자 (초당 이미지 수)
        auto_move_group.addWidget(QLabel("Speed (images/sec):"))
        self.speed_input = QLineEdit("1.0")  # 초기 값 1.0
        self.speed_input.setFixedWidth(100)
        double_validator = QDoubleValidator(0.1, 1000.0, 2)  # 최소 0.1, 최대 1000, 소수점 2자리
        double_validator.setNotation(QDoubleValidator.StandardNotation)
        self.speed_input.setValidator(double_validator)
        auto_move_group.addWidget(self.speed_input)

        # 다음 자동 이동 버튼
        self.auto_next_button = QPushButton("Auto Next =>")
        self.auto_next_button.setCheckable(True)
        self.auto_next_button.clicked.connect(self.toggle_auto_next)
        auto_move_group.addWidget(self.auto_next_button)

        # 그룹 간 간격 조절을 위한 Stretch 추가
        auto_move_group.addStretch()

        # --- 현재 이미지 타임스탬프 레이블 추가 ---
        self.current_timestamp_label = QLabel()
        self.current_timestamp_label.setStyleSheet("""
            QLabel {
                font-size: 14pt;
                font-weight: bold;
                color: #333333;
            }
        """)
        self.current_timestamp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.current_timestamp_label.setMinimumWidth(250)  # 타임스탬프가 잘리지 않도록 충분한 너비 확보

        # Control 레이아웃에 그룹 추가 (기존 코드 수정)
        control_layout.addLayout(search_group)
        control_layout.addSpacing(20)  # 그룹 간 간격
        control_layout.addLayout(auto_move_group)
        control_layout.addWidget(self.current_timestamp_label)  # 타임스탬프 레이블 추가

        # Control 레이아웃에 Stretch 추가
        control_layout.addStretch()

        # Control 레이아웃 추가
        main_layout.addLayout(control_layout)

        # 이미지 디스플레이 및 버튼 레이아웃
        image_layout = QHBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(0)

        # 이전 이미지 버튼을 왼쪽에 배치
        self.prev_button = QPushButton("<")
        self.prev_button.setFixedSize(50, 50)
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 120);
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 20px;
            }
            QPushButton:disabled {
                background-color: rgba(0, 0, 0, 60);
                color: white;
            }
            QPushButton:hover:!disabled {
                background-color: rgba(0, 0, 0, 150);
            }
        """)
        self.prev_button.clicked.connect(self.show_previous_image)
        self.prev_button.setEnabled(False)
        image_layout.addWidget(self.prev_button, alignment=Qt.AlignVCenter)

        # 중앙에 현재 이미지 표시
        self.image_display = QLabel()
        self.image_display.setAlignment(Qt.AlignCenter)
        self.image_display.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_display.setScaledContents(True)  # 자동 스케일링 활성화
        image_layout.addWidget(self.image_display, stretch=1)

        # 다음 이미지 버튼을 오른쪽에 배치
        self.next_button = QPushButton(">")
        self.next_button.setFixedSize(50, 50)
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 120);
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 20px;
            }
            QPushButton:disabled {
                background-color: rgba(0, 0, 0, 60);
                color: white;
            }
            QPushButton:hover:!disabled {
                background-color: rgba(0, 0, 0, 150);
            }
        """)
        self.next_button.clicked.connect(self.show_next_image)
        self.next_button.setEnabled(False)
        image_layout.addWidget(self.next_button, alignment=Qt.AlignVCenter)

        # 이미지 레이아웃을 메인 레이아웃에 추가
        main_layout.addLayout(image_layout, stretch=1)

        # 이미지 로더 초기화
        self.image_loader = ImageLoader()
        self.image_loader.image_loaded.connect(self.display_image)

        # 포커스 정책 설정
        self.setFocusPolicy(Qt.StrongFocus)

    def load_image(self, image_path):
        """ AllTable에서 더블클릭으로 호출 시 이미지를 표시합니다 """
        self.image_loader.load_image(image_path)

    def set_db_path(self, db_path):
        """db_path 설정 및 이미지 로드"""
        self.db_path = db_path
        self.set_default_time_range()  # 시간 범위 초기화 후
        self.load_images()  # 이미지 로드

    def load_images(self):
        """ImageToken이 NULL이 아닌 모든 이미지 로드"""
        if self.db_path is None:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = """
            SELECT wc.Timestamp, wc.ImageToken
            FROM WindowCapture wc
            WHERE wc.ImageToken IS NOT NULL
            ORDER BY wc.Timestamp ASC;
            """
            cursor.execute(query)
            self.images = cursor.fetchall()
            conn.close()

            if self.images:
                self.current_image_index = 0
                self.display_image_from_token(self.images[0][1])  # 첫 번째 이미지 표시
                self.update_button_state()
            else:
                self.image_display.setText("이미지가 없습니다.")
                self.prev_button.setEnabled(False)
                self.next_button.setEnabled(False)
        except sqlite3.Error as e:
            print(f"데이터베이스 오류: {e}")
            self.image_display.setText("데이터베이스 오류가 발생했습니다.")
            self.images = []
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)

    def search_images(self):
        """타임스탬프와 키워드를 기반으로 이미지 검색"""
        if self.db_path is None:
            return

        # 타임스탬프 범위
        start_timestamp = self.start_time.dateTime().toSecsSinceEpoch() * 1000
        end_timestamp = self.end_time.dateTime().toSecsSinceEpoch() * 1000

        # 키워드
        keyword = self.keyword_search.text().strip()

        print(f"검색 범위 (밀리초): {start_timestamp} ~ {end_timestamp}")
        print(f"OCR 검색 키워드: {keyword}")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if keyword:
                # 키워드가 있는 경우
                query = """
                SELECT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                JOIN WindowCaptureTextIndex_content wctc ON wc.Id = wctc.c0
                WHERE wc.TimeStamp BETWEEN ? AND ?
                    AND wc.ImageToken IS NOT NULL
                    AND (wctc.c1 LIKE ? OR wctc.c2 LIKE ?)
                ORDER BY wc.TimeStamp ASC;
                """
                wildcard_keyword = f"%{keyword}%"
                cursor.execute(query, (start_timestamp, end_timestamp, wildcard_keyword, wildcard_keyword))
            else:
                # 키워드가 없는 경우
                query = """
                SELECT wc.TimeStamp, wc.ImageToken
                FROM WindowCapture wc
                WHERE wc.TimeStamp BETWEEN ? AND ? 
                AND wc.ImageToken IS NOT NULL
                ORDER BY wc.TimeStamp ASC;
                """
                cursor.execute(query, (start_timestamp, end_timestamp))

            self.images = cursor.fetchall()
            conn.close()

            if self.images:
                print(f"검색된 이미지 수: {len(self.images)}")
                self.current_image_index = 0
                self.display_image_from_token(self.images[0][1])
                self.update_button_state()
            else:
                self.image_display.clear()
                self.image_display.setText("해당 범위 내 이미지가 없습니다. 검색 범위를 확인해주세요.")
                self.prev_button.setEnabled(False)
                self.next_button.setEnabled(False)
        except sqlite3.Error as e:
            print(f"데이터베이스 오류: {e}")
            self.image_display.setText("데이터베이스 오류가 발생했습니다.")
            self.images = []
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
        except Exception as e:
            print(f"알 수 없는 오류 발생: {e}")
            self.image_display.setText("알 수 없는 오류가 발생했습니다.")
            self.images = []
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)

    def reset_search(self):
        """검색 필드를 초기화하고 기본 타임스탬프 범위로 되돌림"""
        self.set_default_time_range()
        self.keyword_search.clear()
        self.load_images()

    def set_default_time_range(self):
        """ImageToken이 NULL이 아닌 TimeStamp 중 가장 처음과 끝 값을 기본값으로 설정"""
        if self.db_path is None:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = """
            SELECT MIN(wc.Timestamp), MAX(wc.Timestamp)
            FROM WindowCapture wc
            WHERE wc.ImageToken IS NOT NULL;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()

            if result and result[0] and result[1]:
                min_timestamp, max_timestamp = result
                min_time = QDateTime.fromSecsSinceEpoch(min_timestamp // 1000)
                max_time = QDateTime.fromSecsSinceEpoch(max_timestamp // 1000)
                self.start_time.setDateTime(min_time)
                self.end_time.setDateTime(max_time)
                self.update_button_state()
        except sqlite3.Error as e:
            print(f"데이터베이스 오류: {e}")
            self.image_display.setText("데이터베이스 오류가 발생했습니다.")

    def display_image_from_token(self, image_token):
        """이미지 토큰을 통해 이미지를 로드하고 표시"""
        if self.db_path:
            image_dir = os.path.join(os.path.dirname(self.db_path), "ImageStore")
            base_image_path = os.path.join(image_dir, image_token)
            base_image_path = os.path.normpath(base_image_path)

            # 이미지 파일 존재 여부 확인 (확장자 시도)
            possible_extensions = ['', '.jpg', '.jpeg', '.png']
            image_path = None
            for ext in possible_extensions:
                temp_path = base_image_path + ext
                if os.path.exists(temp_path):
                    image_path = temp_path
                    break

            if image_path is None:
                self.image_display.setText(f"이미지 파일을 찾을 수 없습니다: {base_image_path}")
                print(f"이미지 파일 존재하지 않음: {base_image_path}")
                self.image_display.clear()
                self.update_button_state()
                return

            # 비동기적으로 이미지 로드
            self.image_loader.load_image(image_path)
        else:
            self.image_display.setText("데이터베이스 경로가 설정되지 않았습니다.")

    def display_image(self, pixmap):
        """로드된 이미지를 QLabel에 표시"""
        if not pixmap.isNull():
            self.image_display.setPixmap(pixmap)
            if self.current_image_index < len(self.images):
                timestamp = self.get_timestamp(self.images[self.current_image_index][0])
                self.image_display.setToolTip(f"TimeStamp: {timestamp}")
                self.current_timestamp_label.setText(f"이미지 시각: {timestamp}")
            else:
                self.image_display.setToolTip("TimeStamp: N/A")
                self.current_timestamp_label.setText("이미지 시각: N/A")
        else:
            self.image_display.setText("이미지를 로드할 수 없습니다.")
            self.current_timestamp_label.setText("이미지 시각: N/A")
            print("이미지 로드 실패")
        self.update_button_state()

    def get_timestamp(self, timestamp_ms):
        """밀리초 단위의 타임스탬프를 인간이 읽을 수 있는 형식으로 변환"""
        try:
            timestamp_sec = timestamp_ms / 1000
            dt = datetime.fromtimestamp(timestamp_sec)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"임스탬프 변환 오류: {e}")
            return "N/A"

    def show_previous_image(self):
        """이전 이미지로 이동"""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image_from_token(self.images[self.current_image_index][1])

    def show_next_image(self):
        """다음 이미지로 이동"""
        if self.current_image_index < len(self.images) - 1:
            self.current_image_index += 1
            self.display_image_from_token(self.images[self.current_image_index][1])

    # 키보드 이벤트 처리 (좌우 화살표 키로 이미지 전환 및 상하 화살표 키로 자동 이동 제어)
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Left:
            self.show_previous_image()
            event.accept()  # 이벤트 전파 방지
        elif event.key() == Qt.Key_Right:
            self.show_next_image()
            event.accept()  # 이벤트 전파 방지
        elif event.key() == Qt.Key_Up:
            # 자동 다음 이동 토글 (버튼 클릭 시 동일한 로직 적용)
            self.auto_next_button.click()
            event.accept()
        elif event.key() == Qt.Key_Down:
            # 자동 이전 이동 토글 (버튼 클릭 시 동일한 로직 적용)
            self.auto_prev_button.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def update_button_state(self):
        # 이전 버튼 상태 업데이트
        if self.current_image_index > 0:
            self.prev_button.setEnabled(True)
        else:
            self.prev_button.setEnabled(False)

        # 다음 버튼 상태 업데이트
        if self.current_image_index < len(self.images) - 1:
            self.next_button.setEnabled(True)
        else:
            self.next_button.setEnabled(False)

    # 자동 이동 관련 메서드들

    def toggle_auto_prev(self, checked):
        """이전 이미지 자동 이동 토글"""
        if checked:
            # 이전 자동 이동이 활성화될 때 자동 다음 이동을 중지
            if self.auto_next_button.isChecked():
                # 신호 차단하여 재귀 호출 방지
                self.auto_next_button.blockSignals(True)
                self.auto_next_button.setChecked(False)
                self.auto_next_button.setText("Auto Next =>")
                self.auto_next_button.blockSignals(False)
                # 타이머 중지
                self.auto_timer.stop()
                self.auto_move_direction = None

            # 자동 이전 이동 시작
            speed = self.get_speed()
            if speed > 0:
                self.auto_move_direction = 'prev'
                interval = int(1000 / speed)  # 밀리초 단위
                self.auto_timer.start(interval)
                self.auto_prev_button.setText("<= Stop Auto Prev")
        else:
            # 자동 이전 이동 중지
            self.auto_timer.stop()
            self.auto_move_direction = None
            self.auto_prev_button.setText("<= Auto Prev")

    def toggle_auto_next(self, checked):
        """다음 이미지 자동 이동 토글"""
        if checked:
            # 자동 다음 이동이 활성화될 때 자동 이전 이동을 중지
            if self.auto_prev_button.isChecked():
                # 신호 차단하여 재귀 호출 방지
                self.auto_prev_button.blockSignals(True)
                self.auto_prev_button.setChecked(False)
                self.auto_prev_button.setText("<= Auto Prev")
                self.auto_prev_button.blockSignals(False)
                # 타이머 중지
                self.auto_timer.stop()
                self.auto_move_direction = None

            # 자동 다음 이동 시작
            speed = self.get_speed()
            if speed > 0:
                self.auto_move_direction = 'next'
                interval = int(1000 / speed)  # 밀리초 단위
                self.auto_timer.start(interval)
                self.auto_next_button.setText("Stop Auto Next =>")
        else:
            # 자동 다음 이동 중지
            self.auto_timer.stop()
            self.auto_move_direction = None
            self.auto_next_button.setText("Auto Next =>")

    def get_speed(self):
        """속도 입력 상자에서 속도 가져오기"""
        try:
            speed = float(self.speed_input.text())
            if speed <= 0:
                raise ValueError
            return speed
        except ValueError:
            self.speed_input.setText("1.0")  # 기본값으로 재설정
            return 1.0

    def auto_move(self):
        """자동 이동 시그널 처리"""
        if self.auto_move_direction == 'prev':
            if self.current_image_index > 0:
                self.show_previous_image()
            else:
                # 더 이상 이전 이미지가 없으면 자동 이동 중지
                self.auto_timer.stop()
                self.auto_move_direction = None
                self.auto_prev_button.setChecked(False)
                self.auto_prev_button.setText("<= Auto Prev")
        elif self.auto_move_direction == 'next':
            if self.current_image_index < len(self.images) - 1:
                self.show_next_image()
            else:
                # 더 이상 다음 이미지가 없으면 자동 이동 중지
                self.auto_timer.stop()
                self.auto_move_direction = None
                self.auto_next_button.setChecked(False)
                self.auto_next_button.setText("Auto Next =>")

    def display_image_from_token_with_index(self, target_token):
        """특정 이미지 토큰을 찾아서 해당 인덱스로 이동 후 표시"""
        if not self.images:
            return False
            
        # 이미지 토큰으로 인덱스 찾기
        for idx, (_, token) in enumerate(self.images):
            if token == target_token:
                self.current_image_index = idx  # 현재 인덱스 업데이트
                self.display_image_from_token(token)
                return True
        return False
