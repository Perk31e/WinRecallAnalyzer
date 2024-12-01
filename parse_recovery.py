# parse_recovery.py

import subprocess
import sys
import os
import re
import sqlite3
import sqlparse
import shutil

def run_shell_command(command):
    try:
        # 표준 출력과 오류를 모두 캡처
        result = subprocess.run(
            command, 
            shell=True, 
            check=True,
            capture_output=True,
            text=True
        )
        print(f"명령어 출력: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"명령어 실행 중 오류 발생: {e}")
        print(f"오류 출력: {e.stderr}")
        return False
    except Exception as e:
        print(f"예외 발생: {e}")
        return False

def filter_backup_sql(dump_sql, filtered_dump_sql):
    system_tables = [
        "sqlite_master",
        "sqlite_sequence",
        "sqlite_temp_master",
    ]

    try:
        with open(dump_sql, 'r', encoding='utf-8') as infile, \
             open(filtered_dump_sql, 'w', encoding='utf-8') as outfile:
            sql_content = infile.read()
            statements = sqlparse.split(sql_content)
            for statement in statements:
                stmt = statement.strip()
                if not stmt:
                    continue

                if any(re.search(rf'\b{re.escape(table)}\b', stmt, re.IGNORECASE) for table in system_tables):
                    print(f"시스템 테이블 관련 SQL 문을 필터링했습니다: {stmt[:50]}...")
                    continue

                outfile.write(stmt + ';\n')

        print(f"필터링된 덤프 파일이 '{filtered_dump_sql}'에 저장되었습니다.")
    except Exception as e:
        print(f"백업 필터링 중 오류 발생: {e}")
        sys.exit(1)

def execute_filtered_sql(filtered_dump_sql, recovered_db):
    try:
        conn = sqlite3.connect(recovered_db)
        cursor = conn.cursor()

        with open(filtered_dump_sql, 'r', encoding='utf-8') as infile:
            sql_content = infile.read()

        statements = sqlparse.split(sql_content)
        total_statements = len(statements)
        print(f"총 {total_statements}개의 SQL 문을 실행합니다.")
        
        success_count = 0
        error_count = 0

        for idx, statement in enumerate(statements, 1):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                cursor.execute(stmt)
                success_count += 1
            except sqlite3.Error as e:
                error_count += 1
                print(f"SQL 문 {idx} 실행 중 오류 발생: {e}")
                print(f"오류가 발생한 SQL 문: {stmt[:100]}...")
                continue

        print(f"\n실행 완료: 성공 {success_count}개, 실패 {error_count}개")
        conn.commit()
        conn.close()
        print(f"데이터베이스가 성공적으로 '{recovered_db}'로 복구되었습니다.")
    except Exception as e:
        print(f"데이터베이스 복구 중 오류 발생: {e}")
        sys.exit(1)

def check_integrity(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            print("데이터베이스 무결성 검사: 통과")
        else:
            print(f"데이터베이스 무결성 검사 실패: {result}")
        conn.close()
    except sqlite3.Error as e:
        print(f"무결성 검사 중 오류 발생: {e}")

def get_sqlite_path():
    if os.name == 'nt':  # Windows
        # 프로그램 디렉토리 내의 sqlite3.exe를 찾음
        local_sqlite = os.path.join(os.path.dirname(__file__), 'sqlite3.exe')
        if os.path.exists(local_sqlite):
            return local_sqlite
        # 환경 변수에서 찾음
        return shutil.which('sqlite3.exe') or 'sqlite3'
    return shutil.which('sqlite3') or 'sqlite3'

sqlite_executable = get_sqlite_path()

def ensure_directory_exists(path):
    """디렉토리가 존재하는지 확인하고 없으면 생성"""
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"디렉토리 생성됨: {directory}")
        except Exception as e:
            print(f"디렉토리 생성 중 오류 발생: {e}")
            return False
    return True

def check_permissions(path):
    """파일 또는 디렉토리의 권한 확인"""
    try:
        directory = os.path.dirname(path)
        # 디렉토리 쓰기 권한 확인
        if not os.access(directory, os.W_OK):
            print(f"경고: {directory}에 쓰기 권한이 없습니다.")
            return False
        return True
    except Exception as e:
        print(f"권한 확인 중 오류 발생: {e}")
        return False

def main(source_db, recovered_db):
    try:
        # 권한 확인
        if not check_permissions(recovered_db):
            print("필요한 권한이 없습니다.")
            sys.exit(1)

        # 경로 정규화 추가
        source_db = os.path.abspath(source_db)
        recovered_db = os.path.abspath(recovered_db)
        output_dir = os.path.dirname(recovered_db)
        
        # 디렉토리 존재 확인
        if not ensure_directory_exists(output_dir):
            print(f"출력 디렉토리를 생성할 수 없습니다: {output_dir}")
            sys.exit(1)
        
        # 파일 경로 설정
        dump_sql = os.path.join(output_dir, 'backup.sql')
        filtered_dump_sql = os.path.join(output_dir, 'backup_filtered.sql')
        
        if not shutil.which(sqlite_executable):
            print(f"SQLite 명령줄 도구 '{sqlite_executable}'을(를) 찾을 수 없습니다.")
            sys.exit(1)

        if not os.path.exists(source_db):
            print(f"원본 데이터베이스 파일 '{source_db}'이(가) 존재하지 않습니다.")
            sys.exit(1)

        if os.path.exists(dump_sql):
            try:
                os.remove(dump_sql)
                print(f"기존 덤프 파일 '{dump_sql}'을(를) 삭제했습니다.")
            except Exception as e:
                print(f"덤프 파일 삭제 중 오류 발생: {e}")
                sys.exit(1)

        try:
            print("데이터베이스 덤프를 생성 중입니다...")
            if os.name == 'nt':
                command = f'echo .recover | "{sqlite_executable}" "{source_db}" > "{dump_sql}"'
            else:
                command = f'echo ".recover" | "{sqlite_executable}" "{source_db}" > "{dump_sql}"'
            run_shell_command(command)
            print(f"데이터베이스 덤프가 성공적으로 '{dump_sql}'에 저장되었습니다.")
        except Exception as e:
            print(f".recover 명령어 실행 중 오류 발생: {e}")
            sys.exit(1)

        print("필터링된 덤프 파일을 생성 중입니다...")
        filter_backup_sql(dump_sql, filtered_dump_sql)

        if os.path.exists(recovered_db):
            try:
                os.remove(recovered_db)
                print(f"기존 복구 데이터베이스 파일 '{recovered_db}'을(를) 삭제했습니다.")
            except Exception as e:
                print(f"복구 데이터베이스 파일 삭제 중 오류 발생: {e}")
                sys.exit(1)

        print("데이터베이스를 복구 중입니다...")
        execute_filtered_sql(filtered_dump_sql, recovered_db)

        print("데이터베이스 무결성 검사를 실행 중입니다...")
        check_integrity(recovered_db)

        print("데이터베이스 복구 과정이 완료되었습니다.")

    except Exception as e:
        print(f"예외 발생: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python parse_recovery.py <source_db_path> <recovered_db_path>")
        sys.exit(1)
    source_db_path = sys.argv[1]
    recovered_db_path = sys.argv[2]
    main(source_db_path, recovered_db_path)
