# parse_process.py

import sqlite3
import sys
import os

def connect_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        return conn, conn.cursor()
    except sqlite3.Error as e:
        print(f"데이터베이스 연결 오류: {e}")
        sys.exit(1)

def create_re_windowcapture_table(conn, cursor):
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS re_WindowCapture (
                Id INTEGER PRIMARY KEY,
                Name TEXT,
                ImageToken TEXT,
                IsForeground BOOLEAN,
                WindowId INTEGER,
                WindowBounds TEXT,
                WindowTitle TEXT,
                Properties TEXT,
                TimeStamp TEXT,
                IsProcessed BOOLEAN,
                ActivationUri TEXT,
                ActivityId TEXT,
                FallbackUri TEXT
            );
        ''')
        cursor.execute("DELETE FROM re_WindowCapture;")
        conn.commit()
    except sqlite3.Error as e:
        print(f"re_WindowCapture 테이블 생성 오류: {e}")
        conn.rollback()
        sys.exit(1)

def remove_duplicate_ids(cursor):
    try:
        cursor.execute('''
            SELECT Id, COUNT(*) as count
            FROM lost_and_found
            GROUP BY Id
            HAVING count > 1;
        ''')
        duplicates = cursor.fetchall()
        
        for dup in duplicates:
            id_val = dup[0]
            count = dup[1]
            cursor.execute('''
                DELETE FROM lost_and_found
                WHERE Id = ? AND rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM lost_and_found
                    WHERE Id = ?
                );
            ''', (id_val, id_val))
        
        if duplicates:
            print(f"중복된 Id가 {len(duplicates)}개 발견되어 정리되었습니다.")
        else:
            print("중복된 Id가 존재하지 않습니다.")
    except sqlite3.Error as e:
        print(f"중복 Id 정리 중 오류 발생: {e}")
        sys.exit(1)

def check_table_exists(cursor, table_name):
    try:
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?;
        """, (table_name,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"테이블 존재 여부 확인 중 오류 발생: {e}")
        sys.exit(1)

def main(recovered_db):
    # 필수 파일 존재 여부 확인
    if not os.path.exists(recovered_db):
        print(f"원본 데이터베이스 파일 '{recovered_db}'이(가) 존재하지 않습니다.")
        sys.exit(1)

    # 데이터베이스에 연결
    conn, cursor = connect_db(recovered_db)

    # 'lost_and_found' 테이블이 존재하는지 확인
    if not check_table_exists(cursor, "lost_and_found"):
        print("lost_and_found 테이블이 없습니다. 복구할 레코드가 없습니다.")
        conn.close()
        sys.exit(0)  # 정상 종료

    # 'lost_and_found' 테이블의 중복 Id 제거
    remove_duplicate_ids(cursor)

    # 're_WindowCapture' 테이블 생성 및 초기화
    create_re_windowcapture_table(conn, cursor)

    # 'lost_and_found' 테이블의 모든 데이터 읽기
    try:
        cursor.execute("SELECT * FROM lost_and_found;")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    except sqlite3.Error as e:
        print(f"lost_and_found 테이블 읽기 중 오류 발생: {e}")
        conn.close()
        sys.exit(1)

    window_capture_events = [
        "WindowCaptureEvent",
        "WindowCreatedEvent",
        "WindowChangedEvent",
        "WindowDestroyedEvent",
        "ForegroundChangedEvent"
    ]

    # columns_to_move 딕셔너리 수정: 실제 컬럼 이름으로 변경
    columns_to_move = {
        "Id": "id",
        "Name": "c1",
        "ImageToken": "c2",
        "IsForeground": "c3",
        "WindowId": "c4",
        "WindowBounds": "c5",
        "WindowTitle": "c6",
        "Properties": "c7",
        "TimeStamp": "c8",
        "IsProcessed": "c9",
        "ActivationUri": "c10",
        "ActivityId": "c11",
        "FallbackUri": "c12"
    }

    missing_columns = [source_col for target_col, source_col in columns_to_move.items() if source_col not in columns]
    if missing_columns:
        print(f"lost_and_found 테이블에 필요한 칼럼이 없습니다: {missing_columns}")
        conn.close()
        sys.exit(1)

    column_indices = {col: idx for idx, col in enumerate(columns)}

    moved_count = 0
    skipped_count = 0

    for row in rows:
        has_event = False
        for source_col in columns_to_move.values():
            if source_col == "id":  # 'id'는 이벤트와 관련 없는 컬럼이므로 건너뜁니다.
                continue
            cell_value = row[column_indices[source_col]]
            if cell_value in window_capture_events:
                has_event = True
                break

        if has_event:
            non_null_count = 0
            for target_col, source_col in columns_to_move.items():
                if source_col in ["rootpgno", "pgno", "nfield", "c0"]:
                    continue
                if row[column_indices[source_col]] is not None:
                    non_null_count += 1

            if non_null_count <= 3:
                try:
                    row_id = row[column_indices["id"]]
                    cursor.execute('DELETE FROM lost_and_found WHERE id = ?;', (row_id,))
                    skipped_count += 1
                except sqlite3.Error as e:
                    print(f"lost_and_found에서 행 삭제 중 오류 발생: {e}")
                    conn.close()
                    sys.exit(1)
                continue
            else:
                try:
                    window_capture_data = tuple(row[column_indices[source_col]] for target_col, source_col in columns_to_move.items())
                    cursor.execute('''
                        INSERT INTO re_WindowCapture (
                            Id, Name, ImageToken, IsForeground, WindowId, WindowBounds, 
                            WindowTitle, Properties, TimeStamp, IsProcessed, ActivationUri, 
                            ActivityId, FallbackUri
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    ''', window_capture_data)
                    moved_count += 1

                    row_id = row[column_indices["id"]]
                    cursor.execute('DELETE FROM lost_and_found WHERE id = ?;', (row_id,))
                except sqlite3.IntegrityError as e:
                    print(f"re_WindowCapture로 데이터 이동 중 무결성 오류 발생: {e}")
                    continue
                except sqlite3.Error as e:
                    print(f"re_WindowCapture로 데이터 이동 중 오류 발생: {e}")
                    conn.close()
                    sys.exit(1)

    try:
        conn.commit()
    except sqlite3.Error as e:
        print(f"커밋 중 오류 발생: {e}")
        conn.close()
        sys.exit(1)

    conn.close()

    print(f"데이터 이동 완료: {moved_count}개의 행이 re_WindowCapture 테이블로 이동되었습니다.")
    print(f"{skipped_count}개의 행이 조건에 맞지 않아 삭제되었습니다.")
    print("데이터베이스 복구 과정이 완료되었습니다.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python parse_process.py <recovered_db_path>")
        sys.exit(1)
    recovered_db_path = sys.argv[1]
    main(recovered_db_path)
