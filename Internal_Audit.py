from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QSplitter
from PySide6.QtCore import Qt

class InternalAuditWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        
        # 스플리터 생성
        splitter = QSplitter(Qt.Vertical)
        
        # 두 개의 텍스트 상자 생성
        self.upper_text_box = QTextEdit()
        self.lower_text_box = QTextEdit()
        
        # 텍스트 상자를 읽기 전용으로 설정
        self.upper_text_box.setReadOnly(True)
        self.lower_text_box.setReadOnly(True)
        
        # 스플리터에 위젯 추가
        splitter.addWidget(self.upper_text_box)
        splitter.addWidget(self.lower_text_box)
        
        # 스플리터 비율 설정 (1:1)
        splitter.setSizes([500, 500])
        
        # 메인 레이아웃에 스플리터 추가
        main_layout.addWidget(splitter)
        
        # 초기 텍스트 설정
        self.upper_text_box.setText("상단 분석 결과가 여기에 표시됩니다.")
        self.lower_text_box.setText("하단 분석 결과가 여기에 표시됩니다.")

    def set_db_path(self, db_path):
        """데이터베이스 경로 설정"""
        self.db_path = db_path
        # 필요한 경우 여기에 데이터 로드 로직 추가
