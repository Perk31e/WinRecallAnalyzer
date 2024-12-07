# temp-all-fix-cell.py

import shutil
import os

# 데이터에서 00 00 00 혹은 00 00 패턴을 찾습니다. (각 레코드 시작 지점 찾는용도)
def find_next_zeros(cell_data, start_pos):
    current_pos = start_pos
    while current_pos < len(cell_data) - 1:
        if current_pos < len(cell_data) - 3 and cell_data[current_pos:current_pos+3] == b'\x00\x00\x00':
            return current_pos, 3  # 패턴의 시작 위치와 길이 반환
        elif cell_data[current_pos:current_pos+2] == b'\x00\x00':
            return current_pos, 2  # 패턴의 시작 위치와 길이 반환
        current_pos += 1
    return -1, 0  # 패턴이 없을 경우

# 잘못된 cell offset 수정
def process_cell_pointers(page_range):
    page_start_addr = 0   # 페이지 시작 주소
    cell_pointer_offset = 8  # SQLite 페이지에서 셀 포인터 배열은 오프셋 8부터 시작

    while cell_pointer_offset < len(page_range) - 2:
        # 셀 포인터 배열의 끝을 나타내는 00 00을 만나면 종료
        if page_range[cell_pointer_offset:cell_pointer_offset+2] == b'\x00\x00':
            break

        # 현재 셀 포인터와 다음 셀 포인터를 2바이트씩 읽음
        current_offset = page_range[cell_pointer_offset:cell_pointer_offset+2]
        next_offset = page_range[cell_pointer_offset+2:cell_pointer_offset+4]

        # 데이터가 불완전한 경우 종료
        if len(current_offset) < 2 or len(next_offset) < 2:
            break

        # 셀 오프셋이 똑같은 값을 가진다 = 삭제된 셀이 존재한다! (셀 오프셋은 서로 개별적인 값을 가져야 한다)
        if current_offset == next_offset:
            offset_value = int.from_bytes(current_offset, byteorder='big')
            # 셀 오프셋이 가리키는 레코드의 시작주소 획득 (페이지 시작 주소에 셀 오프셋 값을 더함)
            abs_addr = page_start_addr + offset_value

            # 다음 00 00 00 혹은 00 00패턴이 등장하는 주소 찾고 00 00 00 혹은 00 00인지 길이 반환
            # 해당 패턴이 등장하는것은 다음 레코드의 시작을 의미하기 때문이다 (삭제관점에서)
            zero_pos, pattern_length = find_next_zeros(page_range, abs_addr)

            # 00 00 00 혹은 00 00 패턴이 등장하는 주소 찾았다면
            if zero_pos != -1:
                # 다음 셀 오프셋 업데이트
                next_cell_offset = zero_pos - page_start_addr
                page_range[cell_pointer_offset+2:cell_pointer_offset+4] = next_cell_offset.to_bytes(2, byteorder='big')
                prev_value = current_offset
                # 업데이트 한 오프셋 이후의 위치 저장
                update_offset = cell_pointer_offset + 4
                # 여전히 업데이트 할 셀 오프셋이 남아있는지 확인
                while update_offset < len(page_range) - 1 and page_range[update_offset:update_offset+2] == prev_value:
                    # 00 00을 만나면 루프 종료
                    if page_range[update_offset:update_offset+2] == b'\x00\x00':
                        break

                    # 다음 00 00 00 혹은 00 00패턴 찾기
                    next_zero_pos, next_pattern_length = find_next_zeros(page_range, zero_pos + pattern_length)
                    # 다음 00 00 00 혹은 00 00패턴을 찾았다면
                    if next_zero_pos != -1:
                        # 새로운 셀 오프셋 업데이트
                        next_cell_offset = next_zero_pos - page_start_addr
                        page_range[update_offset:update_offset+2] = next_cell_offset.to_bytes(2, byteorder='big')
                        zero_pos = next_zero_pos
                        pattern_length = next_pattern_length
                    else:
                        break  # 더 이상 패턴이 없으면 종료

                    update_offset += 2
            else:
                break  # 패턴을 찾지 못하면 종료
        cell_pointer_offset += 2

    return page_range

# 셀 콘텐츠 영역의 시작 오프셋을 업데이트합니다.
def update_cell_content_area_start(page_range):
    last_valid_pointer = page_range[8:10]  # 첫 번째 셀 포인터로 초기화
    
    for i in range(8, len(page_range) - 1, 2):
        cell_pointer = page_range[i:i+2]
        
        if cell_pointer == b'\x00\x00':
            page_range[5:7] = last_valid_pointer
            return
        
        last_valid_pointer = cell_pointer
    
    # 모든 셀 포인터가 유효한 경우
    page_range[5:7] = last_valid_pointer

# 사용자 입력을 받아서 db 파일 지정, 따옴표 제거
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

# 테이블 리스트
tables = [
    "App", "Web", "WindowCaptureAppRelation", "WindowCaptureWebRelation"
]

# 복사된 데이터베이스 파일 읽기
with open(output_db_path, 'rb') as db_file:
    db_file_content = db_file.read()

# 페이지 크기 가져오기 (16번과 17번 오프셋)
page_size = db_file_content[16:18]
page_size_hex = ' '.join(format(byte, '02X') for byte in page_size)
print(f"Page size(hex): {page_size_hex}")

# 페이지 크기를 16진수 문자열로 변환하여 숫자로 계산할 수 있게 함
page_size_int = int(page_size_hex.replace(" ", ""), 16)  # '10 00' -> '1000' -> 4096

# remained.db-wal 파일 읽기
with open(output_wal_path, 'rb') as wal_file:
    wal_file_content = wal_file.read()

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
    table_hex = ''.join(format(ord(char), '02X') for char in table_create_statement)
    # [디버깅용] 2바이트마다 공백 추가
    table_hex_spaced = ' '.join([table_hex[i:i+2] for i in range(0, len(table_hex), 2)])
    print(f'Find CREATE TABLE {delimiter}{table_name}{delimiter} String(hex): {table_hex_spaced}')

    # 모든 위치 찾기
    # 16진수는 대소문자를 구분하지 않지만, 검색 시 일관성을 유지하기 위해 대문자로 통일합니다.
    hex_content = db_file_content.hex().upper()
    positions = []
    start = 0

    while True:
        position = hex_content.find(table_hex, start)
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
        # 테이블의 페이지 번호 오프셋은 CREATE TABLE 테이블명 바로 앞의 1바이트 값이다.
        page_num_offset = max_offset - 1
        page_num_value = db_file_content[page_num_offset]
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

    # remained.db-wal 파일에서 각 페이지 별 8바이트 크기의 고유 패턴 생성
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
            print(f"{idx}. {table_name} Page Hex values from {hex(page_header_start)} to {hex(page_header_start + 0x20)}:")

            # 페이지 전체를 읽습니다.
            page_range = bytearray(wal_file_content[page_header_start:page_header_start + page_size_int])

            # [DEBUG] 페이지 헤더 처음 0x20(32) 바이트만 출력한다 이때 한줄에 16바이트씩 출력
            header_hex_dump = ' '.join(format(byte, '02X') for byte in page_range[:0x20])
            header_lines = [header_hex_dump[i:i+47] for i in range(0, len(header_hex_dump), 48)]   # 16바이트(32자) + 공백(16자) = 48자
            for line in header_lines:
                print(line)

            # 첫 번째 바이트가 0D인지 확인
            if page_range[0] == 0x0D:
                # 셀 오프셋 포인터 갯수를 세서 실제 레코드 수가 몇개인지 확인
                cell_pointers = page_range[8:]
                num_records = 0
                # 셀 오프셋 포인터는 2바이트씩 구성되어 있기 때문에 2바이트씩 증가하면서 확인 
                for i in range(0, len(cell_pointers), 2):
                    cell_pointer = cell_pointers[i:i+2]
                    if cell_pointer == b'\x00\x00' or len(cell_pointer) < 2:
                        break
                    num_records += 1

                # 페이지 헤더 내 레코드 갯수가 00 00 이고 실제 레코드 갯수가 0보다 크면 셀 포인터 처리
                if page_range[3:5] == b'\x00\x00' and num_records > 0:
                    # 잘못된 셀 포인터 오프셋 올바르게 업데이트
                    page_range = process_cell_pointers(page_range)
                    # 페이지 헤더 내 레코드 수 업데이트
                    page_range[3:5] = num_records.to_bytes(2, byteorder='big')
                    # 셀 콘텐츠 영역의 시작 오프셋 업데이트
                    update_cell_content_area_start(page_range)

                    # 메모리에 로드된 wal 파일에 변경 사항 반영
                    wal_file_content = wal_file_content[:page_header_start] + page_range + wal_file_content[page_header_start + len(page_range):]

                    # 수정된 페이지 내용을 출력 (처음 0x20 바이트만 출력)
                    print(f"[+] {idx}. (Revised) {table_name} Page Hex values from {hex(page_header_start)} to {hex(page_header_start + 0x20)}:")
                    revised_header_hex_dump = ' '.join(format(byte, '02X') for byte in page_range[:0x20])
                    revised_header_lines = [revised_header_hex_dump[i:i+47] for i in range(0, len(revised_header_hex_dump), 48)]
                    for line in revised_header_lines:
                        print(line)

                    # 가장 큰 레코드 수를 가진 페이지 식별
                    if num_records > largest_record_count:
                        largest_record_count = num_records
                        largest_record_index = idx
                        largest_record_start_offset = page_header_start

            print()  # 줄바꿈

        # 가장 큰 레코드 수를 가진 페이지 출력 및 종료 오프셋 계산
        if largest_record_index != -1 and largest_record_start_offset is not None:
            largest_record_end_offset = largest_record_start_offset + page_size_int - 1
            print(f"{table_name} Page {largest_record_index} from {hex(largest_record_start_offset)} to {hex(largest_record_end_offset)} has the most records ({largest_record_count}).")

            # 복사된 데이터 대체 작업 수행
            with open(output_db_path, 'r+b') as db_file:
                # remained.db-wal 파일의 가장 큰 레코드 페이지 읽기
                replacement_data = wal_file_content[largest_record_start_offset:largest_record_start_offset + page_size_int]

                # Start Page Offset 위치로 이동하여 해당 위치부터 대체
                db_file.seek(Start_Page_Offset)
                db_file.write(replacement_data)
                print(f"Replaced data at {table_name} Start Page Offset: {hex(Start_Page_Offset)} with data from remained.db-wal")
    else:
        print(f"Pattern not found in remained.db-wal for {table_name}")

    print("===========================")

# 변경된 remained.db-wal 파일을 저장
with open(output_wal_path, 'wb') as wal_file:
    wal_file.write(wal_file_content)
    print("Updated remained.db-wal has been saved.")