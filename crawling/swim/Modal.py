import tkinter as tk
import time
import sys
import threading
import webbrowser

import ClassScraper

#----------------------------------------------------------------------------
# Tkinter 창 설정
root = tk.Tk()
root.title("잔여 강좌 확인창")
root.geometry("1000x400")
root.resizable(False, False)

# 상단프레임
top_frame = tk.Frame(root)
top_frame.pack(expand=True, fill='both')

# 하단프레임
bottom_frame = tk.Frame(root, height=50)
bottom_frame.pack(fill='x', side='bottom')

# 상태 라벨(하단프레임 좌측 배치)
status_label = tk.Label(bottom_frame, text="상태:", anchor='w')
status_label.pack(side='left', padx=10, fill='x', expand=True)

# 체크박스
check_frame = tk.Frame(bottom_frame, bd=1, relief="ridge", padx=5, pady=5)
check_frame.pack(side='right', padx=0)

check_var = tk.BooleanVar()
def toggle_topmost():
    if check_var.get():
        root.attributes("-topmost", True)
    else:
        root.attributes("-topmost", False)

check_box = tk.Checkbutton(check_frame, text="화면고정", variable=check_var, command=toggle_topmost)
check_box.pack(side='left')

# 텍스트 위젯(상단프레임 배치)
text_widget = tk.Text(top_frame, wrap='word', font=("Consolas", 10))
text_widget.pack(expand=True, fill='both')
text_widget.config(state='disabled')

# stdout 리디렉션 클래스
class RedirectText:
    def __init__(self, widget):
        self.widget = widget

    def write(self, string):
        self.widget.config(state='normal')
        self.widget.insert('end', string)
        self.widget.config(state='disabled')

    def flush(self):
        pass

#sys.stdout = RedirectText(text_widget)
sys.stderr = RedirectText(text_widget)
#----------------------------------------------------------------------------

def open_link(event):
    # 클릭한 위치에서 해당 라인의 시작과 끝 인덱스를 얻어 URL을 추출
    start_index = text_widget.index(tk.CURRENT)
    
    # 클릭된 텍스트가 포함된 라인의 시작과 끝 인덱스를 찾기
    line_start = f"{start_index.split('.')[0]}.0"  # 해당 라인의 시작
    line_end = f"{start_index.split('.')[0]}.end"  # 해당 라인의 끝
    line_text = text_widget.get(line_start, line_end)

    webbrowser.open(line_text)

def countdown(message, seconds):
    for i in range(seconds, 0, -1):
        status_label.config(text=f"{message} {i}초")
        time.sleep(1)
    
    status_label.config(text=f"{message} 완료!")

# 실행 루프
def run_loop():

    refresh_sec = 60
    error_wait_sec = 5
    error_cnt_max = 5
    error_cnt = 1

    while error_cnt < error_cnt_max:
        try:
            status_label.config(text="검색중...")
            classes = ClassScraper.check_remaining_classes()

            # 기존 텍스트 삭제
            text_widget.config(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.config(state='disabled')

            if classes == []:
                text_widget.config(state='normal')
                text_widget.delete('1.0', 'end')
                text_widget.insert('end', "남은 강좌 없음\n")
                text_widget.config(state='disabled')
            else:
                # 결과물 출력
                for cnt, class_row in enumerate(classes):
                    last_text = class_row[-1]   # 링크 주소

                    text_widget.config(state='normal')
                    text_widget.insert('end', str(cnt + 1) + '.' + '\n')
                    text_widget.insert('end', ' / '.join(class_row[:3]) + '\n')
                    text_widget.insert('end', ' / '.join(class_row[3:-1]) + '\n')
                    text_widget.insert('end', last_text + '\n')

                    # 하이퍼링크 스타일을 적용
                    start_index = text_widget.index("end-2l")
                    end_index = text_widget.index("end-1c")

                    text_widget.tag_add("hyperlink", start_index, end_index)
                    text_widget.tag_configure("hyperlink", foreground="blue", underline=True)

                    # 클릭 이벤트 바인딩(Label 위젯에서 텍스트 클릭 시 링크 열기)
                    text_widget.tag_bind("hyperlink", "<Button-1>", open_link)
                    text_widget.config(state='disabled')

            countdown("새로고침까지", refresh_sec)
            error_cnt = 0
            
        except Exception as e:
            error_cnt += 1
            countdown(f'오류발생: {e}, 재시도까지', error_wait_sec)

# 스레드로 실행
threading.Thread(target=run_loop, daemon=True).start()
root.mainloop()