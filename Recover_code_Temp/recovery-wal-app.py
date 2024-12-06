# recovery-wal-app.py
import shutil
import os

# 사용자 입력을 받아서 경로 지정, 따옴표 제거
input_db_path = input("Input ukg.db path: ").strip('"')
input_db_wal_path = os.path.join(os.path.dirname(input_db_path), "ukg.db-wal")

# 현재 스크립트 실행 경로에 복사할 경로 지정
output_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovered_with_wal.db")
output_wal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remained.db-wal")

# 기존 파일이 존재하면 삭제
if os.path.exists(output_db_path):
    os.remove(output_db_path)
if os.path.exists(output_wal_path):
    os.remove(output_wal_path)

# 파일 복사
shutil.copyfile(input_db_wal_path, output_wal_path)
shutil.copyfile(input_db_path, output_db_path)

# 복사된 데이터베이스 파일 읽기
with open(output_db_path, 'rb') as db_file:
    db_file_content = db_file.read()

    # 페이지 크기 가져오기 (16번과 17번 오프셋)
    page_size = db_file_content[16:18]
    page_size_hex = ' '.join(format(byte, '02X') for byte in page_size)
    print(f"Page size(hex): {page_size_hex}")

    # 페이지 크기를 16진수 문자열로 변환하여 숫자로 계산할 수 있게 함
    page_size_int = int(page_size_hex.replace(" ", ""), 16)  # '10 00' -> '1000' -> 4096

# 테이블 명의 헥스값 얻기
App_Table = 'CREATE TABLE "App"'
App_hex = ' '.join(format(ord(char), '02X') for char in App_Table)
print('Find CREATE TABLE "App" String(hex):', App_hex)

# 모든 위치 찾기
# 16진수는 대소문자를 구분하지 않지만, 검색 시 일관성을 유지하기 위해 대문자로 통일합니다.
hex_content = db_file_content.hex().upper()
positions = []
start = 0

while True:
    position = hex_content.find(App_hex.replace(" ", ""), start)
    if position == -1:
        break
    offset = position // 2  # 바이트 단위로 변환
    positions.append(offset)
    start = position + 1  # 다음 위치부터 검색

if positions:
    for offset in positions:
        print(f"Offset (hex): {hex(offset)}")
    
    # 가장 높은 Offset의 직전 값
    max_offset = max(positions)
    # 테이블의 페이지 번호 오프셋은 CREATE TABLE 테이블명 바로 앞의 1바이트 값이다.
    page_num_offset = max_offset - 1
    page_num_value = db_file_content[page_num_offset]
    page_num_hex = format(page_num_value, '02X')  # 페이지 번호 헥스 값 저장
    print(f"Page Num(hex): {page_num_hex}")
    
    # Start_Page_Offset 계산
    adjusted_page_num = page_num_value - 0x01
    Start_Page_Offset = adjusted_page_num * page_size_int
    print(f"Start Page Offset: {hex(Start_Page_Offset)}")
else:
    print("Hex pattern not found for App")

# remained.db-wal 파일에서 패턴 찾기
with open(output_wal_path, 'rb') as wal_file:
    wal_file_content = wal_file.read()
    # 8바이트 패턴 생성
    pattern_bytes = bytes.fromhex(f"000000{page_num_hex}00000000")

    # db-wal 파일 탐색 위치 
    wal_pos = 0
    # 패턴 위치 저장
    pattern_positions = []
    largest_record_count = 0
    largest_record_index = -1
    largest_record_start_offset = None

    # 모든 패턴 위치 찾기 (Buffer Overrun 방지를 위해 8을 뺌)
    while wal_pos < len(wal_file_content) - 8:
        # 8바이트 비교
        if wal_file_content[wal_pos:wal_pos + 8] == pattern_bytes:
            pattern_positions.append(wal_pos)
        wal_pos += 1

    if pattern_positions:
        for idx, position in enumerate(pattern_positions, start=1):
            # 페이지 타입 등장 부분
            page_header_start = position + 0x18
            print(f"{idx}. App Page Hex values from {hex(page_header_start)} to {hex(page_header_start + 0x20)}:")

            # 페이지 전체를 읽습니다.
            page_range = bytearray(wal_file_content[page_header_start:page_header_start + page_size_int])

            # [DEBUG] 페이지 헤더 처음 0x20(32) 바이트만 출력한다 이때 한줄에 16바이트씩 출력
            header_hex_dump = ' '.join(format(byte, '02X') for byte in page_range[:0x20])
            header_lines = [header_hex_dump[i:i+47] for i in range(0, len(header_hex_dump), 48)]   # 16바이트(32자) + 공백(16자) = 48자
            for line in header_lines:
                print(line)

            # 첫 번째 바이트가 0D인지 확인
            if page_range[0] == 0x0D:
                # 네 번째와 다섯 번째 바이트 추출하여 결합하고 정수로 변환
                record_value = int(format(page_range[3], '02X') + format(page_range[4], '02X'), 16)

                # 가장 큰 레코드 값을 확인
                if record_value > largest_record_count:
                    largest_record_count = record_value
                    largest_record_index = idx
                    largest_record_start_offset = page_header_start

            print()  # 줄바꿈

        # 가장 큰 레코드 수를 가진 페이지 출력 및 종료 오프셋 계산
        if largest_record_index != -1 and largest_record_start_offset is not None:
            largest_record_end_offset = largest_record_start_offset + page_size_int - 1
            print(f"App Page {largest_record_index} from {hex(largest_record_start_offset)} to {hex(largest_record_end_offset)} has lots of records")
    else:
        print("Pattern not found in remained.db-wal.")

# 복사된 데이터 대체 작업 수행
if largest_record_start_offset is not None:
    with open(output_db_path, 'r+b') as db_file:
        # remained.db-wal 파일의 가장 큰 레코드 페이지 읽기
        replacement_data = wal_file_content[largest_record_start_offset:largest_record_start_offset + page_size_int]
        
        # Start Page Offset 위치로 이동하여 해당 위치부터 대체
        db_file.seek(Start_Page_Offset)
        db_file.write(replacement_data)
        print(f"Replaced data at Start Page Offset: {hex(Start_Page_Offset)} with data from remained.db-wal")
