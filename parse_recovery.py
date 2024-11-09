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
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"명령어 실행 중 오류 발생: {e}")
        sys.exit(1)

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

        for idx, statement in enumerate(statements, 1):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                cursor.execute(stmt)
            except sqlite3.Error as e:
                print(f"SQL 문 {idx} 실행 중 오류 발생: {e}")
                print(f"오류가 발생한 SQL 문: {stmt[:100]}...")
                continue
            else:
                print(f"SQL 문 {idx}: 성공적으로 실행되었습니다.")

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

def main(source_db, recovered_db):
    sqlite_executable = 'sqlite3'  # 시스템 PATH에 sqlite3가 포함되어 있지 않다면, 절대 경로를 지정하세요.
    dump_sql = 'backup.sql'
    filtered_dump_sql = 'backup_filtered.sql'

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
            command = f'echo .recover | {sqlite_executable} "{source_db}" > "{dump_sql}"'
        else:
            command = f'echo ".recover" | {sqlite_executable} "{source_db}" > "{dump_sql}"'
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

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python parse_recovery.py <source_db_path> <recovered_db_path>")
        sys.exit(1)
    source_db_path = sys.argv[1]
    recovered_db_path = sys.argv[2]
    main(source_db_path, recovered_db_path)
