import requests
from bs4 import BeautifulSoup
import time
import os

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

if __name__ == '__main__':

    refresh_sec = 60

    error_wait_sec = 5
    error_cnt_max = 5
    error_cnt = 1
    while error_cnt < error_cnt_max:
        print("ctrl + c 로 종료\n")
        try:
            remain_check()

            for i in range(refresh_sec, 0, -1):
                print(f"새로고침까지 {i}초", end='\r', flush=True)
                time.sleep(1)
            error_cnt = 0
        except:
            print(f"오류발생({error_cnt}/{error_cnt_max})")
            for i in range(error_wait_sec, 0, -1):
                print(f"재시도까지 {i}초", end='\r', flush=True)
                time.sleep(1)
            error_cnt += 1

        os.system('cls')

    if error_cnt == error_cnt_max:
        print("나중에 다시 시도")
        os.system('pause')