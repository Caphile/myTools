import requests
from bs4 import BeautifulSoup
import time
import sys
import ctypes
import threading
import tkinter as tk

# CMD 창 숨기기
kernel32 = ctypes.WinDLL('kernel32')
user32 = ctypes.WinDLL('user32')
hWnd = kernel32.GetConsoleWindow()
user32.ShowWindow(hWnd, 0)  # SW_HIDE = 0

# Tkinter 창 만들기
root = tk.Tk()
root.title("잔여 강좌 확인창")
root.geometry("400x400")
root.attributes("-topmost", True)

text_widget = tk.Text(root, wrap='word', font=("Consolas", 10))
text_widget.pack(expand=True, fill='both')

# stdout 리디렉션 클래스
class RedirectText:
    def __init__(self, widget):
        self.widget = widget

    def write(self, string):
        self.widget.insert('end', string)   # 텍스트 위젯에 문자열 추가
        self.widget.see('end')              # 자동 스크롤

    def flush(self):
        pass

sys.stdout = RedirectText(text_widget)
sys.stderr = RedirectText(text_widget)

# 잔여 강좌 확인 함수
def remain_check():
    # 사당문화센터 : 3, 삼일수영장 : 7
    center_num = 3
    center = 'DONGJAK0' + str(center_num)

    base_url = 'https://sports.idongjak.or.kr/home/171'
    home_url = base_url + f'?center={center}&category1=01&category2=ALL&title=&train_day='

    response = requests.get(home_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    table = soup.find('table', class_='list_lecture all_border')
    rows = table.find('tbody', class_='txtcenter').find_all('tr')

    indices_to_remove = {0, 5, 6, 7}
    seen_ids = set()

    data = []
    for row in rows:
        cols = row.find_all(['td', 'th'])
        cols_text = [col.get_text(strip=True) for col in cols]

        class_id = row.get('data-classcd')
        if class_id in seen_ids:
            continue
        seen_ids.add(class_id)

        link_tag = row.find('a', href=True)
        if link_tag:
            link = link_tag['href']
            linked_url = base_url + link

            detail_response = requests.get(linked_url)
            detail_response.raise_for_status()

            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

            try:
                info_data = detail_soup.select_one('#contents > article > div > div > div.infomation > div.info_data > dl > dd:nth-child(12)')
                remain_cnt = info_data.get_text(separator=' ').strip()
            except:
                info_data = detail_soup.select_one('#form_lecture_reg > fieldset > div > div.proc_read > div.infomation > div.info_data > dl > dd:nth-child(12)')
                remain_cnt = info_data.get_text(separator=' ').strip()

            cols_text.append(f'잔여{remain_cnt}')
            cols_text.append(linked_url)
            filtered_text = [item for idx, item in enumerate(cols_text) if idx not in indices_to_remove]

        if remain_cnt != '마감':
            data.append(filtered_text)
            print(' / '.join(filtered_text[:-1]))
            print(filtered_text[-1])
            print('')

    if data == []:
        print('남은 강좌 없음')

def update_timer(text_widget, text):
    try:
        # 이전 타이머 줄 삭제
        start = text_widget.index("timer_line_start.first")
        end = text_widget.index("timer_line_end.last")
        text_widget.delete(start, end)
    except:
        pass  # 첫 실행 시에는 태그가 없음

    # 현재 위치 저장 (맨 끝에 삽입되지만 범위 태그를 붙임)
    text_widget.insert("end", text + "\n")
    text_widget.tag_add("timer_line_start", "end-2l", "end-1l")
    text_widget.tag_add("timer_line_end", "end-1l", "end")

    # 맨 아래로 스크롤
    text_widget.see("end")


# 루프 함수 (쓰레드에서 실행)
def run_loop():
    refresh_sec = 60
    error_wait_sec = 5
    error_cnt_max = 5
    error_cnt = 1
    while error_cnt < error_cnt_max:
        try:
            remain_check()

            for i in range(refresh_sec, 0, -1):
                update_timer(text_widget, f"\n새로고침까지 {i}초")
                time.sleep(1)
            error_cnt = 0
        except Exception as e:
            print(f"오류발생({error_cnt}/{error_cnt_max}): {e}")
            for i in range(error_wait_sec, 0, -1):
                update_timer(text_widget, f"\n재시도까지 {i}초")
                time.sleep(1)
            error_cnt += 1

    if error_cnt == error_cnt_max:
        print("나중에 다시 시도")

# 루프를 별도의 쓰레드로 실행 (Tkinter GUI와 동시 작동)
threading.Thread(target=run_loop, daemon=True).start()
root.mainloop()