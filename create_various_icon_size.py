from PIL import Image

def create_ico(input_file, output_file, sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]):
    img = Image.open(input_file)
    img.save(output_file, format='ICO', sizes=sizes)

# 사용 예
create_ico('WinRecallAnalyzer_logo.png', 'WinRecallAnalyzer_logo.ico')