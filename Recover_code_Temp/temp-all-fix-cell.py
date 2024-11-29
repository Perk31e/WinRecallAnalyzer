import shutil
import os

# 데이터에서 00 00 00 또는 00 00 패턴을 찾습니다. (각 레코드 시작 지점 찾는용도)
def find_next_zeros(data, start_pos):
    pos = start_pos
    while pos < len(data) - 1:
        if pos < len(data) - 3 and data[pos:pos+3] == b'\x00\x00\x00':
            return pos, 3  # 패턴의 시작 위치와 길이 반환
        elif data[pos:pos+2] == b'\x00\x00':
            return pos, 2  # 패턴의 시작 위치와 길이 반환
        pos += 1
    return -1, 0  # 패턴이 없을 경우

# 잘못된 cell offset 수정
def process_cell_pointers(hex_range):
    base_addr = 0
    i = 8  # 셀 포인터 배열의 시작 위치

    while i < len(hex_range) - 2:
        # 00 00을 만나면 즉시 종료
        if hex_range[i:i+2] == b'\x00\x00':
            break

        current_offset = hex_range[i:i+2]
        next_offset = hex_range[i+2:i+4]

        if len(current_offset) < 2 or len(next_offset) < 2:
            break

        if current_offset == next_offset:
            offset_value = int.from_bytes(current_offset, byteorder='big')
            abs_addr = base_addr + offset_value

            zero_pos, pattern_length = find_next_zeros(hex_range, abs_addr)

            if zero_pos != -1:
                new_offset = zero_pos - base_addr
                hex_range[i+2:i+4] = new_offset.to_bytes(2, byteorder='big')
                prev_value = current_offset

                j = i + 4
                while j < len(hex_range) - 1 and hex_range[j:j+2] == prev_value:
                    # 00 00을 만나면 루프 종료
                    if hex_range[j:j+2] == b'\x00\x00':
                        break

                    next_zero_pos, next_pattern_length = find_next_zeros(hex_range, zero_pos + pattern_length)

                    if next_zero_pos != -1:
                        new_offset = next_zero_pos - base_addr
                        hex_range[j:j+2] = new_offset.to_bytes(2, byteorder='big')
                        zero_pos = next_zero_pos
                        pattern_length = next_pattern_length
                    else:
                        break  # 더 이상 패턴이 없으면 종료

                    j += 2
            else:
                break  # 패턴을 찾지 못하면 종료
        i += 2

    return hex_range

# 셀 콘텐츠 영역의 시작 오프셋을 업데이트합니다.
def update_cell_content_area_start(hex_range):
    last_valid_pointer = hex_range[8:10]  # 첫 번째 셀 포인터로 초기화
    
    for i in range(8, len(hex_range) - 1, 2):
        cell_pointer = hex_range[i:i+2]
        
        if cell_pointer == b'\x00\x00':
            hex_range[5:7] = last_valid_pointer
            return
        
        last_valid_pointer = cell_pointer
    
    # 모든 셀 포인터가 유효한 경우
    hex_range[5:7] = last_valid_pointer

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

# 테이블 리스트
tables = [
    "App", "AppDwellTime", "File", "ScreenRegion", "Web", "WindowCapture",
    "WindowCaptureAppRelation", "WindowCaptureFileRelation", 
    "WindowCaptureTextIndex_content", "WindowCaptureTextIndex_docsize", 
    "WindowCaptureWebRelation"
]

# 복사된 데이터베이스 파일 읽기
with open(output_db_path, 'rb') as db_file:
    content = db_file.read()

# 페이지 크기 가져오기 (16번과 17번 오프셋)
page_size = content[16:18]
page_size_hex = ' '.join(format(byte, '02X') for byte in page_size)
print(f"Page size(hex): {page_size_hex}")

# 페이지 크기를 16진수 문자열로 변환하여 숫자로 계산할 수 있게 함
page_size_int = int(page_size_hex.replace(" ", ""), 16)  # '10 00' -> 4096

# remained.db-wal 파일 읽기
with open(output_wal_path, 'rb') as wal_file:
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
    table_hex = ''.join(format(ord(char), '02X') for char in table_create_statement)
    # 2바이트마다 공백 추가
    table_hex_spaced = ' '.join([table_hex[i:i+2] for i in range(0, len(table_hex), 2)])
    print(f'Find CREATE TABLE {delimiter}{table_name}{delimiter} String(hex): {table_hex_spaced}')

    # 모든 위치 찾기
    hex_content = content.hex().upper()
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
    largest_record_count = 0
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

            # 페이지 전체를 읽습니다.
            hex_range = bytearray(wal_content[target_offset:target_offset + page_size_int])

            # 처음 0x20 바이트만 출력
            hex_range_str = ' '.join(format(byte, '02X') for byte in hex_range[:0x20])
            # 16바이트씩 출력
            hex_lines = [hex_range_str[i:i+47] for i in range(0, len(hex_range_str), 48)]
            for line in hex_lines:
                print(line)

            # 첫 번째 바이트가 0D인지 확인
            if hex_range[0] == 0x0D:
                # 실제 레코드 수 확인
                cell_pointers = hex_range[8:]
                num_records = 0
                for i in range(0, len(cell_pointers), 2):
                    cell_pointer = cell_pointers[i:i+2]
                    if cell_pointer == b'\x00\x00' or len(cell_pointer) < 2:
                        break
                    num_records += 1

                # 조건에 맞는 경우에만 업데이트와 출력 수행
                if hex_range[3:5] == b'\x00\x00' and num_records > 0:
                    # 셀 포인터 처리
                    hex_range = process_cell_pointers(hex_range)
                    # 레코드 수 업데이트
                    hex_range[3:5] = num_records.to_bytes(2, byteorder='big')
                    # 셀 콘텐츠 영역의 시작 오프셋 업데이트
                    update_cell_content_area_start(hex_range)

                    # 변경된 hex_range를 wal_content에 반영
                    wal_content = wal_content[:target_offset] + hex_range + wal_content[target_offset + len(hex_range):]

                    # 수정된 hex_range 출력 (처음 0x20 바이트만 출력)
                    print(f"[+] {idx}. (Revised) {table_name} Page Hex values from {hex(target_offset)} to {hex(target_offset + 0x32)}:")
                    revised_hex_range_str = ' '.join(format(byte, '02X') for byte in hex_range[:0x20])
                    revised_hex_lines = [revised_hex_range_str[i:i+47] for i in range(0, len(revised_hex_range_str), 48)]
                    for line in revised_hex_lines:
                        print(line)

                    # 가장 큰 레코드 수를 가진 페이지 식별
                    if num_records > largest_record_count:
                        largest_record_count = num_records
                        largest_record_index = idx
                        largest_record_start_offset = position + 0x18

            print()  # 줄바꿈

        # 가장 큰 레코드 수를 가진 페이지 출력 및 종료 오프셋 계산
        if largest_record_index != -1 and largest_record_start_offset is not None:
            largest_record_end_offset = largest_record_start_offset + page_size_int - 1
            print(f"{table_name} Page {largest_record_index} from {hex(largest_record_start_offset)} to {hex(largest_record_end_offset)} has the most records ({largest_record_count}).")

            # 복사된 데이터 대체 작업 수행
            with open(output_db_path, 'r+b') as db_file:
                # remained.db-wal 파일의 가장 큰 레코드 페이지 읽기
                replacement_data = wal_content[largest_record_start_offset:largest_record_start_offset + page_size_int]

                # Start Page Offset 위치로 이동하여 해당 위치부터 대체
                db_file.seek(Start_Page_Offset)
                db_file.write(replacement_data)
                print(f"Replaced data at {table_name} Start Page Offset: {hex(Start_Page_Offset)} with data from remained.db-wal")
    else:
        print(f"Pattern not found in remained.db-wal for {table_name}")

    print("===========================")

# 변경된 remained.db-wal 파일을 저장
with open(output_wal_path, 'wb') as wal_file:
    wal_file.write(wal_content)
    print("Updated remained.db-wal has been saved.")