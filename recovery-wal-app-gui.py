# recovery-wal-app-gui.py

import os
import sys

def main(input_db_path):
    # 입력 파일 경로에서 디렉토리와 파일명 가져오기
    input_dir = os.path.dirname(input_db_path)
    input_db_wal_path = os.path.join(input_dir, "remained.db-wal")

    # 테이블 리스트
    tables = [
        "App", "WindowCaptureAppRelation", "Web", "WindowCaptureWebRelation",
    ]

    # 복사된 데이터베이스 파일 읽기
    with open(input_db_path, 'rb') as db_file:
        content = db_file.read()

    # 페이지 크기 가져오기 (16번과 17번 오프셋)
    page_size = content[16:18]
    page_size_hex = ' '.join(format(byte, '02X') for byte in page_size)
    print(f"Page size(hex): {page_size_hex}")

    # 페이지 크기를 16진수 문자열로 변환하여 숫자로 계산할 수 있게 함
    page_size_int = int(page_size_hex.replace(" ", ""), 16)  # '10 00' -> '1000' -> 4096

    # remained.db-wal 파일 읽기
    with open(input_db_wal_path, 'rb') as wal_file:
        wal_content = wal_file.read()

    # 각 테이블에 대해 작업 반복
    for table_name in tables:
        print(f"Processing table: {table_name}")
        
        # 테이블 명의 구분자 결정
        if table_name in ["WindowCaptureTextIndex_content", "WindowCaptureTextIndex_docsize"]:
            delimiter = "'"
        else:
            delimiter = '"'

        # 테이블 명의 헥스값 얻기
        table_create_statement = f'CREATE TABLE {delimiter}{table_name}{delimiter}'
        table_hex = ' '.join(format(ord(char), '02X') for char in table_create_statement)
        print(f'Find CREATE TABLE {delimiter}{table_name}{delimiter} String(hex):', table_hex)

        # 모든 위치 찾기
        hex_content = content.hex().upper()
        positions = []
        start = 0

        while True:
            position = hex_content.find(table_hex.replace(" ", ""), start)
            if position == -1:
                break
            offset = position // 2  # 바이트 단위로 변환
            positions.append(offset)
            start = position + 1  # 다음 위치부터 검색

        if positions:
            for offset in positions:
                print(f"{table_name} Offset (hex): {hex(offset)}")
            
            # 가장 높은 Offset의 직전 값
            max_offset = max(positions)
            page_num_offset = max_offset - 1
            page_num_value = content[page_num_offset]
            page_num_hex = format(page_num_value, '02X')  # 페이지 번호 헥스 값 저장
            print(f"{table_name} Page Num(hex): {page_num_hex}")
            
            # Start_Page_Offset 계산
            adjusted_page_num = page_num_value - 0x01
            Start_Page_Offset = adjusted_page_num * page_size_int
            print(f"{table_name} Start Page Offset: {hex(Start_Page_Offset)}")
        else:
            print(f"Hex pattern not found for {table_name}")
            print("===========================")
            continue

        # remained.db-wal 파일에서 8바이트 패턴 생성
        pattern_bytes = bytes.fromhex(f"000000{page_num_hex}00000000")

        wal_start = 0
        pattern_positions = []
        largest_record_value = 0
        largest_record_index = -1
        largest_record_start_offset = None

        # 모든 패턴 위치 찾기
        while wal_start < len(wal_content) - 8:
            # 8바이트 비교
            if wal_content[wal_start:wal_start + 8] == pattern_bytes:
                pattern_positions.append(wal_start)
            wal_start += 1

        if pattern_positions:
            for idx, position in enumerate(pattern_positions, start=1):
                target_offset = position + 0x18
                print(f"{idx}. {table_name} Page Hex values from {hex(target_offset)} to {hex(target_offset + 0x32)}:")
                
                # 0x20 바이트까지의 헥스 값을 16바이트씩 나누어 출력(공백포함)
                hex_range = wal_content[target_offset:target_offset + 0x20]
                hex_range_str = ' '.join(format(byte, '02X') for byte in hex_range)
                hex_lines = [hex_range_str[i:i+47] for i in range(0, len(hex_range_str), 48)]
                for line in hex_lines:
                    print(line)

                # 첫 번째 바이트가 0D인지 확인
                if hex_range[0] == 0x0D:
                    # 네 번째와 다섯 번째 바이트 추출하여 결합하고 정수로 변환
                    record_value = int(format(hex_range[3], '02X') + format(hex_range[4], '02X'), 16)

                    # 가장 큰 레코드 값을 확인
                    if record_value > largest_record_value:
                        largest_record_value = record_value
                        largest_record_index = idx
                        largest_record_start_offset = target_offset

                print()  # 줄바꿈

            # 가장 큰 레코드 값을 가진 페이지 출력 및 종료 오프셋 계산
            if largest_record_index != -1 and largest_record_start_offset is not None:
                largest_record_end_offset = largest_record_start_offset + page_size_int - 1
                print(f"{table_name} Page {largest_record_index} from {hex(largest_record_start_offset)} to {hex(largest_record_end_offset)} has lots of records")

                # 복사된 데이터 대체 작업 수행
                with open(input_db_path, 'r+b') as db_file:
                    # remained.db-wal 파일의 가장 큰 레코드 페이지 읽기
                    replacement_data = wal_content[largest_record_start_offset:largest_record_start_offset + page_size_int]
                    
                    # Start Page Offset 위치로 이동하여 해당 위치부터 대체
                    db_file.seek(Start_Page_Offset)
                    db_file.write(replacement_data)
                    print(f"Replaced data at {table_name} Start Page Offset: {hex(Start_Page_Offset)} with data from remained.db-wal")
        else:
            print(f"Pattern not found in remained.db-wal for {table_name}")

        print("===========================")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python recovery-wal-app-gui.py <db_path>")
        sys.exit(1)
    main(sys.argv[1])