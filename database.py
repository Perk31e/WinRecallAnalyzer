#database.py

import sqlite3
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import Qt, QAbstractTableModel
import os


class SQLiteTableModel(QAbstractTableModel):
    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self._data = data
        self._headers = headers

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._headers[section]
            if orientation == Qt.Vertical:
                return section + 1
        return None

    def sort(self, column, order=Qt.AscendingOrder):
        """정렬 기능 추가, None 값을 처리하여 오류 방지"""
        self.layoutAboutToBeChanged.emit()

        # None 값은 항상 마지막으로 정렬되도록 key를 수정
        self._data.sort(
            key=lambda x: (x[column] is None, x[column]),  # None 값은 항상 마지막에 위치
            reverse=(order == Qt.DescendingOrder)
        )

        self.layoutChanged.emit()


# UNIX 타임스탬프를 한국 표준시(KST)로 변환하는 함수
def convert_unix_timestamp(timestamp):
    return (datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc) + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')

def load_data_from_db(db_path):
    """
    WindowCapture 테이블에서 데이터를 불러오고 TimeStamp를 KST로 변환하는 함수.
    :param db_path: 데이터베이스 파일 경로
    :return: 변환된 WindowCapture 관련 데이터와 열 헤더 리스트
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # SQL 쿼리 실행
        query = """
        SELECT 
            wc.Id, wc.Name, wc.ImageToken, wc.WindowTitle, 
            app.Name AS AppName, wc.TimeStamp, file.Path AS FilePath, web.Uri AS WebUri
        FROM WindowCapture wc
        LEFT JOIN WindowCaptureAppRelation war ON wc.Id = war.WindowCaptureId
        LEFT JOIN App app ON war.AppId = app.Id
        LEFT JOIN WindowCaptureFileRelation wfr ON wc.Id = wfr.WindowCaptureId
        LEFT JOIN File file ON wfr.FileId = file.Id
        LEFT JOIN WindowCaptureWebRelation wwr ON wc.Id = wwr.WindowCaptureId
        LEFT JOIN Web web ON wwr.WebId = web.Id
        ORDER BY wc.Id;
        """
        cursor.execute(query)
        data = cursor.fetchall()

        headers = [description[0] for description in cursor.description]

        # TimeStamp 열을 KST로 변환
        converted_data = []
        for row in data:
            row = list(row)  # 튜플을 리스트로 변환하여 수정 가능하게 함
            if row[5]:  # TimeStamp가 None이 아닐 때 변환
                row[5] = convert_unix_timestamp(row[5])
            converted_data.append(row)

        return converted_data, headers
    except sqlite3.Error as e:
        return None, None
    finally:
        conn.close()

def load_app_data_from_db(db_path):
    """
    App 테이블과 AppDwellTime, WindowCapture 테이블에서 필요한 데이터를 조인하여 중복을 줄이고 데이터를 반환합니다.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 각 App ID에 대해 고유한 WindowCapture 데이터만 반환하도록 중복을 제거한 쿼리 작성
        query = """
        SELECT 
            app.ID,
            app.WindowsAppID,
            app.NAME,
            app.PATH,
            adt.HourStartTimeStamp,
            adt.DwellTime,
            wc.TimeStamp
        FROM App app
        LEFT JOIN AppDwellTime adt ON app.WindowsAppID = adt.WindowsAppID
        LEFT JOIN (
            SELECT WindowCaptureAppRelation.AppId, MAX(WindowCapture.TimeStamp) as TimeStamp
            FROM WindowCapture
            JOIN WindowCaptureAppRelation ON WindowCapture.Id = WindowCaptureAppRelation.WindowCaptureId
            GROUP BY WindowCaptureAppRelation.AppId
        ) wc ON wc.AppId = app.ID
        ORDER BY app.ID;
        """
        cursor.execute(query)
        data = cursor.fetchall()

        # 열 이름 가져오기
        headers = [description[0] for description in cursor.description]

        # 시간 변환 처리
        converted_data = []
        for row in data:
            row = list(row)
            # HourStartTimeStamp 변환
            if row[4]:
                row[4] = convert_unix_timestamp(row[4])
            # DwellTime 변환
            if row[5]:
                row[5] = round(row[5] / 1000, 2)  # 밀리초 -> 초 단위 변환
            # TimeStamp 변환
            if row[6]:
                row[6] = convert_unix_timestamp(row[6])
            converted_data.append(row)

        return converted_data, headers
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None, None
    finally:
        conn.close()


def load_web_data(db_path, keywords=None):
    """Web 테이블의 모든 URI는 필터링에 포함되지 않으며, 해당 ID의 WindowTitle과 TimeStamp도 함께 가져옵니다.
       URI가 없는 경우, 키워드를 통해 필터링된 WindowTitle과 TimeStamp만 가져옵니다.
    """
    data, headers = [], ["URI", "Window Title", "TimeStamp"]

    if not db_path:
        return data, headers

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Web 테이블의 모든 URI와 관련된 Title, TimeStamp를 가져오는 쿼리
        query_web = """
        SELECT 
            web.Uri, 
            wc.WindowTitle, 
            wc.TimeStamp
        FROM Web web
        LEFT JOIN WindowCaptureWebRelation wwr ON web.Id = wwr.WebId
        LEFT JOIN WindowCapture wc ON wwr.WindowCaptureId = wc.Id
        """
        cursor.execute(query_web)
        web_data = cursor.fetchall()

        # URI가 없는 WindowCapture의 WindowTitle과 TimeStamp를 키워드로 필터링하여 가져오는 쿼리
        query_wc = """
        SELECT 
            NULL AS URI, 
            wc.WindowTitle, 
            wc.TimeStamp
        FROM WindowCapture wc
        LEFT JOIN WindowCaptureWebRelation wwr ON wc.Id = wwr.WindowCaptureId
        WHERE wwr.WebId IS NULL
        """

        # 여러 키워드가 있을 경우 WindowTitle 필터링 조건 추가
        if keywords:
            keyword_filters = " AND ".join(["wc.WindowTitle LIKE ?"] * len(keywords))
            query_wc += f" AND ({keyword_filters})"
            parameters = tuple(f'%{keyword}%' for keyword in keywords)
        else:
            parameters = ()

        cursor.execute(query_wc, parameters)
        wc_data = cursor.fetchall()

        # 타임스탬프 변환 처리
        converted_data = []
        for row in web_data + wc_data:
            row = list(row)
            if row[2]:  # TimeStamp 변환
                row[2] = convert_unix_timestamp(row[2])
            converted_data.append(row)

        return converted_data, headers

    except sqlite3.Error as e:
        return None, None
    finally:
        conn.close()


def convert_chrome_timestamp(timestamp):
    """Chrome, Edge, Whale 타임스탬프 변환 (1601년 기준, 마이크로초 단위)"""
    base_date = datetime(1601, 1, 1, tzinfo=timezone.utc)  # UTC 기준
    timestamp_seconds = timestamp / 1_000_000  # 마이크로초 -> 초
    return (base_date + timedelta(seconds=timestamp_seconds)).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')

def convert_firefox_timestamp(timestamp):
    """Firefox 타임스탬프 변환 (1970년 기준, 밀리초 단위)"""
    timestamp_seconds = timestamp / 1000  # 밀리초 -> 초
    return datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')

def convert_timestamp(browser, timestamp):
    """브라우저별 타임스탬프 변환 함수"""
    if browser in ["Chrome", "Edge", "Whale"]:
        return convert_chrome_timestamp(timestamp)
    elif browser == "Firefox":
        return convert_firefox_timestamp(timestamp)
    else:
        return None  # 다른 브라우저가 있을 경우 추가 변환 함수 필요

def load_recovery_data(db_path):
    """
    re_WindowCapture 테이블에서 데이터를 불러와 필요한 컬럼을 반환합니다.
    AppName은 빈 문자열로 설정하고, 이미지 컬럼은 'X'로 채웁니다.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = """
        SELECT 
            Id, 
            Name, 
            WindowTitle, 
            '' AS AppName,  -- AppName을 빈 문자열로 설정
            TimeStamp,
            'X' AS 이미지      -- 이미지 컬럼을 'X'로 설정
        FROM re_WindowCapture
        ORDER BY Id;
        """
        cursor.execute(query)
        data = cursor.fetchall()

        headers = ["Id", "Name", "WindowTitle", "AppName", "TimeStamp", "이미지"]

        return data, headers
    except sqlite3.Error as e:
        print(f"re_WindowCapture 데이터 로드 오류: {e}")
        return None, None
    finally:
        conn.close()

def load_file_data_from_db(db_path):
    """
    File 테이블에서 데이터를 불러와 반환합니다.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = """
        SELECT 
            Id, 
            Path, 
            Name, 
            Extension, 
            VolumeId
        FROM File
        ORDER BY Id;
        """
        cursor.execute(query)
        data = cursor.fetchall()

        headers = [description[0] for description in cursor.description]

        return data, headers
    except sqlite3.Error as e:
        print(f"File 테이블 데이터 로드 오류: {e}")
        return None, None
    finally:
        conn.close()
